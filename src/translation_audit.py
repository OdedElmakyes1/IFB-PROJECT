#!/usr/bin/env python3
"""Phase 2.1: translation audit and English-text verification.

Uses only data/nlp_analysis_corpus.db. Does not open IFB.db.
Does not call a translation API. Does not run sentiment/emotion/topics.
"""

from __future__ import annotations

import random
import sqlite3
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_nlp_analysis_corpus import classify_keyword_text  # noqa: E402
from language_detection_and_preprocessing import (  # noqa: E402
    HASHTAG_RE,
    MENTION_RE,
    URL_RE,
    write_csv,
)

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
EXAMPLES_CSV = OUTPUT_DIR / "translation_examples.csv"
REPORT = ROOT / "TRANSLATION_DECISION.md"

RNG_SEED = 2026
CHUNK = 20_000
UPDATE_SIZE = 4_000
PROGRESS = 100_000
N_EXAMPLES = 12

REQUIRED_FIELDS = (
    "original_text",
    "clean_text",
    "topic_text",
    "created_at",
    "lang",
    "source",
    "sample_weight",
)

# Keyword posts excluded from the NLP corpus (from NLP_SAMPLING_PLAN.md census).
KEYWORD_POPULATION = 1_129_607
KEYWORD_RETAINED = 244_221
KEYWORD_IFB_DOMINATED = 513_390
KEYWORD_LIKELY_ENGLISH = 575_775
KEYWORD_SCRIPT_NON_EN = 20_302
KEYWORD_UNCERTAIN = 20_140
KEYWORD_BOILERPLATE = 806_651
KEYWORD_SHORT_CLEAN = 220

TIMELINE_PRIMARY = 37_839_416
TIMELINE_EN_POPULATION = 29_573_764
TIMELINE_SAMPLED = 500_000


def log(msg: str) -> None:
    print(msg, flush=True)


