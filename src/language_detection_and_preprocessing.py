#!/usr/bin/env python3
"""Phase 2.1–2.2: keyword language profiling and text preprocessing.

Read-only on data/analysis_corpus.db. Does not modify IFB.db.
Does not translate millions of posts. Does not export the full corpus to CSV.
"""

from __future__ import annotations

import csv
import hashlib
import random
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import emoji
from langdetect import DetectorFactory, LangDetectException, detect_langs
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DB = ROOT / "data" / "analysis_corpus.db"
WORKING_DB = ROOT / "data" / "nlp_working_sample.db"
OUTPUT_DIR = ROOT / "outputs"
EXAMPLES_CSV = OUTPUT_DIR / "keyword_language_examples.csv"
STATS_CSV = OUTPUT_DIR / "keyword_language_statistics.csv"
PREPROC_CSV = OUTPUT_DIR / "preprocessing_examples.csv"
REPORT = ROOT / "LANGUAGE_AND_PREPROCESSING_REPORT.md"

DetectorFactory.seed = 2026
STEMMER = PorterStemmer()
STOPWORDS = frozenset(stopwords.words("english"))
STEM_METHOD = "Porter stemming (NLTK PorterStemmer); not WordNet lemmatization"

NON_LINGUISTIC = frozenset({"und", "qme", "qam", "zxx"})
CHUNK = 20_000
RNG_SEED = 2026
RANDOM_KEYWORD_N = 8_000
TIMELINE_SAMPLE_N = 6_000
MIN_DETECT_CHARS = 12
MIN_DETECT_LETTERS = 8
MIN_NLP_TOKENS = 3
LANGDETECT_OK = 0.80
LANGDETECT_LOW = 0.50

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@\w+")
HASHTAG_RE = re.compile(r"#(\w+)")
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
MULTI_SPACE_RE = re.compile(r"\s+")

# Longest-first collection phrases from IFB.db keywords + common variants.
IFB_PHRASES = tuple(
    sorted(
        {
            "following whoever follows",
            "following all that follows",
            "follow me and i follow you",
            "follow me and i will follow you",
            "i follow you back",
            "i follow back",
            "follow for follow back",
            "follow for follow",
            "follow 4 follow",
            "team follow back",
            "follow you back",
            "follow back",
            "twitter gains",
            "drop your handle",
        },
        key=len,
        reverse=True,
    )
)
IFB_PHRASE_RE = re.compile("|".join(re.escape(p) for p in IFB_PHRASES), re.IGNORECASE)

IFB_TOKENS = frozenset(
    {
        "ifb",
        "ifbs",
        "ifbdrive",
        "follow",
        "follows",
        "followed",
        "following",
        "follower",
        "followers",
        "followback",
        "followbacks",
        "unfollow",
        "unfollowed",
        "unfollower",
        "unfollowers",
        "refollow",
        "sougofollow",
        "followdaibosyu",
        "followforfollow",
        "followforfollowback",
        "follow4follow",
        "followtrain",
        "teamfollowback",
        "followfriday",
        "followme",
        "ifollowall",
        "ifollowback",
        "ifollowyouback",
        "followmeandifollowyou",
        "f4f",
        "l4l",
        "s4s",
        "fff",
        "ff",
        "rt",
        "gain",
        "gains",
        "gaintrain",
        "followtrick",
        "like4like",
        "likeforlike",
        "sub4sub",
    }
)

SCRIPT_RANGES = (
    ("ar", [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)]),
    ("he", [(0x0590, 0x05FF)]),
    ("hi", [(0x0900, 0x097F)]),
    ("th", [(0x0E00, 0x0E7F)]),
    ("ko", [(0xAC00, 0xD7AF), (0x1100, 0x11FF)]),
    ("ja", [(0x3040, 0x30FF)]),
    ("zh", [(0x4E00, 0x9FFF)]),
    ("ru", [(0x0400, 0x04FF)]),
    ("el", [(0x0370, 0x03FF)]),
)


def log(msg: str) -> None:
    print(msg, flush=True)


def connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def strip_urls_mentions(text: str) -> str:
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    return text


def strip_ifb_phrases(text: str) -> str:
    return IFB_PHRASE_RE.sub(" ", text)


def script_hint(text: str) -> str | None:
    counts: Counter[str] = Counter()
    letters = 0
    for ch in text:
        if not ch.isalpha():
            continue
        letters += 1
        cp = ord(ch)
        for lang, ranges in SCRIPT_RANGES:
            if any(a <= cp <= b for a, b in ranges):
                counts[lang] += 1
                break
    if letters < 8 or not counts:
        return None
    lang, n = counts.most_common(1)[0]
    if n / letters >= 0.25:
        return lang
    return None


