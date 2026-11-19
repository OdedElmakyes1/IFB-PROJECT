#!/usr/bin/env python3
"""Read-only coverage, ID, and date-normalization profiling for IFB.db.

Does not modify IFB.db. Does not load the full database into memory.
Streams tables in chunks and keeps only ID sets, counters, and samples.
"""

from __future__ import annotations

import csv
import hashlib
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "IFB.db"
OUTPUT_DIR = ROOT / "outputs"
COVERAGE_CSV = OUTPUT_DIR / "data_coverage_report.csv"
DATE_CSV = OUTPUT_DIR / "date_parsing_report.csv"
TEXT_CSV = OUTPUT_DIR / "text_feature_profile.csv"

CHUNK_SIZE = 25_000
PROGRESS_EVERY = 500_000
SAMPLE_PER_KEYWORD = 2_000
TIMELINE_SAMPLE_EN = 20_000
TIMELINE_SAMPLE_OTHER = 12_000
TIMELINE_SAMPLE_NONLING = 8_000

TWITTER_LAUNCH = datetime(2006, 3, 21)
COLLECTION_END = datetime(2024, 1, 1)
EPOCH = datetime(1970, 1, 1)

NON_LINGUISTIC_LANGS = frozenset({"und", "qme", "qam", "zxx"})

HASHTAG_RE = re.compile(r"(?<!\w)#\w+", re.UNICODE)
MENTION_RE = re.compile(r"(?<!\w)@\w+", re.UNICODE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
RT_RE = re.compile(r"^\s*RT\s+@", re.IGNORECASE)
WEEKDAY_RE = re.compile(
    r"^(\d{2})-(\d{2})-(\d{2})\s+([A-Za-z]{3})\s+(\d{2}):(\d{2}):(\d{2})$"
)
ISO_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$"
)
ISO_DATE_ONLY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def log(message: str) -> None:
    print(message, flush=True)


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=60)
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA temp_store = FILE")
    return conn


