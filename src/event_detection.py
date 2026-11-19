#!/usr/bin/env python3
"""Phase 2.5: Event detection from emotion series + tweet evidence.

Does not open IFB.db. Does not rerun sentiment or emotion scoring.
Does not invent a world-news list. Peaks without tweet evidence are rejected.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emotion_analysis import (  # noqa: E402
    COLOR,
    EMOTIONS,
    TIME_CSV,
    add_event_lines,
    period_to_dt,
    plot_resolution,
)

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
PLOT_DIR = OUTPUT_DIR / "event_plots"
EMOTION_PLOT_DIR = OUTPUT_DIR / "emotion_plots"
REPORT = ROOT / "EVENT_DETECTION_REPORT.md"
DOCX = ROOT / "detected_events.docx"
EVENTS_JSON = OUTPUT_DIR / "detected_events.json"

CAND_CSV = OUTPUT_DIR / "event_detection_candidates.csv"
EVENTS_CSV = OUTPUT_DIR / "detected_events.csv"
EVID_CSV = OUTPUT_DIR / "event_tweet_evidence.csv"
STATS_CSV = OUTPUT_DIR / "event_statistics.csv"
EXT_CSV = OUTPUT_DIR / "event_external_sources.csv"

STATUS_FILTER = "not_required_english"
EKMAN = ("joy", "anger", "sadness", "fear", "surprise", "disgust")
EVENT_COLOR = {e: COLOR[e] for e in EKMAN}

# --- documented detection parameters ---
MIN_N = {"weekly": 160, "monthly": 400}
# Rare Ekman classes (fear/surprise) seldom reach 25 posts/month; 15 is the documented floor.
MIN_EMO = {"weekly": 12, "monthly": 15}
Z_CUT = {"weekly": 2.75, "monthly": 2.25}
ROLLING = 12
REFRACTORY_DAYS = {"weekly": 21, "monthly": 45}
MIN_UNIQUE_AUTHORS = 5
MIN_UNIQUE_TEXTS = 8
MAX_ONE_AUTHOR = 0.45
MIN_CLEAN_TOKENS = 4
MAX_SELECTED = 6
MAX_PER_EMOTION = 2
EVIDENCE_PER_EVENT = 10
MIN_EVIDENCE_TOTAL = 20
IFB_BOILER = re.compile(
    r"follow\s*4\s*follow|follow4follow|followback|#ifb|had da best dae",
    re.I,
)
SPAM_USER_REPEAT = "had da best dae"

PARAMS = {
    "min_n_weekly": MIN_N["weekly"],
    "min_n_monthly": MIN_N["monthly"],
    "min_emotion_count_weekly": MIN_EMO["weekly"],
    "min_emotion_count_monthly": MIN_EMO["monthly"],
    "z_weekly": Z_CUT["weekly"],
    "z_monthly": Z_CUT["monthly"],
    "rolling_windows": ROLLING,
    "refractory_days_weekly": REFRACTORY_DAYS["weekly"],
    "refractory_days_monthly": REFRACTORY_DAYS["monthly"],
    "min_unique_authors": MIN_UNIQUE_AUTHORS,
    "min_unique_texts": MIN_UNIQUE_TEXTS,
    "max_share_from_one_author": MAX_ONE_AUTHOR,
    "others_not_used_as_signal": True,
    "timeline_weighted_z_confirm": 1.5,
    "drops_scanned_not_auto_selected": True,
    "theme_min_hits": 8,
    "theme_alt_hits": 5,
    "theme_alt_fraction": 0.20,
    "theme_rare_hits": 4,
    "theme_rare_n_max": 25,
    "ifb_boilerplate_max_share": 0.30,
    "untimed_high_z_not_selected": True,
}

THEME_RULES: list[tuple[str, str]] = [
    (r"mother'?s?\s*day", "Mother's Day greetings in user timelines"),
    (r"father'?s?\s*day", "Father's Day greetings in user timelines"),
    (r"thanksgiv", "Thanksgiving greetings in user timelines"),
    (r"happy new year|new year'?s", "New Year greetings"),
    (r"merry christmas|\bchristmas\b|merry xmas", "Christmas greetings"),
    (r"flood warning|#flood|nswses|lismore", "Official flood warnings (eastern Australia / NSW)"),
    (r"ukraine|zelensky|kyiv|kiev|\bputin\b", "Posts mentioning the 2022 Russia–Ukraine war"),
    (r"\bgaza\b|\bhamas\b|\bpalestine\b", "Posts mentioning Israel/Gaza/Hamas"),
    (r"black lives|george floyd|#blm", "Posts mentioning racial-justice protests"),
    (r"covid|coronavirus|lockdown", "Posts mentioning COVID-19"),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{NLP_DB.as_posix()}?mode=ro", uri=True, timeout=120)
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


def load_series(resolution: str, corpus: str) -> list[dict[str, Any]]:
    path = TIME_CSV[resolution]
    rows = []
    with path.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["corpus"] == corpus:
                rec = dict(r)
                rec["_dt"] = period_to_dt(resolution, r["period"])
                rec["n_raw"] = int(float(r["n_raw"]))
                for e in list(EKMAN) + ["others"]:
                    rec[f"n_{e}"] = int(float(r.get(f"n_{e}") or 0))
                    rec[f"share_{e}"] = float(r.get(f"share_{e}") or 0)
                    w = r.get(f"share_weighted_{e}", "")
                    rec[f"share_weighted_{e}"] = float(w) if w not in ("", None) else None
                if rec["_dt"] is not None:
                    rows.append(rec)
    rows.sort(key=lambda r: r["_dt"])
    return rows


def rolling_z(values: list[float], i: int, window: int) -> tuple[float, float, float]:
    left = max(0, i - window)
    base = [values[j] for j in range(left, i) if j != i]
    if len(base) < 6:
        base = [values[j] for j in range(len(values)) if j != i]
    mu = statistics.mean(base) if base else 0.0
    sd = statistics.pstdev(base) if len(base) > 1 else 1e-9
    if sd < 1e-9:
        sd = 1e-9
    return (values[i] - mu) / sd, mu, sd


def is_local_peak(values: list[float], i: int) -> bool:
    if i <= 0 or i >= len(values) - 1:
        return False
    return values[i] >= values[i - 1] and values[i] >= values[i + 1]


def is_local_drop(values: list[float], i: int) -> bool:
    if i <= 0 or i >= len(values) - 1:
        return False
    return values[i] <= values[i - 1] and values[i] <= values[i + 1]


def detect_candidates() -> list[dict[str, Any]]:
    cands = []
    cid = 0
    for resolution in ("weekly", "monthly"):
        for corpus in ("keyword_tweets", "timeline"):
            rows = load_series(resolution, corpus)
            if len(rows) < 10:
                continue
            for emo in EKMAN:
                shares = [r[f"share_{emo}"] for r in rows]
                wshares = [r[f"share_weighted_{emo}"] for r in rows]
                for i, r in enumerate(rows):
                    n = r["n_raw"]
                    n_emo = r[f"n_{emo}"]
                    reject = None
                    direction = ""
                    peak = is_local_peak(shares, i)
                    drop = is_local_drop(shares, i)
                    if n < MIN_N[resolution]:
                        reject = f"n_raw<{MIN_N[resolution]}"
                    elif n_emo < MIN_EMO[resolution] and not drop:
                        reject = f"n_{emo}<{MIN_EMO[resolution]}"
                    elif not peak and not drop:
                        reject = "not_local_peak_or_drop"
                    z, mu, sd = rolling_z(shares, i, ROLLING)
                    if reject is None and peak:
                        direction = "peak"
                        if z < Z_CUT[resolution]:
                            reject = f"z<{Z_CUT[resolution]}"
                    elif reject is None and drop:
                        direction = "drop"
                        if z > -Z_CUT[resolution]:
                            reject = f"|z|<{Z_CUT[resolution]}_drop"
                    wz = None
                    if corpus == "timeline" and wshares[i] is not None:
                        finite = [x for x in wshares if x is not None]
                        if len(finite) == len(wshares):
                            wz, _, _ = rolling_z(wshares, i, ROLLING)
                            if reject is None and peak and wz is not None and wz < 1.5:
                                reject = "weighted_z_not_confirmed"
                            if reject is None and drop and wz is not None and wz > -1.5:
                                reject = "weighted_z_not_confirmed_drop"
                    cid += 1
                    cands.append(
                        {
                            "candidate_id": f"C{cid:04d}",
                            "resolution": resolution,
                            "source": corpus,
                            "period": r["period"],
                            "date": r["_dt"].strftime("%Y-%m-%d"),
                            "emotion": emo,
                            "n_raw": n,
                            "n_emotion": n_emo,
                            "share": round(shares[i], 6),
                            "share_weighted": "" if wshares[i] is None else round(wshares[i], 6),
                            "baseline_share": round(mu, 6),
                            "z_score": round(z, 4),
                            "z_weighted": "" if wz is None else round(wz, 4),
                            "status": "rejected" if reject else "pass_stats",
                            "reject_reason": reject or "",
                            "series": "share_raw",
                            "direction": direction or ("peak" if peak else "drop" if drop else ""),
                        }
                    )
    return cands


def window_bounds(resolution: str, date_iso: str) -> tuple[str, str]:
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    if resolution == "weekly":
        end = dt + timedelta(days=7)
        return dt.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    # monthly: period is YYYY-MM stored as YYYY-MM-01
    if len(date_iso) == 10 and date_iso.endswith("-01"):
        start = dt
    else:
        start = datetime(dt.year, dt.month, 1)
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1)
    else:
        end = datetime(start.year, start.month + 1, 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def norm_text(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"https?://\s*\S+", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"^rt\s+", "", t)
    t = re.sub(r"@\w+", " ", t)
    t = re.sub(r"#\w+", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


def fetch_window_posts(conn: sqlite3.Connection, source: str, start: str, end: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at,
               p.original_text, p.clean_text, p.sample_weight,
               s.sentiment_label, s.sentiment_positive, s.sentiment_neutral, s.sentiment_negative,
               e.emotion_label, e.emotion_joy, e.emotion_anger, e.emotion_sadness,
               e.emotion_fear, e.emotion_surprise, e.emotion_disgust, e.emotion_others
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.source = ? AND p.translation_status = ?
          AND p.created_at >= ? AND p.created_at < ?
        """,
        (source, STATUS_FILTER, start, end),
    ).fetchall()


