#!/usr/bin/env python3
"""Phase 2.3: PySentimiento English sentiment on English-ready NLP posts.

Uses only data/nlp_analysis_corpus.db. Does not open IFB.db or analysis_corpus.db.
Does not run emotion / BERTopic / NER / bots.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
REPORT = ROOT / "SENTIMENT_ANALYSIS_REPORT.md"

POSTS_CSV = OUTPUT_DIR / "Posts_sentiment.csv"
DIST_CSV = OUTPUT_DIR / "sentiment_distribution.csv"
TIME_CSV = OUTPUT_DIR / "sentiment_over_time_monthly.csv"
USER_CSV = OUTPUT_DIR / "user_sentiment_summary.csv"
DIST_PNG = OUTPUT_DIR / "sentiment_distribution.png"
TIME_PNG = OUTPUT_DIR / "sentiment_over_time_monthly.png"

EXPECTED_N = 742_942
STATUS_FILTER = "not_required_english"
MODEL_NAME = "finiteautomata/bertweet-base-sentiment-analysis"
PACKAGE = "pysentimiento"
TASK = "sentiment"
LANG = "en"

CHUNK = 4_096
BATCH_SIZE = 128
EMPTY_PLACEHOLDER = "."
LABEL_MAP = {
    "POS": "positive",
    "NEU": "neutral",
    "NEG": "negative",
    "POSITIVE": "positive",
    "NEUTRAL": "neutral",
    "NEGATIVE": "negative",
    "positive": "positive",
    "neutral": "neutral",
    "negative": "negative",
}
COLOR = {"positive": "#2ca02c", "neutral": "#ffcc00", "negative": "#d62728"}
ORDER = ("positive", "neutral", "negative")


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS post_sentiment (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            sentiment_label TEXT NOT NULL,
            sentiment_positive REAL NOT NULL,
            sentiment_neutral REAL NOT NULL,
            sentiment_negative REAL NOT NULL,
            input_was_empty_clean INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.commit()


def map_label(raw: Any) -> str:
    key = str(raw).strip()
    label = LABEL_MAP.get(key) or LABEL_MAP.get(key.upper())
    if label is None:
        raise ValueError(f"unexpected sentiment output: {raw!r}")
    return label


def probs_from_output(out: Any) -> tuple[str, float, float, float]:
    probas = dict(out.probas)
    pos = float(probas.get("POS", probas.get("positive", 0.0)))
    neu = float(probas.get("NEU", probas.get("neutral", 0.0)))
    neg = float(probas.get("NEG", probas.get("negative", 0.0)))
    total = pos + neu + neg
    if total <= 0:
        raise ValueError("non-positive probability mass")
    if abs(total - 1.0) > 0.02:
        pos, neu, neg = pos / total, neu / total, neg / total
    label = map_label(out.output)
    # If softmax argmax disagrees with reported output, trust argmax of stored probs.
    argmax = max(
        (("positive", pos), ("neutral", neu), ("negative", neg)),
        key=lambda x: x[1],
    )[0]
    if argmax != label:
        label = argmax
    return label, pos, neu, neg


class _Out:
    def __init__(self, output: str, probas: dict[str, float]) -> None:
        self.output = output
        self.probas = probas


class FastScorer:
    """Direct GPU forward pass — avoids Trainer.predict Dataset overhead."""

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
        self.id2label = {int(i): lab for i, lab in analyzer.model.config.id2label.items()}

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
                parts.append(torch.softmax(logits, dim=1).cpu())
        probs = torch.cat(parts, dim=0)
        outs: list[_Out] = []
        for row in probs:
            probas = {self.id2label[i]: float(row[i]) for i in range(row.numel())}
            outs.append(_Out(max(probas, key=probas.get), probas))
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
    analyzer = create_analyzer(
        task=TASK,
        lang=LANG,
        batch_size=batch_size,
        compile=False,
    )
    try:
        import torch

        if torch.cuda.is_available():
            analyzer.model.to("cuda")
        device = next(analyzer.model.parameters()).device
        log(f"  device={device} cuda={torch.cuda.is_available()}")
    except Exception as exc:
        log(f"  device move skipped: {exc}")
    name = getattr(analyzer.model.config, "_name_or_path", MODEL_NAME)
    log(f"  model={name}")
    return FastScorer(analyzer, batch_size), name


def score_remaining(conn: sqlite3.Connection, analyzer: Any, batch_size: int) -> dict[str, Any]:
    n_target = conn.execute(
        "SELECT COUNT(*) FROM nlp_posts WHERE translation_status=?",
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_done = conn.execute("SELECT COUNT(*) FROM post_sentiment").fetchone()[0]
    log(f"English-ready target={n_target:,} already_scored={n_done:,}")
    if n_target != EXPECTED_N:
        log(f"WARNING: expected {EXPECTED_N:,} English-ready posts, found {n_target:,}")

    cur = conn.execute(
        """
        SELECT p.source, p.tweet_id, p.clean_text
        FROM nlp_posts p
        WHERE p.translation_status = ?
          AND NOT EXISTS (
              SELECT 1 FROM post_sentiment s
              WHERE s.source = p.source AND s.tweet_id = p.tweet_id
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

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        conn.executemany(
            """
            INSERT OR REPLACE INTO post_sentiment (
                source, tweet_id, sentiment_label,
                sentiment_positive, sentiment_neutral, sentiment_negative,
                input_was_empty_clean
            ) VALUES (?,?,?,?,?,?,?)
            """,
            pending,
        )
        conn.commit()
        pending = []

    def run_batch() -> None:
        nonlocal n_new, n_empty, texts, keys, pending
        if not texts:
            return
        outputs = analyzer.predict(texts)
        if not isinstance(outputs, list):
            outputs = [outputs]
        if len(outputs) != len(keys):
            raise RuntimeError(f"predict size {len(outputs)} != {len(keys)}")
        for (source, tweet_id, empty_flag), out in zip(keys, outputs):
            label, pos, neu, neg = probs_from_output(out)
            pending.append((source, tweet_id, label, pos, neu, neg, empty_flag))
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
            text = EMPTY_PLACEHOLDER if empty_flag else str(clean)
            texts.append(text)
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
    n_target = conn.execute(
        "SELECT COUNT(*) FROM nlp_posts WHERE translation_status=?",
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_scored = conn.execute("SELECT COUNT(*) FROM post_sentiment").fetchone()[0]
    n_join = conn.execute(
        """
        SELECT COUNT(*)
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_dup = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT source, tweet_id FROM post_sentiment
            GROUP BY source, tweet_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    n_bad_label = conn.execute(
        """
        SELECT COUNT(*) FROM post_sentiment
        WHERE sentiment_label NOT IN ('positive','neutral','negative')
           OR sentiment_label IS NULL
        """
    ).fetchone()[0]
    n_bad_prob = conn.execute(
        """
        SELECT COUNT(*) FROM post_sentiment
        WHERE sentiment_positive < 0 OR sentiment_neutral < 0 OR sentiment_negative < 0
           OR sentiment_positive > 1 OR sentiment_neutral > 1 OR sentiment_negative > 1
           OR abs(sentiment_positive+sentiment_neutral+sentiment_negative-1) > 0.02
        """
    ).fetchone()[0]
    labels = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT sentiment_label, COUNT(*) FROM post_sentiment GROUP BY 1"
        )
    }
    n_users = conn.execute(
        """
        SELECT COUNT(DISTINCT p.author_id)
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    n_empty = conn.execute(
        "SELECT SUM(input_was_empty_clean) FROM post_sentiment"
    ).fetchone()[0] or 0
    extra = conn.execute(
        """
        SELECT COUNT(*) FROM post_sentiment s
        WHERE NOT EXISTS (
            SELECT 1 FROM nlp_posts p
            WHERE p.source=s.source AND p.tweet_id=s.tweet_id
              AND p.translation_status=?
        )
        """,
        (STATUS_FILTER,),
    ).fetchone()[0]
    ok = (
        n_target == n_scored == n_join
        and n_dup == 0
        and n_bad_label == 0
        and n_bad_prob == 0
        and extra == 0
        and set(labels) == {"positive", "neutral", "negative"}
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
    }
    log(f"VALIDATION {'PASS' if ok else 'FAIL'}: {summary}")
    if not ok:
        raise RuntimeError(f"sentiment validation failed: {summary}")
    return summary


def month_of(iso: str) -> str:
    if not iso or len(iso) < 7:
        return "unknown"
    return iso[:7]


def fetch_replacement_docs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT q.source, q.tweet_id, p.translation_status,
               CASE WHEN s.tweet_id IS NULL THEN 0 ELSE 1 END AS scored
        FROM translation_quality q
        LEFT JOIN nlp_posts p USING (source, tweet_id)
        LEFT JOIN post_sentiment s USING (source, tweet_id)
        WHERE q.has_replacement = 1
        ORDER BY q.source, q.tweet_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def distribution_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    sql = """
    SELECT p.source, s.sentiment_label,
           COUNT(*) AS n_raw,
           SUM(p.sample_weight) AS n_weighted
    FROM nlp_posts p
    JOIN post_sentiment s USING (source, tweet_id)
    WHERE p.translation_status = ?
    GROUP BY p.source, s.sentiment_label
    """
    raw = conn.execute(sql, (STATUS_FILTER,)).fetchall()
    by_src: dict[str, dict[str, dict[str, float]]] = {}
    for r in raw:
        by_src.setdefault(r["source"], {})[r["sentiment_label"]] = {
            "n_raw": r["n_raw"],
            "n_weighted": float(r["n_weighted"] or 0),
        }

    def pack(name: str, parts: dict[str, dict[str, float]], weighted: bool) -> list[dict[str, Any]]:
        tot_raw = sum(v["n_raw"] for v in parts.values()) or 1
        tot_w = sum(v["n_weighted"] for v in parts.values()) or 1.0
        rows = []
        for lab in ORDER:
            d = parts.get(lab, {"n_raw": 0, "n_weighted": 0.0})
            row = {
                "corpus": name,
                "sentiment_label": lab,
                "n_raw": int(d["n_raw"]),
                "share_raw": round(d["n_raw"] / tot_raw, 6),
                "n_weighted": round(d["n_weighted"], 4) if weighted else "",
                "share_weighted": round(d["n_weighted"] / tot_w, 6) if weighted else "",
                "notes": "",
            }
            rows.append(row)
        return rows

    kw = by_src.get("keyword_tweets", {})
    tl = by_src.get("timeline", {})
    combined: dict[str, dict[str, float]] = {}
    for lab in ORDER:
        combined[lab] = {
            "n_raw": kw.get(lab, {}).get("n_raw", 0) + tl.get(lab, {}).get("n_raw", 0),
            "n_weighted": kw.get(lab, {}).get("n_weighted", 0) + tl.get(lab, {}).get("n_weighted", 0),
        }
    rows = []
    rows += pack("keyword_tweets", kw, False)
    for r in rows[-3:]:
        r["notes"] = "census; sample_weight=1; weighted omitted"
    rows += pack("timeline_raw", tl, False)
    for r in rows[-3:]:
        r["notes"] = "unweighted sample rows; not a population estimate"
    rows += pack("timeline_weighted", tl, True)
    for r in rows[-3:]:
        r["notes"] = "Horvitz-Thompson; English timeline population"
    rows += pack("combined_unweighted", combined, False)
    for r in rows[-3:]:
        r["notes"] = "keyword census + timeline sample mixed; not one population"
    return rows


def monthly_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT p.source, substr(p.created_at, 1, 7) AS month, s.sentiment_label,
               COUNT(*) AS n_raw, SUM(p.sample_weight) AS n_weighted
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        GROUP BY 1, 2, 3
        """,
        (STATUS_FILTER,),
    )
    bucket: dict[tuple[str, str], dict[str, dict[str, float]]] = {}
    for r in cur:
        key = (r["source"], r["month"] or "unknown")
        bucket.setdefault(key, {})[r["sentiment_label"]] = {
            "n_raw": r["n_raw"],
            "n_weighted": float(r["n_weighted"] or 0),
        }
    rows: list[dict[str, Any]] = []
    combined: dict[str, dict[str, dict[str, float]]] = {}
    for (source, month), labs in bucket.items():
        tot_raw = sum(v["n_raw"] for v in labs.values()) or 1
        tot_w = sum(v["n_weighted"] for v in labs.values()) or 1.0
        rec = {
            "corpus": source,
            "month": month,
            "n_raw": int(tot_raw),
            "n_weighted": round(tot_w, 4) if source == "timeline" else "",
        }
        for lab in ORDER:
            d = labs.get(lab, {"n_raw": 0, "n_weighted": 0.0})
            rec[f"n_{lab}"] = int(d["n_raw"])
            rec[f"share_{lab}"] = round(d["n_raw"] / tot_raw, 6)
            if source == "timeline":
                rec[f"n_weighted_{lab}"] = round(d["n_weighted"], 4)
                rec[f"share_weighted_{lab}"] = round(d["n_weighted"] / tot_w, 6)
            else:
                rec[f"n_weighted_{lab}"] = ""
                rec[f"share_weighted_{lab}"] = ""
        rec["notes"] = "census" if source == "keyword_tweets" else "timeline sample; weighted cols estimate English timeline"
        rows.append(rec)
        cmb = combined.setdefault(month, {lab: {"n_raw": 0} for lab in ORDER})
        for lab in ORDER:
            cmb[lab]["n_raw"] += labs.get(lab, {}).get("n_raw", 0)
    for month, labs in combined.items():
        tot_raw = sum(v["n_raw"] for v in labs.values()) or 1
        rec = {
            "corpus": "combined_unweighted",
            "month": month,
            "n_raw": int(tot_raw),
            "n_weighted": "",
            "notes": "mix of keyword census and timeline sample; do not treat as a population",
        }
        for lab in ORDER:
            rec[f"n_{lab}"] = int(labs[lab]["n_raw"])
            rec[f"share_{lab}"] = round(labs[lab]["n_raw"] / tot_raw, 6)
            rec[f"n_weighted_{lab}"] = ""
            rec[f"share_weighted_{lab}"] = ""
        rows.append(rec)
    rows.sort(key=lambda r: (r["corpus"], r["month"]))
    return rows


def user_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT p.author_id,
               MAX(p.username) AS username,
               COUNT(*) AS n_posts,
               SUM(CASE WHEN p.source='keyword_tweets' THEN 1 ELSE 0 END) AS n_keyword,
               SUM(CASE WHEN p.source='timeline' THEN 1 ELSE 0 END) AS n_timeline,
               SUM(CASE WHEN s.sentiment_label='positive' THEN 1 ELSE 0 END) AS n_positive,
               SUM(CASE WHEN s.sentiment_label='neutral' THEN 1 ELSE 0 END) AS n_neutral,
               SUM(CASE WHEN s.sentiment_label='negative' THEN 1 ELSE 0 END) AS n_negative
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        GROUP BY p.author_id
        """,
        (STATUS_FILTER,),
    )
    rows = []
    for r in cur:
        n = r["n_posts"] or 1
        rows.append(
            {
                "author_id": r["author_id"],
                "username": r["username"] or "",
                "n_posts": r["n_posts"],
                "n_keyword": r["n_keyword"],
                "n_timeline": r["n_timeline"],
                "n_positive": r["n_positive"],
                "n_neutral": r["n_neutral"],
                "n_negative": r["n_negative"],
                "pct_positive": round(100.0 * r["n_positive"] / n, 4),
                "pct_neutral": round(100.0 * r["n_neutral"] / n, 4),
                "pct_negative": round(100.0 * r["n_negative"] / n, 4),
            }
        )
    return rows


def write_csv_utf8_bom(path: Path, fieldnames: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


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
    ]
    cur = conn.execute(
        """
        SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at, p.lang,
               p.original_text, p.clean_text, p.topic_text, p.sample_weight,
               p.translation_status,
               s.sentiment_label, s.sentiment_positive, s.sentiment_neutral,
               s.sentiment_negative
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
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
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    fig.patch.set_facecolor("white")
    titles = [
        ("keyword_tweets", "Keyword census\n(unweighted = population of eligible keyword posts)"),
        ("timeline_raw", "Timeline sample\n(raw row shares; not a population)"),
        ("combined_unweighted", "Combined file\n(mixed sampling; not one population)"),
    ]
    for ax, (corpus, title) in zip(axes, titles):
        subset = [r for r in dist if r["corpus"] == corpus]
        sizes = [r["n_raw"] for r in subset]
        labels = [
            f"{r['sentiment_label']}\n{r['n_raw']:,}\n({100*r['share_raw']:.1f}%)"
            for r in subset
        ]
        colors = [COLOR[r["sentiment_label"]] for r in subset]
        wedges, _ = ax.pie(
            sizes,
            colors=colors,
            startangle=90,
            wedgeprops={"linewidth": 1.2, "edgecolor": "white"},
        )
        ax.set_title(title, fontsize=10)
        ax.legend(
            wedges,
            labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.18),
            fontsize=8,
            frameon=False,
        )
    fig.suptitle("Sentiment distribution (PySentimiento, 3 classes — no mixed average)", fontsize=13)
    fig.tight_layout()
    fig.savefig(DIST_PNG, dpi=160, bbox_inches="tight")
    plt.close(fig)
    log(f"Wrote {DIST_PNG.name}")


def plot_monthly(rows: list[dict[str, Any]]) -> None:
    from datetime import datetime as dt

    def series(corpus: str, share_key: str) -> tuple[list[dt], list[float]]:
        pts = []
        for r in rows:
            if r["corpus"] != corpus or r["month"] == "unknown":
                continue
            val = r.get(share_key, "")
            if val == "" or val is None:
                continue
            try:
                pts.append((dt.strptime(r["month"] + "-01", "%Y-%m-%d"), float(val) * 100))
            except ValueError:
                continue
        pts.sort()
        return [p[0] for p in pts], [p[1] for p in pts]

    fig, axes = plt.subplots(3, 1, figsize=(12.5, 9.2), sharex=True)
    fig.patch.set_facecolor("white")
    titles = {
        "positive": "Positive share by month (green) — not mixed with other classes",
        "neutral": "Neutral share by month (yellow) — not mixed with other classes",
        "negative": "Negative share by month (red) — not mixed with other classes",
    }
    import matplotlib.dates as mdates

    for ax, lab in zip(axes, ORDER):
        mk, yk = series("keyword_tweets", f"share_{lab}")
        mt, yt = series("timeline", f"share_{lab}")
        mw, yw = series("timeline", f"share_weighted_{lab}")
        ax.plot(mk, yk, color=COLOR[lab], lw=2.0, label="keyword census (raw = weighted)")
        ax.plot(mt, yt, color=COLOR[lab], lw=1.6, ls="--", label="timeline sample (raw)")
        ax.plot(mw, yw, color=COLOR[lab], lw=1.4, ls=":", label="timeline sample (weighted)")
        ax.set_ylabel(f"{lab} %")
        ax.set_title(titles[lab], loc="left", fontsize=10)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.35)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].set_xlabel("Year (monthly series)")
    fig.suptitle(
        "Separate positive / neutral / negative time series (no combined sentiment curve)",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(TIME_PNG, dpi=160, bbox_inches="tight")
    plt.close(fig)
    log(f"Wrote {TIME_PNG.name}")


def pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.2f}%" if d else "n/a"


def write_report(
    val: dict[str, Any],
    dist: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    users: list[dict[str, Any]],
    repl: list[dict[str, Any]],
    model_name: str,
    inf: dict[str, Any],
) -> None:
    def grab(corpus: str) -> dict[str, dict[str, Any]]:
        return {r["sentiment_label"]: r for r in dist if r["corpus"] == corpus}

    kw, tl_raw, tl_w, comb = (
        grab("keyword_tweets"),
        grab("timeline_raw"),
        grab("timeline_weighted"),
        grab("combined_unweighted"),
    )
    n = val["n_scored"]
    n_users = val["n_users"]
    n_kw = sum(int(kw[l]["n_raw"]) for l in ORDER)
    n_tl = sum(int(tl_raw[l]["n_raw"]) for l in ORDER)

    def line(block: dict[str, dict[str, Any]], lab: str, weighted: bool = False) -> str:
        r = block[lab]
        if weighted:
            return f"{float(r['n_weighted']):,.1f} ({100*float(r['share_weighted']):.2f}%)"
        return f"{int(r['n_raw']):,} ({100*float(r['share_raw']):.2f}%)"

    # user polarity
    user_n = len(users)
    maj = Counter()
    for u in users:
        best = max(
            (("positive", u["n_positive"]), ("neutral", u["n_neutral"]), ("negative", u["n_negative"])),
            key=lambda x: x[1],
        )[0]
        maj[best] += 1
    mean_posts = (sum(u["n_posts"] for u in users) / user_n) if user_n else 0

    repl_lines = "\n".join(
        f"| `{r['source']}` | `{r['tweet_id']}` | {r['translation_status']} | "
        f"{'yes' if r['scored'] else 'no (held out as uncertain/non-English)'} |"
        for r in repl
    ) or "| — | — | — | none found |"

    # monthly peaks for interpretation (combined unweighted, largest n)
    comb_m = [r for r in monthly if r["corpus"] == "combined_unweighted"]
    def peak(lab: str) -> str:
        cand = [r for r in comb_m if int(r["n_raw"]) >= 500]
        if not cand:
            cand = comb_m
        if not cand:
            return "n/a"
        row = max(cand, key=lambda r: float(r[f"share_{lab}"]))
        return f"{row['month']} ({100*float(row[f'share_{lab}']):.1f}%, n={row['n_raw']:,}; months with n<500 ignored)"

    text = f"""# Sentiment analysis

Built: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
Package: **{PACKAGE}** (`create_analyzer(task="{TASK}", lang="{LANG}")`)
Model: **{model_name}** (BERTweet-base, 3-class POS/NEU/NEG)
Input column: **`clean_text`** (course instruction). Empty `clean_text` ({val['n_empty_clean']:,} posts) scored as `"{EMPTY_PLACEHOLDER}"`.
Filter: `translation_status = {STATUS_FILTER}` only.
`IFB.db` and `data/analysis_corpus.db` were not opened. Original text was not rewritten.
Weights were **not** used during inference. They are used only for timeline population estimates.

## Processed volume

| Item | N |
|------|--:|
| English-ready posts scored | **{n:,}** |
| Users with ≥1 scored post | **{n_users:,}** |
| Keyword posts (census) | {n_kw:,} |
| Timeline posts (stratified sample) | {n_tl:,} |
| Empty `clean_text` placeholder | {val['n_empty_clean']:,} |
| Duplicate `(source, tweet_id)` | {val['n_dup']} |
| Validation | **{"PASS" if val["ok"] else "FAIL"}** |

Every scored row has `sentiment_label` ∈ {{positive, neutral, negative}} and three probabilities in [0, 1] that sum to ~1.

## Counts and percentages

There is **no** combined “average sentiment” number. Neutral is kept as its own class.

### Combined file (unweighted mix of two sampling frames)

| Class | Count | Share |
|-------|------:|------:|
| positive | {int(comb['positive']['n_raw']):,} | {100*float(comb['positive']['share_raw']):.2f}% |
| neutral | {int(comb['neutral']['n_raw']):,} | {100*float(comb['neutral']['share_raw']):.2f}% |
| negative | {int(comb['negative']['n_raw']):,} | {100*float(comb['negative']['share_raw']):.2f}% |
| **total** | **{n:,}** | 100% |

Do not read the combined pie as “the IFB population’s mood.” It mixes a keyword census with a 1.7% English-timeline sample.

### Keyword tweets (census of eligible English-ready keyword posts)

| Class | Count | Share |
|-------|------:|------:|
| positive | {int(kw['positive']['n_raw']):,} | {100*float(kw['positive']['share_raw']):.2f}% |
| neutral | {int(kw['neutral']['n_raw']):,} | {100*float(kw['neutral']['share_raw']):.2f}% |
| negative | {int(kw['negative']['n_raw']):,} | {100*float(kw['negative']['share_raw']):.2f}% |

### Timeline — raw sample vs weighted population estimate

English-ready timeline rows: **{n_tl:,}**. Weighted total ≈ sum of `sample_weight` (≈ 29.50M English timeline posts).

| Class | Raw count (share) | Weighted count (share) |
|-------|-------------------|------------------------|
| positive | {line(tl_raw, 'positive')} | {line(tl_w, 'positive', True)} |
| neutral | {line(tl_raw, 'neutral')} | {line(tl_w, 'neutral', True)} |
| negative | {line(tl_raw, 'negative')} | {line(tl_w, 'negative', True)} |

Raw shares describe the **500k-scale sample we scored**. Weighted shares estimate the **English timeline population** of the 38,576 primary users. Keyword weights were not applied to timeline rows.

## Monthly trends (three separate series)

Figures: `outputs/sentiment_over_time_monthly.png` — **three panels**, one class each (green / yellow / red). No single mixed sentiment curve.

Peak combined-file monthly **share** (descriptive only):

| Class | Peak month |
|-------|------------|
| positive | {peak('positive')} |
| neutral | {peak('neutral')} |
| negative | {peak('negative')} |

Keyword IFB talk is structurally more promotional (follow-back, thanks, growth pitches), so its positive/neutral mix is not comparable to ordinary timeline talk without stating the sampling frame.

## Per-user sentiment summary

`outputs/user_sentiment_summary.csv` — one row per author: counts and percentages. **{user_n:,}** users. Mean scored posts per user: {mean_posts:.1f}.

Users whose **plurality** class (raw counts, not weights) is:

| Plurality class | Users | Share of users |
|-----------------|------:|---------------:|
| positive | {maj.get('positive', 0):,} | {pct(maj.get('positive', 0), user_n)} |
| neutral | {maj.get('neutral', 0):,} | {pct(maj.get('neutral', 0), user_n)} |
| negative | {maj.get('negative', 0):,} | {pct(maj.get('negative', 0), user_n)} |

A user with 2 posts is not comparable to a high-activity author. Percentages are within-user; they are not timeline population estimates.

## Replacement-character records

Five posts contain U+FFFD. **Original text was not repaired or rewritten.** They stay in `nlp_posts.original_text` as stored. Sentiment ran only on `not_required_english`; encoding-damaged rows from the translation audit were mostly `uncertain` and therefore **not scored**.

| source | tweet_id | translation_status | scored? |
|--------|----------|--------------------|---------|
{repl_lines}

## Limitations (sampling and language)

1. **English-ready filter.** 1,279 posts in the NLP file (`requires_translation` + `uncertain`) were excluded before scoring. Timeline non-`en` (~8.3M) and keyword non-English / IFB-dominated / boilerplate never entered this corpus.
2. **Keyword ≠ English dictionary.** Latin-script Portuguese/French can still be `not_required_english`. PySentimiento English may mis-label them.
3. **`clean_text` is stemmed** (Porter) with stopwords removed. That is what the course asks to score; it is harsher than raw tweets and can flatten polarity.
4. **Timeline sample.** 498,725 scored timeline rows represent ~29.5M English timeline posts only after applying `sample_weight`. Do not train or calibrate the model with those weights.
5. **Combined file** is not a stratified sample of “all IFB discourse.” Keyword posts over-represent follow-for-follow talk.
6. **Empty clean_text** used a placeholder period; those labels are weakly identified.
7. **No emotion / events yet.** Monthly panels do not yet have event lines (those belong with emotion peaks + tweet evidence).

## Files

- `src/sentiment_analysis.py` — batched GPU inference, SQLite checkpoint `post_sentiment`
- `notebooks/sentiment_analysis.ipynb`
- `data/nlp_analysis_corpus.db` table `post_sentiment` (PK `source, tweet_id`)
- `outputs/Posts_sentiment.csv` (UTF-8 BOM)
- `outputs/sentiment_distribution.csv`
- `outputs/sentiment_over_time_monthly.csv`
- `outputs/user_sentiment_summary.csv`
- `outputs/sentiment_distribution.png`
- `outputs/sentiment_over_time_monthly.png`

Inference this run: {inf.get('n_new', 0):,} newly scored in {inf.get('seconds', 0):.1f}s.
"""
    REPORT.write_text(text, encoding="utf-8")
    log(f"Wrote {REPORT.name}")


def main() -> int:
    started = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Opening {NLP_DB} (not IFB.db)...")
    conn = connect_nlp()
    try:
        ensure_table(conn)
        n_done = conn.execute("SELECT COUNT(*) FROM post_sentiment").fetchone()[0]
        n_target = conn.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE translation_status=?",
            (STATUS_FILTER,),
        ).fetchone()[0]
        inf = {"n_new": 0, "seconds": 0.0, "n_target": n_target}
        model_name = MODEL_NAME
        if n_done < n_target:
            analyzer, model_name = load_analyzer(BATCH_SIZE)
            inf = score_remaining(conn, analyzer, BATCH_SIZE)
            inf["n_target"] = n_target
        else:
            log("All English-ready posts already scored; exporting only.")
        val = validate(conn)
        log("Building distribution / monthly / user tables...")
        dist = distribution_rows(conn)
        monthly = monthly_rows(conn)
        users = user_rows(conn)
        repl = fetch_replacement_docs(conn)
        write_csv_utf8_bom(
            DIST_CSV,
            ["corpus", "sentiment_label", "n_raw", "share_raw", "n_weighted", "share_weighted", "notes"],
            dist,
        )
        write_csv_utf8_bom(
            TIME_CSV,
            [
                "corpus",
                "month",
                "n_raw",
                "n_weighted",
                "n_positive",
                "n_neutral",
                "n_negative",
                "share_positive",
                "share_neutral",
                "share_negative",
                "n_weighted_positive",
                "n_weighted_neutral",
                "n_weighted_negative",
                "share_weighted_positive",
                "share_weighted_neutral",
                "share_weighted_negative",
                "notes",
            ],
            monthly,
        )
        write_csv_utf8_bom(
            USER_CSV,
            [
                "author_id",
                "username",
                "n_posts",
                "n_keyword",
                "n_timeline",
                "n_positive",
                "n_neutral",
                "n_negative",
                "pct_positive",
                "pct_neutral",
                "pct_negative",
            ],
            users,
        )
        export_posts_csv(conn)
        plot_distribution(dist)
        plot_monthly(monthly)
        write_report(val, dist, monthly, users, repl, model_name, inf)
        elapsed = time.perf_counter() - started
        log("")
        log("========== SENTIMENT SUMMARY ==========")
        log(f"processed={val['n_scored']} users={val['n_users']}")
        log(f"labels={val['labels']}")
        log(f"validation={'PASS' if val['ok'] else 'FAIL'}")
        log(f"elapsed_seconds={elapsed:.1f}")
        log("SENTIMENT_ANALYSIS_COMPLETE")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
