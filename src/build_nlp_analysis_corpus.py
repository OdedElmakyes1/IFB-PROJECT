#!/usr/bin/env python3
"""Build the English NLP analysis corpus (not the 7,428-row QA sample).

Read-only on data/analysis_corpus.db. Does not modify IFB.db or the QA DB.
Does not translate. Does not run sentiment/emotion. No full CSV dump.
"""

from __future__ import annotations

import math
import random
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from language_detection_and_preprocessing import (  # noqa: E402
    MIN_DETECT_CHARS,
    MIN_DETECT_LETTERS,
    clean_text,
    connect_ro,
    detect_language,
    detection_text,
    hash_text,
    letter_count,
    script_hint,
    topic_text,
    write_csv,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DB = ROOT / "data" / "analysis_corpus.db"
QA_DB = ROOT / "data" / "nlp_working_sample.db"
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
CENSUS_CSV = OUTPUT_DIR / "full_keyword_language_census.csv"
STATS_CSV = OUTPUT_DIR / "nlp_corpus_statistics.csv"
PLAN = ROOT / "NLP_SAMPLING_PLAN.md"

RNG_SEED = 2026
CHUNK = 20_000
INSERT_SIZE = 4_000
PROGRESS = 200_000
BENCHMARK_N = 5_000
TARGET_TIMELINE = 500_000
BOILERPLATE_MIN = 5  # hash frequency: all copies excluded
FALSE_FRIEND_LANGS = frozenset(
    "no af ca so cy nl da sv et fi ro tl sw sl hr sq sk vi".split()
)


def log(msg: str) -> None:
    print(msg, flush=True)


def quarter_of(iso: str) -> str:
    try:
        year = iso[:4]
        month = int(iso[5:7])
        q = (month - 1) // 3 + 1
        return f"{year}Q{q}"
    except (TypeError, ValueError, IndexError):
        return "unknownQ"


def activity_level(n: int, t1: int, t2: int) -> str:
    if n <= t1:
        return "low"
    if n <= t2:
        return "mid"
    return "high"


def classify_keyword_text(text: str) -> str:
    """Deterministic census label. Does not call langdetect."""
    raw = (text or "").strip()
    if not raw:
        return "empty"
    hint = script_hint(raw)
    non_latin = sum(
        1 for ch in raw if ch.isalpha() and not ("A" <= ch <= "Z" or "a" <= ch <= "z")
    )
    if hint and hint != "en" and non_latin >= MIN_DETECT_LETTERS:
        return "script_non_english"
    stripped = detection_text(raw)
    if letter_count(stripped) < MIN_DETECT_LETTERS or len(stripped) < MIN_DETECT_CHARS:
        return "ifb_dominated"
    latin = sum(1 for ch in stripped if ch.isalpha() and ch.isascii())
    letters = letter_count(stripped)
    if letters and latin / letters >= 0.85:
        return "likely_english"
    return "uncertain"


def open_nlp_db(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        extra = Path(str(path) + suffix)
        if extra.exists():
            extra.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    conn.execute(
        """
        CREATE TABLE nlp_posts (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            username TEXT,
            created_at TEXT NOT NULL,
            lang TEXT,
            original_text TEXT,
            clean_text TEXT,
            topic_text TEXT,
            stratum TEXT NOT NULL,
            sampling_probability REAL NOT NULL,
            sample_weight REAL NOT NULL,
            content_class TEXT,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE nlp_users (
            author_id TEXT PRIMARY KEY,
            username TEXT,
            en_timeline_posts INTEGER,
            activity_level TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE strata (
            stratum TEXT PRIMARY KEY,
            source TEXT,
            n_population INTEGER,
            n_sampled INTEGER,
            sampling_probability REAL,
            sample_weight REAL
        )
        """
    )
    return conn


def insert_posts(dst: sqlite3.Connection, rows: list[tuple]) -> None:
    if not rows:
        return
    dst.executemany(
        """
        INSERT OR IGNORE INTO nlp_posts (
            source, tweet_id, author_id, username, created_at, lang,
            original_text, clean_text, topic_text, stratum,
            sampling_probability, sample_weight, content_class
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def benchmark(src: sqlite3.Connection) -> dict[str, float]:
    log(f"Benchmark: classify+clean+topic on {BENCHMARK_N:,} keyword rows...")
    t0 = time.perf_counter()
    n = 0
    cur = src.execute(
        "SELECT text FROM posts WHERE source='keyword_tweets' LIMIT ?",
        (BENCHMARK_N,),
    )
    classes: Counter[str] = Counter()
    ld_false = 0
    ld_en = 0
    ld_other = 0
    while n < BENCHMARK_N:
        chunk = cur.fetchmany(min(1000, BENCHMARK_N - n))
        if not chunk:
            break
        for (text,) in chunk:
            cls = classify_keyword_text(text)
            classes[cls] += 1
            _ = hash_text(text)
            _ = clean_text(text)
            _ = topic_text(text)
            det = detect_language(text)
            if det["detect_status"] in {"detected", "low_confidence"}:
                if det["detected_lang"] == "en":
                    ld_en += 1
                elif det["detected_lang"] in FALSE_FRIEND_LANGS:
                    ld_false += 1
                else:
                    ld_other += 1
            n += 1
    elapsed = time.perf_counter() - t0
    per = elapsed / max(n, 1)
    log(f"  {n:,} rows in {elapsed:.1f}s ({per*1000:.2f} ms/row)")
    log(f"  classes={dict(classes)}")
    log(f"  langdetect on same rows: en={ld_en} false_friend={ld_false} other={ld_other}")
    return {
        "n": float(n),
        "seconds": elapsed,
        "ms_per_row": per * 1000,
        "est_keyword_classify_min": (per * 1_129_607) / 60,
        "ld_en": float(ld_en),
        "ld_false": float(ld_false),
        "ld_other": float(ld_other),
        "ld_n": float(n),
    }


def load_users(src: sqlite3.Connection) -> dict[str, str]:
    return {r[0]: r[1] for r in src.execute("SELECT author_id, username FROM users")}


def keyword_pass1(src: sqlite3.Connection) -> dict[str, Any]:
    log("Keyword pass 1/2: classify + hash all 1,129,607 posts (no langdetect)...")
    t0 = time.perf_counter()
    class_n: Counter[str] = Counter()
    hash_n: Counter[str] = Counter()
    hash_best: dict[str, str] = {}
    n = 0
    cur = src.execute(
        "SELECT tweet_id, text FROM posts WHERE source='keyword_tweets'"
    )
    while True:
        chunk = cur.fetchmany(CHUNK)
        if not chunk:
            break
        for tweet_id, text in chunk:
            n += 1
            digest = hash_text(text)
            cls = classify_keyword_text(text)
            class_n[cls] += 1
            hash_n[digest] += 1
            prev = hash_best.get(digest)
            if prev is None or str(tweet_id) < prev:
                hash_best[digest] = str(tweet_id)
            if n % PROGRESS == 0:
                log(f"  keyword pass1 {n:,}")
    extra = sum(v - 1 for v in hash_n.values() if v > 1)
    groups = sum(1 for v in hash_n.values() if v > 1)
    boiler_posts = sum(v for v in hash_n.values() if v >= BOILERPLATE_MIN)
    boiler_groups = sum(1 for v in hash_n.values() if v >= BOILERPLATE_MIN)
    log(
        f"  done n={n:,} extra_dups={extra:,} boiler_posts(>={BOILERPLATE_MIN})={boiler_posts:,} "
        f"in {time.perf_counter()-t0:.1f}s"
    )
    return {
        "n": n,
        "class_n": class_n,
        "hash_n": hash_n,
        "hash_best": hash_best,
        "dup_extra": extra,
        "dup_groups": groups,
        "boiler_posts": boiler_posts,
        "boiler_groups": boiler_groups,
    }


def keyword_eligible(tweet_id: str, digest: str, cls: str, hash_n: Counter[str], hash_best: dict[str, str]) -> bool:
    if cls != "likely_english":
        return False
    freq = hash_n[digest]
    if freq >= BOILERPLATE_MIN:
        return False
    if freq >= 2 and hash_best.get(digest) != str(tweet_id):
        return False
    return True


def keyword_pass2(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    users: dict[str, str],
    meta: dict[str, Any],
) -> dict[str, Any]:
    log("Keyword pass 2/2: write eligible English unique/near-unique posts...")
    t0 = time.perf_counter()
    hash_n = meta["hash_n"]
    hash_best = meta["hash_best"]
    n_written = 0
    n_skip_short_topic = 0
    authors: set[str] = set()
    min_iso = max_iso = None
    batch: list[tuple] = []
    n = 0
    cur = src.execute(
        "SELECT tweet_id, author_id, created_at, text FROM posts WHERE source='keyword_tweets'"
    )
    dst.execute("BEGIN")
    while True:
        chunk = cur.fetchmany(CHUNK)
        if not chunk:
            break
        for tweet_id, author_id, created_at, text in chunk:
            n += 1
            digest = hash_text(text)
            cls = classify_keyword_text(text)
            if not keyword_eligible(str(tweet_id), digest, cls, hash_n, hash_best):
                continue
            clean = clean_text(text)
            topic = topic_text(text)
            if len(clean.split()) < 3:
                n_skip_short_topic += 1
                continue
            q = quarter_of(created_at)
            stratum = f"keyword|{q}|census"
            batch.append(
                (
                    "keyword_tweets",
                    str(tweet_id),
                    author_id,
                    users.get(author_id, ""),
                    created_at,
                    "en",
                    text,
                    clean,
                    topic,
                    stratum,
                    1.0,
                    1.0,
                    cls,
                )
            )
            authors.add(author_id)
            n_written += 1
            if min_iso is None or created_at < min_iso:
                min_iso = created_at
            if max_iso is None or created_at > max_iso:
                max_iso = created_at
            if len(batch) >= INSERT_SIZE:
                insert_posts(dst, batch)
                batch.clear()
            if n % PROGRESS == 0:
                log(f"  keyword pass2 scanned={n:,} written={n_written:,}")
    insert_posts(dst, batch)
    dst.commit()
    log(
        f"  written={n_written:,} authors={len(authors):,} "
        f"skip_short_clean={n_skip_short_topic:,} in {time.perf_counter()-t0:.1f}s"
    )
    return {
        "n_written": n_written,
        "n_authors": len(authors),
        "n_skip_short": n_skip_short_topic,
        "min_iso": min_iso,
        "max_iso": max_iso,
    }


def timeline_author_counts(src: sqlite3.Connection) -> dict[str, int]:
    log("Timeline: counting English posts per author...")
    t0 = time.perf_counter()
    counts: Counter[str] = Counter()
    n = 0
    cur = src.execute(
        "SELECT author_id FROM posts WHERE source='timeline' AND lang='en'"
    )
    while True:
        chunk = cur.fetchmany(CHUNK)
        if not chunk:
            break
        for (author_id,) in chunk:
            counts[author_id] += 1
            n += 1
            if n % 1_000_000 == 0:
                log(f"  en author counts {n:,}")
    log(f"  {n:,} en timeline posts, {len(counts):,} authors in {time.perf_counter()-t0:.1f}s")
    return dict(counts)


def tertiles(values: list[int]) -> tuple[int, int]:
    if not values:
        return 0, 0
    xs = sorted(values)
    n = len(xs)
    t1 = xs[max(0, n // 3 - 1)]
    t2 = xs[max(0, (2 * n) // 3 - 1)]
    return t1, t2


def timeline_stratum_counts(
    src: sqlite3.Connection, activity: dict[str, str]
) -> tuple[Counter[str], int]:
    log("Timeline: counting English posts per quarter x activity stratum...")
    t0 = time.perf_counter()
    counts: Counter[str] = Counter()
    n = 0
    cur = src.execute(
        "SELECT author_id, created_at FROM posts WHERE source='timeline' AND lang='en'"
    )
    while True:
        chunk = cur.fetchmany(CHUNK)
        if not chunk:
            break
        for author_id, created_at in chunk:
            act = activity.get(author_id, "low")
            s = f"timeline|{quarter_of(created_at)}|{act}"
            counts[s] += 1
            n += 1
            if n % 1_000_000 == 0:
                log(f"  stratum counts {n:,}")
    log(f"  {n:,} rows, {len(counts):,} strata in {time.perf_counter()-t0:.1f}s")
    return counts, n


def allocate_strata(counts: Counter[str], target: int) -> dict[str, int]:
    total = sum(counts.values())
    if total == 0:
        return {}
    take = min(target, total)
    raw = {s: take * n / total for s, n in counts.items()}
    need = {s: int(math.floor(v)) for s, v in raw.items()}
    need = {s: min(counts[s], max(1, k) if counts[s] else 0) for s, k in need.items()}
    # fix sum
    diff = take - sum(need.values())
    order = sorted(counts, key=lambda s: (raw[s] - need[s]), reverse=(diff > 0))
    i = 0
    while diff != 0 and order:
        s = order[i % len(order)]
        if diff > 0 and need[s] < counts[s]:
            need[s] += 1
            diff -= 1
        elif diff < 0 and need[s] > 1:
            need[s] -= 1
            diff += 1
        i += 1
        if i > len(order) * 3:
            break
    return need


def timeline_sample_write(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    users: dict[str, str],
    activity: dict[str, str],
    pop: Counter[str],
    need: dict[str, int],
    rng: random.Random,
) -> dict[str, Any]:
    log("Timeline: drawing stratified sample and writing NLP rows...")
    t0 = time.perf_counter()
    seen: Counter[str] = Counter()
    taken: Counter[str] = Counter()
    n = 0
    n_written = 0
    authors: set[str] = set()
    min_iso = max_iso = None
    batch: list[tuple] = []
    cur = src.execute(
        """
        SELECT tweet_id, author_id, created_at, text, lang
        FROM posts
        WHERE source='timeline' AND lang='en'
        """
    )
    dst.execute("BEGIN")
    while True:
        chunk = cur.fetchmany(CHUNK)
        if not chunk:
            break
        for tweet_id, author_id, created_at, text, lang in chunk:
            n += 1
            s = f"timeline|{quarter_of(created_at)}|{activity.get(author_id, 'low')}"
            seen[s] += 1
            n_s = pop.get(s, 0)
            k_s = need.get(s, 0)
            left_pop = n_s - seen[s] + 1
            left_need = k_s - taken[s]
            keep = False
            if left_need > 0 and left_pop > 0:
                if rng.random() < (left_need / left_pop):
                    keep = True
            if keep:
                clean = clean_text(text)
                topic = topic_text(text)
                p = (k_s / n_s) if n_s else 0.0
                w = (n_s / k_s) if k_s else 0.0
                batch.append(
                    (
                        "timeline",
                        str(tweet_id),
                        author_id,
                        users.get(author_id, ""),
                        created_at,
                        lang,
                        text,
                        clean,
                        topic,
                        s,
                        p,
                        w,
                        "timeline_en",
                    )
                )
                taken[s] += 1
                n_written += 1
                authors.add(author_id)
                if min_iso is None or created_at < min_iso:
                    min_iso = created_at
                if max_iso is None or created_at > max_iso:
                    max_iso = created_at
                if len(batch) >= INSERT_SIZE:
                    insert_posts(dst, batch)
                    batch.clear()
            if n % 1_000_000 == 0:
                log(f"  timeline sample scanned={n:,} written={n_written:,}")
    insert_posts(dst, batch)
    dst.commit()
    log(
        f"  written={n_written:,} authors={len(authors):,} "
        f"in {time.perf_counter()-t0:.1f}s"
    )
    return {
        "n_written": n_written,
        "n_authors": len(authors),
        "n_scanned": n,
        "taken": taken,
        "min_iso": min_iso,
        "max_iso": max_iso,
    }


def write_plan(stats: dict[str, Any]) -> None:
    census_lines = "\n".join(
        f"| {r['category']} | {int(r['n']):,} | {r['pct']}% | {r['notes']} |"
        for r in stats["census_rows"]
    )
    text = f"""# NLP sampling plan

Built: {stats['built_at']}
Random seed: **{RNG_SEED}**
QA sample `data/nlp_working_sample.db` (**7,428 retained rows**) was **not** used as the analysis corpus. It remains a debug file only.
`IFB.db` and `data/analysis_corpus.db` were not modified.

## Why this sample is large enough for the course

The course BERTopic instructions say: if you have only tens of thousands of posts, tune on all of them; otherwise tune on 10% then apply. This corpus has **{stats['n_total']:,}** English NLP posts ({stats['n_keyword']:,} keyword + {stats['n_timeline']:,} timeline). That is:

- larger than typical course datasets in the grading workbook (often 100k–400k posts);
- small enough to run `pysentimiento` and BERTopic on a further 10% tune split;
- drawn from **all 38,576** primary users’ keyword stream (census of eligible tweets) plus a **probability sample** of their English timeline history.

A 7k QA sample cannot support topic modeling, event detection, or bot-text features. Half a million+ timeline posts plus every eligible keyword tweet can.

## User-selection and sources

Same 38,576 unambiguous triple-intersection users as `CORPUS_MANIFEST.md`.

| Source | Rule |
|--------|------|
| Keyword tweets | **Census** of posts classified `likely_english`, excluding IFB-dominated templates, hash-boilerplate (freq ≥ {BOILERPLATE_MIN}), and extra copies of duplicated text. `sampling_probability = 1`, `sample_weight = 1`. |
| Timeline | **Only `LANG = en`**. Stratified sample, target {TARGET_TIMELINE:,}. |

## Exact counts

| Item | N |
|------|--:|
| Eligible keyword posts in NLP corpus | **{stats['n_keyword']:,}** |
| Sampled English timeline posts | **{stats['n_timeline']:,}** |
| **Total NLP posts** | **{stats['n_total']:,}** |
| Users with ≥1 NLP post | **{stats['n_users']:,}** |
| Users with ≥1 keyword NLP post | {stats['n_kw_users']:,} |
| Users with ≥1 timeline NLP post | {stats['n_tl_users']:,} |

## Keyword census (all {stats['n_kw_scanned']:,} keyword tweets)

Deterministic rules (Unicode script + IFB-stripped remainder). **langdetect was not used for these counts.**

| category | n | pct | notes |
|----------|--:|----:|-------|
{census_lines}

Duplicate handling: normalized SHA1 of lowercase text without URLs/mentions/emojis. Groups with frequency ≥ {BOILERPLATE_MIN} are **boilerplate** (all copies dropped). Groups of size 2–4 keep **one** tweet (lowest `tweet_id`) if it is `likely_english`.

## Timeline sampling method

1. Count English (`LANG=en`) posts per author.
2. Split authors into activity tertiles: low / mid / high (cuts at {stats['t1']} and {stats['t2']} English timeline posts).
3. Count posts in each stratum `timeline|{{quarter}}|{{activity}}`.
4. Allocate {TARGET_TIMELINE:,} seats **proportional** to stratum size (at least 1 if the stratum is non-empty).
5. Second pass: sequential sampling with exact quota, `random.Random({RNG_SEED})`.
6. `sampling_probability = n_sampled / n_population` within the stratum; `sample_weight = 1 / p`.

Quarters are used instead of months so 2007–2010 sparse months are not empty cells. Source is encoded in the stratum prefix (`timeline` vs `keyword`).

English timeline population: **{stats['n_en_timeline']:,}**. Sample fraction ≈ {stats['tl_fraction']:.4%}.

## Exclusions

| Reason | Where |
|--------|--------|
| IFB-dominated (too little signal after removing follow/IFB terms) | Keyword census, not in NLP corpus |
| Script-confirmed non-English | Keyword census only; no translation this phase |
| Uncertain Latin/mixed | Keyword census, not in NLP corpus |
| Duplicate extras / boilerplate templates | Keyword, not in NLP corpus |
| `clean_text` fewer than 3 tokens | Dropped at write time ({stats['kw_skip_short']:,} keyword). Timeline posts are kept even if clean/topic is empty after stripping. |
| Timeline not `LANG=en` | Never sampled (`und/qme/qam/zxx` and other languages excluded from English NLP) |
| Ambiguous AUTHOR_IDs / non-primary users | Already absent from `analysis_corpus.db` |

## Language uncertainty

- Keyword `lang` in the NLP table is set to `en` **only** for the rule-based `likely_english` class (Latin remainder after IFB strip).
- langdetect **false friends** (`no`, `af`, `ca`, `so`, `cy`, `nl`, …) on IFB spam are documented in the 5,000-row benchmark: {stats['ld_false']:.0f} false-friend vs {stats['ld_en']:.0f} `en` vs {stats['ld_other']:.0f} other among {stats['ld_n']:.0f} benchmark rows. Those codes are **not** used to include/exclude the full 1.13M.
- Timeline English uses Twitter `LANG=en` only.

## Benchmark

{stats['bench_n']:.0f} keyword rows: {stats['bench_s']:.1f}s ({stats['bench_ms']:.2f} ms/row). Estimated classify+clean over 1.13M ≈ {stats['est_min']:.0f} minutes (order of magnitude; hashing-only pass is faster).

## Files

- `data/nlp_analysis_corpus.db` — analysis corpus (SQLite)
- `data/nlp_working_sample.db` — QA only, unchanged
- `outputs/full_keyword_language_census.csv`
- `outputs/nlp_corpus_statistics.csv`

Primary key is `(source, tweet_id)` so the 42,371 cross-source ID overlaps stay distinct rows.
"""
    PLAN.write_text(text, encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    rng = random.Random(RNG_SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not QA_DB.exists():
        log("WARNING: QA db missing; continuing anyway.")
    else:
        log(f"Leaving QA file untouched: {QA_DB}")

    log(f"Opening {CORPUS_DB} read-only...")
    src = connect_ro(CORPUS_DB)
    dst = None
    try:
        bench = benchmark(src)
        log(
            f"ESTIMATE: full keyword classify+clean ~ {bench['est_keyword_classify_min']:.1f} min; "
            f"plus two light timeline count passes and one 500k write pass."
        )
        log("Building final NLP corpus (not the QA sample)...")
        users = load_users(src)
        dst = open_nlp_db(NLP_DB)

        kw1 = keyword_pass1(src)
        kw2 = keyword_pass2(src, dst, users, kw1)

        author_n = timeline_author_counts(src)
        t1, t2 = tertiles(list(author_n.values()))
        activity = {aid: activity_level(n, t1, t2) for aid, n in author_n.items()}
        pop, n_en = timeline_stratum_counts(src, activity)
        need = allocate_strata(pop, TARGET_TIMELINE)
        tl = timeline_sample_write(src, dst, users, activity, pop, need, rng)

        # users table
        dst.execute("BEGIN")
        used = {
            r[0]
            for r in dst.execute("SELECT DISTINCT author_id FROM nlp_posts")
        }
        dst.executemany(
            "INSERT OR REPLACE INTO nlp_users (author_id, username, en_timeline_posts, activity_level) "
            "VALUES (?, ?, ?, ?)",
            [
                (aid, users.get(aid, ""), author_n.get(aid, 0), activity.get(aid, ""))
                for aid in used
            ],
        )
        for s, n_pop in pop.items():
            k = need.get(s, 0)
            p = (k / n_pop) if n_pop else 0.0
            w = (n_pop / k) if k else 0.0
            dst.execute(
                "INSERT OR REPLACE INTO strata "
                "(stratum, source, n_population, n_sampled, sampling_probability, sample_weight) "
                "VALUES (?, 'timeline', ?, ?, ?, ?)",
                (s, n_pop, tl["taken"].get(s, 0), p, w),
            )
        dst.commit()
        dst.execute("CREATE INDEX IF NOT EXISTS idx_nlp_author ON nlp_posts(author_id)")
        dst.execute("CREATE INDEX IF NOT EXISTS idx_nlp_source ON nlp_posts(source)")
        dst.execute("CREATE INDEX IF NOT EXISTS idx_nlp_created ON nlp_posts(created_at)")
        dst.commit()

        n_kw = dst.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE source='keyword_tweets'"
        ).fetchone()[0]
        n_tl = dst.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE source='timeline'"
        ).fetchone()[0]
        n_total = n_kw + n_tl
        n_users = dst.execute("SELECT COUNT(*) FROM nlp_users").fetchone()[0]
        n_kw_users = dst.execute(
            "SELECT COUNT(DISTINCT author_id) FROM nlp_posts WHERE source='keyword_tweets'"
        ).fetchone()[0]
        n_tl_users = dst.execute(
            "SELECT COUNT(DISTINCT author_id) FROM nlp_posts WHERE source='timeline'"
        ).fetchone()[0]
    finally:
        src.close()
        if dst is not None:
            dst.close()

    n_all = kw1["n"] or 1
    census_rows = []

    def add_cat(cat, n, notes):
        census_rows.append(
            {
                "category": cat,
                "n": n,
                "pct": round(100.0 * n / n_all, 4),
                "notes": notes,
            }
        )

    cn = kw1["class_n"]
    add_cat("all_keyword_tweets", kw1["n"], "full scan")
    add_cat("ifb_dominated", cn["ifb_dominated"], "too little signal after IFB/follow strip")
    add_cat("likely_english", cn["likely_english"], "Latin remainder after IFB strip; not langdetect")
    add_cat("script_non_english", cn["script_non_english"], "Unicode script confirmed")
    add_cat("uncertain", cn["uncertain"], "mixed/low Latin ratio")
    add_cat("empty", cn["empty"], "empty original")
    add_cat("duplicate_extra_rows", kw1["dup_extra"], "normalized hash extras (count-1)")
    add_cat("duplicate_groups", kw1["dup_groups"], "hashes with freq>=2")
    add_cat(
        "boilerplate_posts_freq_ge5",
        kw1["boiler_posts"],
        f"all copies excluded from NLP (freq>={BOILERPLATE_MIN})",
    )
    add_cat("boilerplate_groups_freq_ge5", kw1["boiler_groups"], "")
    add_cat("eligible_keyword_written", kw2["n_written"], "likely_english, not boiler, not dup extra, clean>=3")
    add_cat("eligible_dropped_short_clean", kw2["n_skip_short"], "likely english but clean_text < 3 tokens")
    write_csv(CENSUS_CSV, ["category", "n", "pct", "notes"], census_rows)

    stat_rows = [
        {"metric": "rng_seed", "value": RNG_SEED, "notes": ""},
        {"metric": "qa_db_untouched", "value": str(QA_DB.name), "notes": "not the analysis corpus"},
        {"metric": "n_keyword_nlp", "value": n_kw, "notes": "census of eligible keyword tweets"},
        {"metric": "n_timeline_nlp", "value": n_tl, "notes": f"stratified LANG=en target {TARGET_TIMELINE}"},
        {"metric": "n_nlp_posts_total", "value": n_total, "notes": ""},
        {"metric": "n_nlp_users", "value": n_users, "notes": ""},
        {"metric": "n_users_with_keyword_nlp", "value": n_kw_users, "notes": ""},
        {"metric": "n_users_with_timeline_nlp", "value": n_tl_users, "notes": ""},
        {"metric": "n_english_timeline_population", "value": n_en, "notes": "LANG=en"},
        {"metric": "activity_tertile_low_max", "value": t1, "notes": "en timeline posts"},
        {"metric": "activity_tertile_mid_max", "value": t2, "notes": ""},
        {"metric": "n_timeline_strata", "value": len(pop), "notes": "quarter x activity"},
        {"metric": "keyword_date_min", "value": kw2["min_iso"], "notes": ""},
        {"metric": "keyword_date_max", "value": kw2["max_iso"], "notes": ""},
        {"metric": "timeline_sample_date_min", "value": tl["min_iso"], "notes": ""},
        {"metric": "timeline_sample_date_max", "value": tl["max_iso"], "notes": ""},
        {"metric": "benchmark_rows", "value": int(bench["n"]), "notes": ""},
        {"metric": "benchmark_seconds", "value": round(bench["seconds"], 2), "notes": ""},
        {"metric": "benchmark_ms_per_row", "value": round(bench["ms_per_row"], 3), "notes": "includes langdetect"},
        {"metric": "langdetect_false_friends_in_benchmark", "value": int(bench["ld_false"]), "notes": ",".join(sorted(FALSE_FRIEND_LANGS))},
        {"metric": "langdetect_en_in_benchmark", "value": int(bench["ld_en"]), "notes": ""},
        {"metric": "corpus_db", "value": "data/nlp_analysis_corpus.db", "notes": "SQLite not CSV"},
    ]
    write_csv(STATS_CSV, ["metric", "value", "notes"], stat_rows)

    size_gb = NLP_DB.stat().st_size / 1024**3 if NLP_DB.exists() else 0
    write_plan(
        {
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_keyword": n_kw,
            "n_timeline": n_tl,
            "n_total": n_total,
            "n_users": n_users,
            "n_kw_users": n_kw_users,
            "n_tl_users": n_tl_users,
            "n_kw_scanned": kw1["n"],
            "census_rows": census_rows,
            "t1": t1,
            "t2": t2,
            "n_en_timeline": n_en,
            "tl_fraction": (n_tl / n_en) if n_en else 0,
            "kw_skip_short": kw2["n_skip_short"],
            "ld_false": bench["ld_false"],
            "ld_en": bench["ld_en"],
            "ld_other": bench["ld_other"],
            "ld_n": bench["ld_n"],
            "bench_n": bench["n"],
            "bench_s": bench["seconds"],
            "bench_ms": bench["ms_per_row"],
            "est_min": bench["est_keyword_classify_min"],
        }
    )

    elapsed = time.perf_counter() - started
    log("")
    log("========== NLP CORPUS SUMMARY ==========")
    log(f"eligible_keyword_posts={n_kw}")
    log(f"sampled_timeline_en_posts={n_tl}")
    log(f"total_nlp_posts={n_total}")
    log(f"nlp_users={n_users} kw_users={n_kw_users} tl_users={n_tl_users}")
    log(f"keyword_census={dict(kw1['class_n'])}")
    log(f"dup_extra={kw1['dup_extra']} boiler_posts={kw1['boiler_posts']}")
    log(f"en_timeline_population={n_en} activity_cuts={t1},{t2}")
    log(f"db_gb={size_gb:.2f} elapsed_seconds={elapsed:.1f}")
    log("NLP_CORPUS_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