def detection_text(original: str) -> str:
    text = strip_urls_mentions(original or "")
    text = emoji.replace_emoji(text, replace=" ")
    text = strip_ifb_phrases(text)
    text = HASHTAG_RE.sub(
        lambda m: " " if m.group(1).lower().replace("_", "") in IFB_TOKENS or m.group(1).lower() in IFB_TOKENS else " " + m.group(1),
        text,
    )
    tokens = []
    for tok in re.findall(r"[A-Za-zA-ZÀ-ÿ]+|[A-Za-z]+|\w+", text, flags=re.UNICODE):
        key = tok.lower().replace("_", "")
        if key in IFB_TOKENS or tok.lower() in IFB_TOKENS:
            continue
        if tok.lower() in STOPWORDS:
            continue
        tokens.append(tok)
    return MULTI_SPACE_RE.sub(" ", " ".join(tokens)).strip()


def letter_count(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha())


def detect_language(original: str) -> dict[str, Any]:
    raw = (original or "").strip()
    if not raw:
        return {
            "detected_lang": "und",
            "detect_confidence": 0.0,
            "detect_status": "empty",
            "detect_method": "none",
            "detect_text": "",
        }
    stripped = detection_text(raw)
    probe = stripped if letter_count(stripped) >= MIN_DETECT_LETTERS else ""
    non_latin = sum(
        1
        for ch in raw
        if ch.isalpha() and not ("A" <= ch <= "Z" or "a" <= ch <= "z")
    )
    hint = script_hint(raw)
    if hint and hint != "en" and non_latin >= MIN_DETECT_LETTERS:
        return {
            "detected_lang": hint,
            "detect_confidence": 0.99,
            "detect_status": "script_override",
            "detect_method": f"unicode_script:{hint}",
            "detect_text": stripped[:200],
        }
    if letter_count(stripped) < MIN_DETECT_LETTERS or len(stripped) < MIN_DETECT_CHARS:
        return {
            "detected_lang": "und",
            "detect_confidence": 0.0,
            "detect_status": "ifb_dominated",
            "detect_method": "insufficient_after_ifb_strip",
            "detect_text": stripped[:200],
        }
    try:
        DetectorFactory.seed = 2026
        langs = detect_langs(probe)
        if not langs:
            raise LangDetectException("no lang", "none")
        best = langs[0]
        code = best.lang
        conf = float(best.prob)
        if code == "zh-cn" or code == "zh-tw":
            code = "zh"
        status = "detected" if conf >= LANGDETECT_OK else ("low_confidence" if conf >= LANGDETECT_LOW else "low_confidence")
        if conf < LANGDETECT_LOW:
            status = "low_confidence"
        return {
            "detected_lang": code,
            "detect_confidence": round(conf, 4),
            "detect_status": status,
            "detect_method": "langdetect_on_ifb_stripped",
            "detect_text": stripped[:200],
        }
    except LangDetectException:
        return {
            "detected_lang": "und",
            "detect_confidence": 0.0,
            "detect_status": "detect_error",
            "detect_method": "langdetect_exception",
            "detect_text": stripped[:200],
        }


def tokenize_for_clean(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text or "")
    text = text.lower()
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = HASHTAG_RE.sub(r" \1 ", text)
    text = emoji.replace_emoji(text, replace=" ")
    text = PUNCT_RE.sub(" ", text)
    text = MULTI_SPACE_RE.sub(" ", text).strip()
    return [t for t in text.split(" ") if t]


def apply_stop_and_stem(tokens: list[str]) -> list[str]:
    out = []
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        if tok.isdigit():
            continue
        if len(tok) < 2:
            continue
        out.append(STEMMER.stem(tok))
    return out


def clean_text(original: str) -> str:
    return " ".join(apply_stop_and_stem(tokenize_for_clean(original)))


def topic_text(original: str) -> str:
    text = unicodedata.normalize("NFC", original or "")
    text = text.lower()
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = strip_ifb_phrases(text)
    text = HASHTAG_RE.sub(r" \1 ", text)
    text = emoji.replace_emoji(text, replace=" ")
    text = PUNCT_RE.sub(" ", text)
    tokens = []
    for tok in MULTI_SPACE_RE.sub(" ", text).strip().split(" "):
        if not tok or len(tok) < 2 or tok.isdigit():
            continue
        compact = tok.replace("_", "").replace("-", "")
        if tok in IFB_TOKENS or compact in IFB_TOKENS:
            continue
        if tok in STOPWORDS:
            continue
        tokens.append(STEMMER.stem(tok))
    return " ".join(tokens)