def evidence_quality(posts: list[sqlite3.Row], emotion: str) -> dict[str, Any]:
    focused = [p for p in posts if p["emotion_label"] == emotion]
    authors = Counter(p["author_id"] for p in focused)
    texts = [norm_text(p["original_text"] or "") for p in focused]
    uniq_txt = {t for t in texts if t}
    top_author_share = (authors.most_common(1)[0][1] / len(focused)) if focused else 1
    spam = sum(1 for p in focused if SPAM_USER_REPEAT in (p["original_text"] or "").lower())
    reasons = []
    ok = True
    ifb = sum(1 for p in focused if IFB_BOILER.search(p["original_text"] or ""))
    ifb_share = ifb / max(len(focused), 1)
    if len(focused) < MIN_EMO["weekly"]:
        ok = False
        reasons.append("too_few_emotion_tweets_in_window")
    if len(authors) < MIN_UNIQUE_AUTHORS and len(uniq_txt) < MIN_UNIQUE_TEXTS:
        ok = False
        reasons.append("low_author_or_text_diversity")
    if top_author_share > MAX_ONE_AUTHOR and len(uniq_txt) < MIN_UNIQUE_TEXTS:
        ok = False
        reasons.append("dominated_by_one_author")
    if spam / max(len(focused), 1) > 0.5:
        ok = False
        reasons.append("boilerplate_spam")
    if ifb_share > 0.30 and emotion == "joy":
        ok = False
        reasons.append("ifb_followback_templates")
    return {
        "ok": ok,
        "n_emotion_tweets": len(focused),
        "n_unique_authors": len(authors),
        "n_unique_texts": len(uniq_txt),
        "top_author_share": round(top_author_share, 4),
        "reasons": ";".join(reasons),
    }


