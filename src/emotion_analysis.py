#!/usr/bin/env python3
"""Phase 2.4: PySentimiento English emotion on sentiment-scored NLP posts.

Uses data/nlp_analysis_corpus.db only. Does not open IFB.db.
Does not rerun sentiment. Does not invent events.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
PLOT_DIR = OUTPUT_DIR / "emotion_plots"
REPORT = ROOT / "EMOTION_ANALYSIS_REPORT.md"
EVENTS_JSON = OUTPUT_DIR / "detected_events.json"

POSTS_CSV = OUTPUT_DIR / "Posts_emotions.csv"
DIST_CSV = OUTPUT_DIR / "emotion_distribution.csv"
CROSSTAB_CSV = OUTPUT_DIR / "emotion_sentiment_crosstab.csv"
USER_CSV = OUTPUT_DIR / "user_emotion_summary.csv"

EXPECTED_N = 742_942
STATUS_FILTER = "not_required_english"
MODEL_NAME = "finiteautomata/bertweet-base-emotion-analysis"
PACKAGE = "pysentimiento"
TASK = "emotion"
LANG = "en"
CHUNK = 4_096
BATCH_SIZE = 128
EMPTY_PLACEHOLDER = "."

EMOTIONS = ("joy", "anger", "sadness", "fear", "surprise", "disgust", "others")
COLOR = {
    "joy": "#2ca02c",
    "anger": "#d62728",
    "sadness": "#1f77b4",
    "fear": "#9467bd",
    "surprise": "#ff7f0e",
    "disgust": "#8c564b",
    "others": "#7f7f7f",
}
GO_MAP = {
    "joy": "joy",
    "amusement": "joy",
    "excitement": "joy",
    "love": "joy",
    "admiration": "joy",
    "approval": "joy",
    "caring": "joy",
    "gratitude": "joy",
    "optimism": "joy",
    "pride": "joy",
    "relief": "joy",
    "anger": "anger",
    "annoyance": "anger",
    "disapproval": "anger",
    "sadness": "sadness",
    "disappointment": "sadness",
    "grief": "sadness",
    "remorse": "sadness",
    "fear": "fear",
    "nervousness": "fear",
    "surprise": "surprise",
    "realization": "surprise",
    "confusion": "surprise",
    "disgust": "disgust",
    "embarrassment": "disgust",
    "others": "others",
    "other": "others",
    "neutral": "others",
    "curiosity": "others",
    "desire": "others",
}

RESOLUTIONS = (
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "halfyearly",
    "yearly",
)
TIME_CSV = {
    "weekly": OUTPUT_DIR / "emotion_over_time_weekly.csv",
    "biweekly": OUTPUT_DIR / "emotion_over_time_biweekly.csv",
    "monthly": OUTPUT_DIR / "emotion_over_time_monthly.csv",
    "quarterly": OUTPUT_DIR / "emotion_over_time_quarterly.csv",
    "halfyearly": OUTPUT_DIR / "emotion_over_time_halfyearly.csv",
    "yearly": OUTPUT_DIR / "emotion_over_time_yearly.csv",
}
BIWEEK_ORIGIN = datetime(2007, 1, 1)


def log(msg: str) -> None:
    print(msg, flush=True)


def connect_nlp() -> sqlite3.Connection:
    if not NLP_DB.exists():
        raise FileNotFoundError(NLP_DB)
    conn = sqlite3.connect(str(NLP_DB), timeout=180)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    return conn


def ensure_table(conn: sqlite3.Connection) -> None:
    cols = ", ".join(f"emotion_{e} REAL NOT NULL" for e in EMOTIONS)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS post_emotion (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            emotion_label TEXT NOT NULL,
            {cols},
            input_was_empty_clean INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.commit()


def to_seven(probas: dict[str, Any]) -> dict[str, float]:
    keys = {str(k).lower(): float(v) for k, v in probas.items()}
    out = {e: 0.0 for e in EMOTIONS}
    if "others" not in keys:
        if "other" in keys:
            keys["others"] = keys["other"]
        elif "neutral" in keys and not any(k in keys for k in GO_MAP if GO_MAP[k] != "others" or k == "neutral"):
            keys["others"] = keys.get("neutral", 0.0)
    if all(e in keys for e in EMOTIONS):
        for e in EMOTIONS:
            out[e] = max(0.0, keys[e])
    else:
        for k, v in keys.items():
            out[GO_MAP.get(k, "others")] += max(0.0, v)
    total = sum(out.values())
    if total <= 0:
        out["others"] = 1.0
        return out
    if abs(total - 1.0) > 0.02:
        out = {k: v / total for k, v in out.items()}
    return out


class _Out:
    def __init__(self, output: str, probas: dict[str, float]) -> None:
        self.output = output
        self.probas = probas


class FastScorer:
    def __init__(self, analyzer: Any, batch_size: int) -> None:
        import torch
        from pysentimiento.preprocessing import preprocess_tweet

        self.torch = torch
        self.preprocess_tweet = preprocess_tweet
        self.preprocessing_args = analyzer.preprocessing_args
        self.tokenizer = analyzer.tokenizer
        self.model = analyzer.model
        self.model.eval()
        if torch.cuda.is_available():
            self.model.to("cuda")
        self.device = next(self.model.parameters()).device
        self.batch_size = batch_size
        self.id2label = {int(i): str(lab) for i, lab in analyzer.model.config.id2label.items()}
        nlab = int(getattr(analyzer.model.config, "num_labels", len(self.id2label)))
        ptype = str(getattr(analyzer.model.config, "problem_type", "") or "")
        self.multilabel = ptype == "multi_label_classification" or nlab > 7
        log(f"  labels={list(self.id2label.values())} multilabel={self.multilabel}")

    def predict(self, texts: list[str]) -> list[_Out]:
        torch = self.torch
        parts = []
        with torch.inference_mode():
            for i in range(0, len(texts), self.batch_size):
                chunk = [
                    self.preprocess_tweet(t, **self.preprocessing_args)
                    for t in texts[i : i + self.batch_size]
                ]
                enc = self.tokenizer(
                    chunk,
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                enc = {k: v.to(self.device, non_blocking=True) for k, v in enc.items()}
                logits = self.model(**enc).logits
                if self.multilabel:
                    parts.append(torch.sigmoid(logits).cpu())
                else:
                    parts.append(torch.softmax(logits, dim=1).cpu())
        probs = torch.cat(parts, dim=0)
        outs: list[_Out] = []
        for row in probs:
            raw = {self.id2label[i]: float(row[i]) for i in range(row.numel())}
            seven = to_seven(raw)
            outs.append(_Out(max(seven, key=seven.get), seven))
        return outs


def load_analyzer(batch_size: int):
    import pysentimiento
    from pysentimiento import create_analyzer

    log(f"Loading {PACKAGE} {getattr(pysentimiento, '__version__', '?')} {MODEL_NAME} ...")
    try:
        from datasets.utils.logging import disable_progress_bar

        disable_progress_bar()
    except Exception:
        pass
    analyzer = create_analyzer(task=TASK, lang=LANG, batch_size=batch_size, compile=False)
    try:
        import torch

        if torch.cuda.is_available():
            analyzer.model.to("cuda")
        log(f"  device={next(analyzer.model.parameters()).device} cuda={torch.cuda.is_available()}")
    except Exception as exc:
        log(f"  device move skipped: {exc}")
    name = getattr(analyzer.model.config, "_name_or_path", MODEL_NAME)
    log(f"  model={name}")
    return FastScorer(analyzer, batch_size), name


def eligible_sql() -> str:
    return """
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
    """


def score_remaining(conn: sqlite3.Connection, scorer: FastScorer) -> dict[str, Any]:
    n_target = conn.execute(
        "SELECT COUNT(*) " + eligible_sql(), (STATUS_FILTER,)
    ).fetchone()[0]
    n_done = conn.execute("SELECT COUNT(*) FROM post_emotion").fetchone()[0]
    log(f"Eligible sentiment-scored target={n_target:,} already_scored={n_done:,}")
    if n_target != EXPECTED_N:
        log(f"WARNING: expected {EXPECTED_N:,}, found {n_target:,}")

    cur = conn.execute(
        """
        SELECT p.source, p.tweet_id, p.clean_text
        """
        + eligible_sql()
        + """
          AND NOT EXISTS (
              SELECT 1 FROM post_emotion e
              WHERE e.source = p.source AND e.tweet_id = p.tweet_id
          )
        """,
        (STATUS_FILTER,),
    )
    t0 = time.perf_counter()
    n_new = 0
    n_empty = 0
    pending: list[tuple] = []
    texts: list[str] = []
    keys: list[tuple[str, str, int]] = []
    col_sql = ", ".join(f"emotion_{e}" for e in EMOTIONS)
    placeholders = ",".join("?" for _ in range(4 + len(EMOTIONS)))

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO post_emotion (
                source, tweet_id, emotion_label, {col_sql}, input_was_empty_clean
            ) VALUES ({placeholders})
            """,
            pending,
        )
        conn.commit()
        pending = []

    def run_batch() -> None:
        nonlocal n_new, n_empty, texts, keys, pending
        if not texts:
            return
        outputs = scorer.predict(texts)
        if len(outputs) != len(keys):
            raise RuntimeError(f"predict size {len(outputs)} != {len(keys)}")
        for (source, tweet_id, empty_flag), out in zip(keys, outputs):
            seven = to_seven(out.probas)
            label = max(seven, key=seven.get)
            pending.append(
                (source, tweet_id, label, *[seven[e] for e in EMOTIONS], empty_flag)
            )
            n_new += 1
            n_empty += empty_flag
        texts = []
        keys = []
        if len(pending) >= CHUNK:
            flush()

    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        for source, tweet_id, clean in rows:
            empty_flag = int(clean is None or str(clean).strip() == "")
            texts.append(EMPTY_PLACEHOLDER if empty_flag else str(clean))
            keys.append((source, tweet_id, empty_flag))
            if len(texts) >= CHUNK:
                run_batch()
                elapsed = time.perf_counter() - t0
                rate = n_new / elapsed if elapsed else 0
                left = n_target - n_done - n_new
                eta = left / rate if rate else 0
                log(
                    f"  scored {n_done + n_new:,}/{n_target:,} "
                    f"({rate:.1f} rows/s, eta {eta/60:.1f} min)"
                )
        run_batch()
        flush()
    run_batch()
    flush()
    elapsed = time.perf_counter() - t0
    log(f"Inference new={n_new:,} empty_clean_input={n_empty:,} in {elapsed:.1f}s")
    return {"n_new": n_new, "n_empty_new": n_empty, "seconds": elapsed, "n_target": n_target}