def translation_plan(source: str, orig_lang: str, detected: dict[str, Any], topic: str, clean: str) -> dict[str, str]:
    if source == "timeline":
        code = (orig_lang or "").strip().lower()
        if code == "en":
            nlp = "retain" if len(clean.split()) >= MIN_NLP_TOKENS else "exclude_too_short"
            return {
                "translation_status": "already_english",
                "text_translated_en": "",  # not copied; original is English
                "nlp_status": nlp,
                "exclude_reason": "" if nlp == "retain" else "too_few_tokens_after_clean",
            }
        if code in NON_LINGUISTIC:
            return {
                "translation_status": "not_applicable",
                "text_translated_en": "",
                "nlp_status": "exclude_non_linguistic",
                "exclude_reason": f"timeline LANG={code} is not a language",
            }
        return {
            "translation_status": "translation_required",
            "text_translated_en": "",
            "nlp_status": "hold_for_translation",
            "exclude_reason": "",
        }
    # keyword tweets
    status = detected["detect_status"]
    lang = detected["detected_lang"]
    if status == "empty":
        return {
            "translation_status": "not_applicable",
            "text_translated_en": "",
            "nlp_status": "exclude_empty",
            "exclude_reason": "empty original text",
        }
    if status == "ifb_dominated":
        return {
            "translation_status": "unknown_ifb_template",
            "text_translated_en": "",
            "nlp_status": "exclude_ifb_boilerplate",
            "exclude_reason": "after IFB/follow stripping, too little language signal remains",
        }
    if lang == "en" and status in {"detected", "low_confidence"}:
        nlp = "retain" if len(clean.split()) >= MIN_NLP_TOKENS else "exclude_too_short"
        topic_ok = len(topic.split()) >= MIN_NLP_TOKENS
        if nlp == "retain" and not topic_ok:
            return {
                "translation_status": "already_english",
                "text_translated_en": "",
                "nlp_status": "retain_sentiment_exclude_topics",
                "exclude_reason": "topic_text too short after IFB term removal",
            }
        return {
            "translation_status": "already_english",
            "text_translated_en": "",
            "nlp_status": nlp,
            "exclude_reason": "" if nlp == "retain" else "too_few_tokens_after_clean",
        }
    if lang not in {"en", "und"} and status in {"detected", "script_override", "low_confidence"}:
        return {
            "translation_status": "translation_required",
            "text_translated_en": "",
            "nlp_status": "hold_for_translation",
            "exclude_reason": "",
        }
    return {
        "translation_status": "uncertain",
        "text_translated_en": "",
        "nlp_status": "exclude_uncertain_language",
        "exclude_reason": f"status={status} lang={lang}",
    }


def normalize_dup_key(text: str) -> str:
    t = (text or "").lower()
    t = URL_RE.sub(" ", t)
    t = MENTION_RE.sub(" ", t)
    t = emoji.replace_emoji(t, replace=" ")
    t = MULTI_SPACE_RE.sub(" ", t).strip()
    return t


def hash_text(text: str) -> str:
    return hashlib.sha1(normalize_dup_key(text).encode("utf-8", "ignore")).hexdigest()


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


def enrich_row(row: dict[str, Any], detected: dict[str, Any]) -> dict[str, Any]:
    original = row.get("text") or ""
    clean = clean_text(original)
    topic = topic_text(original)
    plan = translation_plan(row.get("source") or "", row.get("lang") or "", detected, topic, clean)
    out = dict(row)
    out.update(detected)
    out["original_text"] = original
    out["clean_text"] = clean
    out["topic_text"] = topic
    out["clean_tokens"] = len(clean.split()) if clean else 0
    out["topic_tokens"] = len(topic.split()) if topic else 0
    out["dup_hash"] = hash_text(original)
    out.update(plan)
    return out


