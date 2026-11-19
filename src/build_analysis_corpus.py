#!/usr/bin/env python3
"""Build the frozen IFB analysis corpus from IFB.db (read-only).

Writes data/analysis_corpus.db. Does not modify IFB.db.
Does not export tens of millions of rows to CSV.
"""

from __future__ import annotations

import csv
import random
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_coverage_and_normalization import (  # noqa: E402
    ISO_RE,
    NON_LINGUISTIC_LANGS,
    TWITTER_LAUNCH,
    canon_author_id,
    connect_readonly,
    parse_created_at,
    self_check_parser,
)

ROOT = Path(__file__).resolve().parents[1]
IFB_DB = ROOT / "IFB.db"
CORPUS_DB = ROOT / "data" / "analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
SAMPLE_CSV = OUTPUT_DIR / "analysis_corpus_sample.csv"
STATS_CSV = OUTPUT_DIR / "corpus_statistics.csv"
LANG_CSV = OUTPUT_DIR / "language_statistics.csv"
MANIFEST = ROOT / "CORPUS_MANIFEST.md"

CHUNK_SIZE = 25_000
INSERT_SIZE = 5_000
PROGRESS_EVERY = 500_000
KEYWORD_SAMPLE_PER_KW = 120
INSPECT_KEYWORD = 1_200
INSPECT_TL_EN = 500
INSPECT_TL_OTHER = 300
INSPECT_TL_NONLING = 200
RNG_SEED = 2026

SOURCE_KEYWORD = "keyword_tweets"
SOURCE_TIMELINE = "timeline"
LANG_UNKNOWN = "unknown"


def log(message: str) -> None:
    print(message, flush=True)


def to_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        dt, _kind = parse_created_at(value)
        return to_iso(dt) if dt is not None else None
    text = "" if value is None else str(value).strip()
    match = ISO_RE.match(text)
    if match:
        year = int(match.group(1))
        if TWITTER_LAUNCH.year <= year <= 2023:
            return (
                f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                f"T{match.group(4)}:{match.group(5)}:{match.group(6)}"
            )
    dt, _kind = parse_created_at(value)
    return to_iso(dt) if dt is not None else None


def lang_bucket(code: str) -> str:
    c = (code or "").strip().lower()
    if not c or c == LANG_UNKNOWN:
        return "unknown"
    if c == "en":
        return "english"
    if c in NON_LINGUISTIC_LANGS:
        return "non_linguistic"
    return "other_language"


class Reservoir:
    def __init__(self, size: int, rng: random.Random) -> None:
        self.size = size
        self.rng = rng
        self.items: list[Any] = []
        self.seen = 0

    def offer(self, item: Any) -> None:
        self.seen += 1
        if len(self.items) < self.size:
            self.items.append(item)
            return
        j = self.rng.randrange(self.seen)
        if j < self.size:
            self.items[j] = item


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def load_author_maps(src: sqlite3.Connection) -> tuple[dict[str, str], set[str], int]:
    log("Loading authors (IDs and usernames only)...")
    t0 = time.perf_counter()
    counts: Counter[str] = Counter()
    last_username: dict[str, str] = {}
    n_rows = 0
    cur = src.execute("SELECT CAST(AUTHOR_ID AS TEXT), USERNAME FROM authors")
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for raw_id, username in chunk:
            n_rows += 1
            author_id = canon_author_id(raw_id)
            if not author_id:
                continue
            counts[author_id] += 1
            last_username[author_id] = "" if username is None else str(username)
    ambiguous = {aid for aid, n in counts.items() if n > 1}
    unambiguous = {aid: last_username[aid] for aid, n in counts.items() if n == 1}
    log(
        f"  authors rows={n_rows:,} unique={len(counts):,} "
        f"unambiguous={len(unambiguous):,} ambiguous={len(ambiguous):,} "
        f"in {time.perf_counter() - t0:.1f}s"
    )
    return unambiguous, ambiguous, n_rows