def canon_author_id(value: Any) -> str:
    """Normalize AUTHOR_ID to a comparable text key (mirrors CAST(... AS TEXT))."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        return text[:-2]
    return text


def parse_unix_number(n: int) -> tuple[datetime | None, str]:
    if n >= 10**14:  # microseconds
        seconds = n / 1_000_000
        kind = "unix_microseconds"
    elif n >= 10**11:  # milliseconds (Twitter ms are ~1.2e12–1.7e12)
        seconds = n / 1_000
        kind = "unix_milliseconds"
    elif n >= 10**9:  # seconds
        seconds = float(n)
        kind = "unix_seconds"
    else:
        return None, "unix_out_of_range"
    try:
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)
    except (OSError, OverflowError, ValueError):
        return None, "unix_unconvertible"
    return validate_datetime(dt, kind)


def validate_datetime(dt: datetime, kind: str) -> tuple[datetime | None, str]:
    if dt <= EPOCH:
        return None, "placeholder_epoch"
    if dt < TWITTER_LAUNCH:
        return None, "before_twitter"
    if dt >= COLLECTION_END:
        return None, "after_collection"
    return dt, kind


def parse_created_at(value: Any) -> tuple[datetime | None, str]:
    if value is None:
        return None, "empty"
    if isinstance(value, datetime):
        return validate_datetime(value, "datetime_object")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return parse_unix_number(int(value))

    text = str(value).strip()
    if not text:
        return None, "empty"
    if text.lower() in {"none", "null", "nan"}:
        return None, "empty"

    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return parse_unix_number(int(text))

    match = WEEKDAY_RE.match(text)
    if match:
        yy, mm, dd, _dow, hh, mi, ss = match.groups()
        year = 2000 + int(yy)
        try:
            dt = datetime(year, int(mm), int(dd), int(hh), int(mi), int(ss))
        except ValueError:
            return None, "weekday_invalid_calendar"
        return validate_datetime(dt, "weekday_yymmdd")

    match = ISO_RE.match(text)
    if match:
        year, mm, dd, hh, mi, ss = (int(x) for x in match.groups())
        try:
            dt = datetime(year, mm, dd, hh, mi, ss)
        except ValueError:
            return None, "iso_invalid_calendar"
        return validate_datetime(dt, "iso_datetime")

    match = ISO_DATE_ONLY_RE.match(text)
    if match:
        year, mm, dd = (int(x) for x in match.groups())
        try:
            dt = datetime(year, mm, dd)
        except ValueError:
            return None, "iso_invalid_calendar"
        return validate_datetime(dt, "iso_date")

    return None, "unparseable"


def self_check_parser() -> None:
    checks = [
        (1609530189000, True, "unix_milliseconds"),
        ("1609530189000", True, "unix_milliseconds"),
        ("23-01-05 Thu 23:59:56", True, "weekday_yymmdd"),
        ("19-01-01 Tue 00:00:03", True, "weekday_yymmdd"),
        ("2022-08-27 22:28:18.000000", True, "iso_datetime"),
        ("1970-01-01 00:00:00.000000", False, "placeholder_epoch"),
        ("", False, "empty"),
        (None, False, "empty"),
        ("not-a-date", False, "unparseable"),
    ]
    for raw, expect_ok, expect_kind in checks:
        dt, kind = parse_created_at(raw)
        ok = dt is not None
        if ok != expect_ok or kind != expect_kind:
            raise RuntimeError(f"Parser self-check failed for {raw!r}: {dt}, {kind}")


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


def lang_bucket(lang: Any) -> str:
    code = ("" if lang is None else str(lang).strip().lower())
    if not code:
        return "missing"
    if code == "en":
        return "english"
    if code in NON_LINGUISTIC_LANGS:
        return "non_linguistic"
    return "other_language"


def sum_counts(counter: dict[str, int], keys: Iterable[str]) -> int:
    keys = list(keys) if not isinstance(keys, (set, frozenset, dict)) else keys
    if len(keys) <= len(counter):
        return sum(counter.get(k, 0) for k in keys)
    key_set = keys if isinstance(keys, (set, frozenset)) else set(keys)
    return sum(n for k, n in counter.items() if k in key_set)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def load_authors(conn: sqlite3.Connection) -> dict[str, Any]:
    log("Scanning authors...")
    t0 = time.perf_counter()
    rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    date_status: Counter[str] = Counter()
    n_rows = 0
    n_epoch = 0
    usernames: set[str] = set()
    duplicate_usernames = 0

    cur = conn.execute(
        """
        SELECT CAST(AUTHOR_ID AS TEXT) AS author_id,
               USERNAME,
               CREATED_AT
        FROM authors
        """
    )
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for raw_id, username, created_at in chunk:
            n_rows += 1
            author_id = canon_author_id(raw_id)
            uname = "" if username is None else str(username)
            if uname in usernames:
                duplicate_usernames += 1
            else:
                usernames.add(uname)
            dt, kind = parse_created_at(created_at)
            date_status[kind] += 1
            if kind == "placeholder_epoch":
                n_epoch += 1
            rows_by_id[author_id].append(
                {
                    "username": uname,
                    "created_at": created_at,
                }
            )

    unique_ids = set(rows_by_id)
    ambiguous_ids = {aid for aid, rows in rows_by_id.items() if len(rows) > 1}
    n_ambiguous_rows = sum(len(rows_by_id[aid]) for aid in ambiguous_ids)

    same_username_groups = 0
    distinct_username_groups = 0
    same_created_groups = 0
    max_group = 0
    for aid in ambiguous_ids:
        rows = rows_by_id[aid]
        max_group = max(max_group, len(rows))
        unames = {r["username"] for r in rows}
        created = {str(r["created_at"]) for r in rows}
        if len(unames) == 1:
            same_username_groups += 1
        else:
            distinct_username_groups += 1
        if len(created) == 1:
            same_created_groups += 1

    log(
        f"  authors rows={n_rows:,} unique_ids={len(unique_ids):,} "
        f"ambiguous_ids={len(ambiguous_ids):,} in {time.perf_counter() - t0:.1f}s"
    )
    return {
        "n_rows": n_rows,
        "unique_ids": unique_ids,
        "ambiguous_ids": ambiguous_ids,
        "n_ambiguous_rows": n_ambiguous_rows,
        "usernames": len(usernames),
        "duplicate_usernames": duplicate_usernames,
        "same_username_groups": same_username_groups,
        "distinct_username_groups": distinct_username_groups,
        "same_created_groups": same_created_groups,
        "max_group": max_group,
        "date_status": date_status,
        "n_epoch": n_epoch,
    }


def scan_tweets(
    conn: sqlite3.Connection,
    author_ids: set[str],
    rng: random.Random,
) -> dict[str, Any]:
    log("Scanning tweets (IDs, dates, stratified text sample)...")
    t0 = time.perf_counter()
    posts_by_author: dict[str, int] = {}
    date_status: Counter[str] = Counter()
    keyword_raw: Counter[str] = Counter()
    keyword_trimmed: Counter[str] = Counter()
    usable_min: datetime | None = None
    usable_max: datetime | None = None
    n_rows = 0
    samples_by_keyword: dict[str, Reservoir] = {}

    cur = conn.execute(
        """
        SELECT CAST(AUTHOR_ID AS TEXT) AS author_id,
               CREATED_AT,
               TWEET_CONTENT,
               KEYWORD
        FROM tweets
        """
    )
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for raw_id, created_at, content, keyword in chunk:
            n_rows += 1
            author_id = canon_author_id(raw_id)
            posts_by_author[author_id] = posts_by_author.get(author_id, 0) + 1

            dt, kind = parse_created_at(created_at)
            date_status[kind] += 1
            if dt is not None:
                if usable_min is None or dt < usable_min:
                    usable_min = dt
                if usable_max is None or dt > usable_max:
                    usable_max = dt

            raw_kw = "" if keyword is None else str(keyword)
            trim_kw = raw_kw.strip()
            keyword_raw[raw_kw] += 1
            keyword_trimmed[trim_kw] += 1
            bucket = samples_by_keyword.get(trim_kw)
            if bucket is None:
                bucket = Reservoir(SAMPLE_PER_KEYWORD, rng)
                samples_by_keyword[trim_kw] = bucket
            bucket.offer(content or "")

            if n_rows % PROGRESS_EVERY == 0:
                log(f"  tweets {n_rows:,} rows...")

    sample_texts = [text for res in samples_by_keyword.values() for text in res.items]
    n_in_authors_users = sum(1 for aid in posts_by_author if aid in author_ids)
    n_in_authors_posts = sum(n for aid, n in posts_by_author.items() if aid in author_ids)

    log(
        f"  tweets rows={n_rows:,} unique_authors={len(posts_by_author):,} "
        f"sample={len(sample_texts):,} in {time.perf_counter() - t0:.1f}s"
    )
    return {
        "n_rows": n_rows,
        "posts_by_author": posts_by_author,
        "date_status": date_status,
        "usable_min": usable_min,
        "usable_max": usable_max,
        "keyword_raw": keyword_raw,
        "keyword_trimmed": keyword_trimmed,
        "sample_texts": sample_texts,
        "n_in_authors_users": n_in_authors_users,
        "n_in_authors_posts": n_in_authors_posts,
        "samples_by_keyword": {k: v.seen for k, v in samples_by_keyword.items()},
    }


def scan_timeline(
    conn: sqlite3.Connection,
    author_ids: set[str],
    tweet_author_ids: set[str],
    rng: random.Random,
) -> dict[str, Any]:
    log("Scanning timeline (IDs, languages, stratified text sample)...")
    t0 = time.perf_counter()
    posts_by_author: dict[str, int] = {}
    lang_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    date_status: Counter[str] = Counter()
    usable_min: datetime | None = None
    usable_max: datetime | None = None
    n_rows = 0
    sample_en = Reservoir(TIMELINE_SAMPLE_EN, rng)
    sample_other = Reservoir(TIMELINE_SAMPLE_OTHER, rng)
    sample_nonling = Reservoir(TIMELINE_SAMPLE_NONLING, rng)

    cur = conn.execute(
        """
        SELECT CAST(AUTHOR_ID AS TEXT) AS author_id,
               CREATED_AT,
               TWEET,
               LANG
        FROM timeline
        """
    )
    while True:
        chunk = cur.fetchmany(CHUNK_SIZE)
        if not chunk:
            break
        for raw_id, created_at, content, lang in chunk:
            n_rows += 1
            author_id = canon_author_id(raw_id)
            posts_by_author[author_id] = posts_by_author.get(author_id, 0) + 1

            code = "" if lang is None else str(lang).strip()
            lang_counts[code or "MISSING"] += 1
            bucket = lang_bucket(code)
            bucket_counts[bucket] += 1

            raw_date = created_at
            if isinstance(raw_date, datetime):
                dt, kind = validate_datetime(raw_date, "datetime_object")
            else:
                text_date = "" if raw_date is None else str(raw_date).strip()
                iso_match = ISO_RE.match(text_date)
                if iso_match:
                    year = int(iso_match.group(1))
                    if year <= 1970:
                        dt, kind = None, "placeholder_epoch"
                    elif year < 2006:
                        dt, kind = None, "before_twitter"
                    elif year >= 2024:
                        dt, kind = None, "after_collection"
                    else:
                        # ISO text sorts chronologically; keep min/max as strings.
                        kind = "iso_datetime"
                        if usable_min is None or text_date < usable_min:
                            usable_min = text_date
                        if usable_max is None or text_date > usable_max:
                            usable_max = text_date
                        dt = True  # sentinel: parsed OK
                else:
                    dt, kind = parse_created_at(raw_date)
                    if dt is not None:
                        stamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        if usable_min is None or stamp < usable_min:
                            usable_min = stamp
                        if usable_max is None or stamp > usable_max:
                            usable_max = stamp
            date_status[kind] += 1

            text = content or ""
            if bucket == "english":
                sample_en.offer(text)
            elif bucket == "non_linguistic":
                sample_nonling.offer(text)
            else:
                sample_other.offer(text)

            if n_rows % PROGRESS_EVERY == 0:
                log(f"  timeline {n_rows:,} rows...")

    sample_texts = sample_en.items + sample_other.items + sample_nonling.items
    if isinstance(usable_min, str):
        usable_min, _ = parse_created_at(usable_min)
    if isinstance(usable_max, str):
        usable_max, _ = parse_created_at(usable_max)
    log(
        f"  timeline rows={n_rows:,} unique_authors={len(posts_by_author):,} "
        f"sample={len(sample_texts):,} in {time.perf_counter() - t0:.1f}s"
    )
    tweet_keys = tweet_author_ids
    n_in_authors_users = sum(1 for aid in posts_by_author if aid in author_ids)
    n_in_tweets_users = sum(1 for aid in posts_by_author if aid in tweet_keys)
    return {
        "n_rows": n_rows,
        "posts_by_author": posts_by_author,
        "lang_counts": lang_counts,
        "bucket_counts": bucket_counts,
        "date_status": date_status,
        "usable_min": usable_min,
        "usable_max": usable_max,
        "sample_texts": sample_texts,
        "sample_by_bucket": {
            "english": sample_en.items,
            "other_language": sample_other.items,
            "non_linguistic": sample_nonling.items,
        },
        "n_in_authors_users": n_in_authors_users,
        "n_in_tweets_users": n_in_tweets_users,
    }


def profile_text(texts: list[str], source: str) -> list[dict[str, Any]]:
    n = len(texts)
    if n == 0:
        return [{"source": source, "feature": "sample_size", "value": 0, "n": 0, "pct": 0, "notes": "empty sample"}]

    hashtag_n = []
    mention_n = []
    url_n = []
    lengths = []
    tokens = []
    n_rt = 0
    n_hashtag = 0
    n_mention = 0
    n_url = 0
    n_empty = 0
    exact = Counter()
    normalized = Counter()

    for text in texts:
        if not text or not str(text).strip():
            n_empty += 1
            hashtag_n.append(0)
            mention_n.append(0)
            url_n.append(0)
            lengths.append(0)
            tokens.append(0)
            continue
        body = str(text)
        hs = HASHTAG_RE.findall(body)
        ms = MENTION_RE.findall(body)
        us = URL_RE.findall(body)
        hashtag_n.append(len(hs))
        mention_n.append(len(ms))
        url_n.append(len(us))
        lengths.append(len(body))
        tokens.append(len(body.split()))
        if hs:
            n_hashtag += 1
        if ms:
            n_mention += 1
        if us:
            n_url += 1
        if RT_RE.search(body):
            n_rt += 1
        exact[body] += 1
        norm = " ".join(body.lower().split())
        digest = hashlib.sha1(norm.encode("utf-8", "ignore")).hexdigest()
        normalized[digest] += 1

    extra_exact = sum(c - 1 for c in exact.values() if c > 1)
    extra_norm = sum(c - 1 for c in normalized.values() if c > 1)
    dup_groups_exact = sum(1 for c in exact.values() if c > 1)
    dup_groups_norm = sum(1 for c in normalized.values() if c > 1)

    def pct(x: int) -> float:
        return round(100.0 * x / n, 4)

    rows = [
        {"source": source, "feature": "sample_size", "value": n, "n": n, "pct": 100.0, "notes": "reservoir / stratified"},
        {"source": source, "feature": "empty_text", "value": n_empty, "n": n_empty, "pct": pct(n_empty), "notes": ""},
        {"source": source, "feature": "contains_hashtag", "value": n_hashtag, "n": n_hashtag, "pct": pct(n_hashtag), "notes": r"regex (?<!\w)#\w+"},
        {"source": source, "feature": "contains_mention", "value": n_mention, "n": n_mention, "pct": pct(n_mention), "notes": r"regex (?<!\w)@\w+"},
        {"source": source, "feature": "contains_url", "value": n_url, "n": n_url, "pct": pct(n_url), "notes": r"regex https?://"},
        {"source": source, "feature": "retweet_indicator", "value": n_rt, "n": n_rt, "pct": pct(n_rt), "notes": "text starts with RT @"},
        {"source": source, "feature": "mean_hashtags_per_post", "value": round(mean(hashtag_n), 4), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "median_hashtags_per_post", "value": median(hashtag_n), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "mean_mentions_per_post", "value": round(mean(mention_n), 4), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "median_mentions_per_post", "value": median(mention_n), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "mean_urls_per_post", "value": round(mean(url_n), 4), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "mean_chars", "value": round(mean(lengths), 2), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "median_chars", "value": median(lengths), "n": n, "pct": "", "notes": ""},
        {"source": source, "feature": "mean_tokens", "value": round(mean(tokens), 2), "n": n, "pct": "", "notes": "whitespace split"},
        {"source": source, "feature": "median_tokens", "value": median(tokens), "n": n, "pct": "", "notes": "whitespace split"},
        {"source": source, "feature": "exact_duplicate_extra_rows", "value": extra_exact, "n": extra_exact, "pct": pct(extra_exact), "notes": "within sample only"},
        {"source": source, "feature": "exact_duplicate_groups", "value": dup_groups_exact, "n": dup_groups_exact, "pct": "", "notes": "within sample only"},
        {"source": source, "feature": "normalized_duplicate_extra_rows", "value": extra_norm, "n": extra_norm, "pct": pct(extra_norm), "notes": "lowercased / collapsed whitespace; sample only"},
        {"source": source, "feature": "normalized_duplicate_groups", "value": dup_groups_norm, "n": dup_groups_norm, "pct": "", "notes": "sample only"},
    ]
    return rows


def coverage_row(
    metric: str,
    group: str,
    n_users: int,
    n_posts: int,
    notes: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "metric": metric,
        "group": group,
        "n_users": n_users,
        "n_posts": n_posts,
        "notes": notes,
    }
    if extra:
        row.update(extra)
    return row


def fmt_dt(dt: datetime | None) -> str:
    return "" if dt is None else dt.strftime("%Y-%m-%d %H:%M:%S")


def build_coverage_rows(
    authors: dict[str, Any],
    tweets: dict[str, Any],
    timeline: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    a_ids: set[str] = authors["unique_ids"]
    t_posts: dict[str, int] = tweets["posts_by_author"]
    l_posts: dict[str, int] = timeline["posts_by_author"]
    t_ids = set(t_posts)
    l_ids = set(l_posts)
    amb = authors["ambiguous_ids"]

    tweets_in_authors = t_ids & a_ids
    tweets_not_authors = t_ids - a_ids
    timeline_in_authors = l_ids & a_ids
    timeline_not_authors = l_ids - a_ids
    tweets_in_timeline = t_ids & l_ids
    tweets_not_timeline = t_ids - l_ids
    timeline_in_tweets = l_ids & t_ids
    timeline_not_tweets = l_ids - t_ids
    triple = a_ids & t_ids & l_ids
    authors_not_tweets = a_ids - t_ids
    authors_not_timeline = a_ids - l_ids
    unambiguous = a_ids - amb
    triple_clean = triple - amb

    summary = {
        "authors_rows": authors["n_rows"],
        "authors_unique": len(a_ids),
        "ambiguous_ids": len(amb),
        "tweets_rows": tweets["n_rows"],
        "tweets_unique": len(t_ids),
        "timeline_rows": timeline["n_rows"],
        "timeline_unique": len(l_ids),
        "tweets_in_authors_users": len(tweets_in_authors),
        "tweets_in_authors_posts": sum_counts(t_posts, tweets_in_authors),
        "tweets_not_authors_users": len(tweets_not_authors),
        "tweets_not_authors_posts": sum_counts(t_posts, tweets_not_authors),
        "timeline_in_authors_users": len(timeline_in_authors),
        "timeline_in_authors_posts": sum_counts(l_posts, timeline_in_authors),
        "timeline_not_authors_users": len(timeline_not_authors),
        "timeline_not_authors_posts": sum_counts(l_posts, timeline_not_authors),
        "tweets_in_timeline_users": len(tweets_in_timeline),
        "tweets_in_timeline_posts": sum_counts(t_posts, tweets_in_timeline),
        "tweets_not_timeline_users": len(tweets_not_timeline),
        "tweets_not_timeline_posts": sum_counts(t_posts, tweets_not_timeline),
        "timeline_in_tweets_users": len(timeline_in_tweets),
        "timeline_in_tweets_posts": sum_counts(l_posts, timeline_in_tweets),
        "timeline_not_tweets_users": len(timeline_not_tweets),
        "timeline_not_tweets_posts": sum_counts(l_posts, timeline_not_tweets),
        "triple_users": len(triple),
        "triple_keyword_posts": sum_counts(t_posts, triple),
        "triple_timeline_posts": sum_counts(l_posts, triple),
        "triple_clean_users": len(triple_clean),
        "triple_clean_keyword_posts": sum_counts(t_posts, triple_clean),
        "triple_clean_timeline_posts": sum_counts(l_posts, triple_clean),
        "authors_not_tweets_users": len(authors_not_tweets),
        "authors_not_timeline_users": len(authors_not_timeline),
        "unambiguous_authors": len(unambiguous),
        "ambiguous_in_tweets": len(amb & t_ids),
        "ambiguous_in_timeline": len(amb & l_ids),
        "ambiguous_in_triple": len(amb & triple),
    }

    rows = [
        coverage_row("table_size", "authors", authors["n_rows"], authors["n_rows"], "row count; AUTHOR_ID is not unique"),
        coverage_row("table_size", "authors_unique_AUTHOR_ID", len(a_ids), 0, "CAST(AUTHOR_ID AS TEXT)"),
        coverage_row("table_size", "tweets", len(t_ids), tweets["n_rows"], "users=unique AUTHOR_ID; posts=all keyword tweets"),
        coverage_row("table_size", "timeline", len(l_ids), timeline["n_rows"], "users=unique AUTHOR_ID; posts=all timeline tweets"),
        coverage_row(
            "tweets_authors_vs_authors",
            "matched",
            summary["tweets_in_authors_users"],
            summary["tweets_in_authors_posts"],
            "keyword-tweet authors present in authors table; n_posts = keyword tweets",
        ),
        coverage_row(
            "tweets_authors_vs_authors",
            "unmatched",
            summary["tweets_not_authors_users"],
            summary["tweets_not_authors_posts"],
            "keyword-tweet authors with no authors-table metadata",
        ),
        coverage_row(
            "timeline_authors_vs_authors",
            "matched",
            summary["timeline_in_authors_users"],
            summary["timeline_in_authors_posts"],
            "timeline authors present in authors table; n_posts = timeline tweets",
        ),
        coverage_row(
            "timeline_authors_vs_authors",
            "unmatched",
            summary["timeline_not_authors_users"],
            summary["timeline_not_authors_posts"],
            "timeline authors with no authors-table metadata",
        ),
        coverage_row(
            "tweets_authors_vs_timeline_authors",
            "matched",
            summary["tweets_in_timeline_users"],
            summary["tweets_in_timeline_posts"],
            "authors in both tweets and timeline; n_posts = keyword tweets from those users",
        ),
        coverage_row(
            "tweets_authors_vs_timeline_authors",
            "unmatched_tweets_only",
            summary["tweets_not_timeline_users"],
            summary["tweets_not_timeline_posts"],
            "keyword-tweet authors with no timeline rows; n_posts = keyword tweets",
        ),
        coverage_row(
            "timeline_authors_vs_tweets_authors",
            "matched",
            summary["timeline_in_tweets_users"],
            summary["timeline_in_tweets_posts"],
            "same user overlap as tweets∩timeline; n_posts = timeline tweets from those users",
        ),
        coverage_row(
            "timeline_authors_vs_tweets_authors",
            "unmatched_timeline_only",
            summary["timeline_not_tweets_users"],
            summary["timeline_not_tweets_posts"],
            "timeline authors with no keyword tweets; n_posts = timeline tweets",
        ),
        coverage_row(
            "authors_table_vs_tweets",
            "authors_not_in_tweets",
            summary["authors_not_tweets_users"],
            0,
            "authors-table IDs that never appear in tweets",
        ),
        coverage_row(
            "authors_table_vs_timeline",
            "authors_not_in_timeline",
            summary["authors_not_timeline_users"],
            0,
            "authors-table IDs that never appear in timeline",
        ),
        coverage_row(
            "triple_intersection",
            "authors_and_tweets_and_timeline",
            summary["triple_users"],
            summary["triple_keyword_posts"],
            f"n_posts=keyword tweets; timeline posts={summary['triple_timeline_posts']:,}",
        ),
        coverage_row(
            "triple_intersection",
            "unambiguous_AUTHOR_ID_only",
            summary["triple_clean_users"],
            summary["triple_clean_keyword_posts"],
            f"excludes duplicate AUTHOR_ID groups; timeline posts={summary['triple_clean_timeline_posts']:,}",
        ),
        coverage_row(
            "duplicate_authors",
            "ambiguous_AUTHOR_ID_groups",
            len(amb),
            authors["n_ambiguous_rows"],
            "n_users=duplicate ID groups; n_posts=author rows involved. USERNAMEs in a group are distinct.",
        ),
        coverage_row(
            "duplicate_authors",
            "ambiguous_ids_in_tweets",
            summary["ambiguous_in_tweets"],
            sum_counts(t_posts, amb & t_ids),
            "duplicate AUTHOR_IDs that also appear in tweets; n_posts=keyword tweets",
        ),
        coverage_row(
            "duplicate_authors",
            "ambiguous_ids_in_timeline",
            summary["ambiguous_in_timeline"],
            sum_counts(l_posts, amb & l_ids),
            "duplicate AUTHOR_IDs that also appear in timeline; n_posts=timeline tweets",
        ),
        coverage_row(
            "identifier_quality",
            "unique_USERNAME_in_authors",
            authors["usernames"],
            authors["duplicate_usernames"],
            "USERNAME is unique per authors row (n_posts=duplicate username rows, should be 0)",
        ),
        coverage_row(
            "identifier_quality",
            "duplicate_groups_distinct_usernames",
            authors["distinct_username_groups"],
            authors["same_username_groups"],
            "n_users=groups with different usernames; n_posts=groups with identical username",
        ),
        coverage_row(
            "identifier_quality",
            "duplicate_groups_same_CREATED_AT",
            authors["same_created_groups"],
            authors["max_group"],
            "n_users=groups sharing account CREATED_AT; n_posts=max group size",
        ),
    ]
    return rows, summary


def build_date_rows(authors: dict[str, Any], tweets: dict[str, Any], timeline: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add_table(table: str, total: int, status: Counter[str], usable_min: datetime | None, usable_max: datetime | None) -> None:
        success = sum(n for k, n in status.items() if k in {"unix_milliseconds", "unix_seconds", "unix_microseconds", "weekday_yymmdd", "iso_datetime", "iso_date", "datetime_object"})
        excluded = total - success
        rows.append(
            {
                "table": table,
                "status": "TOTAL",
                "n_records": total,
                "pct": 100.0,
                "min_parsed": fmt_dt(usable_min),
                "max_parsed": fmt_dt(usable_max),
                "notes": "all stored CREATED_AT values",
            }
        )
        rows.append(
            {
                "table": table,
                "status": "PARSE_SUCCESS",
                "n_records": success,
                "pct": round(100.0 * success / total, 4) if total else 0.0,
                "min_parsed": fmt_dt(usable_min),
                "max_parsed": fmt_dt(usable_max),
                "notes": "parsed and inside 2006-03-21 .. 2023-12-31",
            }
        )
        rows.append(
            {
                "table": table,
                "status": "EXCLUDED",
                "n_records": excluded,
                "pct": round(100.0 * excluded / total, 4) if total else 0.0,
                "min_parsed": "",
                "max_parsed": "",
                "notes": "empty, unparseable, epoch placeholder, before Twitter, or after collection",
            }
        )
        for kind, n in status.most_common():
            rows.append(
                {
                    "table": table,
                    "status": kind,
                    "n_records": n,
                    "pct": round(100.0 * n / total, 4) if total else 0.0,
                    "min_parsed": fmt_dt(usable_min) if kind.startswith(("unix", "weekday", "iso")) else "",
                    "max_parsed": fmt_dt(usable_max) if kind.startswith(("unix", "weekday", "iso")) else "",
                    "notes": "",
                }
            )

    add_table("tweets", tweets["n_rows"], tweets["date_status"], tweets["usable_min"], tweets["usable_max"])
    add_table("timeline", timeline["n_rows"], timeline["date_status"], timeline["usable_min"], timeline["usable_max"])
    add_table("authors", authors["n_rows"], authors["date_status"], None, None)
    return rows


def build_text_rows(tweets: dict[str, Any], timeline: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    rows.extend(profile_text(tweets["sample_texts"], "tweets_keyword_stratified"))
    rows.extend(profile_text(timeline["sample_texts"], "timeline_lang_stratified"))
    for bucket, texts in timeline["sample_by_bucket"].items():
        rows.extend(profile_text(texts, f"timeline_{bucket}"))

    t_total = timeline["n_rows"]
    for bucket, n in timeline["bucket_counts"].most_common():
        rows.append(
            {
                "source": "timeline_language_census",
                "feature": f"lang_bucket_{bucket}",
                "value": n,
                "n": n,
                "pct": round(100.0 * n / t_total, 4) if t_total else 0.0,
                "notes": "und/qme/qam/zxx counted as non_linguistic, never as English",
            }
        )
    for code, n in timeline["lang_counts"].most_common(25):
        note = "non_linguistic Twitter code; not English" if code.lower() in NON_LINGUISTIC_LANGS else ""
        if code.lower() == "en":
            note = "English only"
        rows.append(
            {
                "source": "timeline_language_census",
                "feature": f"lang_{code}",
                "value": n,
                "n": n,
                "pct": round(100.0 * n / t_total, 4) if t_total else 0.0,
                "notes": note,
            }
        )

    n_kw_raw = len(tweets["keyword_raw"])
    n_kw_trim = len(tweets["keyword_trimmed"])
    rows.append(
        {
            "source": "tweets_keywords",
            "feature": "distinct_KEYWORD_raw",
            "value": n_kw_raw,
            "n": n_kw_raw,
            "pct": "",
            "notes": "leading/trailing spaces kept",
        }
    )
    rows.append(
        {
            "source": "tweets_keywords",
            "feature": "distinct_KEYWORD_trimmed",
            "value": n_kw_trim,
            "n": n_kw_trim,
            "pct": "",
            "notes": "TRIM applied; use this for grouping",
        }
    )
    for kw, n in tweets["keyword_trimmed"].most_common(25):
        rows.append(
            {
                "source": "tweets_keywords",
                "feature": f"keyword::{kw}",
                "value": n,
                "n": n,
                "pct": round(100.0 * n / tweets["n_rows"], 4),
                "notes": "trimmed keyword",
            }
        )
    return rows


def main() -> int:
    started = time.perf_counter()
    log(f"Opening {DB_PATH} read-only...")
    self_check_parser()
    log("Date parser self-check passed.")
    rng = random.Random(2026)

    try:
        conn = connect_readonly(DB_PATH)
    except Exception as exc:
        log("FAILED to open IFB.db in read-only mode.")
        log(f"{type(exc).__name__}: {exc}")
        return 1

    try:
        authors = load_authors(conn)
        tweets = scan_tweets(conn, authors["unique_ids"], rng)
        timeline = scan_timeline(conn, authors["unique_ids"], set(tweets["posts_by_author"]), rng)
    finally:
        conn.close()
        log("Connection closed.")

    coverage_rows, summary = build_coverage_rows(authors, tweets, timeline)
    date_rows = build_date_rows(authors, tweets, timeline)
    text_rows = build_text_rows(tweets, timeline)

    write_csv(
        COVERAGE_CSV,
        ["metric", "group", "n_users", "n_posts", "notes"],
        coverage_rows,
    )
    write_csv(
        DATE_CSV,
        ["table", "status", "n_records", "pct", "min_parsed", "max_parsed", "notes"],
        date_rows,
    )
    write_csv(
        TEXT_CSV,
        ["source", "feature", "value", "n", "pct", "notes"],
        text_rows,
    )

    elapsed = time.perf_counter() - started
    log("")
    log("========== SUMMARY ==========")
    for key in [
        "authors_rows",
        "authors_unique",
        "ambiguous_ids",
        "tweets_rows",
        "tweets_unique",
        "timeline_rows",
        "timeline_unique",
        "tweets_in_authors_users",
        "tweets_in_authors_posts",
        "tweets_not_authors_users",
        "tweets_not_authors_posts",
        "timeline_in_authors_users",
        "timeline_in_authors_posts",
        "timeline_not_authors_users",
        "timeline_not_authors_posts",
        "tweets_in_timeline_users",
        "tweets_in_timeline_posts",
        "tweets_not_timeline_users",
        "tweets_not_timeline_posts",
        "timeline_in_tweets_users",
        "timeline_in_tweets_posts",
        "timeline_not_tweets_users",
        "timeline_not_tweets_posts",
        "triple_users",
        "triple_keyword_posts",
        "triple_timeline_posts",
        "triple_clean_users",
        "triple_clean_keyword_posts",
        "triple_clean_timeline_posts",
        "ambiguous_in_tweets",
        "ambiguous_in_timeline",
        "ambiguous_in_triple",
    ]:
        log(f"{key}={summary[key]}")
    log(f"tweets_date_min={fmt_dt(tweets['usable_min'])} max={fmt_dt(tweets['usable_max'])}")
    log(f"tweets_date_status={dict(tweets['date_status'])}")
    log(f"timeline_date_min={fmt_dt(timeline['usable_min'])} max={fmt_dt(timeline['usable_max'])}")
    log(f"timeline_lang_buckets={dict(timeline['bucket_counts'])}")
    log(f"elapsed_seconds={elapsed:.1f}")
    log(f"Wrote {COVERAGE_CSV.name}, {DATE_CSV.name}, {TEXT_CSV.name}")
    log("COVERAGE_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
