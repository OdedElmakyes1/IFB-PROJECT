#!/usr/bin/env python3
"""Phase 5: behavioral risk / suspicious-user detection.

Read-only on IFB.db (authors metadata only). Does not modify IFB.db.
Does not rerun sentiment, emotion, events, BERTopic, NER, or the entity network.

This is a behavioral risk classification, not verified bot identity.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sqlite3
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneOut, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

try:
    from xgboost import XGBClassifier

    XGB_OK = True
    XGB_ERR = ""
except Exception as exc:  # pragma: no cover
    XGBClassifier = None
    XGB_OK = False
    XGB_ERR = str(exc)

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Inches, Pt

    PPTX_OK = True
except Exception as exc:  # pragma: no cover
    PPTX_OK = False
    PPTX_ERR = str(exc)

ROOT = Path(__file__).resolve().parents[1]
IFB_DB = ROOT / "IFB.db"
ANALYSIS_DB = ROOT / "data" / "analysis_corpus.db"
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"

FEATURES_CSV = OUTPUT_DIR / "user_bot_features.csv"
UNLABELED_CSV = OUTPUT_DIR / "unlabled_dataset.csv"
LABELS_CSV = OUTPUT_DIR / "manual_bot_labels.csv"
COURSE_LABELS_CSV = OUTPUT_DIR / "labeled_bots_and_not_bots.csv"
EXAMPLES_CSV = OUTPUT_DIR / "manual_review_examples.csv"
PACKETS_JSONL = OUTPUT_DIR / "manual_review_packets.jsonl"
RULE_SCORES_CSV = OUTPUT_DIR / "rule_based_bot_scores.csv"
RULE_SUMMARY_CSV = OUTPUT_DIR / "rule_based_summary.csv"
EXPERIMENTS_CSV = OUTPUT_DIR / "bot_detection_experiments.csv"
PREDICTIONS_CSV = OUTPUT_DIR / "bot_detection_predictions.csv"
UNLABELED_RESULTS_CSV = OUTPUT_DIR / "unlabeled_dataset_results.csv"
IMPORTANCE_CSV = OUTPUT_DIR / "bot_feature_importance.csv"
CM_PNG = OUTPUT_DIR / "bot_confusion_matrices.png"
CMP_PNG = OUTPUT_DIR / "bot_model_comparison.png"
DIST_PNG = OUTPUT_DIR / "bot_feature_distributions.png"
FLOW_PNG = OUTPUT_DIR / "malicious_detection_flow.png"
PPTX = ROOT / "malicious_detection_flow.pptx"
GUIDE = ROOT / "MANUAL_BOT_REVIEW_GUIDE.md"
REPORT = ROOT / "BOT_DETECTION_REPORT.md"

SEED = 2026
COLLECTION_END = datetime(2023, 12, 3, tzinfo=timezone.utc)
N_REVIEW = 100
MIN_POSTS_FOR_TEXT = 3
FEATURE_SET = "v1_profile_plus_nlp_behavior"

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#\w+")
RT_RE = re.compile(r"^\s*rt\s+@", re.I)
IFB_PHRASE_RE = re.compile(
    r"follow\s*(for|4|and)?\s*follow|i follow back|follow back|teamfollowback|"
    r"follow me and i|#ifb\b|\bifb\b|f4f|l4l|s4s|\bfff\b|twitter gains|drop your handle",
    re.I,
)
DEFAULT_IMG_RE = re.compile(r"default_profile|sticky/default|abs\.twimg\.com/sticky", re.I)

MODEL_FEATURES = [
    "followers_count", "following_count", "tweet_count", "listed_count", "ifb_count",
    "verified", "protected", "freelancer", "account_age_days", "missing_profile_fields",
    "bio_length", "default_profile_image", "followers_following_ratio",
    "n_posts", "n_keyword", "n_timeline", "ifb_collection_share",
    "duplicate_template_ratio", "boilerplate_ratio", "unique_text_ratio",
    "avg_text_length", "url_ratio", "mention_ratio", "hashtag_ratio",
    "active_days", "posts_per_active_day", "posting_span_days", "burstiness",
    "hour_concentration", "dow_concentration",
    "pct_positive", "pct_neutral", "pct_negative",
    "pct_joy", "pct_anger", "pct_sadness", "pct_fear", "pct_surprise", "pct_disgust", "pct_others",
    "topic_outlier_share", "top_topic_share", "topic_entropy",
    "rt_at_ratio", "has_nlp_posts",
]

EMOTIONS = ("joy", "anger", "sadness", "fear", "surprise", "disgust", "others")


def log(msg: str) -> None:
    print(msg, flush=True)


def connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=180)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def to_int(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def to_bool01(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return 1.0 if int(v) != 0 else 0.0
    s = str(v).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1.0
    if s in {"0", "false", "no"}:
        return 0.0
    return None


def parse_created(s: str | None) -> datetime | None:
    if not s:
        return None
    raw = str(s).strip()
    if "T" in raw:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def entropy(values: list[int]) -> float:
    tot = sum(values)
    if tot <= 0:
        return 0.0
    h = 0.0
    for v in values:
        if v <= 0:
            continue
        p = v / tot
        h -= p * math.log(p)
    return h


def concentration(values: list[int]) -> float:
    k = len(values)
    if k <= 1:
        return 0.0
    h = entropy(values)
    return float(max(0.0, min(1.0, 1.0 - h / math.log(k))))


def norm_text(text: str) -> str:
    s = URL_RE.sub(" ", (text or "").lower())
    s = MENTION_RE.sub(" ", s)
    s = HASHTAG_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:240]


def load_primary_users() -> list[dict[str, str]]:
    conn = connect_ro(ANALYSIS_DB)
    try:
        rows = conn.execute("SELECT author_id, username FROM users").fetchall()
    finally:
        conn.close()
    return [{"author_id": str(r["author_id"]), "username": r["username"] or ""} for r in rows]


def load_authors(ids: list[str]) -> dict[str, dict[str, Any]]:
    conn = connect_ro(IFB_DB)
    out: dict[str, dict[str, Any]] = {}
    try:
        chunk = 400
        cols = (
            "AUTHOR_ID, REALNAME, USERNAME, CREATED_AT, DESCRIPTION, LOACATION, "
            "VERIFIED, PROTECTED, IMAGE_URL, FOLLOWERS_COUNT, FOLLOWING_COUNT, "
            "TWEET_COUNT, LISTED_COUNT, FREELANCER, IFB_COUNT"
        )
        for i in range(0, len(ids), chunk):
            part = ids[i : i + chunk]
            q = f"SELECT {cols} FROM authors WHERE AUTHOR_ID IN ({','.join('?' * len(part))})"
            for r in conn.execute(q, part):
                out[str(r["AUTHOR_ID"])] = dict(r)
    finally:
        conn.close()
    return out


def load_nlp_posts() -> list[sqlite3.Row]:
    conn = connect_ro(NLP_DB)
    try:
        return conn.execute(
            """
            SELECT p.author_id, p.username, p.source, p.tweet_id, p.created_at,
                   p.original_text, p.lang, p.sample_weight,
                   s.sentiment_label, e.emotion_label, t.topic_id
            FROM nlp_posts p
            JOIN post_sentiment s ON s.source=p.source AND s.tweet_id=p.tweet_id
            JOIN post_emotion e ON e.source=p.source AND e.tweet_id=p.tweet_id
            JOIN post_topic t ON t.source=p.source AND t.tweet_id=p.tweet_id
            """
        ).fetchall()
    finally:
        conn.close()


def empty_behavior() -> dict[str, Any]:
    d = {
        "n_posts": 0, "n_keyword": 0, "n_timeline": 0, "ifb_collection_share": None,
        "duplicate_template_ratio": None, "boilerplate_ratio": None, "unique_text_ratio": None,
        "avg_text_length": None, "url_ratio": None, "mention_ratio": None, "hashtag_ratio": None,
        "active_days": 0, "posts_per_active_day": None, "posting_span_days": None, "burstiness": None,
        "hour_concentration": None, "dow_concentration": None,
        "pct_positive": None, "pct_neutral": None, "pct_negative": None,
        "topic_outlier_share": None, "top_topic_share": None, "topic_entropy": None,
        "rt_at_ratio": None, "timeline_weighted_post_estimate": 0.0, "has_nlp_posts": 0,
        "username_nlp": "",
    }
    for e in EMOTIONS:
        d[f"pct_{e}"] = None
    return d


def aggregate_behavior(posts: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
    by: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for p in posts:
        by[str(p["author_id"])].append(p)
    out = {}
    for aid, rows in by.items():
        texts = []
        norms = []
        hours = [0] * 24
        dows = [0] * 7
        days: Counter[str] = Counter()
        dts = []
        sent = Counter()
        emo = Counter()
        topics = Counter()
        n_kw = n_tl = n_url = n_men = n_hash = n_boiler = n_rt = 0
        tl_w = 0.0
        lens = []
        for r in rows:
            txt = r["original_text"] or ""
            texts.append(txt)
            norms.append(norm_text(txt))
            lens.append(len(txt))
            if r["source"] == "keyword_tweets":
                n_kw += 1
            else:
                n_tl += 1
                tl_w += float(r["sample_weight"] or 1)
            if URL_RE.search(txt):
                n_url += 1
            if MENTION_RE.search(txt):
                n_men += 1
            if HASHTAG_RE.search(txt):
                n_hash += 1
            if IFB_PHRASE_RE.search(txt):
                n_boiler += 1
            if RT_RE.search(txt):
                n_rt += 1
            sent[r["sentiment_label"] or "neutral"] += 1
            emo[(r["emotion_label"] or "others").lower()] += 1
            topics[int(r["topic_id"] if r["topic_id"] is not None else -1)] += 1
            dt = parse_created(r["created_at"])
            if dt:
                dts.append(dt)
                hours[dt.hour] += 1
                dows[dt.weekday()] += 1
                days[dt.date().isoformat()] += 1
        n = len(rows)
        uniq = len({x for x in norms if x})
        span = None
        burst = None
        if len(dts) >= 2:
            span = max((max(dts) - min(dts)).total_seconds() / 86400.0, 0.0)
        if days:
            arr = np.array(list(days.values()), dtype=float)
            burst = float(arr.std() / arr.mean()) if arr.mean() > 0 else 0.0
        top_n = topics.most_common(1)[0][1] if topics else 0
        rec = empty_behavior()
        rec.update(
            {
                "n_posts": n,
                "n_keyword": n_kw,
                "n_timeline": n_tl,
                "ifb_collection_share": n_kw / n,
                "duplicate_template_ratio": 1.0 - (uniq / n),
                "boilerplate_ratio": n_boiler / n,
                "unique_text_ratio": uniq / n,
                "avg_text_length": float(np.mean(lens)) if lens else None,
                "url_ratio": n_url / n,
                "mention_ratio": n_men / n,
                "hashtag_ratio": n_hash / n,
                "active_days": len(days),
                "posts_per_active_day": n / len(days) if days else None,
                "posting_span_days": span,
                "burstiness": burst,
                "hour_concentration": concentration(hours) if sum(hours) else None,
                "dow_concentration": concentration(dows) if sum(dows) else None,
                "pct_positive": sent.get("positive", 0) / n,
                "pct_neutral": sent.get("neutral", 0) / n,
                "pct_negative": sent.get("negative", 0) / n,
                "topic_outlier_share": topics.get(-1, 0) / n,
                "top_topic_share": top_n / n,
                "topic_entropy": entropy(list(topics.values())),
                "rt_at_ratio": n_rt / n,
                "timeline_weighted_post_estimate": round(tl_w, 2),
                "has_nlp_posts": 1,
                "username_nlp": rows[0]["username"] or "",
            }
        )
        for e in EMOTIONS:
            rec[f"pct_{e}"] = emo.get(e, 0) / n
        rec["_posts"] = rows
        out[aid] = rec
    return out


def build_features() -> list[dict[str, Any]]:
    log("Loading 38,576 primary users from analysis_corpus.db (read-only)")
    users = load_primary_users()
    ids = [u["author_id"] for u in users]
    log(f"primary users {len(ids):,}")
    log("Loading author metadata from IFB.db (read-only, query_only)")
    authors = load_authors(ids)
    log(f"author rows matched {len(authors):,}")
    log("Loading NLP posts + sentiment/emotion/topic")
    posts = load_nlp_posts()
    log(f"nlp scored posts {len(posts):,}")
    behavior = aggregate_behavior(posts)
    log(f"users with NLP behavior {len(behavior):,}")
    rows = []
    for u in users:
        aid = u["author_id"]
        a = authors.get(aid, {})
        b = behavior.get(aid, empty_behavior())
        followers = to_int(a.get("FOLLOWERS_COUNT"))
        following = to_int(a.get("FOLLOWING_COUNT"))
        tweet_count = to_int(a.get("TWEET_COUNT"))
        created = parse_created(a.get("CREATED_AT"))
        age = None
        if created and created.year > 1971:
            age = max((COLLECTION_END - created).total_seconds() / 86400.0, 0.0)
        desc = a.get("DESCRIPTION") or ""
        loc = a.get("LOACATION") or ""
        img = a.get("IMAGE_URL") or ""
        missing = 0
        for key in ("USERNAME", "DESCRIPTION", "CREATED_AT", "FOLLOWERS_COUNT", "FOLLOWING_COUNT", "TWEET_COUNT"):
            val = a.get(key)
            if val is None or str(val).strip() == "" or (key == "CREATED_AT" and created and created.year <= 1971):
                missing += 1
        ff = None
        if followers is not None and following is not None:
            ff = followers / (following + 1.0)
        username = a.get("USERNAME") or u["username"] or b.get("username_nlp") or ""
        rec = {
            "user_id": aid,
            "author_id": aid,
            "username": username,
            "realname": a.get("REALNAME") or "",
            "followers_count": followers,
            "following_count": following,
            "tweet_count": tweet_count,
            "listed_count": to_int(a.get("LISTED_COUNT")),
            "ifb_count": to_int(a.get("IFB_COUNT")),
            "verified": to_bool01(a.get("VERIFIED")),
            "protected": to_bool01(a.get("PROTECTED")),
            "freelancer": to_bool01(a.get("FREELANCER")),
            "account_created_at": a.get("CREATED_AT") or "",
            "account_age_days": round(age, 2) if age is not None else None,
            "missing_profile_fields": missing,
            "bio_length": len(desc.strip()),
            "location_present": 1 if str(loc).strip() else 0,
            "default_profile_image": 1 if (not img.strip() or DEFAULT_IMG_RE.search(img)) else 0,
            "followers_following_ratio": round(ff, 4) if ff is not None else None,
            "description": desc,
            "location": loc,
            "image_url": img,
            "profile_row_found": 1 if a else 0,
            **{k: b[k] for k in empty_behavior() if k != "username_nlp"},
        }
        rec["posts_per_day_profile"] = (
            tweet_count / age if tweet_count is not None and age and age > 0 else None
        )
        rows.append(rec)
    rows.sort(key=lambda r: r["author_id"])
    return rows


FEATURE_FIELDS = [
    "user_id", "author_id", "username", "realname", "description", "location",
    "followers_count", "following_count", "tweet_count",
    "listed_count", "ifb_count", "verified", "protected", "freelancer", "account_created_at",
    "account_age_days", "missing_profile_fields", "bio_length", "location_present",
    "default_profile_image", "followers_following_ratio", "posts_per_day_profile",
    "n_posts", "n_keyword", "n_timeline", "ifb_collection_share",
    "duplicate_template_ratio", "boilerplate_ratio", "unique_text_ratio",
    "avg_text_length", "url_ratio", "mention_ratio", "hashtag_ratio",
    "active_days", "posts_per_active_day", "posting_span_days", "burstiness",
    "hour_concentration", "dow_concentration",
    "pct_positive", "pct_neutral", "pct_negative",
    "pct_joy", "pct_anger", "pct_sadness", "pct_fear", "pct_surprise", "pct_disgust", "pct_others",
    "topic_outlier_share", "top_topic_share", "topic_entropy",
    "rt_at_ratio", "timeline_weighted_post_estimate", "has_nlp_posts", "profile_row_found",
]


def fnum(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = row.get(key)
    if v is None or v == "":
        return default
    return float(v)


def rule_score(row: dict[str, Any]) -> dict[str, Any]:
    """Interpretable risk score. Not ground truth."""
    reasons = []
    score = 0.0
    n = fnum(row, "n_posts")
    if n < MIN_POSTS_FOR_TEXT:
        reasons.append("few_nlp_posts")
        return {
            "rule_score": 0.15,
            "rule_label": "insufficient_posts",
            "rule_reasons": ";".join(reasons) or "low_activity",
            "rule_confidence": "low",
        }
    boiler = fnum(row, "boilerplate_ratio")
    dup = fnum(row, "duplicate_template_ratio")
    uniq = fnum(row, "unique_text_ratio", 1)
    kw = fnum(row, "ifb_collection_share")
    rt = fnum(row, "rt_at_ratio")
    burst = fnum(row, "burstiness")
    hour_c = fnum(row, "hour_concentration")
    ifb = fnum(row, "ifb_count")
    ff = fnum(row, "followers_following_ratio", 1)
    following = fnum(row, "following_count")
    followers = fnum(row, "followers_count")
    missing = fnum(row, "missing_profile_fields")

    if boiler >= 0.45:
        score += 0.22
        reasons.append("high_ifb_boilerplate")
    if dup >= 0.55:
        score += 0.20
        reasons.append("high_duplicate_templates")
    if uniq <= 0.40:
        score += 0.12
        reasons.append("low_unique_text")
    if kw >= 0.75 and n >= 8:
        score += 0.10
        reasons.append("keyword_dominated")
    if rt >= 0.50:
        score += 0.12
        reasons.append("high_rt_at_text")
    if burst >= 2.2 and hour_c >= 0.35:
        score += 0.10
        reasons.append("bursty_concentrated_hours")
    if ifb >= 20:
        score += 0.08
        reasons.append("high_ifb_count")
    if following >= 2000 and 0.7 <= ff <= 1.4:
        score += 0.08
        reasons.append("symmetric_mass_follow")
    if missing >= 3:
        score += 0.06
        reasons.append("missing_profile_fields")
    if fnum(row, "verified") == 1 and uniq >= 0.7:
        score = max(0.0, score - 0.15)
        reasons.append("verified_diverse_text_discount")
    score = float(min(1.0, score))
    if score >= 0.55:
        label = "high_risk"
    elif score >= 0.30:
        label = "medium_risk"
    else:
        label = "low_risk"
    conf = "high" if score >= 0.70 or score <= 0.10 else "medium"
    return {
        "rule_score": round(score, 4),
        "rule_label": label,
        "rule_reasons": ";".join(reasons) or "no_rule_fired",
        "rule_confidence": conf,
    }


def apply_rules(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rec = dict(r)
        rec.update(rule_score(r))
        out.append(rec)
    return out


def stratified_sample(rows: list[dict[str, Any]], n: int = N_REVIEW) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    scored = apply_rules(rows)
    usable = [r for r in scored if int(r.get("has_nlp_posts") or 0) == 1]
    usable.sort(key=lambda r: r["rule_score"])
    low = [r for r in usable if r["rule_label"] == "low_risk"]
    mid = [r for r in usable if r["rule_label"] == "medium_risk"]
    high = [r for r in usable if r["rule_label"] == "high_risk"]
    # 35 / 30 / 35, then fill
    want = {"low_risk": 35, "medium_risk": 30, "high_risk": 35}
    pools = {"low_risk": low, "medium_risk": mid, "high_risk": high}
    picked = []
    used = set()
    for lab, k in want.items():
        pool = pools[lab][:]
        rng.shuffle(pool)
        take = pool[:k]
        picked.extend(take)
        used.update(r["author_id"] for r in take)
    if len(picked) < n:
        rest = [r for r in usable if r["author_id"] not in used]
        rng.shuffle(rest)
        picked.extend(rest[: n - len(picked)])
    rng.shuffle(picked)
    return picked[:n]


def representative_posts(posts: list[sqlite3.Row], k: int = 6) -> list[dict[str, str]]:
    # mix keyword + timeline, prefer longer unique texts
    seen = set()
    ranked = []
    for p in posts:
        txt = (p["original_text"] or "").strip()
        key = norm_text(txt)
        if not key or key in seen:
            continue
        seen.add(key)
        ranked.append(p)
    ranked.sort(key=lambda p: (0 if p["source"] == "keyword_tweets" else 1, -len(p["original_text"] or "")))
    # take 3 keyword-ish + 3 timeline-ish if possible
    kw = [p for p in ranked if p["source"] == "keyword_tweets"][:3]
    tl = [p for p in ranked if p["source"] == "timeline"][:3]
    mix = kw + tl
    if len(mix) < k:
        extra = [p for p in ranked if p not in mix]
        mix.extend(extra[: k - len(mix)])
    out = []
    for p in mix[:k]:
        out.append(
            {
                "source": p["source"],
                "tweet_id": str(p["tweet_id"]),
                "created_at": p["created_at"] or "",
                "text": (p["original_text"] or "")[:400],
            }
        )
    return out


def write_packets(sample: list[dict[str, Any]], behavior_posts: dict[str, list]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with PACKETS_JSONL.open("w", encoding="utf-8") as fh:
        for i, r in enumerate(sample, 1):
            posts = representative_posts(behavior_posts.get(r["author_id"], []), 6)
            rec = {
                "review_index": i,
                "author_id": r["author_id"],
                "username": r.get("username") or "",
                "realname": r.get("realname") or "",
                "followers_count": r.get("followers_count"),
                "following_count": r.get("following_count"),
                "tweet_count": r.get("tweet_count"),
                "ifb_count": r.get("ifb_count"),
                "verified": r.get("verified"),
                "protected": r.get("protected"),
                "account_created_at": r.get("account_created_at"),
                "account_age_days": r.get("account_age_days"),
                "bio": (r.get("description") or "")[:280],
                "location": r.get("location") or "",
                "n_posts": r.get("n_posts"),
                "n_keyword": r.get("n_keyword"),
                "n_timeline": r.get("n_timeline"),
                "boilerplate_ratio": r.get("boilerplate_ratio"),
                "duplicate_template_ratio": r.get("duplicate_template_ratio"),
                "unique_text_ratio": r.get("unique_text_ratio"),
                "rt_at_ratio": r.get("rt_at_ratio"),
                "rule_score": r.get("rule_score"),
                "rule_label": r.get("rule_label"),
                "rule_reasons": r.get("rule_reasons"),
                "posts": posts,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"Wrote {PACKETS_JSONL.name} n={len(sample)}")


def write_guide() -> None:
    GUIDE.write_text(
        """# Manual bot / malicious-user review guide