def rank_evidence(
    posts: list[sqlite3.Row], emotion: str, n: int, theme_pat: str | None = None
) -> list[sqlite3.Row]:
    col = f"emotion_{emotion}"
    scored = []
    seen_txt = set()
    seen_auth: Counter[str] = Counter()
    for p in posts:
        if p["emotion_label"] != emotion:
            continue
        orig = p["original_text"] or ""
        clean = p["clean_text"] or ""
        if len(clean.split()) < MIN_CLEAN_TOKENS:
            continue
        if len(orig.strip()) < 25:
            continue
        if IFB_BOILER.search(orig) and emotion == "joy" and not (
            theme_pat and re.search(theme_pat, orig.lower())
        ):
            continue
        if orig.count("@") >= 6:
            continue
        if theme_pat and not re.search(theme_pat, orig.lower()):
            continue
        key = norm_text(orig)
        if not key or key in seen_txt:
            continue
        auth_cap = 6 if theme_pat else 2
        if seen_auth[p["author_id"]] >= auth_cap:
            continue
        prob = float(p[col] or 0)
        theme_hit = 1.0 if theme_pat and re.search(theme_pat, orig.lower()) else 0.0
        scored.append((theme_hit, prob, p, key))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    out = []
    used_txt = set()
    used_auth: Counter[str] = Counter()
    for theme_hit, prob, p, key in scored:
        if key in used_txt:
            continue
        if used_auth[p["author_id"]] >= (6 if theme_pat else 2):
            continue
        used_txt.add(key)
        used_auth[p["author_id"]] += 1
        out.append(p)
        if len(out) >= n:
            break
    return out


def sentiment_mix(posts: list[sqlite3.Row]) -> dict[str, Any]:
    c = Counter((p["sentiment_label"] or "") for p in posts)
    n = len(posts) or 1
    return {
        "n_posts": len(posts),
        "n_positive": c.get("positive", 0),
        "n_neutral": c.get("neutral", 0),
        "n_negative": c.get("negative", 0),
        "pct_positive": round(100 * c.get("positive", 0) / n, 2),
        "pct_neutral": round(100 * c.get("neutral", 0) / n, 2),
        "pct_negative": round(100 * c.get("negative", 0) / n, 2),
    }


def theme_from_tweets(posts: list[sqlite3.Row]) -> tuple[str, int, float, str]:
    texts = [(p["original_text"] or "").lower() for p in posts]
    n = len(texts)
    if n == 0:
        return "no_coherent_named_theme", 0, 0.0, ""
    best_label = "no_coherent_named_theme"
    best_hits = 0
    best_pat = ""
    for pat, label in THEME_RULES:
        hits = sum(1 for t in texts if re.search(pat, t))
        if hits > best_hits:
            best_hits = hits
            best_label = label
            best_pat = pat
    frac = best_hits / n if n else 0.0
    rare_ok = best_hits >= 4 and n <= 25 and frac >= 0.25
    abs_ok = best_hits >= 8 and frac >= 0.08
    conc_ok = best_hits >= 5 and frac >= 0.20
    if not (rare_ok or abs_ok or conc_ok):
        return "no_coherent_named_theme", best_hits, frac, ""
    return best_label, best_hits, frac, best_pat


def attach_external(theme: str, date_iso: str = "") -> dict[str, str]:
    """Only when tweets already name the phenomenon. Never a generic news dump."""
    year = (date_iso or "")[:4]
    catalog = {
        "Mother's Day greetings in user timelines": {
            "title": "Mother's Day (United States) — second Sunday of May",
            "url": "https://en.wikipedia.org/wiki/Mother%27s_Day",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "US/Australia-style Mother's Day is the second Sunday of May. Some joy tweets in that week say 'Happy Mother's Day'.",
        },
        "Official flood warnings (eastern Australia / NSW)": {
            "title": "2022 eastern Australia floods",
            "url": "https://en.wikipedia.org/wiki/2022_eastern_Australia_floods",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "Bureau of Meteorology NSW accounts posted flood warnings in Feb–Mar 2022; those texts are in the keyword corpus because they contain the word 'follow' (follow SES advice).",
        },
        "Posts mentioning Israel/Gaza/Hamas": {
            "title": "October 2023 Hamas-led attack on Israel / Gaza war",
            "url": "https://en.wikipedia.org/wiki/October_7_Hamas-led_attack_on_Israel",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "Some posts mention Gaza/Israel/Hamas. Most emotion tweets in the same bins can be unrelated; this is not treated as proof that the war caused the IFB sample's emotion mix.",
        },
        "New Year greetings": {
            "title": "New Year's Day",
            "url": "https://en.wikipedia.org/wiki/New_Year%27s_Day",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "Calendar New Year; some joy tweets wish a happy new year.",
        },
        "Thanksgiving greetings in user timelines": {
            "title": "Thanksgiving (United States) — fourth Thursday of November",
            "url": "https://en.wikipedia.org/wiki/Thanksgiving_(United_States)",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": (
                "US Thanksgiving 2022 fell on 24 November. Keyword IFB posts that week include 'Happy Thanksgiving'. That does not prove Thanksgiving caused the joy share."
                if year == "2022"
                else "US Thanksgiving 2021 fell on 25 November. Timeline joy tweets that week include 'Happy Thanksgiving'. That does not prove Thanksgiving caused the joy share."
                if year == "2021"
                else "US Thanksgiving is the fourth Thursday of November. Some joy tweets in the window say 'Happy Thanksgiving'."
            ),
        },
        "Posts mentioning the 2022 Russia–Ukraine war": {
            "title": "Russian invasion of Ukraine (24 February 2022)",
            "url": "https://en.wikipedia.org/wiki/Russian_invasion_of_Ukraine",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "A subset of fear-labeled timeline tweets in the 21–27 Feb 2022 week mention Ukraine or explosions there. Other fear tweets in the same week do not. This is not treated as proof that the invasion caused the IFB sample's fear share.",
        },
        "Christmas greetings": {
            "title": "Christmas",
            "url": "https://en.wikipedia.org/wiki/Christmas",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "Calendar Christmas greetings in timelines.",
        },
        "Father's Day greetings in user timelines": {
            "title": "Father's Day (United States) — third Sunday of June",
            "url": "https://en.wikipedia.org/wiki/Father%27s_Day",
            "publication_date": "encyclopedia article (accessed 2026-09-11)",
            "paraphrase": "US-style Father's Day is the third Sunday of June. Timeline joy tweets in that week say 'Happy Father's Day'.",
        },
    }
    hit = catalog.get(theme)
    if not hit:
        return {
            "title": "",
            "url": "",
            "publication_date": "",
            "paraphrase": "no confirmed external explanation",
        }
    return hit