def open_corpus_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    conn.execute("BEGIN")
    conn.execute(
        """
        CREATE TABLE users (
            author_id TEXT PRIMARY KEY,
            username TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE posts (
            tweet_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            text TEXT,
            lang TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE keyword_lang_sample (
            tweet_id TEXT PRIMARY KEY,
            author_id TEXT,
            username TEXT,
            created_at TEXT,
            text TEXT,
            lang TEXT,
            source TEXT,
            keyword TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIEW corpus AS
        SELECT p.tweet_id,
               p.author_id,
               u.username,
               p.created_at,
               p.text,
               p.lang,
               p.source
        FROM posts p
        JOIN users u ON u.author_id = p.author_id
        """
    )
    return conn


def insert_posts(dst: sqlite3.Connection, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    dst.executemany(
        "INSERT OR IGNORE INTO posts (tweet_id, author_id, created_at, text, lang, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def scan_timeline(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    unambiguous: dict[str, str],
    rng: random.Random,
) -> dict[str, Any]:
    log("Scanning timeline and writing matching posts...")
    t0 = time.perf_counter()
    primary: set[str] = set()
    n_seen = 0
    n_written = 0
    n_excluded_id = 0
    n_excluded_date = 0
    lang_counts: Counter[str] = Counter()
    min_iso: str | None = None
    max_iso: str | None = None
    sample_en = Reservoir(INSPECT_TL_EN, rng)
    sample_other = Reservoir(INSPECT_TL_OTHER, rng)
    sample_nonling = Reservoir(INSPECT_TL_NONLING, rng)
    batch: list[tuple[Any, ...]] = []

    cur = src.execute(
        "SELECT CAST(TWEET_ID AS TEXT), CAST(AUTHOR_ID AS TEXT), CREATED_AT, TWEET, LANG "
        "FROM timeline"
    )
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for tweet_id, raw_author, created_at, text, lang in chunk:
            n_seen += 1
            author_id = canon_author_id(raw_author)
            if author_id not in unambiguous:
                n_excluded_id += 1
                if n_seen % PROGRESS_EVERY == 0:
                    log(f"  timeline seen={n_seen:,} written={n_written:,}")
                continue
            iso = normalize_datetime(created_at)
            if iso is None:
                n_excluded_date += 1
                continue
            lang_code = LANG_UNKNOWN if lang is None else str(lang).strip() or LANG_UNKNOWN
            batch.append((str(tweet_id), author_id, iso, text, lang_code, SOURCE_TIMELINE))
            primary.add(author_id)
            lang_counts[lang_code] += 1
            n_written += 1
            if min_iso is None or iso < min_iso:
                min_iso = iso
            if max_iso is None or iso > max_iso:
                max_iso = iso
            row = {
                "tweet_id": str(tweet_id),
                "author_id": author_id,
                "username": unambiguous[author_id],
                "created_at": iso,
                "text": text,
                "lang": lang_code,
                "source": SOURCE_TIMELINE,
            }
            bucket = lang_bucket(lang_code)
            if bucket == "english":
                sample_en.offer(row)
            elif bucket == "non_linguistic":
                sample_nonling.offer(row)
            else:
                sample_other.offer(row)
            if len(batch) >= INSERT_SIZE:
                insert_posts(dst, batch)
                batch.clear()
            if n_seen % PROGRESS_EVERY == 0:
                log(f"  timeline seen={n_seen:,} written={n_written:,} users={len(primary):,}")
    insert_posts(dst, batch)
    dst.commit()
    dst.execute("BEGIN")
    log(
        f"  timeline written={n_written:,} primary_users={len(primary):,} "
        f"excluded_id={n_excluded_id:,} excluded_date={n_excluded_date:,} "
        f"in {time.perf_counter() - t0:.1f}s"
    )
    return {
        "n_seen": n_seen,
        "n_written": n_written,
        "n_excluded_id": n_excluded_id,
        "n_excluded_date": n_excluded_date,
        "primary": primary,
        "lang_counts": lang_counts,
        "min_iso": min_iso,
        "max_iso": max_iso,
        "inspect_rows": sample_en.items + sample_other.items + sample_nonling.items,
    }


def scan_tweets(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    unambiguous: dict[str, str],
    primary: set[str],
    rng: random.Random,
) -> dict[str, Any]:
    log("Scanning keyword tweets and writing matching posts...")
    t0 = time.perf_counter()
    n_seen = 0
    n_written = 0
    n_excluded_id = 0
    n_excluded_date = 0
    n_users_with_kw = 0
    users_hit: set[str] = set()
    min_iso: str | None = None
    max_iso: str | None = None
    samples_by_kw: dict[str, Reservoir] = {}
    batch: list[tuple[Any, ...]] = []

    cur = src.execute(
        "SELECT CAST(TWEET_ID AS TEXT), CAST(AUTHOR_ID AS TEXT), CREATED_AT, TWEET_CONTENT, KEYWORD "
        "FROM tweets"
    )
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for tweet_id, raw_author, created_at, text, keyword in chunk:
            n_seen += 1
            author_id = canon_author_id(raw_author)
            if author_id not in primary:
                n_excluded_id += 1
                if n_seen % PROGRESS_EVERY == 0:
                    log(f"  tweets seen={n_seen:,} written={n_written:,}")
                continue
            iso = normalize_datetime(created_at)
            if iso is None:
                n_excluded_date += 1
                continue
            batch.append((str(tweet_id), author_id, iso, text, LANG_UNKNOWN, SOURCE_KEYWORD))
            users_hit.add(author_id)
            n_written += 1
            if min_iso is None or iso < min_iso:
                min_iso = iso
            if max_iso is None or iso > max_iso:
                max_iso = iso
            kw = "" if keyword is None else str(keyword).strip()
            bucket = samples_by_kw.get(kw)
            if bucket is None:
                bucket = Reservoir(KEYWORD_SAMPLE_PER_KW, rng)
                samples_by_kw[kw] = bucket
            bucket.offer(
                {
                    "tweet_id": str(tweet_id),
                    "author_id": author_id,
                    "username": unambiguous[author_id],
                    "created_at": iso,
                    "text": text,
                    "lang": LANG_UNKNOWN,
                    "source": SOURCE_KEYWORD,
                    "keyword": kw,
                }
            )
            if len(batch) >= INSERT_SIZE:
                insert_posts(dst, batch)
                batch.clear()
            if n_seen % PROGRESS_EVERY == 0:
                log(f"  tweets seen={n_seen:,} written={n_written:,}")
    insert_posts(dst, batch)
    n_users_with_kw = len(users_hit)
    kw_sample = [row for res in samples_by_kw.values() for row in res.items]
    if kw_sample:
        dst.executemany(
            "INSERT OR REPLACE INTO keyword_lang_sample "
            "(tweet_id, author_id, username, created_at, text, lang, source, keyword) "
            "VALUES (:tweet_id, :author_id, :username, :created_at, :text, :lang, :source, :keyword)",
            kw_sample,
        )
    dst.commit()
    dst.execute("BEGIN")
    log(
        f"  keyword written={n_written:,} users_with_keyword_tweets={n_users_with_kw:,} "
        f"lang_sample={len(kw_sample):,} excluded_id={n_excluded_id:,} "
        f"excluded_date={n_excluded_date:,} in {time.perf_counter() - t0:.1f}s"
    )
    return {
        "n_seen": n_seen,
        "n_written": n_written,
        "n_excluded_id": n_excluded_id,
        "n_excluded_date": n_excluded_date,
        "n_users_with_kw": n_users_with_kw,
        "users_hit": users_hit,
        "min_iso": min_iso,
        "max_iso": max_iso,
        "kw_sample": kw_sample,
        "n_keywords_sampled": len(samples_by_kw),
    }


def count_cross_source_duplicates(dst: sqlite3.Connection) -> tuple[int, list[str]]:
    log("Indexing corpus and checking cross-source tweet_id overlap...")
    t0 = time.perf_counter()
    dst.execute("CREATE INDEX IF NOT EXISTS idx_posts_tweet_id ON posts(tweet_id)")
    dst.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id)")
    dst.execute("CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source)")
    dst.execute("CREATE INDEX IF NOT EXISTS idx_posts_lang ON posts(lang)")
    dst.commit()
    n = dst.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT tweet_id FROM posts WHERE source = ?
            INTERSECT
            SELECT tweet_id FROM posts WHERE source = ?
        )
        """,
        (SOURCE_KEYWORD, SOURCE_TIMELINE),
    ).fetchone()[0]
    examples = [
        row[0]
        for row in dst.execute(
            """
            SELECT tweet_id FROM posts WHERE source = ?
            INTERSECT
            SELECT tweet_id FROM posts WHERE source = ?
            LIMIT 10
            """,
            (SOURCE_KEYWORD, SOURCE_TIMELINE),
        )
    ]
    log(f"  cross-source duplicate tweet_ids={n:,} in {time.perf_counter() - t0:.1f}s")
    return int(n), examples


def write_manifest(stats: dict[str, Any]) -> None:
    examples = stats["dup_examples"]
    example_txt = ", ".join(examples) if examples else "(none)"
    lang_lines = "\n".join(
        f"| `{code}` | {n:,} | {100.0 * n / stats['n_timeline']:.4f}% |"
        for code, n in stats["lang_top"]
    )
    text = f"""# Corpus manifest