This review is a **behavioral risk** judgment from the 2023 IFB snapshot. It is **not** a verified bot identity.

## What we can see

- Profile fields stored in `IFB.db.authors` at collection time (followers, following, tweets, IFB_COUNT, bio, verified, created date).
- Representative **original posts** from the English NLP corpus (keyword IFB tweets + stratified timeline sample).

## What we cannot see

- Live X/Twitter pages in 2026 (many IFB accounts churned after 2023).
- Follower / following graphs, reply trees, or native retweet cascades.
- A vendor `is_bot` score.

Deleted, suspended, or empty snapshots are labeled **`insufficient_evidence`**, never malicious.

## Labels

| Label | Meaning |
|-------|---------|
| `likely_normal` | Varied original posts and a plausible profile. Still may use IFB hashtags. |
| `suspicious` | Strong automation / follow-farm signals, but a human IFB user remains possible. |
| `likely_malicious` | Repeated spam, commercial follow-gain scripts, or RT-only amplification with almost no original voice. Still not a proven bot. |
| `insufficient_evidence` | Too few posts, missing profile, epoch signup date, or mixed/unreadable evidence. |

Also store course flags: `is_bot` ∈ {0,1,unknown}, `is_troll`, `is_malicious`, reviewer confidence (`high`/`medium`/`low`), and a short evidence note.