def merge_refractory(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in cands:
        if c["status"] != "pass_stats":
            continue
        by_key[(c["source"], c["emotion"])].append(c)
    for (source, emo), group in by_key.items():
        group.sort(key=lambda x: -abs(float(x["z_score"])))
        chosen = []
        for c in group:
            dt = datetime.strptime(c["date"], "%Y-%m-%d")
            gap = REFRACTORY_DAYS[c["resolution"]]
            if any(abs((dt - datetime.strptime(o["date"], "%Y-%m-%d")).days) < gap for o in chosen):
                c["status"] = "rejected"
                c["reject_reason"] = "too_close_to_stronger_peak"
                continue
            chosen.append(c)
        kept.extend(chosen)
    return cands


def select_events(cands: list[dict[str, Any]], reviewed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only peaks with a tweet-supported named theme. High-z unthemed bins stay rejected."""
    pool = [
        r
        for r in reviewed
        if r["evidence_ok"]
        and r.get("direction") != "drop"
        and r["theme"] != "no_coherent_named_theme"
    ]
    pool.sort(
        key=lambda r: (
            -float(r.get("theme_fraction") or 0),
            -int(r.get("theme_hits") or 0),
            -abs(float(r["z_score"])),
        )
    )
    selected = []
    emo_n: Counter[str] = Counter()
    months: set[tuple[str, str]] = set()
    seen_theme_month: set[tuple[str, str]] = set()
    for r in pool:
        if len(selected) >= MAX_SELECTED:
            break
        if emo_n[r["emotion"]] >= MAX_PER_EMOTION:
            continue
        month_key = (r["source"], r["date"][:7], r["emotion"])
        if month_key in months:
            continue
        theme_month = (r["theme"], r["date"][:7])
        if theme_month in seen_theme_month:
            continue
        r = dict(r)
        r["event_id"] = f"E{len(selected)+1:02d}"
        r["status"] = "selected"
        selected.append(r)
        emo_n[r["emotion"]] += 1
        months.add(month_key)
        seen_theme_month.add(theme_month)
    return selected


def explain(event: dict[str, Any]) -> str:
    return (
        f"{event['resolution']} {event['source']} {event['emotion']} share={100*float(event['share']):.2f}% "
        f"(baseline {100*float(event['baseline_share']):.2f}%, z={event['z_score']}) with "
        f"{event['n_emotion']} {event['emotion']} posts out of {event['n_raw']} in {event['period']}. "
        f"Local peak vs neighbouring bins. Tweet theme: {event['theme']} "
        f"({event.get('theme_hits', 0)} matching emotion tweets, "
        f"{100 * float(event.get('theme_fraction') or 0):.1f}% of that emotion in the window). "
        "This describes an observed change in the sample, not a proven cause."
    )


def load_time_rows_for_plot(resolution: str) -> list[dict[str, Any]]:
    rows = []
    with TIME_CSV[resolution].open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rec = dict(r)
            rec["n_raw"] = int(float(r["n_raw"] or 0))
            for e in list(EKMAN) + ["others"]:
                rec[f"share_{e}"] = float(r.get(f"share_{e}") or 0)
                rec[f"n_{e}"] = int(float(r.get(f"n_{e}") or 0))
            rows.append(rec)
    return rows


def plot_single_corpus(
    resolution: str,
    corpus: str,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12.4, 4.6))
    fig.patch.set_facecolor("white")
    ymax_data = 0.0
    prefix = "share_"
    for emo in EKMAN:
        pts = []
        for r in rows:
            if r["corpus"] != corpus:
                continue
            dt = period_to_dt(resolution, r["period"])
            if dt is None:
                continue
            val = 100 * float(r[f"{prefix}{emo}"])
            pts.append((dt, val))
            ymax_data = max(ymax_data, val)
        pts.sort()
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=COLOR[emo], lw=1.7, label=emo)
        if corpus == "timeline":
            wpts = []
            for r in rows:
                if r["corpus"] != corpus:
                    continue
                dt = period_to_dt(resolution, r["period"])
                val = r.get(f"share_weighted_{emo}", "")
                if dt is None or val in ("", None):
                    continue
                wval = 100 * float(val)
                wpts.append((dt, wval))
                ymax_data = max(ymax_data, wval)
            wpts.sort()
            if wpts:
                ax.plot(
                    [p[0] for p in wpts],
                    [p[1] for p in wpts],
                    color=COLOR[emo],
                    lw=1.1,
                    ls=":",
                    label="_nolegend_",
                )
    ax.set_title(
        f"{resolution} — {corpus} Ekman shares (others omitted as event signal; dashed = selected events)",
        loc="left",
        fontsize=10,
    )
    ax.set_ylabel("Share %")
    ax.set_ylim(0, min(45.0, max(12.0, ymax_data * 1.35)))
    ax.grid(axis="y", alpha=0.3)
    ax.legend(frameon=False, ncol=6, fontsize=8)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    add_event_lines(
        ax,
        [e for e in events if not e.get("source") or e.get("source") == corpus],
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def build_docx(
    selected: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    ext: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    doc.add_heading("Detected events — IFB emotion corpus", level=0)
    p = doc.add_paragraph()
    p.add_run(
        "Events are statistically unusual bins in the six Ekman emotion shares, kept only when "
        "multiple distinct tweets in that window support a readable theme. "
        "No chatbot world-news list. Correlation is not causation."
    )

    doc.add_heading("Methodology and thresholds", level=1)
    doc.add_paragraph(
        "Inputs: emotion weekly and monthly CSVs from Phase 2.4; SQLite nlp_posts ⋈ post_emotion ⋈ "
        "post_sentiment; translation_status = not_required_english. Sentiment/emotion models were not rerun. IFB.db was not opened."
    )
    for k, v in PARAMS.items():
        doc.add_paragraph(f"{k} = {v}", style="List Bullet")
    doc.add_paragraph(
        "A bin is a statistical candidate if it is a local peak, n_raw and n_emotion meet minima, "
        "and rolling z-score of the emotion share (12 prior bins) exceeds the cut. "
        "`others` is never the detection signal. Nearby peaks of the same emotion/source are collapsed."
    )
    doc.add_paragraph(
        "Tweet-evidence gate: unique authors or unique normalised texts; one-author cap; drop "
        "empty/short/boilerplate. Themes are read off the tweets. External URLs are attached only "
        "when the tweets already name the phenomenon."
    )

    doc.add_heading("Selected events", level=1)
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(["ID", "Date/period", "Emotion", "Source", "z", "N window", "Theme"]):
        hdr[i].text = h
    for ev in selected:
        row = table.add_row().cells
        row[0].text = ev["event_id"]
        row[1].text = f"{ev['date']} ({ev['resolution']} {ev['period']})"
        row[2].text = ev["emotion"]
        row[3].text = ev["source"]
        row[4].text = str(ev["z_score"])
        row[5].text = str(ev["n_raw"])
        row[6].text = ev["theme"][:80]

    doc.add_heading("Counts", level=1)
    doc.add_paragraph(
        f"English-ready scored posts in NLP corpus: {stats['n_corpus']:,}. "
        f"Statistical candidates: {stats['n_stat']}. Rejected after stats or evidence: {stats['n_rejected']}. "
        f"Selected: {stats['n_selected']}. Evidence tweets: {stats['n_evidence']}."
    )

    fig_monthly = PLOT_DIR / "emotion_over_time_monthly.png"
    if fig_monthly.exists():
        doc.add_heading("Monthly Ekman series with event lines", level=1)
        doc.add_picture(str(fig_monthly), width=Inches(6.3))
        cap = doc.add_paragraph("Dashed vertical lines = selected events. Six Ekman emotions; others not used as the signal.")
        cap.italic = True

    fig_kw = PLOT_DIR / "emotion_over_time_monthly_keyword.png"
    fig_tl = PLOT_DIR / "emotion_over_time_monthly_timeline.png"
    if fig_kw.exists() and fig_tl.exists():
        doc.add_paragraph("Keyword vs timeline (monthly):")
        doc.add_picture(str(fig_kw), width=Inches(6.3))
        doc.add_picture(str(fig_tl), width=Inches(6.3))

    by_ev = defaultdict(list)
    for row in evidence:
        by_ev[row["event_id"]].append(row)
    ext_by = {e["event_id"]: e for e in ext}

    for ev in selected:
        doc.add_heading(f"{ev['event_id']}: {ev['emotion']} / {ev['source']} / {ev['period']}", level=1)
        doc.add_paragraph("Observed Twitter change").bold = False
        doc.add_paragraph(explain(ev))
        mix = ev
        doc.add_paragraph(
            f"Window sentiment: +{mix.get('pct_positive')}% / neu {mix.get('pct_neutral')}% / −{mix.get('pct_negative')}% "
            f"(n={mix.get('n_posts_window')})."
        )
        src = ext_by.get(ev["event_id"], {})
        doc.add_paragraph("Possible real-world explanation (not causation)")
        if src.get("paraphrase") == "no confirmed external explanation" or not src.get("url"):
            doc.add_paragraph("no confirmed external explanation")
        else:
            doc.add_paragraph(src.get("paraphrase", ""))
            doc.add_paragraph(f"Source: {src.get('title')} — {src.get('url')} ({src.get('publication_date')})")
        doc.add_paragraph("Tweet evidence")
        for tw in by_ev.get(ev["event_id"], []):
            para = doc.add_paragraph()
            para.add_run(
                f"{tw['created_at'][:10]} @{tw['username']} ({tw['source']}, {tw['sentiment_label']}, "
                f"{tw['emotion_label']} p={float(tw['emotion_probability']):.2f})\n"
            ).italic = True
            para.add_run((tw["original_text"] or "").replace("\n", " ")[:500])
            para.add_run(f"\n[tweet_id {tw['tweet_id']}]")

    doc.add_heading("Limitations and no-causation", level=1)
    for t in [
        "Timeline posts are a stratified sample (~1.7% of English timeline). Weighted shares estimate the English timeline population but rare weeks can still be noisy.",
        "Keyword posts have no native Twitter LANG; English-ready status is rule-based. IFB templates distort joy.",
        "No follower graph or conversation thread IDs exist in IFB.db, so we cannot show who amplified whom.",
        "Porter stemming / stopword cleaning used for emotion labels can miss lexical emotion cues.",
        "A peak coinciding with a calendar date or news topic is not evidence that the news caused the peak.",
        "Engagement (likes/replies/retweets) was not copied into nlp_posts; evidence ranking uses emotion probability and text quality only.",
    ]:
        doc.add_paragraph(t, style="List Bullet")

    doc.add_heading("Additional annotated figures", level=1)
    for name in [
        "emotion_over_time_weekly.png",
        "emotion_over_time_weekly_keyword.png",
        "emotion_over_time_weekly_timeline.png",
        "emotion_over_time_quarterly.png",
        "emotion_over_time_halfyearly.png",
        "emotion_over_time_yearly.png",
    ]:
        fp = PLOT_DIR / name
        if fp.exists():
            doc.add_picture(str(fp), width=Inches(6.3))
            doc.add_paragraph(fp.stem.replace("_", " "), style="Intense Quote")

    DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DOCX))
    log(f"Wrote {DOCX.name}")


def write_md(
    selected: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    cands: list[dict[str, Any]],
    stats: dict[str, Any],
    checklist: dict[str, bool],
) -> None:
    rej = Counter(c.get("reject_reason") or c.get("status") for c in cands if c.get("status") != "selected")
    lines = [
        "# Event detection",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "IFB.db was not opened. Sentiment and emotion scores were not recomputed.",
        "No chatbot news list. No causation claims.",
        "",
        "## Input row counts",
        "",
        f"| Item | N |",
        f"|------|--:|",
        f"| English-ready NLP posts with sentiment+emotion | **{stats['n_corpus']:,}** |",
        f"| Weekly series bins scanned (keyword+timeline × 6 emotions) | {stats['n_weekly_bins']:,} |",
        f"| Monthly series bins scanned | {stats['n_monthly_bins']:,} |",
        f"| Statistical candidates (`pass_stats` before evidence) | {stats['n_stat']:,} |",
        f"| Selected events | **{stats['n_selected']}** |",
        f"| Evidence tweets | **{stats['n_evidence']}** |",
        "",
        "## Detection parameters",
        "",
    ]
    for k, v in PARAMS.items():
        lines.append(f"- `{k}`: {v}")
    lines += [
        "",
        "## Candidate rejection criteria",
        "",
        "| Reason | N |",
        "|--------|--:|",
    ]
    for k, n in rej.most_common():
        lines.append(f"| {k} | {n} |")
    lines += [
        "",
        "## Selected events",
        "",
        "| ID | Date | Emotion | Source | z | Window N | Emotion N | Theme | Evidence tweets |",
        "|----|------|---------|--------|--:|--------:|----------:|-------|----------------:|",
    ]
    ev_n = Counter(e["event_id"] for e in evidence)
    for ev in selected:
        lines.append(
            f"| {ev['event_id']} | {ev['date']} | {ev['emotion']} | {ev['source']} | {ev['z_score']} | "
            f"{ev['n_raw']} | {ev['n_emotion']} | {ev['theme']} | {ev_n[ev['event_id']]} |"
        )
    lines += [
        "",
        "## Limitations",
        "",
        "- Sampled timeline (~1.7% of English timeline): weekly bins especially can spike from a handful of users.",
        "- Keyword language is rule-based, not Twitter LANG; IFB/follow templates contaminate joy and also pull in official 'follow SES advice' weather alerts.",
        "- No conversation IDs or follower graph in the released tables, so amplification paths cannot be shown.",
        "- Missing engagement fields on `nlp_posts` (likes/replies/retweets were not copied).",
        "- External pages are encyclopedic context only, attached when tweets already name the thing. Correlation is not causation.",
        "- `others` is the majority emotion class and was not used as a detection signal.",
        "",
        "## Output checklist",
        "",
        "| File | Present |",
        "|------|---------|",
    ]
    for k, ok in checklist.items():
        lines.append(f"| `{k}` | {'yes' if ok else 'NO'} |")
    lines += [
        "",
        "Every selected event has ≥1 tweet in `event_tweet_evidence.csv` that exists in SQLite. "
        "Plots include dashed labeled vertical lines. `others` was not used as the detection signal.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {REPORT.name}")


def main() -> int:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        n_corpus = conn.execute(
            """
            SELECT COUNT(*) FROM nlp_posts p
            JOIN post_sentiment s USING (source, tweet_id)
            JOIN post_emotion e USING (source, tweet_id)
            WHERE p.translation_status = ?
            """,
            (STATUS_FILTER,),
        ).fetchone()[0]
        date_min, date_max = conn.execute(
            "SELECT MIN(created_at), MAX(created_at) FROM nlp_posts WHERE translation_status=?",
            (STATUS_FILTER,),
        ).fetchone()
        log(f"Corpus n={n_corpus:,} dates {date_min} .. {date_max}")

        cands = detect_candidates()
        n_weekly = sum(1 for c in cands if c["resolution"] == "weekly")
        n_monthly = sum(1 for c in cands if c["resolution"] == "monthly")
        cands = merge_refractory(cands)
        n_stat = sum(1 for c in cands if c["status"] == "pass_stats")
        log(f"Candidates after stats+refractory: {n_stat}")

        reviewed = []
        for c in cands:
            if c["status"] != "pass_stats":
                continue
            start, end = window_bounds(c["resolution"], c["date"])
            posts = fetch_window_posts(conn, c["source"], start + "T00:00:00", end + "T00:00:00")
            q = evidence_quality(posts, c["emotion"])
            mix = sentiment_mix(posts)
            evid = rank_evidence(posts, c["emotion"], EVIDENCE_PER_EVENT)
            focused = [p for p in posts if p["emotion_label"] == c["emotion"]]
            theme, theme_hits, theme_frac, theme_pat = theme_from_tweets(focused)
            if theme != "no_coherent_named_theme":
                evid = rank_evidence(posts, c["emotion"], EVIDENCE_PER_EVENT, theme_pat)
                if len(evid) < 3:
                    q = dict(q)
                    q["ok"] = False
                    q["reasons"] = (q["reasons"] + ";" if q["reasons"] else "") + "too_few_theme_matching_tweets"
            item = dict(c)
            item.update(q)
            item.update(mix)
            item["n_posts_window"] = mix["n_posts"]
            item["theme"] = theme
            item["theme_hits"] = theme_hits
            item["theme_fraction"] = round(theme_frac, 4)
            item["theme_pat"] = theme_pat
            item["evidence_ok"] = q["ok"]
            item["window_start"] = start
            item["window_end"] = end
            item["_posts"] = evid
            if not q["ok"]:
                item["status"] = "rejected"
                item["reject_reason"] = q["reasons"] or "evidence_gate"
                c["status"] = "rejected"
                c["reject_reason"] = item["reject_reason"]
            elif theme == "no_coherent_named_theme":
                item["status"] = "rejected"
                item["reject_reason"] = "no_coherent_named_theme"
                c["status"] = "rejected"
                c["reject_reason"] = "no_coherent_named_theme"
            reviewed.append(item)
            c["theme"] = theme

        selected = select_events(cands, reviewed)
        for ev in selected:
            for c in cands:
                if (
                    c["date"] == ev["date"]
                    and c["source"] == ev["source"]
                    and c["emotion"] == ev["emotion"]
                    and c["resolution"] == ev["resolution"]
                ):
                    c["status"] = "selected"
                    c["reject_reason"] = ""
        for c in cands:
            if c["status"] == "pass_stats":
                c["status"] = "rejected"
                c["reject_reason"] = "outranked_themed_peak"
        log(f"Selected {len(selected)} events")

        evidence_rows = []
        ext_rows = []
        for ev in selected:
            start, end = ev["window_start"], ev["window_end"]
            if not (date_min <= start <= date_max or date_min <= end <= date_max):
                log(f"WARNING date outside corpus: {ev}")
            src = attach_external(ev["theme"], ev["date"])
            ev["external"] = src["paraphrase"]
            ev["why_selected"] = explain(ev)
            ext_rows.append(
                {
                    "event_id": ev["event_id"],
                    "observed_change": explain(ev),
                    "possible_explanation": src["paraphrase"],
                    "title": src["title"],
                    "url": src["url"],
                    "publication_date": src["publication_date"],
                    "causation_claimed": "no",
                }
            )
            for p in ev["_posts"]:
                evidence_rows.append(
                    {
                        "event_id": ev["event_id"],
                        "source": p["source"],
                        "tweet_id": p["tweet_id"],
                        "author_id": p["author_id"],
                        "username": p["username"],
                        "created_at": p["created_at"],
                        "original_text": p["original_text"],
                        "clean_text": p["clean_text"],
                        "sentiment_label": p["sentiment_label"],
                        "emotion_label": p["emotion_label"],
                        "emotion_probability": p[f"emotion_{ev['emotion']}"],
                        "likes": "",
                        "replies": "",
                        "retweets": "",
                        "engagement_note": "not stored on nlp_posts",
                    }
                )
        # ensure >= 20 evidence rows: top up from selected windows
        if len(evidence_rows) < MIN_EVIDENCE_TOTAL:
            for ev in selected:
                if len(evidence_rows) >= MIN_EVIDENCE_TOTAL:
                    break
                start, end = ev["window_start"], ev["window_end"]
                posts = fetch_window_posts(conn, ev["source"], start + "T00:00:00", end + "T00:00:00")
                extra = rank_evidence(posts, ev["emotion"], 12, ev.get("theme_pat") or None)
                have = {r["tweet_id"] for r in evidence_rows}
                for p in extra:
                    if p["tweet_id"] in have:
                        continue
                    evidence_rows.append(
                        {
                            "event_id": ev["event_id"],
                            "source": p["source"],
                            "tweet_id": p["tweet_id"],
                            "author_id": p["author_id"],
                            "username": p["username"],
                            "created_at": p["created_at"],
                            "original_text": p["original_text"],
                            "clean_text": p["clean_text"],
                            "sentiment_label": p["sentiment_label"],
                            "emotion_label": p["emotion_label"],
                            "emotion_probability": p[f"emotion_{ev['emotion']}"],
                            "likes": "",
                            "replies": "",
                            "retweets": "",
                            "engagement_note": "not stored on nlp_posts",
                        }
                    )
                    have.add(p["tweet_id"])
                    if len(evidence_rows) >= MIN_EVIDENCE_TOTAL:
                        break

        # validate evidence exists in SQLite
        for row in evidence_rows:
            hit = conn.execute(
                "SELECT 1 FROM nlp_posts WHERE source=? AND tweet_id=?",
                (row["source"], row["tweet_id"]),
            ).fetchone()
            if not hit:
                raise RuntimeError(f"evidence tweet missing: {row['source']} {row['tweet_id']}")
        dup = len(evidence_rows) - len({(r["source"], r["tweet_id"]) for r in evidence_rows})
        if dup:
            raise RuntimeError(f"duplicate evidence rows: {dup}")
        if selected and any(
            not any(e["event_id"] == ev["event_id"] for e in evidence_rows) for ev in selected
        ):
            raise RuntimeError("selected event without evidence")
    finally:
        conn.close()

    overlay = []
    for ev in selected:
        overlay.append(
            {
                "date": ev["date"],
                "name": f"{ev['event_id']} {ev['emotion']}",
                "short_name": f"{ev['event_id']} {ev['emotion']}",
                "color": EVENT_COLOR[ev["emotion"]],
                "source": ev["source"],
            }
        )
    EVENTS_JSON.write_text(json.dumps(overlay, indent=2), encoding="utf-8")

    # plots: all resolutions, combined + separate keyword/timeline
    for res in ("weekly", "biweekly", "monthly", "quarterly", "halfyearly", "yearly"):
        rows = load_time_rows_for_plot(res)
        plot_resolution(res, rows, overlay, EMOTION_PLOT_DIR / f"emotion_over_time_{res}.png")
        plot_resolution(res, rows, overlay, PLOT_DIR / f"emotion_over_time_{res}.png")
        plot_single_corpus(res, "keyword_tweets", rows, overlay, PLOT_DIR / f"emotion_over_time_{res}_keyword.png")
        plot_single_corpus(res, "timeline", rows, overlay, PLOT_DIR / f"emotion_over_time_{res}_timeline.png")

    event_fields = [
        "event_id",
        "date",
        "window_start",
        "window_end",
        "period",
        "resolution",
        "emotion",
        "source",
        "share",
        "share_weighted",
        "baseline_share",
        "z_score",
        "n_raw",
        "n_emotion",
        "n_posts_window",
        "n_positive",
        "n_neutral",
        "n_negative",
        "pct_positive",
        "pct_neutral",
        "pct_negative",
        "theme",
        "theme_hits",
        "theme_fraction",
        "why_selected",
        "external",
    ]
    write_csv(EVENTS_CSV, event_fields, selected)
    write_csv(
        CAND_CSV,
        [
            "candidate_id",
            "resolution",
            "source",
            "period",
            "date",
            "emotion",
            "n_raw",
            "n_emotion",
            "share",
            "share_weighted",
            "baseline_share",
            "z_score",
            "z_weighted",
            "status",
            "reject_reason",
            "series",
            "direction",
            "theme",
        ],
        cands,
    )
    write_csv(
        EVID_CSV,
        [
            "event_id",
            "source",
            "tweet_id",
            "author_id",
            "username",
            "created_at",
            "original_text",
            "clean_text",
            "sentiment_label",
            "emotion_label",
            "emotion_probability",
            "likes",
            "replies",
            "retweets",
            "engagement_note",
        ],
        evidence_rows,
    )
    write_csv(
        EXT_CSV,
        [
            "event_id",
            "observed_change",
            "possible_explanation",
            "title",
            "url",
            "publication_date",
            "causation_claimed",
        ],
        ext_rows,
    )
    stat_rows = [
        {"metric": "n_corpus", "value": n_corpus},
        {"metric": "n_selected", "value": len(selected)},
        {"metric": "n_evidence", "value": len(evidence_rows)},
        {"metric": "n_stat_candidates", "value": n_stat},
        {"metric": "n_candidates_total", "value": len(cands)},
        {"metric": "date_min", "value": date_min},
        {"metric": "date_max", "value": date_max},
    ]
    for ev in selected:
        stat_rows.append(
            {
                "metric": f"{ev['event_id']}_window_n",
                "value": ev["n_posts_window"],
            }
        )
    write_csv(STATS_CSV, ["metric", "value"], stat_rows)

    stats = {
        "n_corpus": n_corpus,
        "n_weekly_bins": n_weekly,
        "n_monthly_bins": n_monthly,
        "n_stat": n_stat,
        "n_rejected": sum(1 for c in cands if c["status"] != "selected" and c.get("reject_reason")),
        "n_selected": len(selected),
        "n_evidence": len(evidence_rows),
    }
    build_docx(selected, evidence_rows, ext_rows, stats)

    required = {
        "src/event_detection.py": (ROOT / "src" / "event_detection.py").exists(),
        "notebooks/event_detection.ipynb": (ROOT / "notebooks" / "event_detection.ipynb").exists(),
        "outputs/detected_events.csv": EVENTS_CSV.exists(),
        "outputs/event_tweet_evidence.csv": EVID_CSV.exists(),
        "outputs/event_statistics.csv": STATS_CSV.exists(),
        "outputs/event_external_sources.csv": EXT_CSV.exists(),
        "outputs/event_detection_candidates.csv": CAND_CSV.exists(),
        "outputs/detected_events.json": EVENTS_JSON.exists(),
        "detected_events.docx": DOCX.exists(),
        "EVENT_DETECTION_REPORT.md": True,
    }
    for res in ("weekly", "biweekly", "monthly", "quarterly", "halfyearly", "yearly"):
        required[f"event_plots/{res}"] = (PLOT_DIR / f"emotion_over_time_{res}.png").exists()
        required[f"event_plots/{res}_keyword"] = (PLOT_DIR / f"emotion_over_time_{res}_keyword.png").exists()
        required[f"event_plots/{res}_timeline"] = (PLOT_DIR / f"emotion_over_time_{res}_timeline.png").exists()
        required[f"emotion_plots/{res}_annotated"] = (EMOTION_PLOT_DIR / f"emotion_over_time_{res}.png").exists()
    write_md(selected, evidence_rows, cands, stats, required)

    log("========== EVENT DETECTION ==========")
    log(f"selected={len(selected)} evidence={len(evidence_rows)} candidates={len(cands)}")
    for ev in selected:
        log(f"  {ev['event_id']} {ev['date']} {ev['emotion']} {ev['source']} z={ev['z_score']} {ev['theme']}")
    log("EVENT_DETECTION_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