Built: {stats['built_at']}
Source database: `IFB.db` (read-only; not modified)
Corpus database: `data/analysis_corpus.db`

No full CSV dump of tens of millions of rows was written. Inspection files are small UTF-8 CSVs plus this manifest.

## User-selection rule

A user is included if and only if all of the following hold, using `CAST(AUTHOR_ID AS TEXT)` / `canon_author_id`:

1. The ID appears **exactly once** in `authors` (ambiguous duplicate `AUTHOR_ID` groups are dropped).
2. The ID appears in `timeline`.
3. The ID therefore also appears in `tweets` (coverage showed `authors` ⊂ `tweets` authors; keyword posts are still filtered to this ID set).

`USERNAME` is taken from the single `authors` row for that ID. It is a display label, not a join key.

## Counts

| Item | Value |
|------|------:|
| Users | {stats['n_users']:,} |
| Keyword tweets (`source = keyword_tweets`) | {stats['n_keyword']:,} |
| Timeline tweets (`source = timeline`) | {stats['n_timeline']:,} |
| Total posts in corpus | {stats['n_posts']:,} |
| Users with at least one keyword tweet | {stats['n_users_with_kw']:,} |
| Ambiguous AUTHOR_ID groups excluded | {stats['n_ambiguous']:,} |
| Timeline rows skipped (not in unambiguous authors) | {stats['tl_excluded_id']:,} |
| Timeline rows skipped (unparseable date) | {stats['tl_excluded_date']:,} |
| Keyword rows skipped (author not in primary set) | {stats['kw_excluded_id']:,} |
| Keyword rows skipped (unparseable date) | {stats['kw_excluded_date']:,} |