def validate(conn: sqlite3.Connection) -> dict[str, Any]:
    n_target = conn.execute("SELECT COUNT(*) " + eligible_sql(), (STATUS_FILTER,)).fetchone()[0]
    n_scored = conn.execute("SELECT COUNT(*) FROM post_emotion").fetchone()[0]
    n_join = conn.execute(
        """
        SELECT COUNT(*)
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_dup = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT source, tweet_id FROM post_emotion
            GROUP BY source, tweet_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    allowed = "', '".join(EMOTIONS)
    n_bad_label = conn.execute(
        f"SELECT COUNT(*) FROM post_emotion WHERE emotion_label NOT IN ('{allowed}') OR emotion_label IS NULL"
    ).fetchone()[0]
    prob_checks = " OR ".join(
        f"emotion_{e} < 0 OR emotion_{e} > 1" for e in EMOTIONS
    )
    sum_expr = "+".join(f"emotion_{e}" for e in EMOTIONS)
    n_bad_prob = conn.execute(
        f"SELECT COUNT(*) FROM post_emotion WHERE {prob_checks} OR abs(({sum_expr})-1) > 0.02"
    ).fetchone()[0]
    labels = {
        r[0]: r[1]
        for r in conn.execute("SELECT emotion_label, COUNT(*) FROM post_emotion GROUP BY 1")
    }
    mass = {
        e: conn.execute(f"SELECT SUM(emotion_{e}) FROM post_emotion").fetchone()[0] or 0.0
        for e in EMOTIONS
    }
    n_users = conn.execute(
        """
        SELECT COUNT(DISTINCT p.author_id)
        FROM nlp_posts p
        JOIN post_emotion e USING (source, tweet_id)
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_empty = conn.execute("SELECT SUM(input_was_empty_clean) FROM post_emotion").fetchone()[0] or 0
    extra = conn.execute(
        """
        SELECT COUNT(*) FROM post_emotion e
        WHERE NOT EXISTS (
            SELECT 1 FROM nlp_posts p
            JOIN post_sentiment s USING (source, tweet_id)
            WHERE p.source=e.source AND p.tweet_id=e.tweet_id
              AND p.translation_status=?
        )
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    mass_ok = all(v > 0 for v in mass.values())
    ok = (
        n_target == n_scored == n_join == EXPECTED_N
        and n_dup == 0
        and n_bad_label == 0
        and n_bad_prob == 0
        and extra == 0
        and set(labels).issubset(set(EMOTIONS))
        and mass_ok
        and len(labels) >= 1
    )
    summary = {
        "ok": ok,
        "n_target": n_target,
        "n_scored": n_scored,
        "n_join": n_join,
        "n_dup": n_dup,
        "n_bad_label": n_bad_label,
        "n_bad_prob": n_bad_prob,
        "n_extra": extra,
        "n_users": n_users,
        "n_empty_clean": int(n_empty),
        "labels": labels,
        "prob_mass": {k: round(float(v), 2) for k, v in mass.items()},
        "all_seven_argmax": set(EMOTIONS) <= set(labels),
    }
    log(f"VALIDATION {'PASS' if ok else 'FAIL'}: {summary}")
    if not ok:
        raise RuntimeError(f"emotion validation failed: {summary}")
    return summary


def fetch_replacement_docs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT q.source, q.tweet_id, p.translation_status,
               CASE WHEN e.tweet_id IS NULL THEN 0 ELSE 1 END AS scored
        FROM translation_quality q
        LEFT JOIN nlp_posts p USING (source, tweet_id)
        LEFT JOIN post_emotion e USING (source, tweet_id)
        WHERE q.has_replacement = 1
        ORDER BY q.source, q.tweet_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def parse_dt(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None


def period_keys(dt: datetime) -> dict[str, str]:
    monday = dt - timedelta(days=dt.weekday())
    monday = datetime(monday.year, monday.month, monday.day)
    delta_days = (monday - BIWEEK_ORIGIN).days
    bi = monday - timedelta(days=delta_days % 14)
    q = (dt.month - 1) // 3 + 1
    h = 1 if dt.month <= 6 else 2
    return {
        "weekly": monday.strftime("%Y-%m-%d"),
        "biweekly": bi.strftime("%Y-%m-%d"),
        "monthly": dt.strftime("%Y-%m"),
        "quarterly": f"{dt.year}Q{q}",
        "halfyearly": f"{dt.year}H{h}",
        "yearly": str(dt.year),
    }


def period_to_dt(resolution: str, key: str) -> datetime | None:
    try:
        if resolution in {"weekly", "biweekly"}:
            return datetime.strptime(key, "%Y-%m-%d")
        if resolution == "monthly":
            return datetime.strptime(key + "-01", "%Y-%m-%d")
        if resolution == "quarterly":
            y, q = key.split("Q")
            return datetime(int(y), (int(q) - 1) * 3 + 1, 1)
        if resolution == "halfyearly":
            y, h = key.split("H")
            return datetime(int(y), 1 if h == "1" else 7, 1)
        if resolution == "yearly":
            return datetime(int(key), 1, 1)
    except (ValueError, TypeError):
        return None
    return None


def load_event_lines(path: Path = EVENTS_JSON) -> list[dict[str, Any]]:
    """Overlay spec for later Event Detection. Empty until that phase writes the file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [ev for ev in data if isinstance(ev, dict) and ev.get("date") and ev.get("name")]


def add_event_lines(ax: Any, events: list[dict[str, Any]] | None = None) -> None:
    """Dashed vertical named event lines. No-op if the event list is empty."""
    events = load_event_lines() if events is None else events
    if not events:
        return
    ymin, ymax = ax.get_ylim()
    shown = []
    for i, ev in enumerate(events):
        when = parse_dt(str(ev["date"])) or period_to_dt("monthly", str(ev["date"])[:7])
        if when is None:
            continue
        color = ev.get("color") or "#222222"
        ax.axvline(when, color=color, linestyle="--", linewidth=1.2, zorder=5)
        # stagger labels so overlapping dates stay readable
        height = ymax - 4 - (i % 4) * (ymax * 0.08)
        ax.text(
            when,
            max(ymin + 2, height),
            str(ev.get("short_name") or ev.get("name") or ""),
            rotation=90,
            va="top",
            ha="right",
            fontsize=7,
            color=color,
            clip_on=True,
        )
        shown.append(when)
    _ = shown


def write_csv_utf8_bom(path: Path, fieldnames: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def distribution_and_crosstab(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    raw = conn.execute(
        """
        SELECT p.source, e.emotion_label, s.sentiment_label,
               COUNT(*) AS n_raw, SUM(p.sample_weight) AS n_weighted
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.translation_status = ?
        GROUP BY p.source, e.emotion_label, s.sentiment_label
        """,
        (STATUS_FILTER,),
    ).fetchall()
    dist_parts: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"n_raw": 0, "n_weighted": 0.0}))
    cross: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {"n_raw": 0, "n_weighted": 0.0})
    for r in raw:
        dist_parts[r["source"]][r["emotion_label"]]["n_raw"] += r["n_raw"]
        dist_parts[r["source"]][r["emotion_label"]]["n_weighted"] += float(r["n_weighted"] or 0)
        cross[(r["source"], r["sentiment_label"], r["emotion_label"])]["n_raw"] += r["n_raw"]
        cross[(r["source"], r["sentiment_label"], r["emotion_label"])]["n_weighted"] += float(r["n_weighted"] or 0)

    def pack_dist(name: str, parts: dict[str, dict[str, float]], weighted: bool, notes: str) -> list[dict[str, Any]]:
        tot_raw = sum(v["n_raw"] for v in parts.values()) or 1
        tot_w = sum(v["n_weighted"] for v in parts.values()) or 1.0
        rows = []
        for lab in EMOTIONS:
            d = parts.get(lab, {"n_raw": 0, "n_weighted": 0.0})
            rows.append(
                {
                    "corpus": name,
                    "emotion_label": lab,
                    "n_raw": int(d["n_raw"]),
                    "share_raw": round(d["n_raw"] / tot_raw, 6),
                    "n_weighted": round(d["n_weighted"], 4) if weighted else "",
                    "share_weighted": round(d["n_weighted"] / tot_w, 6) if weighted else "",
                    "notes": notes,
                }
            )
        return rows

    kw = dist_parts.get("keyword_tweets", {})
    tl = dist_parts.get("timeline", {})
    combined: dict[str, dict[str, float]] = {
        lab: {
            "n_raw": kw.get(lab, {}).get("n_raw", 0) + tl.get(lab, {}).get("n_raw", 0),
            "n_weighted": kw.get(lab, {}).get("n_weighted", 0) + tl.get(lab, {}).get("n_weighted", 0),
        }
        for lab in EMOTIONS
    }
    dist_rows = []
    dist_rows += pack_dist("keyword_tweets", kw, False, "census; sample_weight=1")
    dist_rows += pack_dist("timeline_raw", tl, False, "unweighted sample rows")
    dist_rows += pack_dist("timeline_weighted", tl, True, "Horvitz-Thompson English timeline")
    dist_rows += pack_dist("combined_unweighted", combined, False, "mixed sampling frames; not one population")

    sentiments = ("positive", "neutral", "negative")
    cross_rows = []
    corpora_cross = {
        "keyword_tweets": [k for k in cross if k[0] == "keyword_tweets"],
        "timeline": [k for k in cross if k[0] == "timeline"],
        "combined_unweighted": list(cross),
    }
    for corpus, keys in corpora_cross.items():
        sent_tot: dict[str, float] = defaultdict(float)
        sent_w: dict[str, float] = defaultdict(float)
        cells: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"n_raw": 0, "n_weighted": 0.0})
        for src, sent, emo in keys:
            d = cross[(src, sent, emo)]
            cells[(sent, emo)]["n_raw"] += d["n_raw"]
            cells[(sent, emo)]["n_weighted"] += d["n_weighted"]
            sent_tot[sent] += d["n_raw"]
            sent_w[sent] += d["n_weighted"]
        weighted = corpus == "timeline"
        for sent in sentiments:
            for emo in EMOTIONS:
                d = cells.get((sent, emo), {"n_raw": 0, "n_weighted": 0.0})
                den = sent_tot[sent] or 1
                wden = sent_w[sent] or 1.0
                cross_rows.append(
                    {
                        "corpus": corpus if corpus != "timeline" else "timeline_raw",
                        "sentiment_label": sent,
                        "emotion_label": emo,
                        "n_raw": int(d["n_raw"]),
                        "row_share_raw": round(d["n_raw"] / den, 6),
                        "n_weighted": round(d["n_weighted"], 4) if weighted else "",
                        "row_share_weighted": round(d["n_weighted"] / wden, 6) if weighted else "",
                        "notes": "row shares are P(emotion | sentiment)",
                    }
                )
        if corpus == "timeline":
            for sent in sentiments:
                for emo in EMOTIONS:
                    d = cells.get((sent, emo), {"n_raw": 0, "n_weighted": 0.0})
                    wden = sent_w[sent] or 1.0
                    den = sent_tot[sent] or 1
                    cross_rows.append(
                        {
                            "corpus": "timeline_weighted",
                            "sentiment_label": sent,
                            "emotion_label": emo,
                            "n_raw": int(d["n_raw"]),
                            "row_share_raw": round(d["n_raw"] / den, 6),
                            "n_weighted": round(d["n_weighted"], 4),
                            "row_share_weighted": round(d["n_weighted"] / wden, 6),
                            "notes": "weighted P(emotion | sentiment) for English timeline",
                        }
                    )
    return dist_rows, cross_rows