def choose_examples(rows: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["detect_status"] == "ifb_dominated":
            key = "ifb_dominated"
        elif r["detected_lang"] != "en" and r["detect_status"] in {"detected", "script_override", "low_confidence"}:
            key = "non_english"
        elif r["detect_status"] == "low_confidence":
            key = "low_confidence"
        elif r["nlp_status"] == "retain_sentiment_exclude_topics":
            key = "empty_topic"
        elif r["detected_lang"] == "en":
            key = "english"
        else:
            key = "other"
        buckets[key].append(r)
    quotas = {
        "english": 25,
        "non_english": 25,
        "ifb_dominated": 25,
        "low_confidence": 15,
        "empty_topic": 10,
        "other": 10,
    }
    chosen: list[dict[str, Any]] = []
    seen = set()
    for key, n in quotas.items():
        pool = [r for r in buckets.get(key, []) if r["tweet_id"] not in seen]
        rng.shuffle(pool)
        for r in pool[:n]:
            r = dict(r)
            r["example_role"] = key
            chosen.append(r)
            seen.add(r["tweet_id"])
    # Fill to 100+ with remaining diverse keywords
    by_kw: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["tweet_id"] not in seen:
            by_kw[r.get("keyword") or ""].append(r)
    for kw, pool in by_kw.items():
        if len(chosen) >= 120:
            break
        rng.shuffle(pool)
        r = dict(pool[0])
        r["example_role"] = "keyword_coverage"
        chosen.append(r)
        seen.add(r["tweet_id"])
    return chosen


def open_working_db(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE nlp_working (
            tweet_id TEXT,
            author_id TEXT,
            username TEXT,
            created_at TEXT,
            source TEXT,
            keyword TEXT,
            original_text TEXT,
            original_lang TEXT,
            detected_lang TEXT,
            detect_confidence REAL,
            detect_status TEXT,
            detect_method TEXT,
            text_translated_en TEXT,
            translation_status TEXT,
            clean_text TEXT,
            topic_text TEXT,
            nlp_status TEXT,
            exclude_reason TEXT,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    return conn


def insert_working(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO nlp_working (
            tweet_id, author_id, username, created_at, source, keyword,
            original_text, original_lang, detected_lang, detect_confidence,
            detect_status, detect_method, text_translated_en, translation_status,
            clean_text, topic_text, nlp_status, exclude_reason
        ) VALUES (
            :tweet_id, :author_id, :username, :created_at, :source, :keyword,
            :original_text, :lang, :detected_lang, :detect_confidence,
            :detect_status, :detect_method, :text_translated_en, :translation_status,
            :clean_text, :topic_text, :nlp_status, :exclude_reason
        )
        """,
        rows,
    )


def write_report(stats: dict[str, Any]) -> None:
    kw_lang_lines = "\n".join(
        f"| `{lang}` | {n:,} | {pct:.2f}% | {note} |"
        for lang, n, pct, note in stats["random_lang_table"]
    )
    sample_lang_lines = "\n".join(
        f"| `{lang}` | {n:,} | {pct:.2f}% |"
        for lang, n, pct in stats["sample_lang_table"]
    )
    status_lines = "\n".join(
        f"| {k} | {v:,} |" for k, v in stats["sample_status"].items()
    )
    nlp_lines = "\n".join(f"| {k} | {v:,} |" for k, v in stats["sample_nlp"].items())
    boiler_lines = "\n".join(
        f"| {n} | {repr(t)[:80]} |" for t, n in stats["top_boilerplate"]
    )
    ifb_token_preview = ", ".join(sorted(list(IFB_TOKENS))[:40]) + ", …"
    text = f"""# Language detection and preprocessing report

Built: {stats['built_at']}
Input: `data/analysis_corpus.db` (read-only). `IFB.db` was not opened.
Working sample DB: `data/nlp_working_sample.db` (not a 39-million-row CSV).
Stemming: **{STEM_METHOD}**.
Language detector: **langdetect** with `DetectorFactory.seed = 2026`, plus Unicode-script overrides.
No sentiment, emotion, BERTopic, NER, network, or bot detection was run.
No bulk translation was run.

## How keyword languages were determined

Keyword tweets have no `LANG` column. They were **not** assumed to be English.

1. Load the stratified table `keyword_lang_sample` (**{stats['n_stratified']:,}** rows; ~120 per collection keyword).
2. Strip URLs, @mentions, emojis, and IFB/follow collection phrases/tokens.
3. If the remaining alphabetic signal is too short → status `ifb_dominated` (typical copy-paste “follow for follow” templates).
4. If the original text is dominated by a non-Latin script (Arabic, CJK, Hangul, Hiragana, Cyrillic, Hebrew, Thai, Devanagari) → `script_override`.
5. Otherwise run `langdetect` on the IFB-stripped probe text.
6. A **random reservoir of {stats['n_random']:,}** keyword tweets from the full **{stats['n_keyword_corpus']:,}** keyword posts was detected the same way. That random sample is the **population estimate**. The stratified 2,734-row sample is biased toward rare keywords and is used for manual review and per-keyword checks.

### Stratified sample (2,734) — unweighted

| detected_lang | n | percent |
|---------------|--:|--------:|
{sample_lang_lines}

### Detection status (stratified sample)

| status | n |
|--------|--:|
{status_lines}

### Random keyword sample — estimated distribution of {stats['n_keyword_corpus']:,} keyword tweets

| detected_lang | n in sample | estimated % | note |
|---------------|------------:|------------:|------|
{kw_lang_lines}

**Do not treat `ifb_dominated` as English.** Those posts are mostly collection templates; langdetect would often label the raw string `en` because the template words are English.

## Which posts require translation

| Group | Rule | This phase |
|-------|------|------------|
| Timeline `LANG=en` | Already English | No translation |
| Timeline `und`,`qme`,`qam`,`zxx` | Not languages | **Do not translate**; exclude from NLP |
| Timeline other codes (`es`,`ja`,…) | Real languages | **Translation required** later (batch 500) |
| Keyword `detected`/`script_override` and not `en` | Real non-English | **Translation required** later |
| Keyword `already_english` | Detected English with enough tokens | No translation |
| Keyword `ifb_dominated` / uncertain | No reliable language | **Do not translate** until reviewed |

Estimated keyword tweets needing translation (from random sample, excluding `ifb_dominated` and `en`): **{stats['est_kw_translation_pct']:.2f}%** of keyword tweets (~{stats['est_kw_translation_n']:,} of {stats['n_keyword_corpus']:,}).

Timeline (already counted in the corpus, not re-detected): English 78.2% (no translation); non-linguistic 10.0% (exclude); other languages 11.8% (translation required).

`text_translated_en` is stored as empty in this phase. Original text is always preserved.

## Which posts are excluded from NLP and why

| nlp_status | Meaning |
|------------|---------|
| retain | Eligible for sentiment/emotion (and topics if `topic_text` has ≥{MIN_NLP_TOKENS} tokens) |
| retain_sentiment_exclude_topics | English/IFB leftovers too thin for BERTopic |
| hold_for_translation | Wait until Phase 2.1 translation |
| exclude_non_linguistic | Timeline `und/qme/qam/zxx` |
| exclude_ifb_boilerplate | No language left after IFB strip |
| exclude_too_short | `< {MIN_NLP_TOKENS}` tokens after `clean_text` |
| exclude_uncertain_language | Detector failed or `und` |
| exclude_empty | Empty original |

Stratified keyword sample NLP statuses:

| nlp_status | n |
|------------|--:|
{nlp_lines}

Records processed in this phase (not the full 39M):

| Set | Processed | Retained for later English NLP (`retain` + `retain_sentiment_exclude_topics`) |
|-----|----------:|----------------------------------:|
| Stratified keyword sample | {stats['n_stratified']:,} | {stats['n_sample_retained']:,} |
| Random keyword sample | {stats['n_random']:,} | {stats['n_random_retained']:,} |
| Timeline working sample | {stats['n_timeline_sample']:,} | {stats['n_timeline_retained']:,} |
| **Total working rows written** | {stats['n_working']:,} | {stats['n_working_retained']:,} |

Full corpus still lives only in `data/analysis_corpus.db`. Cleaning functions are applied to working samples so later stages can reuse the same code on chunks.

## Duplicate / boilerplate IFB text

Normalized duplicate key: lowercase, URLs/mentions/emojis removed, whitespace collapsed.

| Corpus slice | Exact extra rows | Duplicate groups |
|--------------|-----------------:|-----------------:|
| Stratified keyword sample ({stats['n_stratified']:,}) | {stats['sample_dup_extra']:,} | {stats['sample_dup_groups']:,} |
| All keyword tweets hashed ({stats['n_keyword_corpus']:,}) | {stats['all_kw_dup_extra']:,} | {stats['all_kw_dup_groups']:,} |

Top normalized templates in the stratified sample:

| copies | text preview |
|-------:|--------------|
{boiler_lines}

These templates should not drive topics. `topic_text` is designed to empty them out.

## How IFB / follow terms were removed for topic modeling

`clean_text` (sentiment/emotion): lowercase; drop URLs, @mentions, emojis, punctuation; keep hashtag tokens without `#`; drop English stopwords (NLTK, {stats['n_stopwords']} words); **Porter stem**. Collection words such as “follow” are **kept** here because they are the tweet content.

`topic_text` (BERTopic later): the same steps, **plus**:

1. Phrase deletion (longest first), including: {", ".join(IFB_PHRASES[:8])}, …
2. Token deletion of the collection lexicon ({len(IFB_TOKENS)} tokens), including: {ifb_token_preview}
3. Hashtags whose token is in that lexicon (`#ifb`, `#followforfollow`, `#f4f`, …)

Original text is never overwritten.

## Preprocessing examples

See `outputs/preprocessing_examples.csv` ({stats['n_preproc_examples']} before/after rows) and `outputs/keyword_language_examples.csv` ({stats['n_examples']} curated review rows; ≥100).

## Limitations and likely detector errors

- Short IFB English templates are labeled `ifb_dominated`, not `en`. That is intentional.
- Mixed tweets (French/Japanese + English “follow back”) may still be classified as the majority remaining script or as `en` if many English words survive.
- `langdetect` is unstable on very short strings; seed 2026 makes this run reproducible but not perfectly accurate.
- Indonesian (`id`/`in`) vs English confusion is possible on Latin-alphabet spam.
- Keyword population percentages are **estimates from {stats['n_random']:,} random posts**, not a full 1.13M detection pass.
- Timeline language uses Twitter `LANG` from the corpus; this phase does not re-detect timeline text.
- Porter stemming is crude (`follow` → `follow` already; `following` → `follow`). It is deterministic and does not need a POS tagger.
- No Google Translate / googletrans calls were made.

## Next phase (not done)

Translate only `translation_status = translation_required` rows, in batches of 500, after reviewing `outputs/keyword_language_examples.csv`. Then run sentiment on English + translated text, never on `und/qme/qam/zxx`.
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    rng = random.Random(RNG_SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Opening {CORPUS_DB} read-only...")
    src = connect_ro(CORPUS_DB)
    try:
        n_kw = src.execute(
            "SELECT COUNT(*) FROM posts WHERE source='keyword_tweets'"
        ).fetchone()[0]
        n_tl = src.execute(
            "SELECT COUNT(*) FROM posts WHERE source='timeline'"
        ).fetchone()[0]
        log(f"Corpus keyword={n_kw:,} timeline={n_tl:,}")

        stratified_raw = [dict(r) for r in src.execute("SELECT * FROM keyword_lang_sample")]
        log(f"Detecting language on stratified sample n={len(stratified_raw):,}...")
        stratified = []
        for r in stratified_raw:
            det = detect_language(r.get("text") or "")
            stratified.append(enrich_row(r, det))

        log("Streaming keyword tweets: random language sample + duplicate hashes...")
        random_res = Reservoir(RANDOM_KEYWORD_N, rng)
        dup_counter: Counter[str] = Counter()
        n_stream = 0
        cur = src.execute(
            "SELECT tweet_id, author_id, created_at, text, lang, source FROM posts WHERE source='keyword_tweets'"
        )
        while True:
            chunk = cur.fetchmany(CHUNK)
            if not chunk:
                break
            for tweet_id, author_id, created_at, text, lang, source in chunk:
                n_stream += 1
                dup_counter[hash_text(text or "")] += 1
                random_res.offer(
                    {
                        "tweet_id": tweet_id,
                        "author_id": author_id,
                        "username": "",
                        "created_at": created_at,
                        "text": text,
                        "lang": lang,
                        "source": source,
                        "keyword": "",
                    }
                )
                if n_stream % 200_000 == 0:
                    log(f"  keyword stream {n_stream:,}")
        log(f"  hashed {n_stream:,} keyword tweets")

        # attach usernames for random sample
        ids = list({r["author_id"] for r in random_res.items})
        unames = {}
        for i in range(0, len(ids), 500):
            batch = ids[i : i + 500]
            q = ",".join("?" * len(batch))
            for aid, uname in src.execute(
                f"SELECT author_id, username FROM users WHERE author_id IN ({q})", batch
            ):
                unames[aid] = uname
        random_rows = []
        log(f"Detecting language on random keyword sample n={len(random_res.items):,}...")
        for r in random_res.items:
            r["username"] = unames.get(r["author_id"], "")
            det = detect_language(r.get("text") or "")
            random_rows.append(enrich_row(r, det))

        log("Sampling timeline rows for preprocessing (SQL modulo, not full CSV)...")
        tl_raw = [
            dict(r)
            for r in src.execute(
                """
                SELECT p.tweet_id, p.author_id, u.username, p.created_at, p.text, p.lang, p.source,
                       '' AS keyword
                FROM posts p
                JOIN users u ON u.author_id = p.author_id
                WHERE p.source = 'timeline' AND p.rowid % 7919 = 3
                LIMIT ?
                """,
                (TIMELINE_SAMPLE_N,),
            )
        ]
        timeline_rows = []
        for r in tl_raw:
            det = {
                "detected_lang": (r.get("lang") or "und"),
                "detect_confidence": 1.0 if (r.get("lang") == "en") else 0.0,
                "detect_status": "twitter_lang",
                "detect_method": "corpus_timeline_LANG",
                "detect_text": "",
            }
            timeline_rows.append(enrich_row(r, det))
        log(f"  timeline sample {len(timeline_rows):,}")
    finally:
        src.close()

    def count_dups(rows: list[dict[str, Any]]) -> tuple[int, int, list[tuple[str, int]]]:
        c = Counter((r.get("text") or "") for r in rows)
        extra = sum(v - 1 for v in c.values() if v > 1)
        groups = sum(1 for v in c.values() if v > 1)
        top = [(t, n) for t, n in c.most_common(8) if n > 1]
        return extra, groups, top

    sample_dup_extra, sample_dup_groups, top_boiler = count_dups(stratified)
    all_extra = sum(v - 1 for v in dup_counter.values() if v > 1)
    all_groups = sum(1 for v in dup_counter.values() if v > 1)

    sample_lang = Counter(r["detected_lang"] for r in stratified)
    sample_status = Counter(r["detect_status"] for r in stratified)
    sample_nlp = Counter(r["nlp_status"] for r in stratified)
    random_lang = Counter(r["detected_lang"] for r in random_rows)
    random_status = Counter(r["detect_status"] for r in random_rows)

    def pct_table(counter: Counter, n: int):
        rows = []
        for lang, c in counter.most_common():
            rows.append((lang, c, 100.0 * c / n if n else 0.0))
        return rows

    n_random = len(random_rows) or 1
    translation_like = sum(
        1
        for r in random_rows
        if r["translation_status"] == "translation_required"
    )
    est_pct = 100.0 * translation_like / n_random
    est_n = int(round(est_pct / 100.0 * n_kw))

    random_lang_table = []
    for lang, c in random_lang.most_common():
        note = random_status.get("ifb_dominated", 0) and lang == "und"
        status_note = ""
        if lang == "und":
            status_note = "mostly ifb_dominated / undetectable, not English"
        elif lang == "en":
            status_note = "English after IFB strip"
        else:
            status_note = "translation required later"
        random_lang_table.append((lang, c, 100.0 * c / n_random, status_note))
    # also add status breakdown rows via notes only

    n_sample_retained = sum(
        1
        for r in stratified
        if r["nlp_status"] in {"retain", "retain_sentiment_exclude_topics"}
    )
    n_random_retained = sum(
        1
        for r in random_rows
        if r["nlp_status"] in {"retain", "retain_sentiment_exclude_topics"}
    )
    n_timeline_retained = sum(
        1
        for r in timeline_rows
        if r["nlp_status"] in {"retain", "retain_sentiment_exclude_topics"}
    )

    examples = choose_examples(stratified, rng)
    example_fields = [
        "example_role",
        "tweet_id",
        "author_id",
        "username",
        "created_at",
        "keyword",
        "source",
        "original_text",
        "detected_lang",
        "detect_confidence",
        "detect_status",
        "detect_method",
        "translation_status",
        "nlp_status",
        "exclude_reason",
        "clean_text",
        "topic_text",
    ]
    write_csv(EXAMPLES_CSV, example_fields, examples)

    preproc_pool = stratified + timeline_rows
    rng.shuffle(preproc_pool)
    preproc_examples = []
    seen_roles = Counter()
    for r in preproc_pool:
        role = r["nlp_status"]
        if seen_roles[role] >= 6:
            continue
        seen_roles[role] += 1
        preproc_examples.append(
            {
                "tweet_id": r["tweet_id"],
                "source": r["source"],
                "keyword": r.get("keyword") or "",
                "original_lang": r.get("lang") or "",
                "detected_lang": r["detected_lang"],
                "detect_status": r["detect_status"],
                "nlp_status": r["nlp_status"],
                "original_text": r["original_text"],
                "clean_text": r["clean_text"],
                "topic_text": r["topic_text"],
                "clean_tokens": r["clean_tokens"],
                "topic_tokens": r["topic_tokens"],
            }
        )
        if len(preproc_examples) >= 40:
            break
    write_csv(
        PREPROC_CSV,
        [
            "tweet_id",
            "source",
            "keyword",
            "original_lang",
            "detected_lang",
            "detect_status",
            "nlp_status",
            "original_text",
            "clean_text",
            "topic_text",
            "clean_tokens",
            "topic_tokens",
        ],
        preproc_examples,
    )

    working_rows = []
    for r in stratified + random_rows + timeline_rows:
        working_rows.append(
            {
                "tweet_id": r["tweet_id"],
                "author_id": r["author_id"],
                "username": r.get("username") or "",
                "created_at": r["created_at"],
                "source": r["source"],
                "keyword": r.get("keyword") or "",
                "original_text": r["original_text"],
                "lang": r.get("lang") or "",
                "detected_lang": r["detected_lang"],
                "detect_confidence": r["detect_confidence"],
                "detect_status": r["detect_status"],
                "detect_method": r["detect_method"],
                "text_translated_en": r["text_translated_en"],
                "translation_status": r["translation_status"],
                "clean_text": r["clean_text"],
                "topic_text": r["topic_text"],
                "nlp_status": r["nlp_status"],
                "exclude_reason": r["exclude_reason"],
            }
        )
    dst = open_working_db(WORKING_DB)
    insert_working(dst, working_rows)
    dst.commit()
    n_working = dst.execute("SELECT COUNT(*) FROM nlp_working").fetchone()[0]
    n_working_retained = dst.execute(
        "SELECT COUNT(*) FROM nlp_working WHERE nlp_status IN ('retain','retain_sentiment_exclude_topics')"
    ).fetchone()[0]
    dst.close()

    stat_rows = []

    def add(metric, value, notes=""):
        stat_rows.append({"metric": metric, "value": value, "notes": notes})

    add("n_keyword_corpus", n_kw, "from analysis_corpus.db")
    add("n_timeline_corpus", n_tl, "")
    add("n_stratified_keyword_sample", len(stratified), "keyword_lang_sample")
    add("n_random_keyword_sample", len(random_rows), "reservoir from all keyword tweets")
    add("n_timeline_working_sample", len(timeline_rows), "rowid modulo sample")
    add("n_working_rows", n_working, "data/nlp_working_sample.db")
    add("n_working_retained_english_nlp", n_working_retained, "")
    add("stratified_retained", n_sample_retained, "")
    add("random_retained", n_random_retained, "")
    add("timeline_sample_retained", n_timeline_retained, "")
    add("est_keyword_translation_pct", round(est_pct, 4), "from random sample")
    add("est_keyword_translation_n", est_n, "extrapolated")
    add("keyword_exact_dup_extra_all", all_extra, "normalized hash over all keyword tweets")
    add("keyword_exact_dup_groups_all", all_groups, "")
    add("sample_dup_extra", sample_dup_extra, "")
    add("sample_dup_groups", sample_dup_groups, "")
    add("n_review_examples", len(examples), ">=100")
    add("stemming", STEM_METHOD, "")
    add("detector", "langdetect seed=2026 + unicode script override", "")
    add("ifb_token_count", len(IFB_TOKENS), "removed in topic_text only")
    for lang, c, pct, note in random_lang_table:
        add(f"random_lang_{lang}", c, f"{pct:.2f}% {note}")
    for st, c in sample_status.most_common():
        add(f"stratified_status_{st}", c, "")
    for st, c in sample_nlp.most_common():
        add(f"stratified_nlp_{st}", c, "")
    write_csv(STATS_CSV, ["metric", "value", "notes"], stat_rows)

    write_report(
        {
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_stratified": len(stratified),
            "n_random": len(random_rows),
            "n_keyword_corpus": n_kw,
            "n_timeline_sample": len(timeline_rows),
            "n_working": n_working,
            "n_working_retained": n_working_retained,
            "n_sample_retained": n_sample_retained,
            "n_random_retained": n_random_retained,
            "n_timeline_retained": n_timeline_retained,
            "sample_lang_table": pct_table(sample_lang, len(stratified)),
            "sample_status": dict(sample_status),
            "sample_nlp": dict(sample_nlp),
            "random_lang_table": random_lang_table,
            "est_kw_translation_pct": est_pct,
            "est_kw_translation_n": est_n,
            "sample_dup_extra": sample_dup_extra,
            "sample_dup_groups": sample_dup_groups,
            "all_kw_dup_extra": all_extra,
            "all_kw_dup_groups": all_groups,
            "top_boilerplate": top_boiler,
            "n_stopwords": len(STOPWORDS),
            "n_preproc_examples": len(preproc_examples),
            "n_examples": len(examples),
        }
    )

    elapsed = time.perf_counter() - started
    log("")
    log("========== LANGUAGE / PREPROCESS SUMMARY ==========")
    log(f"stratified={len(stratified)} random_kw={len(random_rows)} timeline_sample={len(timeline_rows)}")
    log(f"sample_status={dict(sample_status)}")
    log(f"sample_nlp={dict(sample_nlp)}")
    log(f"random_lang={dict(random_lang)}")
    log(f"est_keyword_translation_pct={est_pct:.2f} est_n={est_n}")
    log(f"keyword_dup_extra={all_extra} groups={all_groups}")
    log(f"review_examples={len(examples)} preproc_examples={len(preproc_examples)}")
    log(f"working_rows={n_working} retained={n_working_retained}")
    log(f"elapsed_seconds={elapsed:.1f}")
    log("LANG_PREPROCESS_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