Expected from `DATASET_DECISION.md`: 38,576 users; 1,129,607 keyword tweets; 37,839,416 timeline tweets. Date exclusions can reduce post counts slightly.

## Date range

Dates are stored as ISO-8601 `YYYY-MM-DDTHH:MM:SS` (no timezone; values treated as naive UTC as stored).

| Source | Minimum | Maximum |
|--------|---------|---------|
| keyword_tweets | {stats['kw_min']} | {stats['kw_max']} |
| timeline | {stats['tl_min']} | {stats['tl_max']} |
| combined | {stats['all_min']} | {stats['all_max']} |

Parser: Unix milliseconds/seconds, `YY-MM-DD Weekday HH:MM:SS`, and ISO datetimes. Placeholders (`1970-01-01`), pre-Twitter dates, and dates in 2024+ are excluded.

## Duplicate handling

- Within a source, uniqueness is enforced by `PRIMARY KEY (source, tweet_id)`. Inserts use `INSERT OR IGNORE`.
- Cross-source `tweet_id` overlap (same ID in both `keyword_tweets` and `timeline`): **{stats['n_cross_dup']:,}**
- Example overlapping IDs: {example_txt}
- Overlapping IDs are **kept in both sources** (they are different rows: keyword seed tweet vs timeline copy). Downstream joins on `tweet_id` alone must also filter `source`.