## Sampling (seed 2026)

100 users, stratified on the **unlabeled** rule score (35 low / 30 medium / 35 high). Rules are **not** copied as labels.

## Process

1. Read username, bio, follower/following/IFB counts, account age.
2. Read 4–6 original posts (keyword and timeline when both exist).
3. Ask: is the text a copy-paste follow-back machine, a normal IFB hobbyist, or unclear?
4. Write evidence quotes. Do not use the rule score as the label.

## Mapping used for ML

Training uses a binary **risk** target, not “is bot”:

- positive = `likely_malicious` or `suspicious`
- negative = `likely_normal`
- `insufficient_evidence` is excluded from training

There is **no** second 200-user manual validation set. Creating 200 extra labels without another real review would be fabrication.
""",
        encoding="utf-8",
    )


def load_labels() -> dict[str, dict[str, Any]]:
    if not LABELS_CSV.exists():
        return {}
    out = {}
    with LABELS_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            out[str(r["author_id"])] = r
    return out


def risk_y(label: str) -> int | None:
    if label in {"likely_malicious", "suspicious"}:
        return 1
    if label == "likely_normal":
        return 0
    return None


def matrix_row(y_true, y_pred, y_prob, algo: str, split: str, n_train: int, n_test: int, counts: dict[str, int], runtime: float) -> dict[str, Any]:
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    acc = accuracy_score(yt, yp)
    prec = precision_score(yt, yp, zero_division=0)
    rec = recall_score(yt, yp, zero_division=0)
    f1 = f1_score(yt, yp, zero_division=0)
    bacc = balanced_accuracy_score(yt, yp)
    auc = None
    prauc = None
    if y_prob is not None and len(set(yt.tolist())) == 2:
        try:
            auc = float(roc_auc_score(yt, y_prob))
            prauc = float(average_precision_score(yt, y_prob))
        except Exception:
            auc = None
            prauc = None
    cm = confusion_matrix(yt, yp, labels=[0, 1])
    return {
        "target_column": "risk_positive",
        "algorithm": algo,
        "feature_set": FEATURE_SET,
        "training_type": split,
        "K": 5 if split.startswith("kfold") else (len(yt) if split == "loocv" else ""),
        "balanced": "class_weight_or_scale_pos",
        "n_train": n_train,
        "n_test": n_test,
        "n_train_pos": counts.get("train_pos", ""),
        "n_train_neg": counts.get("train_neg", ""),
        "n_test_pos": counts.get("test_pos", ""),
        "n_test_neg": counts.get("test_neg", ""),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "F1": round(f1, 4),
        "balanced_accuracy": round(bacc, 4),
        "AUC": "" if auc is None else round(auc, 4),
        "PR_AUC": "" if prauc is None else round(prauc, 4),
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
        "runtime_sec": round(runtime, 3),
        "seed": SEED,
        "note": "Behavioral risk, not verified bot identity",
    }


def make_models() -> dict[str, Any]:
    models = {
        "Logistic Regression": LogisticRegression(max_iter=400, class_weight="balanced", random_state=SEED),
        "Decision Tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=3, class_weight="balanced", random_state=SEED),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=6, min_samples_leaf=2, class_weight="balanced", random_state=SEED, n_jobs=-1
        ),
        "SVM": SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=SEED),
    }
    if XGB_OK:
        models["XGBoost"] = XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=SEED,
            n_jobs=-1,
            eval_metric="logloss",
        )
    return models


def build_pipeline(name: str, clf: Any, pos: int, neg: int) -> Pipeline:
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    if name == "XGBoost" and hasattr(clf, "set_params") and neg > 0:
        clf.set_params(scale_pos_weight=float(neg) / max(pos, 1))
    if name in {"Decision Tree", "Random Forest", "XGBoost"}:
        return Pipeline([("impute", imputer), ("clf", clf)])
    return Pipeline([("impute", imputer), ("scale", scaler), ("clf", clf)])


def xy(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    ids = []
    xs = []
    ys = []
    for r in rows:
        y = risk_y(r["manual_label"])
        if y is None:
            continue
        ids.append(r["author_id"])
        xs.append([fnum(r, f, default=np.nan) for f in MODEL_FEATURES])
        ys.append(y)
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=int), ids


def run_cv(X, y, ids: list[str], models: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray]]:
    experiments = []
    preds = []
    cms: dict[str, np.ndarray] = {}
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    loo = LeaveOneOut()

    for split_name, splitter in (("kfold_k5", skf), ("loocv", loo)):
        for algo, proto in models.items():
            t0 = time.perf_counter()
            yt_all, yp_all, pr_all = [], [], []
            warnings.filterwarnings("ignore", message="Skipping features without any observed values")
            n_trains = []
            overlaps = 0
            fold_i = 0
            fold_rows = []
            for train_idx, test_idx in splitter.split(X, y):
                fold_i += 1
                tr_ids = {ids[i] for i in train_idx}
                te_ids = {ids[i] for i in test_idx}
                if tr_ids & te_ids:
                    overlaps += 1
                Xtr, Xte = X[train_idx], X[test_idx]
                ytr, yte = y[train_idx], y[test_idx]
                n_trains.append(len(train_idx))
                pos, neg = int((ytr == 1).sum()), int((ytr == 0).sum())
                # rebuild a fresh estimator each fold
                clf = make_models()[algo]
                pipe = build_pipeline(algo, clf, pos, neg)
                pipe.fit(Xtr, ytr)
                yp = pipe.predict(Xte)
                if hasattr(pipe, "predict_proba"):
                    pr = pipe.predict_proba(Xte)[:, 1]
                else:
                    pr = yp.astype(float)
                yt_all.extend(yte.tolist())
                yp_all.extend(yp.tolist())
                pr_all.extend(pr.tolist())
                for j, idx in enumerate(test_idx):
                    preds.append(
                        {
                            "user_id": ids[idx],
                            "author_id": ids[idx],
                            "username": "",
                            "model": algo,
                            "fold": f"{split_name}_{fold_i}",
                            "evaluation_method": split_name,
                            "predicted_label": "risk_positive" if int(yp[j]) == 1 else "risk_negative",
                            "prediction_probability": round(float(pr[j]), 6),
                            "manual_label": "likely_malicious_or_suspicious" if int(yte[j]) == 1 else "likely_normal",
                            "true_risk": int(yte[j]),
                            "evidence_availability": "snapshot_profile_plus_nlp_posts",
                            "confidence_category": (
                                "high" if float(pr[j]) >= 0.8 or float(pr[j]) <= 0.2 else "medium"
                            ),
                        }
                    )
                if split_name == "kfold_k5":
                    fold_rows.append(
                        matrix_row(
                            yte,
                            yp,
                            pr,
                            algo,
                            f"kfold_k5_fold{fold_i}",
                            len(train_idx),
                            len(test_idx),
                            {
                                "train_pos": pos,
                                "train_neg": neg,
                                "test_pos": int((yte == 1).sum()),
                                "test_neg": int((yte == 0).sum()),
                            },
                            time.perf_counter() - t0,
                        )
                    )
            runtime = time.perf_counter() - t0
            if overlaps:
                raise RuntimeError(f"train/test user overlap in {algo} {split_name}: {overlaps}")
            pooled = matrix_row(
                yt_all,
                yp_all,
                pr_all,
                algo,
                f"{split_name}_pooled",
                int(np.mean(n_trains)),
                len(yt_all),
                {
                    "train_pos": int(round(np.mean([r["n_train_pos"] for r in fold_rows]))) if fold_rows else int((y == 1).sum()),
                    "train_neg": int(round(np.mean([r["n_train_neg"] for r in fold_rows]))) if fold_rows else int((y == 0).sum()),
                    "test_pos": int(sum(yt_all)),
                    "test_neg": int(len(yt_all) - sum(yt_all)),
                },
                runtime,
            )
            experiments.extend(fold_rows)
            experiments.append(pooled)
            if split_name == "kfold_k5" and fold_rows:
                experiments.append(
                    {
                        **pooled,
                        "training_type": "kfold_k5_mean",
                        "accuracy": round(float(np.mean([r["accuracy"] for r in fold_rows])), 4),
                        "precision": round(float(np.mean([r["precision"] for r in fold_rows])), 4),
                        "recall": round(float(np.mean([r["recall"] for r in fold_rows])), 4),
                        "F1": round(float(np.mean([r["f1"] if "f1" in r else r["F1"] for r in fold_rows])), 4),
                        "balanced_accuracy": round(float(np.mean([r["balanced_accuracy"] for r in fold_rows])), 4),
                        "AUC": round(float(np.mean([r["AUC"] for r in fold_rows if r["AUC"] != ""])), 4)
                        if any(r["AUC"] != "" for r in fold_rows)
                        else "",
                        "note": f"mean±std F1 {np.mean([r['F1'] for r in fold_rows]):.3f}±{np.std([r['F1'] for r in fold_rows]):.3f}; no user overlap; seed {SEED}",
                    }
                )
            cms[f"{algo}|{split_name}"] = confusion_matrix(yt_all, yp_all, labels=[0, 1])
            log(f"{algo} {split_name} F1={pooled['F1']} bacc={pooled['balanced_accuracy']} n_train~{pooled['n_train']}")
    return experiments, preds, cms


def fit_full_and_predict(rows: list[dict[str, Any]], labeled: list[dict[str, Any]], models: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    X, y, ids = xy(labeled)
    pos, neg = int((y == 1).sum()), int((y == 0).sum())
    # pick best by K=5 pooled F1 later; default Random Forest for full predict
    chosen_name = "Random Forest"
    clf = make_models()[chosen_name]
    pipe = build_pipeline(chosen_name, clf, pos, neg)
    pipe.fit(X, y)
    imp = {}
    model = pipe.named_steps["clf"]
    if hasattr(model, "feature_importances_"):
        for f, v in zip(MODEL_FEATURES, model.feature_importances_):
            imp[f] = float(v)
    elif hasattr(model, "coef_"):
        for f, v in zip(MODEL_FEATURES, np.abs(model.coef_[0])):
            imp[f] = float(v)
    Xu = np.asarray([[fnum(r, f, default=np.nan) for f in MODEL_FEATURES] for r in rows], dtype=float)
    proba = pipe.predict_proba(Xu)[:, 1]
    pred = (proba >= 0.5).astype(int)
    out = []
    labels = {r["author_id"]: r for r in labeled}
    for r, p, pr in zip(rows, pred, proba):
        lab = labels.get(r["author_id"], {})
        out.append(
            {
                "user_id": r["author_id"],
                "author_id": r["author_id"],
                "username": r.get("username") or "",
                "model": f"{chosen_name}_full_labeled_fit",
                "fold": "full_labeled",
                "evaluation_method": "predict_unlabeled_after_labeled_fit",
                "predicted_label": "risk_positive" if int(p) == 1 else "risk_negative",
                "prediction_probability": round(float(pr), 6),
                "manual_label": lab.get("manual_label", ""),
                "true_risk": "" if not lab else risk_y(lab.get("manual_label", "")),
                "evidence_availability": "snapshot_profile_plus_nlp_posts" if int(r.get("has_nlp_posts") or 0) else "profile_only",
                "confidence_category": "high" if pr >= 0.8 or pr <= 0.2 else "medium",
                "prob_0": round(1.0 - float(pr), 6),
                "prob_1": round(float(pr), 6),
                "predicted_class": int(p),
                "confidence_level": round(float(max(pr, 1 - pr)), 6),
            }
        )
    return out, imp


def plot_distributions(labeled: list[dict[str, Any]]) -> None:
    keys = [
        "ifb_count", "boilerplate_ratio", "duplicate_template_ratio", "rt_at_ratio",
        "followers_following_ratio", "unique_text_ratio",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 7.2))
    fig.patch.set_facecolor("white")
    groups = {
        "likely_normal": [r for r in labeled if r["manual_label"] == "likely_normal"],
        "suspicious": [r for r in labeled if r["manual_label"] == "suspicious"],
        "likely_malicious": [r for r in labeled if r["manual_label"] == "likely_malicious"],
    }
    colors = {"likely_normal": "#2ca02c", "suspicious": "#ffcc00", "likely_malicious": "#d62728"}
    for ax, key in zip(axes.ravel(), keys):
        data = []
        cols = []
        labs = []
        for lab, rs in groups.items():
            vals = [fnum(r, key, default=np.nan) for r in rs]
            vals = [v for v in vals if not math.isnan(v)]
            if vals:
                data.append(vals)
                cols.append(colors[lab])
                labs.append(f"{lab}\nn={len(vals)}")
        if data:
            bp = ax.boxplot(data, tick_labels=labs, patch_artist=True)
            for patch, c in zip(bp["boxes"], cols):
                patch.set_facecolor(c)
                patch.set_alpha(0.7)
        ax.set_title(key, fontsize=10)
        ax.tick_params(labelsize=7)
    fig.suptitle("Feature distributions by manual behavioral label (not bot identity)", fontsize=12)
    fig.tight_layout()
    fig.savefig(DIST_PNG, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_models(experiments: list[dict[str, Any]], cms: dict[str, np.ndarray]) -> None:
    pooled = [r for r in experiments if r["training_type"] == "kfold_k5_pooled"]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    fig.patch.set_facecolor("white")
    names = [r["algorithm"] for r in pooled]
    x = np.arange(len(names))
    w = 0.18
    metrics = [("F1", "#4c78a8"), ("balanced_accuracy", "#54a24b"), ("precision", "#f58518"), ("recall", "#e45756")]
    for i, (m, c) in enumerate(metrics):
        ax.bar(x + (i - 1.5) * w, [float(r[m]) for r in pooled], width=w, color=c, label=m)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("K=5 pooled metrics — behavioral risk, not bot identity")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CMP_PNG, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    keys = [k for k in cms if k.endswith("|kfold_k5")]
    fig, axes = plt.subplots(1, max(len(keys), 1), figsize=(3.2 * max(len(keys), 1), 3.4))
    fig.patch.set_facecolor("white")
    if len(keys) == 1:
        axes = [axes]
    for ax, key in zip(axes, keys):
        cm = cms[key]
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["pred 0", "pred 1"], fontsize=8)
        ax.set_yticklabels(["true 0", "true 1"], fontsize=8)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(int(cm[i, j])), ha="center", va="center", color="black")
        ax.set_title(key.split("|")[0], fontsize=9)
    fig.suptitle("K=5 pooled confusion matrices (0=likely_normal, 1=suspicious/malicious risk)", fontsize=11)
    fig.tight_layout()
    fig.savefig(CM_PNG, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def draw_flow_png() -> None:
    fig, ax = plt.subplots(figsize=(11.2, 8.4))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    boxes = [
        (3.2, 9.0, "User snapshot + NLP posts"),
        (3.2, 7.7, "Enough posts and profile?"),
        (0.4, 6.4, "insufficient_evidence\n(not malicious)"),
        (3.2, 6.4, "IFB boilerplate / duplicate templates?"),
        (6.4, 6.4, "High RT @ share + low unique text?"),
        (3.2, 5.1, "Mass follow + high IFB_COUNT?"),
        (3.2, 3.8, "Burst + hour concentration?"),
        (0.4, 2.2, "low_risk"),
        (3.2, 2.2, "medium_risk"),
        (6.4, 2.2, "high_risk"),
        (3.2, 0.7, "Manual review is the label.\nRule score is not ground truth."),
    ]
    for x, y, t in boxes:
        ax.add_patch(FancyBboxPatch((x, y), 2.8, 0.9, boxstyle="round,pad=0.04", facecolor="#eef3f8", edgecolor="#333"))
        ax.text(x + 1.4, y + 0.45, t, ha="center", va="center", fontsize=8)
    ax.set_title("Malicious / suspicious detection flow — behavioral risk, not bot identity", fontsize=12)
    fig.tight_layout()
    fig.savefig(FLOW_PNG, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_pptx() -> None:
    if not PPTX_OK:
        log("python-pptx missing: " + PPTX_ERR)
        return
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    def add_title(slide, text: str, top=0.25):
        box = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.7))
        tf = box.text_frame
        tf.text = text
        tf.paragraphs[0].font.size = Pt(26)
        tf.paragraphs[0].font.bold = True

    def add_note(slide, text: str, top=6.8):
        box = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(12.3), Inches(0.5))
        tf = box.text_frame
        tf.text = text
        tf.paragraphs[0].font.size = Pt(14)
        tf.paragraphs[0].font.italic = True

    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "Behavioral risk classification — not verified bot identity")
    box = s.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(12), Inches(5))
    box.text_frame.text = (
        "IFB.db has counts, not follow edges. There are no reply/quote IDs and no native retweet cascade.\n"
        "Manual labels come from snapshot profiles + original posts. Deleted/unavailable ≠ malicious.\n"
        "Rules and models estimate suspicious behavior. They do not prove an account is a bot."
    )
    add_note(s, "Course phase 5. Seed 2026. Do not present scores as ground truth.")

    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s2, "Detection flowchart (rules are not labels)")
    steps = [
        (0.5, 1.4, "1. Profile + posts"),
        (3.6, 1.4, "2. Enough evidence?"),
        (6.7, 1.4, "3. Templates / IFB?"),
        (9.8, 1.4, "4. RT @ + low unique?"),
        (2.0, 3.4, "5. Mass-follow + IFB_COUNT"),
        (5.2, 3.4, "6. Burst + hour lock"),
        (8.4, 3.4, "7. Risk band"),
        (3.6, 5.3, "Manual review decides the label"),
    ]
    for x, y, t in steps:
        sh = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(2.8), Inches(1.0))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(0xEE, 0xF3, 0xF8)
        sh.text_frame.text = t
        sh.text_frame.paragraphs[0].font.size = Pt(12)
        sh.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    add_note(s2, "Thresholds: boilerplate≥0.45, duplicate≥0.55, unique≤0.40, RT@≥0.50, IFB_COUNT≥20, burst≥2.2 & hour conc.≥0.35")

    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s3, "Why this is not a bot identity system")
    box = s3.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(12), Inches(5))
    box.text_frame.text = (
        "False-positive risk: ordinary IFB hobbyists use the same hashtags as spam scripts.\n"
        "False-negative risk: a careful automated account can look like a normal poster in a 1.7% timeline sample.\n"
        "Live profiles were not required to label someone malicious. Missing profiles stay insufficient_evidence.\n"
        "ML is trained only on manually reviewed users. No unlabeled row is treated as a label."
    )
    prs.save(str(PPTX))
    log(f"Wrote {PPTX.name}")


def write_report(
    n_users: int,
    n_nlp: int,
    labels: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    importance: dict[str, float],
    rule_summary: list[dict[str, Any]],
    checklist: dict[str, bool],
) -> None:
    lab_c = Counter(r["manual_label"] for r in labels)
    usable = [r for r in labels if risk_y(r["manual_label"]) is not None]
    pos = sum(1 for r in usable if risk_y(r["manual_label"]) == 1)
    neg = len(usable) - pos
    pooled = [r for r in experiments if r["training_type"] == "kfold_k5_pooled"]
    top_imp = sorted(importance.items(), key=lambda kv: -kv[1])[:12]
    lines = [
        "# Bot / malicious-user detection",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "**This is a behavioral risk classification, not verified bot identity.**",
        "",
        "IFB.db was opened **read-only** for `authors` metadata only and was not modified. "
        "Sentiment, emotion, events, BERTopic, NER, and the entity network were not rerun.",
        "",
        "## Operational definition",
        "",
        "A user is treated as **suspicious / likely malicious** when snapshot metadata and original posts show "
        "follow-farm automation, copy-paste IFB templates, or RT-@ amplification with little original voice. "
        "That is **not** proof the account is a software bot. Humans run IFB campaigns.",
        "",
        "## Why bot status cannot be proven",
        "",
        "- No follower graph, no reply/quote IDs, no native retweet flag or cascade.",
        "- Profiles are a 2023 snapshot. Live X pages were not used as a required oracle.",
        "- Timeline text is a stratified ~1.7% English sample (seed 2026), not a full history.",
        "- Deleted or empty accounts are **insufficient_evidence**, not bots.",
        "",
        "## Population",
        "",
        f"- Primary triple-intersection users: **{n_users:,}**",
        f"- Users with English NLP posts (behavior features): **{n_nlp:,}**",
        "- Keyword features and timeline features are stored as separate counts. Combined `n_posts` is labeled as mixed frames.",
        "- `timeline_weighted_post_estimate` is a population estimate only and is **not** a model feature or training weight.",
        "",
        "## Features",
        "",
        "Profile: followers, following, tweet_count, listed_count, IFB_COUNT, verified, protected, freelancer, "
        "account age (to 2023-12-03), missing-field count, bio length, default-image heuristic, followers/(following+1).",
        "",
        "Behavior (NLP corpus only): post counts by source, IFB-collection share, duplicate-template ratio, "
        "boilerplate ratio, unique-text ratio, mean length, URL/mention/hashtag ratios, active days, posts/active day, "
        "burstiness (CV of daily counts), hour/day-of-week concentration, sentiment and emotion shares, "
        "topic outlier/top-share/entropy, text `RT @` ratio.",
        "",
        "Not used as model features: `user_id`, `username`, `tweet_id`, raw post text, the manual label, `sample_weight`.",
        "",
        "Missing values: median imputed **inside each training fold**. Trees skip scaling; linear/SVM use StandardScaler fit on the train fold only. "
        "Epoch `1970-01-01` ages are treated as missing. Extreme counts stay in the table; models see raw values after median/scale.",
        "",
        "## Manual review",
        "",
        f"100 users, seed 2026, stratified on unlabeled rule bands (35 low / 30 medium / 35 high). "
        f"Labels: {dict(lab_c)}. Usable for ML: **{len(usable)}** (pos={pos}, neg={neg}). "
        "See `MANUAL_BOT_REVIEW_GUIDE.md` and `outputs/manual_review_examples.csv`.",
        "",
        "There is **no 200-user second manual set**. Extra labels were not invented. Rule accuracy below is measured only on the 100 reviewed users.",
        "",
        "## Rule thresholds",
        "",
        "| Rule | Threshold | Why | FP risk |",
        "|------|-----------|-----|---------|",
        "| IFB boilerplate | ≥ 0.45 of posts | Collection copy is the IFB tell | Honest IFB hobbyists |",
        "| Duplicate templates | ≥ 0.55 | Scripted repetition | Quote-heavy humans |",
        "| Unique text | ≤ 0.40 | Thin original voice | Short-form posters |",
        "| Keyword share | ≥ 0.75 (≥8 posts) | Almost only IFB tweets in the sample | Users rare in the timeline sample |",
        "| `RT @` text | ≥ 0.50 | Amplifiers; no native retweet flag | Heavy conversational RT users |",
        "| Burst + hour lock | burst ≥ 2.2 and hour conc. ≥ 0.35 | Scheduler-like timing | Event-day humans |",
        "| IFB_COUNT | ≥ 20 | Database follow-back counter | Active community members |",
        "| Symmetric mass follow | following ≥ 2000 and ratio 0.7–1.4 | Follow-for-follow farms | Popular IFB accounts |",
        "",
        "Rule score is **not** ground truth.",
        "",
    ]
    if rule_summary:
        lines += ["## Rule vs manual labels (100 reviewed users only)", "", "| metric | value |", "|--------|------:|"]
        for r in rule_summary:
            lines.append(f"| {r.get('metric')} | {r.get('value')} |")
        lines.append("")
    lines += [
        "## Machine learning",
        "",
        f"Algorithms: Logistic Regression, Decision Tree, Random Forest, SVM"
        + (", XGBoost" if XGB_OK else f". XGBoost unavailable: {XGB_ERR}"),
        "",
        f"Training rows: **{len(usable)}** users (positive {pos}, negative {neg}). "
        "K=5 stratified CV and LOOCV. User-level splits; overlap check raises an error. "
        f"Seed {SEED}. Preprocessing fit on the training fold only. Class weights / XGBoost `scale_pos_weight`.",
        "",
        "Accuracy is reported with precision, recall, F1, balanced accuracy, ROC-AUC and PR-AUC where both classes exist.",
        "",
        "### K=5 pooled",
        "",
        "| Algorithm | n_train (mean) | n_test | pos/neg test | accuracy | precision | recall | F1 | bal. acc. | AUC |",
        "|-----------|---------------:|-------:|-------------:|---------:|----------:|-------:|---:|----------:|----:|",
    ]
    for r in pooled:
        lines.append(
            f"| {r['algorithm']} | {r['n_train']} | {r['n_test']} | {r['n_test_pos']}/{r['n_test_neg']} | "
            f"{r['accuracy']} | {r['precision']} | {r['recall']} | {r['F1']} | {r['balanced_accuracy']} | {r['AUC']} |"
        )
    loo = [r for r in experiments if r["training_type"] == "loocv_pooled"]
    lines += [
        "",
        "### LOOCV pooled",
        "",
        "| Algorithm | n_train | n_test | F1 | bal. acc. | AUC |",
        "|-----------|--------:|-------:|---:|----------:|----:|",
    ]
    for r in loo:
        lines.append(f"| {r['algorithm']} | {r['n_train']} | {r['n_test']} | {r['F1']} | {r['balanced_accuracy']} | {r['AUC']} |")
    lines += [
        "",
        "## Important features (Random Forest full labeled fit)",
        "",
        "| Feature | importance |",
        "|---------|-----------:|",
    ]
    for f, v in top_imp:
        lines.append(f"| {f} | {v:.4f} |")
    lines += [
        "",
        "## False positives and false negatives",
        "",
        "False positives are mostly ordinary IFB users whose bios and posts are follow-back templates. "
        "False negatives are accounts that look conversational in the sampled timeline posts even if keyword tweets are promotional. "
        "High-confidence (`≥ 0.8`) risk_positive predictions are a **filter suggestion**, not a ban list.",
        "",
        "## Limitations",
        "",
        "- No live profile confirmation in this environment.",
        "- No follower graph, conversation IDs, or native retweet flag.",
        "- Timeline is a stratified sample; keyword is a census of IFB tweets.",
        "- 100 labels is a small, imbalanced set. Metrics have wide uncertainty.",
        "- 200-user rule validation was **not** fabricated.",
        "",
        "## Output checklist",
        "",
        "| File | Present |",
        "|------|---------|",
    ]
    for k, ok in checklist.items():
        lines.append(f"| `{k}` | {'yes' if ok else 'NO'} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {REPORT.name}")


def evaluate_rules_on_labels(rows: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    y_true = []
    y_pred = []
    for r in rows:
        lab = labels.get(r["author_id"])
        if not lab:
            continue
        yt = risk_y(lab["manual_label"])
        if yt is None:
            continue
        yp = 1 if r.get("rule_label") == "high_risk" else 0
        y_true.append(yt)
        y_pred.append(yp)
    if not y_true:
        return []
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return [
        {"metric": "n_reviewed_usable", "value": len(y_true)},
        {"metric": "rule_high_risk_as_positive_accuracy", "value": round(accuracy_score(y_true, y_pred), 4)},
        {"metric": "rule_precision", "value": round(precision_score(y_true, y_pred, zero_division=0), 4)},
        {"metric": "rule_recall", "value": round(recall_score(y_true, y_pred, zero_division=0), 4)},
        {"metric": "rule_f1", "value": round(f1_score(y_true, y_pred, zero_division=0), 4)},
        {"metric": "rule_balanced_accuracy", "value": round(balanced_accuracy_score(y_true, y_pred), 4)},
        {"metric": "tn", "value": int(cm[0, 0])},
        {"metric": "fp", "value": int(cm[0, 1])},
        {"metric": "fn", "value": int(cm[1, 0])},
        {"metric": "tp", "value": int(cm[1, 1])},
        {"metric": "note", "value": "Rules evaluated only on manual labels; not ground truth"},
    ]


def attach_posts_map(posts: list[sqlite3.Row]) -> dict[str, list]:
    by = defaultdict(list)
    for p in posts:
        by[str(p["author_id"])].append(p)
    return by


def features_stage() -> list[dict[str, Any]]:
    rows = build_features()
    write_csv(FEATURES_CSV, FEATURE_FIELDS, rows)
    write_csv(UNLABELED_CSV, FEATURE_FIELDS, rows)
    log(f"Wrote {FEATURES_CSV.name} n={len(rows):,}")
    return rows


def sample_stage(rows: list[dict[str, Any]]) -> None:
    write_guide()
    posts = load_nlp_posts()
    pmap = attach_posts_map(posts)
    sample = stratified_sample(rows)
    # attach descriptions already on rows
    write_packets(sample, pmap)
    log("SAMPLE_READY — write manual_bot_labels.csv then rerun --train")


def train_stage(rows: list[dict[str, Any]]) -> int:
    labels = load_labels()
    if len(labels) < 100:
        log(f"Need 100 manual labels, found {len(labels)}")
        return 2
    labeled_rows = []
    for r in rows:
        lab = labels.get(r["author_id"])
        if not lab:
            continue
        rec = dict(r)
        rec.update(lab)
        labeled_rows.append(rec)
    if len(labeled_rows) < 100:
        log(f"Only {len(labeled_rows)} labeled users matched features")
        return 2

    scored = apply_rules(rows)
    write_csv(
        RULE_SCORES_CSV,
        FEATURE_FIELDS
        + ["rule_score", "rule_label", "rule_reasons", "rule_confidence"],
        scored,
    )
    rule_sum = evaluate_rules_on_labels(scored, labels)
    write_csv(RULE_SUMMARY_CSV, ["metric", "value"], rule_sum)

    usable = [r for r in labeled_rows if risk_y(r.get("manual_label", "")) is not None]
    X, y, ids = xy(usable)
    log(f"ML usable {len(ids)} pos={int((y==1).sum())} neg={int((y==0).sum())}")
    models = make_models()
    if not XGB_OK:
        log("XGBoost unavailable: " + XGB_ERR)
    experiments, cv_preds, cms = run_cv(X, y, ids, models)
    uname = {r["author_id"]: r.get("username") or "" for r in rows}
    for p in cv_preds:
        p["username"] = uname.get(p["user_id"], "")
    full_preds, importance = fit_full_and_predict(rows, usable, models)
    write_csv(
        EXPERIMENTS_CSV,
        [
            "target_column", "algorithm", "feature_set", "training_type", "K", "balanced",
            "n_train", "n_test", "n_train_pos", "n_train_neg", "n_test_pos", "n_test_neg",
            "accuracy", "precision", "recall", "F1", "balanced_accuracy", "AUC", "PR_AUC",
            "tn", "fp", "fn", "tp", "runtime_sec", "seed", "note",
        ],
        experiments,
    )
    pred_fields = [
        "user_id", "author_id", "username", "model", "fold", "evaluation_method",
        "predicted_label", "prediction_probability", "manual_label", "true_risk",
        "evidence_availability", "confidence_category", "prob_0", "prob_1",
        "predicted_class", "confidence_level",
    ]
    write_csv(PREDICTIONS_CSV, pred_fields, full_preds + cv_preds)
    write_csv(UNLABELED_RESULTS_CSV, pred_fields, full_preds)
    write_csv(
        IMPORTANCE_CSV,
        ["feature", "importance", "model"],
        [{"feature": f, "importance": round(v, 6), "model": "Random Forest"} for f, v in sorted(importance.items(), key=lambda kv: -kv[1])],
    )
    plot_distributions(labeled_rows)
    plot_models(experiments, cms)
    draw_flow_png()
    write_pptx()
    n_nlp = sum(1 for r in rows if int(r.get("has_nlp_posts") or 0) == 1)
    checklist = {
        "src/bot_detection.py": True,
        "notebooks/bot_detection.ipynb": (ROOT / "notebooks" / "bot_detection.ipynb").exists(),
        "outputs/user_bot_features.csv": FEATURES_CSV.exists(),
        "outputs/manual_bot_labels.csv": LABELS_CSV.exists(),
        "outputs/manual_review_examples.csv": EXAMPLES_CSV.exists(),
        "outputs/rule_based_bot_scores.csv": RULE_SCORES_CSV.exists(),
        "outputs/rule_based_summary.csv": RULE_SUMMARY_CSV.exists(),
        "outputs/bot_detection_experiments.csv": EXPERIMENTS_CSV.exists(),
        "outputs/bot_detection_predictions.csv": PREDICTIONS_CSV.exists(),
        "outputs/bot_feature_importance.csv": IMPORTANCE_CSV.exists(),
        "outputs/bot_confusion_matrices.png": CM_PNG.exists(),
        "outputs/bot_model_comparison.png": CMP_PNG.exists(),
        "outputs/bot_feature_distributions.png": DIST_PNG.exists(),
        "malicious_detection_flow.pptx": PPTX.exists(),
        "MANUAL_BOT_REVIEW_GUIDE.md": GUIDE.exists(),
        "BOT_DETECTION_REPORT.md": True,
        "xgboost": XGB_OK,
    }
    write_report(len(rows), n_nlp, labeled_rows, experiments, importance, rule_sum, checklist)
    log("TRAIN_COMPLETE")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["features", "sample", "train", "all"], default="all")
    args = ap.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.stage in {"features", "sample", "all"}:
        if FEATURES_CSV.exists() and args.stage != "features":
            log("Loading existing user_bot_features.csv")
            with FEATURES_CSV.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        else:
            rows = features_stage()
    else:
        with FEATURES_CSV.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    if args.stage in {"sample", "all"} and not LABELS_CSV.exists():
        sample_stage(rows)
        if args.stage == "all":
            log("Stopped before train: labels missing")
            return 0
    if args.stage in {"train", "all"} and LABELS_CSV.exists():
        return train_stage(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
