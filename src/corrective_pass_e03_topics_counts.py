"""Final corrective pass: E03 evidence, topic-over-time, keyword 4-row audit.

Read-only on data/nlp_analysis_corpus.db. Does not open or modify IFB.db.
Does not rescore sentiment/emotion and does not rerun BERTopic.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from emotion_analysis import add_event_lines, load_event_lines  # noqa: E402
from event_detection import build_docx  # noqa: E402

NLP = ROOT / "data" / "nlp_analysis_corpus.db"
OUT = ROOT / "outputs"
EVID = OUT / "event_tweet_evidence.csv"
EVENTS = OUT / "detected_events.csv"
EXT = OUT / "event_external_sources.csv"
STATS = OUT / "event_statistics.csv"
TOPICS = OUT / "final_topics.csv"
ADD_IDS = ("1497370141889376258", "1496560010545016833")


def ro() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{NLP}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def add_e03_evidence() -> list[dict[str, str]]:
    rows = read_csv(EVID)
    have = {(r["source"], r["tweet_id"]) for r in rows}
    con = ro()
    added = []
    for tid in ADD_IDS:
        rec = con.execute(
            """
            SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at,
                   p.original_text, p.clean_text, s.sentiment_label,
                   e.emotion_label, e.emotion_fear
            FROM nlp_posts p
            JOIN post_sentiment s USING (source, tweet_id)
            JOIN post_emotion e USING (source, tweet_id)
            WHERE p.tweet_id=?
              AND p.created_at >= '2022-02-21' AND p.created_at < '2022-02-28'
              AND e.emotion_label='fear'
            """,
            (tid,),
        ).fetchone()
        if rec is None:
            raise RuntimeError(f"refused to add missing/out-of-window tweet {tid}")
        key = (rec["source"], rec["tweet_id"])
        if key in have:
            continue
        row = {
            "event_id": "E03",
            "source": rec["source"],
            "tweet_id": rec["tweet_id"],
            "author_id": rec["author_id"],
            "username": rec["username"],
            "created_at": rec["created_at"],
            "original_text": rec["original_text"],
            "clean_text": rec["clean_text"],
            "sentiment_label": rec["sentiment_label"],
            "emotion_label": rec["emotion_label"],
            "emotion_probability": rec["emotion_fear"],
            "likes": "",
            "replies": "",
            "retweets": "",
            "engagement_note": "not stored on nlp_posts",
        }
        rows.append(row)
        have.add(key)
        added.append(row)
        print("added E03", tid, rec["username"], (rec["original_text"] or "")[:80])
    con.close()
    if len(added) < 2:
        raise RuntimeError(f"expected 2 new E03 tweets, added {len(added)}")
    write_csv(EVID, rows, list(rows[0].keys()))
    e03 = [r for r in rows if r["event_id"] == "E03"]
    print("E03 evidence now", len(e03), "total", len(rows))
    return rows


def audit_four_keyword_rows() -> list[dict[str, str]]:
    con = ro()
    recs = list(
        con.execute(
            """
            SELECT p.tweet_id, p.author_id, p.username, p.created_at,
                   p.translation_status, p.content_class,
                   p.original_text, p.clean_text, p.text_translated_en,
                   CASE WHEN s.tweet_id IS NULL THEN 0 ELSE 1 END AS in_sentiment,
                   instr(COALESCE(p.original_text,''), char(65533)) > 0 AS has_fffd
            FROM nlp_posts p
            LEFT JOIN post_sentiment s
              ON s.source=p.source AND s.tweet_id=p.tweet_id
            WHERE p.source='keyword_tweets'
              AND p.translation_status != 'not_required_english'
            ORDER BY p.created_at
            """
        )
    )
    con.close()
    if len(recs) != 4:
        raise RuntimeError(f"expected 4 unscored keyword rows, got {len(recs)}")
    out = []
    reasons = {
        "1110608490748207104": "uncertain: U+FFFD replacement characters in original_text (Henri-Frédéric). text_translated_en NULL; not scored.",
        "1132322951167205376": "uncertain: U+FFFD replacement characters in original_text (Jörgens). text_translated_en NULL; not scored.",
        "1325385083428237312": "uncertain: unreadable control/legacy encoding byte in original_text (Pique\\x92). text_translated_en NULL; not scored.",
        "1481686488005763072": "uncertain: U+FFFD plus invisible separators (U+2063) in original_text. text_translated_en NULL; not scored.",
    }
    for r in recs:
        tid = str(r["tweet_id"])
        out.append(
            {
                "tweet_id": tid,
                "author_id": r["author_id"],
                "username": r["username"],
                "created_at": r["created_at"],
                "translation_status": r["translation_status"],
                "content_class": r["content_class"],
                "in_post_sentiment": r["in_sentiment"],
                "has_u_fffd": r["has_fffd"],
                "text_translated_en_is_null": 1 if r["text_translated_en"] is None else 0,
                "reason": reasons.get(tid, "uncertain: encoding/control damage; not scored."),
                "original_preview": (r["original_text"] or "").replace("\n", " ")[:180],
            }
        )
    write_csv(OUT / "keyword_unscored_four_rows.csv", out, list(out[0].keys()))
    return out


def plot_topic_over_time() -> None:
    names = {}
    for r in read_csv(TOPICS):
        names[int(r["topic_id"])] = r["topic_name"]
    keep = [0, 1, 4, 2, 6, 8]
    con = ro()
    rows = list(
        con.execute(
            """
            SELECT substr(p.created_at, 1, 7) AS ym, p.source, t.topic_id, COUNT(*) AS n
            FROM post_topic t
            JOIN nlp_posts p USING (source, tweet_id)
            GROUP BY 1, 2, 3
            """
        )
    )
    con.close()
    totals = defaultdict(int)
    counts = defaultdict(int)
    for r in rows:
        ym, src, tid, n = r["ym"], r["source"], int(r["topic_id"]), int(r["n"])
        totals[(src, ym)] += n
        counts[(src, ym, tid)] += n
    write_csv(
        OUT / "topic_over_time_monthly.csv",
        [
            {
                "year_month": r["ym"],
                "source": r["source"],
                "topic_id": r["topic_id"],
                "topic_name": names.get(int(r["topic_id"]), str(r["topic_id"])),
                "n": r["n"],
            }
            for r in rows
        ],
        ["year_month", "source", "topic_id", "topic_name", "n"],
    )

    colors = {
        0: "#1f77b4",
        1: "#ff7f0e",
        4: "#2ca02c",
        2: "#9467bd",
        6: "#8c564b",
        8: "#17becf",
    }
    fig, axes = plt.subplots(2, 1, figsize=(11.2, 7.2), sharex=False)
    panels = [
        (axes[0], "keyword_tweets", "Keyword census — monthly share of C13 topics", "keyword"),
        (axes[1], "timeline", "Timeline sample — monthly share of C13 topics", "timeline"),
    ]
    events = load_event_lines()
    for ax, source, title, ev_src in panels:
        yms = sorted({ym for (src, ym) in totals if src == source and ym >= "2018-01"})
        xs = [mdates.datestr2num(f"{ym}-01") for ym in yms]
        for tid in keep:
            ys = []
            for ym in yms:
                den = totals[(source, ym)] or 1
                ys.append(100.0 * counts[(source, ym, tid)] / den)
            ax.plot(
                xs,
                ys,
                color=colors[tid],
                linewidth=1.4,
                label=f"{tid}: {names.get(tid, '')[:32]}",
            )
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("Share of month (%)")
        ax.set_ylim(0, 55)
        ax.xaxis.set_major_formatter(DateFormatter("%Y"))
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        add_event_lines(ax, [e for e in events if e.get("source") == source or e.get("source") == ev_src])
        ax.legend(loc="upper left", fontsize=7, frameon=False, ncol=2)
    axes[1].set_xlabel("Month (existing C13 assignments; BERTopic was not rerun)")
    fig.suptitle(
        "Topic share over time — dashed lines are selected events (correlation, not causation)",
        fontsize=12,
    )
    fig.tight_layout()
    dest = OUT / "topic_over_time_monthly.png"
    fig.savefig(dest, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", dest, dest.stat().st_size)


def rebuild_detected_events_docx(evidence: list[dict[str, str]]) -> None:
    selected = read_csv(EVENTS)
    ext = read_csv(EXT) if EXT.exists() else []
    stats_rows = {r["metric"]: r["value"] for r in read_csv(STATS)} if STATS.exists() else {}
    stats = {
        "n_corpus": int(float(stats_rows.get("n_corpus", 742942))),
        "n_stat": int(float(stats_rows.get("n_stat", 68))),
        "n_rejected": int(float(stats_rows.get("n_rejected", 64))),
        "n_selected": len(selected),
        "n_evidence": len(evidence),
    }
    if "n_evidence" in stats_rows or STATS.exists():
        updated = read_csv(STATS)
        for r in updated:
            if r["metric"] == "n_evidence":
                r["value"] = str(len(evidence))
        if updated:
            write_csv(STATS, updated, list(updated[0].keys()))
    build_docx(selected, evidence, ext, stats)
    print("rewrote detected_events.docx")


def main() -> None:
    four = audit_four_keyword_rows()
    print("four keyword rows:")
    for r in four:
        print(r["tweet_id"], r["reason"])
    evidence = add_e03_evidence()
    rebuild_detected_events_docx(evidence)
    plot_topic_over_time()
    print("IFB.db was not opened.")


if __name__ == "__main__":
    main()