## Language handling

- `timeline.lang`: original `LANG` value, trimmed. Empty/NULL stored as `unknown` (should be rare).
- `keyword_tweets.lang`: always `{LANG_UNKNOWN}`. Keyword tweets have **no** `LANG` column. They are **not** assumed to be English.
- Non-linguistic Twitter codes `und`, `qme`, `qam`, `zxx` are preserved as-is on timeline rows and are **not** English.
- A stratified keyword sample (`keyword_lang_sample` table, {stats['n_kw_sample']:,} rows) is stored for later language detection or manual inspection. No detector was run in this step.

### Timeline language totals (corpus)

| LANG | Rows | Percent of timeline |
|------|------:|--------------------:|
{lang_lines}

## Physical schema (`data/analysis_corpus.db`)

`users`

| Column | Type | Notes |
|--------|------|-------|
| author_id | TEXT PRIMARY KEY | Canonical `CAST(AUTHOR_ID AS TEXT)` |
| username | TEXT | From `authors.USERNAME` |

`posts`

| Column | Type | Notes |
|--------|------|-------|
| tweet_id | TEXT | `CAST(TWEET_ID AS TEXT)` |
| author_id | TEXT | FK logically to `users` |
| created_at | TEXT | ISO `YYYY-MM-DDTHH:MM:SS` |
| text | TEXT | `tweets.TWEET_CONTENT` or `timeline.TWEET` |
| lang | TEXT | original timeline LANG, or `unknown` for keyword tweets |
| source | TEXT | `keyword_tweets` or `timeline` |
| PRIMARY KEY | (source, tweet_id) | |

`corpus` **view** exposes the required analysis columns:

`tweet_id, author_id, username, created_at, text, lang, source`

`keyword_lang_sample`: inspection/language-detection sample of keyword tweets (includes `keyword`).

## Included vs excluded

**Included**

- Unambiguous authors who appear in `timeline` (and therefore in the triple intersection).
- All parseable timeline tweets of those users.
- All parseable keyword tweets of those users.

**Excluded**

- 1,203 ambiguous `AUTHOR_ID` groups and all of their posts.
- Authors in `authors` with no timeline (~535k IDs).
- Keyword-only authors with no `authors` row (~1.54M IDs).
- Timeline authors not in unambiguous `authors`.
- Rows with unparseable / placeholder dates.

## Inspection files (not the full corpus)

- `outputs/analysis_corpus_sample.csv` — small UTF-8 mixed sample (keyword + timeline).
- `outputs/corpus_statistics.csv` — counts and date ranges.
- `outputs/language_statistics.csv` — language census.

## Limitations (must stay in later reports)

- **Missing language on keyword tweets.** `lang = unknown`. Do not treat them as English until a detector is run on the keyword sample / full keyword set.
- **No follower graph.** Only follower/following *counts* exist on `authors`.
- **No conversation IDs.** No `in_reply_to` / quoted tweet fields.
- **No native retweet indicator.** `timeline.RETWEETS` is a count; keyword tweets have no engagement fields. `RT @` in text is a weak proxy only.
- **Scale.** The SQLite corpus holds tens of millions of timeline rows. Translation, sentiment, and BERTopic must sample from this file; do not export it all to CSV.
- **Mixed original schemas.** IDs were cast to text; dates were parsed; `LOACATION` is unused here.

## Reproducibility

```
python src/build_analysis_corpus.py
```