def time_rows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    cur = conn.execute(
        """
        SELECT p.source, p.created_at, p.sample_weight, e.emotion_label
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    )
    # (resolution, corpus, period, emotion) -> [n_raw, n_weighted]
    bucket: dict[tuple[str, str, str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    skipped = 0
    n = 0
    while True:
        chunk = cur.fetchmany(20_000)
        if not chunk:
            break
        for source, created_at, weight, emo in chunk:
            n += 1
            dt = parse_dt(created_at)
            if dt is None or emo not in EMOTIONS:
                skipped += 1
                continue
            w = float(weight or 0)
            keys = period_keys(dt)
            for res, period in keys.items():
                bucket[(res, source, period, emo)][0] += 1
                bucket[(res, source, period, emo)][1] += w
    log(f"Time aggregation scanned={n:,} skipped_dates={skipped:,}")

    out: dict[str, list[dict[str, Any]]] = {res: [] for res in RESOLUTIONS}
    grouped: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(dict)
    for (res, source, period, emo), vals in bucket.items():
        grouped[(res, source, period)][emo] = vals
        grouped[(res, "combined_unweighted", period)][emo] = [
            grouped[(res, "combined_unweighted", period)].get(emo, [0.0, 0.0])[0] + vals[0],
            grouped[(res, "combined_unweighted", period)].get(emo, [0.0, 0.0])[1] + vals[1],
        ]

    for (res, source, period), labs in grouped.items():
        tot_raw = sum(v[0] for v in labs.values()) or 1.0
        tot_w = sum(v[1] for v in labs.values()) or 1.0
        weighted = source == "timeline"
        rec = {
            "corpus": source,
            "period": period,
            "n_raw": int(tot_raw),
            "n_weighted": round(tot_w, 4) if weighted else "",
            "notes": (
                "census"
                if source == "keyword_tweets"
                else "timeline sample; weighted cols estimate English timeline"
                if source == "timeline"
                else "mixed keyword census + timeline sample; not a population"
            ),
        }
        for emo in EMOTIONS:
            n_raw, n_w = labs.get(emo, [0.0, 0.0])
            rec[f"n_{emo}"] = int(n_raw)
            rec[f"share_{emo}"] = round(n_raw / tot_raw, 6)
            if weighted:
                rec[f"n_weighted_{emo}"] = round(n_w, 4)
                rec[f"share_weighted_{emo}"] = round(n_w / tot_w, 6)
            else:
                rec[f"n_weighted_{emo}"] = ""
                rec[f"share_weighted_{emo}"] = ""
        out[res].append(rec)
    for res in RESOLUTIONS:
        out[res].sort(key=lambda r: (r["corpus"], r["period"]))
    return out


def user_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    sums = ", ".join(
        f"SUM(CASE WHEN e.emotion_label='{e}' THEN 1 ELSE 0 END) AS n_{e}" for e in EMOTIONS
    )
    cur = conn.execute(
        f"""
        SELECT p.author_id, MAX(p.username) AS username, COUNT(*) AS n_posts,
               SUM(CASE WHEN p.source='keyword_tweets' THEN 1 ELSE 0 END) AS n_keyword,
               SUM(CASE WHEN p.source='timeline' THEN 1 ELSE 0 END) AS n_timeline,
               {sums}
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.translation_status = ?
        GROUP BY p.author_id
        """,
        (STATUS_FILTER,),
    )
    rows = []
    for r in cur:
        n = r["n_posts"] or 1
        rec = {
            "author_id": r["author_id"],
            "username": r["username"] or "",
            "n_posts": r["n_posts"],
            "n_keyword": r["n_keyword"],
            "n_timeline": r["n_timeline"],
        }
        best = "others"
        best_n = -1
        for e in EMOTIONS:
            rec[f"n_{e}"] = r[f"n_{e}"]
            rec[f"pct_{e}"] = round(100.0 * r[f"n_{e}"] / n, 4)
            if r[f"n_{e}"] > best_n:
                best, best_n = e, r[f"n_{e}"]
        rec["plurality_emotion"] = best
        rows.append(rec)
    return rows


def export_posts_csv(conn: sqlite3.Connection) -> int:
    fields = [
        "source",
        "tweet_id",
        "author_id",
        "username",
        "created_at",
        "lang",
        "original_text",
        "clean_text",
        "topic_text",
        "sample_weight",
        "translation_status",
        "sentiment_label",
        "sentiment_positive",
        "sentiment_neutral",
        "sentiment_negative",
        "emotion_label",
        *[f"emotion_{e}" for e in EMOTIONS],
    ]
    emo_cols = ", ".join(f"e.emotion_{e}" for e in EMOTIONS)
    cur = conn.execute(
        f"""
        SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at, p.lang,
               p.original_text, p.clean_text, p.topic_text, p.sample_weight,
               p.translation_status,
               s.sentiment_label, s.sentiment_positive, s.sentiment_neutral, s.sentiment_negative,
               e.emotion_label, {emo_cols}
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_emotion e USING (source, tweet_id)
        WHERE p.translation_status = ?
        ORDER BY p.source, p.created_at, p.tweet_id
        """,
        (STATUS_FILTER,),
    )
    n = 0
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with POSTS_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        while True:
            chunk = cur.fetchmany(4_000)
            if not chunk:
                break
            for r in chunk:
                w.writerow({k: r[k] for k in fields})
                n += 1
    log(f"Wrote {POSTS_CSV.name} n={n:,}")
    return n


def plot_distribution(dist: list[dict[str, Any]]) -> None:
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    fig.patch.set_facecolor("white")
    corpora = [
        ("keyword_tweets", "Keyword census", 0.95, None),
        ("timeline_raw", "Timeline raw", 0.75, "///"),
        ("combined_unweighted", "Combined (mixed)", 0.55, "..."),
    ]
    x = list(range(len(EMOTIONS)))
    width = 0.26
    for i, (corpus, title, alpha, hatch) in enumerate(corpora):
        subset = {r["emotion_label"]: r for r in dist if r["corpus"] == corpus}
        shares = [100 * float(subset.get(e, {}).get("share_raw", 0) or 0) for e in EMOTIONS]
        ax.bar(
            [xi + (i - 1) * width for xi in x],
            shares,
            width=width,
            color=[COLOR[e] for e in EMOTIONS],
            edgecolor="#333333",
            linewidth=0.4,
            alpha=alpha,
            hatch=hatch,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(EMOTIONS)
    ax.set_ylabel("Share of posts (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Emotion label shares — seven classes, not one mixed score")
    ax.legend(
        handles=[
            Patch(facecolor="#bbbbbb", edgecolor="#333333", label="Keyword census"),
            Patch(facecolor="#bbbbbb", edgecolor="#333333", hatch="///", label="Timeline raw"),
            Patch(facecolor="#bbbbbb", edgecolor="#333333", hatch="...", label="Combined (mixed)"),
        ],
        frameon=False,
    )
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / "emotion_distribution.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_crosstab(cross: list[dict[str, Any]]) -> None:
    subset = [r for r in cross if r["corpus"] == "combined_unweighted"]
    sentiments = ["positive", "neutral", "negative"]
    mat = []
    for sent in sentiments:
        mat.append(
            [
                100
                * float(
                    next(
                        (r["row_share_raw"] for r in subset if r["sentiment_label"] == sent and r["emotion_label"] == e),
                        0,
                    )
                    or 0
                )
                for e in EMOTIONS
            ]
        )
    fig, ax = plt.subplots(figsize=(10.2, 3.8))
    fig.patch.set_facecolor("white")
    im = ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(EMOTIONS)))
    ax.set_xticklabels(EMOTIONS)
    ax.set_yticks(range(3))
    ax.set_yticklabels(sentiments)
    for i in range(3):
        for j in range(len(EMOTIONS)):
            ax.text(j, i, f"{mat[i][j]:.1f}%", ha="center", va="center", fontsize=8)
    ax.set_title("P(emotion | sentiment) — combined file, unweighted")
    fig.colorbar(im, ax=ax, fraction=0.03, label="%")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "emotion_sentiment_crosstab.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_resolution(
    resolution: str,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    outfile: Path | None = None,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12.6, 8.6), sharex=False)
    fig.patch.set_facecolor("white")
    panels = [
        ("keyword_tweets", "Keyword census (raw = weighted)", "share_"),
        ("timeline", "Timeline sample — solid raw, dotted weighted", "share_"),
    ]
    for ax, (corpus, title, prefix) in zip(axes, panels):
        for emo in EMOTIONS:
            pts = []
            wpts = []
            for r in rows:
                if r["corpus"] != corpus:
                    continue
                dt = period_to_dt(resolution, r["period"])
                if dt is None:
                    continue
                pts.append((dt, 100 * float(r[f"{prefix}{emo}"])))
                if corpus == "timeline":
                    val = r.get(f"share_weighted_{emo}", "")
                    if val != "" and val is not None:
                        wpts.append((dt, 100 * float(val)))
            pts.sort()
            if pts:
                ax.plot(
                    [p[0] for p in pts],
                    [p[1] for p in pts],
                    color=COLOR[emo],
                    lw=1.6,
                    label=emo,
                )
            if wpts:
                wpts.sort()
                ax.plot(
                    [p[0] for p in wpts],
                    [p[1] for p in wpts],
                    color=COLOR[emo],
                    lw=1.2,
                    ls=":",
                    label="_nolegend_",
                )
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_ylabel("Share %")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(frameon=False, ncol=7, fontsize=8, loc="upper right")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        add_event_lines(
            ax,
            [e for e in events if not e.get("source") or e.get("source") == corpus],
        )
    axes[-1].set_xlabel("Year")
    event_note = (
        "Dashed vertical lines mark selected emotion events (correlation, not causation)."
        if events
        else "Dashed vertical event lines will be added after Event Detection (none claimed now)."
    )
    fig.suptitle(
        f"Emotion shares by {resolution} — seven separate series, no mixed emotion score\n"
        + event_note,
        fontsize=12,
    )
    fig.tight_layout()
    dest = outfile or (PLOT_DIR / f"emotion_over_time_{resolution}.png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=160, bbox_inches="tight")
    plt.close(fig)
    log(f"Wrote {dest.name}")


def time_csv_fields() -> list[str]:
    fields = ["corpus", "period", "n_raw", "n_weighted"]
    for e in EMOTIONS:
        fields += [f"n_{e}", f"share_{e}", f"n_weighted_{e}", f"share_weighted_{e}"]
    fields.append("notes")
    return fields


def write_report(
    val: dict[str, Any],
    dist: list[dict[str, Any]],
    cross: list[dict[str, Any]],
    users: list[dict[str, Any]],
    repl: list[dict[str, Any]],
    model_name: str,
    inf: dict[str, Any],
    n_events: int,
) -> None:
    def grab(corpus: str) -> dict[str, dict[str, Any]]:
        return {r["emotion_label"]: r for r in dist if r["corpus"] == corpus}

    kw, tl_raw, tl_w, comb = (
        grab("keyword_tweets"),
        grab("timeline_raw"),
        grab("timeline_weighted"),
        grab("combined_unweighted"),
    )
    n = val["n_scored"]
    n_users = val["n_users"]
    n_kw = sum(int(kw[e]["n_raw"]) for e in EMOTIONS if e in kw)
    n_tl = sum(int(tl_raw[e]["n_raw"]) for e in EMOTIONS if e in tl_raw)

    def block_table(block: dict[str, dict[str, Any]], weighted: bool) -> str:
        lines = ["| Emotion | Count / estimate | Share |", "|---------|------------------:|------:|"]
        for e in EMOTIONS:
            r = block.get(e, {"n_raw": 0, "share_raw": 0, "n_weighted": 0, "share_weighted": 0})
            if weighted:
                lines.append(
                    f"| {e} | {float(r.get('n_weighted') or 0):,.1f} | {100*float(r.get('share_weighted') or 0):.2f}% |"
                )
            else:
                lines.append(
                    f"| {e} | {int(r.get('n_raw') or 0):,} | {100*float(r.get('share_raw') or 0):.2f}% |"
                )
        return "\n".join(lines)

    maj = Counter(u["plurality_emotion"] for u in users)
    mean_posts = (sum(u["n_posts"] for u in users) / len(users)) if users else 0

    # combined crosstab highlights
    comb_cross = [r for r in cross if r["corpus"] == "combined_unweighted"]

    def cell(sent: str, emo: str) -> str:
        r = next((x for x in comb_cross if x["sentiment_label"] == sent and x["emotion_label"] == emo), None)
        if not r:
            return "n/a"
        return f"{int(r['n_raw']):,} ({100*float(r['row_share_raw']):.1f}%)"

    repl_lines = "\n".join(
        f"| `{r['source']}` | `{r['tweet_id']}` | {r['translation_status']} | "
        f"{'yes' if r['scored'] else 'no (held out)'} |"
        for r in repl
    ) or "| — | — | — | none |"

    missing_argmax = [e for e in EMOTIONS if e not in val["labels"]]
    argmax_note = (
        "All seven labels appear as argmax at least once."
        if not missing_argmax
        else f"Argmax never chose: {', '.join(missing_argmax)} (probability mass still present in columns)."
    )

    text = f"""# Emotion analysis

Built: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Package: **{PACKAGE}** (`create_analyzer(task="{TASK}", lang="{LANG}")`)
Model: **{model_name}**
Input: **`clean_text`**. Empty `clean_text` ({val['n_empty_clean']:,} posts) scored as `"{EMPTY_PLACEHOLDER}"`.
Universe: `translation_status = not_required_english` ⋈ `post_sentiment` (**{n:,}** posts). Sentiment was **not** rerun.
`IFB.db` was not opened. Original text was not rewritten.
Sample weights were **not** used for scoring. They are used only for timeline population estimates.

## Events (not this phase)

**No events are claimed here.** Peak dates on the emotion series are descriptive only. Event Detection will read tweet evidence, then write `outputs/detected_events.json`. Plotting already calls `add_event_lines()` on every time-resolution figure (dashed vertical line + name). Until that file exists, overlays are empty. Event lines = {n_events} loaded this run.

## Processed volume

| Item | N |
|------|--:|
| Posts scored | **{n:,}** |
| Users | **{n_users:,}** |
| Keyword | {n_kw:,} |
| Timeline | {n_tl:,} |
| Empty `clean_text` placeholder | {val['n_empty_clean']:,} |
| Duplicate `(source, tweet_id)` | {val['n_dup']} |
| Validation | **{"PASS" if val["ok"] else "FAIL"}** |

{argmax_note}

Every row has `emotion_label` ∈ {{{", ".join(EMOTIONS)}}} and seven probabilities in [0, 1] that sum to ~1. There is **no** single mixed “emotion score.”

## Distribution of every emotion

### Combined file (unweighted mix — not a population)

{block_table(comb, False)}

### Keyword census

{block_table(kw, False)}

### Timeline raw sample

{block_table(tl_raw, False)}

### Timeline weighted (English timeline population)

{block_table(tl_w, True)}

`others` is large because Porter-stemmed, stopword-stripped IFB talk is often not a clear Ekman emotion. That is a limitation, not a reason to collapse the six other series.

## Time resolutions

Numeric series (raw counts/shares and timeline weighted estimates) are saved for **all** of:

| Resolution | CSV | PNG |
|------------|-----|-----|
| weekly (Monday start) | `outputs/emotion_over_time_weekly.csv` | `outputs/emotion_plots/emotion_over_time_weekly.png` |
| biweekly (14-day bins from 2007-01-01) | `outputs/emotion_over_time_biweekly.csv` | `outputs/emotion_plots/emotion_over_time_biweekly.png` |
| monthly | `outputs/emotion_over_time_monthly.csv` | `outputs/emotion_plots/emotion_over_time_monthly.png` |
| quarterly | `outputs/emotion_over_time_quarterly.csv` | `outputs/emotion_plots/emotion_over_time_quarterly.png` |
| half-yearly | `outputs/emotion_over_time_halfyearly.csv` | `outputs/emotion_plots/emotion_over_time_halfyearly.png` |
| yearly | `outputs/emotion_over_time_yearly.csv` | `outputs/emotion_plots/emotion_over_time_yearly.png` |

Each PNG has two panels (keyword census; timeline raw + dotted weighted) and **seven separate lines**. Dashed event lines are wired but unused until Event Detection.

## Sentiment–emotion relationship

Row shares are P(emotion | sentiment) on the combined unweighted file:

| Sentiment \\ Emotion | joy | anger | sadness | fear | surprise | disgust | others |
|---------------------|-----|-------|---------|------|----------|---------|--------|
| positive | {cell('positive','joy')} | {cell('positive','anger')} | {cell('positive','sadness')} | {cell('positive','fear')} | {cell('positive','surprise')} | {cell('positive','disgust')} | {cell('positive','others')} |
| neutral | {cell('neutral','joy')} | {cell('neutral','anger')} | {cell('neutral','sadness')} | {cell('neutral','fear')} | {cell('neutral','surprise')} | {cell('neutral','disgust')} | {cell('neutral','others')} |
| negative | {cell('negative','joy')} | {cell('negative','anger')} | {cell('negative','sadness')} | {cell('negative','fear')} | {cell('negative','surprise')} | {cell('negative','disgust')} | {cell('negative','others')} |

Full tables including timeline weighted: `outputs/emotion_sentiment_crosstab.csv`. Heatmap: `outputs/emotion_plots/emotion_sentiment_crosstab.png`.

Positive sentiment should load on **joy** more than anger/sadness; negative on anger/sadness/fear/disgust. Residual mass in `others` is expected with stemmed IFB templates.

## Per-user emotion summary

`outputs/user_emotion_summary.csv` — **{len(users):,}** users, mean {mean_posts:.1f} scored posts.

| Plurality emotion | Users | Share |
|-------------------|------:|------:|
"""
    for e in EMOTIONS:
        text += f"| {e} | {maj.get(e, 0):,} | {100.0 * maj.get(e, 0) / (len(users) or 1):.2f}% |\n"
    text += f"""
Percentages are within-user raw counts. Timeline weights are not applied at user level.

## Replacement-character records

Five U+FFFD posts. **Original text was not repaired.** They remain `uncertain` and are **not** in `post_emotion`.

| source | tweet_id | translation_status | scored? |
|--------|----------|--------------------|---------|
{repl_lines}

## Limitations

1. **Porter stemming + English stopword removal** on `clean_text` strip many emotion cues (“happy”, “angry” may be stemmed; function words gone). This inflates `others` and flattens the six Ekman series.
2. **Language filter.** Only `not_required_english` ∩ sentiment-scored rows. Latin-script Portuguese/French can still be in the set; the English emotion head may mis-label them.
3. **Sampling.** Keyword = eligible census (promotional IFB talk). Timeline = stratified ~1.7% of English timeline; use `sample_weight` only for population shares, never for scoring.
4. **Combined plots/tables mix two frames** and are not a population parameter.
5. **Empty clean_text** ({val['n_empty_clean']:,}) used a placeholder period.
6. **No events yet.** Do not treat monthly wiggles as world events without tweet evidence.

## Files

- `src/emotion_analysis.py` — GPU batches, SQLite checkpoint `post_emotion`, `add_event_lines()`
- `notebooks/emotion_analysis.ipynb`
- `data/nlp_analysis_corpus.db` table `post_emotion`
- `outputs/Posts_emotions.csv` (UTF-8 BOM)
- `outputs/emotion_distribution.csv`
- six `outputs/emotion_over_time_*.csv`
- `outputs/emotion_sentiment_crosstab.csv`
- `outputs/user_emotion_summary.csv`
- `outputs/emotion_plots/`

Inference this run: {inf.get('n_new', 0):,} newly scored in {inf.get('seconds', 0):.1f}s.
"""
    REPORT.write_text(text, encoding="utf-8")
    log(f"Wrote {REPORT.name}")


def main() -> int:
    started = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Opening {NLP_DB} (not IFB.db). Sentiment table is read, not rebuilt.")
    conn = connect_nlp()
    try:
        n_sent = conn.execute("SELECT COUNT(*) FROM post_sentiment").fetchone()[0]
        if n_sent != EXPECTED_N:
            log(f"WARNING: post_sentiment has {n_sent:,}, expected {EXPECTED_N:,}")
        ensure_table(conn)
        n_done = conn.execute("SELECT COUNT(*) FROM post_emotion").fetchone()[0]
        n_target = conn.execute("SELECT COUNT(*) " + eligible_sql(), (STATUS_FILTER,)).fetchone()[0]
        inf = {"n_new": 0, "seconds": 0.0, "n_target": n_target}
        model_name = MODEL_NAME
        if n_done < n_target:
            scorer, model_name = load_analyzer(BATCH_SIZE)
            inf = score_remaining(conn, scorer)
        else:
            log("All eligible posts already have emotions; exporting only.")
        val = validate(conn)
        log("Building distribution, crosstab, time series, users...")
        dist, cross = distribution_and_crosstab(conn)
        times = time_rows(conn)
        users = user_rows(conn)
        repl = fetch_replacement_docs(conn)
        events = load_event_lines()
        write_csv_utf8_bom(
            DIST_CSV,
            ["corpus", "emotion_label", "n_raw", "share_raw", "n_weighted", "share_weighted", "notes"],
            dist,
        )
        write_csv_utf8_bom(
            CROSSTAB_CSV,
            [
                "corpus",
                "sentiment_label",
                "emotion_label",
                "n_raw",
                "row_share_raw",
                "n_weighted",
                "row_share_weighted",
                "notes",
            ],
            cross,
        )
        user_fields = [
            "author_id",
            "username",
            "n_posts",
            "n_keyword",
            "n_timeline",
            *[f"n_{e}" for e in EMOTIONS],
            *[f"pct_{e}" for e in EMOTIONS],
            "plurality_emotion",
        ]
        write_csv_utf8_bom(USER_CSV, user_fields, users)
        fields_t = time_csv_fields()
        for res in RESOLUTIONS:
            write_csv_utf8_bom(TIME_CSV[res], fields_t, times[res])
        export_posts_csv(conn)
        plot_distribution(dist)
        plot_crosstab(cross)
        for res in RESOLUTIONS:
            plot_resolution(res, times[res], events)
        write_report(val, dist, cross, users, repl, model_name, inf, len(events))
        elapsed = time.perf_counter() - started
        log("")
        log("========== EMOTION SUMMARY ==========")
        log(f"processed={val['n_scored']} users={val['n_users']}")
        log(f"labels={val['labels']}")
        log(f"validation={'PASS' if val['ok'] else 'FAIL'}")
        log(f"event_lines_loaded={len(events)} (should be 0 until Event Detection)")
        log(f"elapsed_seconds={elapsed:.1f}")
        log("EMOTION_ANALYSIS_COMPLETE")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