def connect_nlp(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(str(path), timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = set(table_columns(conn, "nlp_posts"))
    missing = [c for c in REQUIRED_FIELDS if c not in cols]
    if missing:
        raise RuntimeError(f"nlp_posts missing required fields: {missing}")
    for name, decl in (
        ("translation_status", "TEXT"),
        ("text_translated_en", "TEXT"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE nlp_posts ADD COLUMN {name} {decl}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_quality (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            translation_status TEXT NOT NULL,
            keyword_rule_class TEXT,
            encoding_ok INTEGER NOT NULL,
            has_replacement INTEGER NOT NULL,
            has_unreadable INTEGER NOT NULL,
            has_hashtag INTEGER NOT NULL,
            has_mention INTEGER NOT NULL,
            has_url INTEGER NOT NULL,
            empty_original INTEGER NOT NULL,
            empty_clean INTEGER NOT NULL,
            empty_topic INTEGER NOT NULL,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.execute("DELETE FROM translation_quality")
    conn.commit()


def is_empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def has_unreadable(text: str) -> bool:
    for ch in text:
        if ch in "\t\n\r":
            continue
        cat = unicodedata.category(ch)
        if cat in {"Cc", "Cs"}:
            return True
        if ch == "\ufffd":
            return True
    return False


def encoding_ok(text: str) -> bool:
    try:
        text.encode("utf-8").decode("utf-8")
    except UnicodeError:
        return False
    return "\ufffd" not in text


def decide_status(
    source: str,
    lang: str,
    original: str,
    keyword_class: str | None,
) -> str:
    """Assign translation_status. Never calls a translator."""
    if is_empty(original):
        return "uncertain"
    if "\ufffd" in original or has_unreadable(original):
        return "uncertain"
    if source == "timeline":
        if (lang or "").lower() != "en":
            return "requires_translation"
        if keyword_class == "script_non_english":
            return "requires_translation"
        if keyword_class == "uncertain":
            return "uncertain"
        return "not_required_english"
    # keyword_tweets: stored lang='en' is the census label, not Twitter LANG.
    if keyword_class == "script_non_english":
        return "requires_translation"
    if keyword_class in {"uncertain", "empty", "ifb_dominated"}:
        return "uncertain"
    if keyword_class == "likely_english":
        return "not_required_english"
    return "uncertain"


def audit_row(source: str, lang: str, original: str, clean: str, topic: str) -> dict[str, Any]:
    raw = original or ""
    kw_class = classify_keyword_text(raw)
    status = decide_status(source, lang, raw, kw_class)
    translated = raw if status == "not_required_english" else None
    return {
        "translation_status": status,
        "text_translated_en": translated,
        "keyword_rule_class": kw_class if source == "keyword_tweets" else kw_class,
        "encoding_ok": int(encoding_ok(raw)),
        "has_replacement": int("\ufffd" in raw),
        "has_unreadable": int(has_unreadable(raw)),
        "has_hashtag": int(bool(HASHTAG_RE.search(raw))),
        "has_mention": int(bool(MENTION_RE.search(raw))),
        "has_url": int(bool(URL_RE.search(raw))),
        "empty_original": int(is_empty(raw)),
        "empty_clean": int(is_empty(clean)),
        "empty_topic": int(is_empty(topic)),
    }


def reservoir_offer(
    buckets: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    key: str,
    row: dict[str, Any],
    cap: int = 40,
) -> None:
    bucket = buckets[key]
    if len(bucket) < cap:
        bucket.append(row)
        return
    j = rng.randint(0, 10**9) % (cap + 1)
    if j < cap:
        bucket[j] = row


def pick_examples(
    buckets: dict[str, list[dict[str, Any]]], rng: random.Random, n: int
) -> list[dict[str, Any]]:
    kw_need = n // 2
    tl_need = n - kw_need
    kw_order = ["kw_hash", "kw_mention", "kw_url", "kw_plain", "kw_empty_clean"]
    tl_order = ["tl_hash", "tl_mention", "tl_url", "tl_plain", "tl_empty_clean"]

    def take(keys: list[str], need: int) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for key in keys:
            rng.shuffle(buckets[key])
            for row in buckets[key]:
                ident = (row["source"], row["tweet_id"])
                if ident in seen:
                    continue
                if row["translation_status"] != "not_required_english":
                    continue
                if not row["text_translated_en"]:
                    continue
                picked.append(row)
                seen.add(ident)
                if len(picked) >= need:
                    return picked
        return picked

    return take(kw_order, kw_need) + take(tl_order, tl_need)


def write_report(stats: dict[str, Any]) -> None:
    st = stats["status"]
    src = stats["source_status"]
    q = stats["quality"]
    field_lines = "\n".join(f"| `{c}` | present |" for c in REQUIRED_FIELDS)
    example_rows = "\n".join(
        f"| {i} | {r['source']} | `{r['tweet_id']}` | {r['original_preview']} | {r['translated_preview']} | {r['same_as_original']} |"
        for i, r in enumerate(stats["example_previews"], start=1)
    )
    text = f"""# Translation decision

Built: {stats['built_at']}
Random seed: **{RNG_SEED}**
Input: `data/nlp_analysis_corpus.db` only. **`IFB.db` was not opened or modified.**
No translation API was called. Sentiment, emotion, BERTopic, NER, entity network, and bot detection were **not** run.

## Why translation was skipped for the retained English corpus

This is not “most posts are English, so skip the rest.” The NLP corpus was **built as English-ready** in `src/build_nlp_analysis_corpus.py`:

| Source | English rule |
|--------|----------------|
| Timeline | Twitter/X **`LANG = en` only**. Non-English and non-linguistic codes (`und`, `qme`, `qam`, `zxx`, `es`, `ja`, …) never entered this file. |
| Keyword tweets | No `LANG` column in the raw data. Posts were kept only if the **rule-based** class was `likely_english` (Latin remainder after IFB/follow strip), and not boilerplate / extra duplicates / too-short `clean_text`. |

For every retained post with `translation_status = not_required_english`, `text_translated_en` is a **byte-for-byte copy of `original_text`**. Translation was skipped because there is nothing to translate for the analysis set: later models (`pysentimiento`, BERTopic) will read English text.

Copying original → `text_translated_en` is an explicit no-op, not a silent machine translation.

## How keyword language uncertainty was handled

Keyword `lang = en` in `nlp_posts` is **not** a Twitter language tag. It means the census class was `likely_english`. This audit **re-ran** the same deterministic classifier (`classify_keyword_text`: Unicode script + IFB-stripped Latin ratio). langdetect was **not** used.

| Rule class on retained keyword posts | n |
|--------------------------------------|--:|
| `likely_english` | {stats['kw_class'].get('likely_english', 0):,} |
| `ifb_dominated` | {stats['kw_class'].get('ifb_dominated', 0):,} |
| `script_non_english` | {stats['kw_class'].get('script_non_english', 0):,} |
| `uncertain` | {stats['kw_class'].get('uncertain', 0):,} |
| `empty` | {stats['kw_class'].get('empty', 0):,} |

- Script-confirmed non-English remaining in this file (should be ~0) → `requires_translation`. **Not translated.** `text_translated_en` is NULL.
- Residual `uncertain` / `ifb_dominated` / empty / replacement characters → `uncertain`. **Not translated.** `text_translated_en` is NULL.
- `likely_english` with readable UTF-8 → `not_required_english`.

Do **not** treat langdetect codes `no` / `af` / `ca` / `so` / `cy` / `nl` on IFB spam as translation targets (documented in `NLP_SAMPLING_PLAN.md`).

## How many posts were excluded before this corpus was created

Exclusion happened **before** this audit, when `data/nlp_analysis_corpus.db` was built. Those rows are **not** in this file and were **not** sent to a translator.

### Keyword tweets (population 1,129,607)

| Item | N | Role vs translation |
|------|--:|---------------------|
| Retained in NLP corpus | **{KEYWORD_RETAINED:,}** | English-ready census |
| Not retained | **{KEYWORD_POPULATION - KEYWORD_RETAINED:,}** | out of this corpus |
| IFB-dominated templates | {KEYWORD_IFB_DOMINATED:,} | not a language to translate |
| Script-confirmed non-English | {KEYWORD_SCRIPT_NON_EN:,} | would need translation; **excluded instead** |
| Uncertain mixed/low-Latin | {KEYWORD_UNCERTAIN:,} | no reliable target language |
| Likely English before dup/boiler/short filters | {KEYWORD_LIKELY_ENGLISH:,} | many are copy-paste templates |
| Boilerplate hash freq ≥ 5 | {KEYWORD_BOILERPLATE:,} | duplicate spam, not translated |
| Dropped short `clean_text` | {KEYWORD_SHORT_CLEAN:,} | too little signal |

Exclusion reasons **overlap** (a post can be English-like and still boilerplate). Do not add the rows.

### Timeline posts (primary users: 37,839,416)

| Item | N | Role vs translation |
|------|--:|---------------------|
| `LANG = en` population | **{TIMELINE_EN_POPULATION:,}** | sampling frame |
| Not `LANG = en` | **{TIMELINE_PRIMARY - TIMELINE_EN_POPULATION:,}** | other languages + `und/qme/qam/zxx`; **excluded, not translated** |
| Stratified sample in NLP corpus | **{TIMELINE_SAMPLED:,}** | English-ready |

## Why excluded posts were not translated

1. **IFB templates and boilerplate** are English-looking spam. Translating them would not add discourse and would recreate the instructor’s “every post contains Follow/IFB” topic collapse.
2. **Keyword uncertain** text has no trustworthy language label. langdetect false-friends on this data are a known failure mode.
3. **Script-confirmed non-English keywords (~20k)** and **timeline non-`en` (~8.3M)** are real other languages. Translating them now would require an API/model, mix language communities into English sentiment, and blow past course compute. They were left **out of the NLP corpus** rather than silently dropped from a mixed file.
4. This is the opposite of the US-Elections grading note (keeping a mixed corpus and skipping ~12% non-English). Here the analysis file is English by construction, and the excluded counts are reported.

If a later stage needs multilingual coverage, translate only script-confirmed keyword posts and timeline rows with a real `LANG` (not `und/qme/qam/zxx`), in batches, without putting them into this English corpus first.

## Audit of the retained 744,221 posts

Verified fields:

| Field | Status |
|-------|--------|
{field_lines}

Timeline `lang = en`: **{stats['tl_en']:,}** / {stats['n_timeline']:,} (non-en = {stats['tl_not_en']:,}).

### `translation_status`

| Status | n | Share | `text_translated_en` |
|--------|--:|------:|----------------------|
| `not_required_english` | {st.get('not_required_english', 0):,} | {stats['pct_ok']:.4f}% | copy of `original_text` |
| `requires_translation` | {st.get('requires_translation', 0):,} | {stats['pct_need']:.4f}% | NULL (not translated) |
| `uncertain` | {st.get('uncertain', 0):,} | {stats['pct_unc']:.4f}% | NULL (not translated) |

By source:

| Source | not_required_english | requires_translation | uncertain |
|--------|---------------------:|---------------------:|----------:|
| keyword_tweets | {src['keyword_tweets'].get('not_required_english', 0):,} | {src['keyword_tweets'].get('requires_translation', 0):,} | {src['keyword_tweets'].get('uncertain', 0):,} |
| timeline | {src['timeline'].get('not_required_english', 0):,} | {src['timeline'].get('requires_translation', 0):,} | {src['timeline'].get('uncertain', 0):,} |

Posts used for later English NLP = `translation_status = not_required_english` (**{st.get('not_required_english', 0):,}**). Residual `requires_translation` / `uncertain` rows stay in SQLite for audit but must not be treated as translated English.

## Quality checks (original text)

| Check | Posts |
|-------|------:|
| UTF-8 round-trip OK and no U+FFFD | {q['encoding_ok']:,} |
| Replacement character U+FFFD | {q['has_replacement']:,} |
| Unreadable control/surrogate chars | {q['has_unreadable']:,} |
| Contains hashtag `#` | {q['has_hashtag']:,} |
| Contains username `@` | {q['has_mention']:,} |
| Contains URL | {q['has_url']:,} |
| Empty `original_text` | {q['empty_original']:,} |
| Empty `clean_text` | {q['empty_clean']:,} |
| Empty `topic_text` | {q['empty_topic']:,} |

Hashtags, @usernames, and URLs are **unchanged** in `text_translated_en` because that column is a copy of `original_text` for English-ready rows (not a translator that might drop entities).

`original_text` was never rewritten. Fingerprint before/after: {stats['fingerprint_ok']}.

## Raw counts vs weighted timeline estimates

Keyword posts are a **census** (`sampling_probability = 1`, `sample_weight = 1`). Timeline posts are a **probability sample** of the English timeline.

| Source | Raw rows in NLP file | Sum of `sample_weight` | What the weight estimates |
|--------|---------------------:|-----------------------:|---------------------------|
| keyword_tweets | {stats['n_keyword']:,} | {stats['w_keyword']:,.1f} | same as raw (census) |
| timeline | {stats['n_timeline']:,} | {stats['w_timeline']:,.1f} | English timeline population (~{TIMELINE_EN_POPULATION:,}) |
| **total** | {stats['n_total']:,} | {stats['w_total']:,.1f} | mixed; do not treat as one population |

Use **raw rows** for model fitting (sentiment on 744k texts). Use **`sample_weight`** only when estimating how common a timeline phenomenon is among the 29.6M English timeline posts. Do not apply keyword weights to timeline questions or the reverse.

## Columns for later analysis

| Column | Use |
|--------|-----|
| `source`, `tweet_id` | Primary key (cross-source ID overlaps stay distinct) |
| `author_id`, `username` | User coverage |
| `created_at` | Time series |
| `original_text` | Immutable raw text |
| `text_translated_en` | English analysis text (copy of original when `not_required_english`) |
| `clean_text` | Sentiment / generic NLP (URLs/mentions/stopwords/Porter; **keeps** follow) |
| `topic_text` | BERTopic (IFB/follow phrases stripped) |
| `lang` | Timeline: Twitter `en`. Keyword: census label, not a detector |
| `sample_weight` | Timeline Horvitz–Thompson weight (`1/p`); keyword = 1 |
| `translation_status` | Filter: later stages should use `not_required_english` |

Quality flags live in `translation_quality` (same DB). No giant CSV of 744k rows. Examples only: `outputs/translation_examples.csv` (UTF-8).

## Quality sample ({len(stats['example_previews'])} pairs)

`original_text` and `text_translated_en` are the same string. That is the verification that translation was skipped on purpose.

| # | source | tweet_id | original (preview) | text_translated_en (preview) | identical |
|---|--------|----------|--------------------|------------------------------|-----------|
{example_rows}

Full strings: `outputs/translation_examples.csv`.

## Files

- `src/translation_audit.py`
- `notebooks/translator.ipynb`
- `data/nlp_analysis_corpus.db` — added `translation_status`, `text_translated_en`, table `translation_quality`
- `outputs/translation_examples.csv`
- `TRANSLATION_DECISION.md`
"""
    REPORT.write_text(text, encoding="utf-8")


def preview(text: str, n: int = 90) -> str:
    s = (text or "").replace("\n", " ").replace("|", "/")
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    started = time.perf_counter()
    rng = random.Random(RNG_SEED)
    log(f"Opening {NLP_DB} (not IFB.db)...")
    conn = connect_nlp(NLP_DB)
    try:
        ensure_columns(conn)
        n_total = conn.execute("SELECT COUNT(*) FROM nlp_posts").fetchone()[0]
        n_kw = conn.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE source='keyword_tweets'"
        ).fetchone()[0]
        n_tl = conn.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE source='timeline'"
        ).fetchone()[0]
        tl_en = conn.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE source='timeline' AND lower(lang)='en'"
        ).fetchone()[0]
        tl_not_en = n_tl - tl_en
        log(f"  rows={n_total:,} keyword={n_kw:,} timeline={n_tl:,} timeline_en={tl_en:,}")
        if (n_kw, n_tl, n_total) != (KEYWORD_RETAINED, TIMELINE_SAMPLED, 744_221):
            log(
                f"WARNING: counts differ from expected "
                f"({KEYWORD_RETAINED}, {TIMELINE_SAMPLED}, 744221)"
            )

        fp_before = conn.execute(
            "SELECT COUNT(*), SUM(length(original_text)), SUM(unicode(substr(original_text,1,1))) "
            "FROM nlp_posts"
        ).fetchone()

        status_n: Counter[str] = Counter()
        source_status = {"keyword_tweets": Counter(), "timeline": Counter()}
        kw_class: Counter[str] = Counter()
        quality = Counter()
        buckets = {
            "kw_hash": [],
            "tl_hash": [],
            "kw_mention": [],
            "tl_mention": [],
            "kw_url": [],
            "tl_url": [],
            "kw_plain": [],
            "tl_plain": [],
            "kw_empty_clean": [],
            "tl_empty_clean": [],
        }

        post_batch: list[tuple] = []
        qual_batch: list[tuple] = []
        n = 0
        cur = conn.execute(
            """
            SELECT source, tweet_id, original_text, clean_text, topic_text, lang
            FROM nlp_posts
            """
        )
        conn.execute("BEGIN")
        while True:
            chunk = cur.fetchmany(CHUNK)
            if not chunk:
                break
            for source, tweet_id, original, clean, topic, lang in chunk:
                n += 1
                info = audit_row(source, lang or "", original or "", clean, topic)
                status_n[info["translation_status"]] += 1
                source_status[source][info["translation_status"]] += 1
                if source == "keyword_tweets":
                    kw_class[info["keyword_rule_class"]] += 1
                for k in (
                    "encoding_ok",
                    "has_replacement",
                    "has_unreadable",
                    "has_hashtag",
                    "has_mention",
                    "has_url",
                    "empty_original",
                    "empty_clean",
                    "empty_topic",
                ):
                    quality[k] += info[k]
                post_batch.append(
                    (
                        info["translation_status"],
                        info["text_translated_en"],
                        source,
                        tweet_id,
                    )
                )
                qual_batch.append(
                    (
                        source,
                        tweet_id,
                        info["translation_status"],
                        info["keyword_rule_class"],
                        info["encoding_ok"],
                        info["has_replacement"],
                        info["has_unreadable"],
                        info["has_hashtag"],
                        info["has_mention"],
                        info["has_url"],
                        info["empty_original"],
                        info["empty_clean"],
                        info["empty_topic"],
                    )
                )
                if info["translation_status"] == "not_required_english":
                    ex = {
                        "source": source,
                        "tweet_id": str(tweet_id),
                        "original_text": original or "",
                        "text_translated_en": info["text_translated_en"] or "",
                        "translation_status": info["translation_status"],
                        "lang": lang or "",
                        "has_hashtag": info["has_hashtag"],
                        "has_mention": info["has_mention"],
                        "has_url": info["has_url"],
                        "empty_clean": info["empty_clean"],
                        "notes": "translation skipped; text_translated_en = original_text",
                    }
                    prefix = "kw" if source == "keyword_tweets" else "tl"
                    if info["has_hashtag"]:
                        reservoir_offer(buckets, rng, f"{prefix}_hash", ex)
                    elif info["has_mention"]:
                        reservoir_offer(buckets, rng, f"{prefix}_mention", ex)
                    elif info["has_url"]:
                        reservoir_offer(buckets, rng, f"{prefix}_url", ex)
                    else:
                        reservoir_offer(buckets, rng, f"{prefix}_plain", ex)
                    if info["empty_clean"]:
                        reservoir_offer(buckets, rng, f"{prefix}_empty_clean", ex)
                if len(post_batch) >= UPDATE_SIZE:
                    conn.executemany(
                        """
                        UPDATE nlp_posts
                        SET translation_status = ?, text_translated_en = ?
                        WHERE source = ? AND tweet_id = ?
                        """,
                        post_batch,
                    )
                    conn.executemany(
                        """
                        INSERT INTO translation_quality (
                            source, tweet_id, translation_status, keyword_rule_class,
                            encoding_ok, has_replacement, has_unreadable,
                            has_hashtag, has_mention, has_url,
                            empty_original, empty_clean, empty_topic
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        qual_batch,
                    )
                    post_batch.clear()
                    qual_batch.clear()
                if n % PROGRESS == 0:
                    log(f"  audited {n:,}")
        if post_batch:
            conn.executemany(
                """
                UPDATE nlp_posts
                SET translation_status = ?, text_translated_en = ?
                WHERE source = ? AND tweet_id = ?
                """,
                post_batch,
            )
            conn.executemany(
                """
                INSERT INTO translation_quality (
                    source, tweet_id, translation_status, keyword_rule_class,
                    encoding_ok, has_replacement, has_unreadable,
                    has_hashtag, has_mention, has_url,
                    empty_original, empty_clean, empty_topic
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                qual_batch,
            )
        conn.commit()
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_nlp_translation_status "
            "ON nlp_posts(translation_status)"
        )
        conn.commit()

        fp_after = conn.execute(
            "SELECT COUNT(*), SUM(length(original_text)), SUM(unicode(substr(original_text,1,1))) "
            "FROM nlp_posts"
        ).fetchone()
        fingerprint_ok = list(fp_before) == list(fp_after)

        w_kw, w_tl = conn.execute(
            """
            SELECT
              SUM(CASE WHEN source='keyword_tweets' THEN sample_weight ELSE 0 END),
              SUM(CASE WHEN source='timeline' THEN sample_weight ELSE 0 END)
            FROM nlp_posts
            """
        ).fetchone()
        w_kw = float(w_kw or 0)
        w_tl = float(w_tl or 0)

        identical = conn.execute(
            """
            SELECT COUNT(*) FROM nlp_posts
            WHERE translation_status='not_required_english'
              AND text_translated_en = original_text
            """
        ).fetchone()[0]
        copied = conn.execute(
            "SELECT COUNT(*) FROM nlp_posts WHERE translation_status='not_required_english'"
        ).fetchone()[0]
        if identical != copied:
            log(f"WARNING: {copied - identical} English rows where copy != original")

        examples = pick_examples(buckets, rng, N_EXAMPLES)
        write_csv(
            EXAMPLES_CSV,
            [
                "source",
                "tweet_id",
                "lang",
                "translation_status",
                "original_text",
                "text_translated_en",
                "has_hashtag",
                "has_mention",
                "has_url",
                "empty_clean",
                "notes",
            ],
            examples,
        )
        previews = [
            {
                "source": r["source"],
                "tweet_id": r["tweet_id"],
                "original_preview": preview(r["original_text"]),
                "translated_preview": preview(r["text_translated_en"]),
                "same_as_original": str(
                    r["original_text"] == r["text_translated_en"]
                ).lower(),
            }
            for r in examples
        ]

        n_ok = status_n.get("not_required_english", 0)
        n_need = status_n.get("requires_translation", 0)
        n_unc = status_n.get("uncertain", 0)
        denom = n_total or 1
        stats = {
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status_n,
            "source_status": source_status,
            "kw_class": kw_class,
            "quality": quality,
            "n_keyword": n_kw,
            "n_timeline": n_tl,
            "n_total": n_total,
            "tl_en": tl_en,
            "tl_not_en": tl_not_en,
            "w_keyword": w_kw,
            "w_timeline": w_tl,
            "w_total": w_kw + w_tl,
            "pct_ok": 100.0 * n_ok / denom,
            "pct_need": 100.0 * n_need / denom,
            "pct_unc": 100.0 * n_unc / denom,
            "fingerprint_ok": fingerprint_ok,
            "example_previews": previews,
        }
        write_report(stats)

        elapsed = time.perf_counter() - started
        log("")
        log("========== TRANSLATION AUDIT ==========")
        log(f"n_total={n_total}")
        log(f"timeline_lang_en={tl_en} timeline_lang_not_en={tl_not_en}")
        log(f"status={dict(status_n)}")
        log(f"keyword_rule_class={dict(kw_class)}")
        log(f"quality={dict(quality)}")
        log(f"identical_copies={identical}/{copied} fingerprint_ok={fingerprint_ok}")
        log(f"weighted_keyword={w_kw:.1f} weighted_timeline={w_tl:.1f}")
        log(f"examples={len(examples)} csv={EXAMPLES_CSV}")
        log(f"elapsed_seconds={elapsed:.1f}")
        log("TRANSLATION_AUDIT_COMPLETE")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