RNG seed for samples: {RNG_SEED}.
"""
    MANIFEST.write_text(text, encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    self_check_parser()
    rng = random.Random(RNG_SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Opening {IFB_DB} read-only...")
    try:
        src = connect_readonly(IFB_DB)
    except Exception as exc:
        log(f"FAILED to open IFB.db: {type(exc).__name__}: {exc}")
        return 1

    dst = None
    try:
        unambiguous, ambiguous, n_author_rows = load_author_maps(src)
        dst = open_corpus_db(CORPUS_DB)
        tl = scan_timeline(src, dst, unambiguous, rng)
        primary = tl["primary"]
        kw = scan_tweets(src, dst, unambiguous, primary, rng)

        log("Writing users table...")
        dst.executemany(
            "INSERT INTO users (author_id, username) VALUES (?, ?)",
            [(aid, unambiguous[aid]) for aid in primary],
        )
        dst.commit()

        n_cross, dup_examples = count_cross_source_duplicates(dst)
        n_users = dst.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        n_kw = dst.execute(
            "SELECT COUNT(*) FROM posts WHERE source = ?", (SOURCE_KEYWORD,)
        ).fetchone()[0]
        n_tl = dst.execute(
            "SELECT COUNT(*) FROM posts WHERE source = ?", (SOURCE_TIMELINE,)
        ).fetchone()[0]
        n_posts = n_kw + n_tl

        inspect_kw = kw["kw_sample"][:INSPECT_KEYWORD]
        inspect_rows = inspect_kw + tl["inspect_rows"]
        rng.shuffle(inspect_rows)
        write_csv(
            SAMPLE_CSV,
            ["tweet_id", "author_id", "username", "created_at", "text", "lang", "source"],
            inspect_rows,
        )

        all_min = min(x for x in [kw["min_iso"], tl["min_iso"]] if x)
        all_max = max(x for x in [kw["max_iso"], tl["max_iso"]] if x)
        lang_total = sum(tl["lang_counts"].values()) or 1
        lang_rows = []
        lang_rows.append(
            {
                "source": SOURCE_KEYWORD,
                "lang": LANG_UNKNOWN,
                "n": n_kw,
                "pct": 100.0 if n_kw else 0.0,
                "bucket": "unknown",
                "notes": "tweets table has no LANG; not assumed English",
            }
        )
        bucket_counts: Counter[str] = Counter()
        for code, n in tl["lang_counts"].most_common():
            bucket = lang_bucket(code)
            bucket_counts[bucket] += n
            note = ""
            if code.lower() == "en":
                note = "English only"
            elif code.lower() in NON_LINGUISTIC_LANGS:
                note = "non-linguistic Twitter code; not English"
            lang_rows.append(
                {
                    "source": SOURCE_TIMELINE,
                    "lang": code,
                    "n": n,
                    "pct": round(100.0 * n / lang_total, 4),
                    "bucket": bucket,
                    "notes": note,
                }
            )
        for bucket, n in bucket_counts.most_common():
            lang_rows.append(
                {
                    "source": SOURCE_TIMELINE,
                    "lang": f"BUCKET:{bucket}",
                    "n": n,
                    "pct": round(100.0 * n / lang_total, 4),
                    "bucket": bucket,
                    "notes": "und/qme/qam/zxx never counted as English",
                }
            )
        write_csv(LANG_CSV, ["source", "lang", "n", "pct", "bucket", "notes"], lang_rows)

        stat_rows = [
            {"metric": "n_users", "value": n_users, "notes": "unambiguous triple intersection"},
            {"metric": "n_posts", "value": n_posts, "notes": "keyword + timeline"},
            {"metric": "n_keyword_tweets", "value": n_kw, "notes": SOURCE_KEYWORD},
            {"metric": "n_timeline_tweets", "value": n_tl, "notes": SOURCE_TIMELINE},
            {"metric": "n_users_with_keyword_tweets", "value": kw["n_users_with_kw"], "notes": ""},
            {"metric": "n_ambiguous_author_id_groups_excluded", "value": len(ambiguous), "notes": ""},
            {"metric": "authors_table_rows_scanned", "value": n_author_rows, "notes": ""},
            {"metric": "timeline_rows_scanned", "value": tl["n_seen"], "notes": ""},
            {"metric": "keyword_rows_scanned", "value": kw["n_seen"], "notes": ""},
            {"metric": "timeline_excluded_not_primary", "value": tl["n_excluded_id"], "notes": "includes ambiguous and non-authors"},
            {"metric": "timeline_excluded_bad_date", "value": tl["n_excluded_date"], "notes": ""},
            {"metric": "keyword_excluded_not_primary", "value": kw["n_excluded_id"], "notes": ""},
            {"metric": "keyword_excluded_bad_date", "value": kw["n_excluded_date"], "notes": ""},
            {"metric": "cross_source_duplicate_tweet_ids", "value": n_cross, "notes": "kept in both sources"},
            {"metric": "keyword_date_min", "value": kw["min_iso"], "notes": "ISO"},
            {"metric": "keyword_date_max", "value": kw["max_iso"], "notes": "ISO"},
            {"metric": "timeline_date_min", "value": tl["min_iso"], "notes": "ISO"},
            {"metric": "timeline_date_max", "value": tl["max_iso"], "notes": "ISO"},
            {"metric": "corpus_date_min", "value": all_min, "notes": "ISO"},
            {"metric": "corpus_date_max", "value": all_max, "notes": "ISO"},
            {"metric": "keyword_lang_sample_rows", "value": len(kw["kw_sample"]), "notes": "for later language detection"},
            {"metric": "inspection_sample_rows", "value": len(inspect_rows), "notes": SAMPLE_CSV.name},
            {"metric": "corpus_db_path", "value": str(CORPUS_DB.relative_to(ROOT)), "notes": "SQLite, not a full CSV dump"},
        ]
        write_csv(STATS_CSV, ["metric", "value", "notes"], stat_rows)

        lang_top = tl["lang_counts"].most_common(20)
        write_manifest(
            {
                "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "n_users": n_users,
                "n_keyword": n_kw,
                "n_timeline": n_tl,
                "n_posts": n_posts,
                "n_users_with_kw": kw["n_users_with_kw"],
                "n_ambiguous": len(ambiguous),
                "tl_excluded_id": tl["n_excluded_id"],
                "tl_excluded_date": tl["n_excluded_date"],
                "kw_excluded_id": kw["n_excluded_id"],
                "kw_excluded_date": kw["n_excluded_date"],
                "kw_min": kw["min_iso"],
                "kw_max": kw["max_iso"],
                "tl_min": tl["min_iso"],
                "tl_max": tl["max_iso"],
                "all_min": all_min,
                "all_max": all_max,
                "n_cross_dup": n_cross,
                "dup_examples": dup_examples,
                "n_kw_sample": len(kw["kw_sample"]),
                "lang_top": lang_top,
                "n_timeline": n_tl,
            }
        )
        size_gb = CORPUS_DB.stat().st_size / 1024**3
        elapsed = time.perf_counter() - started
        log("")
        log("========== CORPUS SUMMARY ==========")
        log(f"n_users={n_users}")
        log(f"n_keyword_tweets={n_kw}")
        log(f"n_timeline_tweets={n_tl}")
        log(f"n_posts={n_posts}")
        log(f"n_users_with_keyword_tweets={kw['n_users_with_kw']}")
        log(f"n_ambiguous_excluded={len(ambiguous)}")
        log(f"cross_source_duplicate_tweet_ids={n_cross}")
        log(f"keyword_date_range={kw['min_iso']} .. {kw['max_iso']}")
        log(f"timeline_date_range={tl['min_iso']} .. {tl['max_iso']}")
        log(f"keyword_lang=unknown for all {n_kw} rows")
        log(f"timeline_lang_codes={len(tl['lang_counts'])}")
        log(f"corpus_db_gb={size_gb:.2f}")
        log(f"elapsed_seconds={elapsed:.1f}")
        log("CORPUS_BUILD_COMPLETE")
    finally:
        src.close()
        if dst is not None:
            dst.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
