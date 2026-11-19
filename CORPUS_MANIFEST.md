# Corpus manifest

Built: 2026-09-11T11:09:18Z
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
| Users | 38,576 |
| Keyword tweets (`source = keyword_tweets`) | 1,129,607 |
| Timeline tweets (`source = timeline`) | 37,839,416 |
| Total posts in corpus | 38,969,023 |
| Users with at least one keyword tweet | 38,576 |
| Ambiguous AUTHOR_ID groups excluded | 1,203 |
| Timeline rows skipped (not in unambiguous authors) | 7,128,769 |
| Timeline rows skipped (unparseable date) | 0 |
| Keyword rows skipped (author not in primary set) | 6,007,278 |
| Keyword rows skipped (unparseable date) | 0 |

Expected from `DATASET_DECISION.md`: 38,576 users; 1,129,607 keyword tweets; 37,839,416 timeline tweets. Date exclusions can reduce post counts slightly.

## Date range

Dates are stored as ISO-8601 `YYYY-MM-DDTHH:MM:SS` (no timezone; values treated as naive UTC as stored).

| Source | Minimum | Maximum |
|--------|---------|---------|
| keyword_tweets | 2019-01-01T00:13:46 | 2023-01-05T23:59:10 |
| timeline | 2007-05-11T22:13:23 | 2023-12-03T04:50:17 |
| combined | 2007-05-11T22:13:23 | 2023-12-03T04:50:17 |

Parser: Unix milliseconds/seconds, `YY-MM-DD Weekday HH:MM:SS`, and ISO datetimes. Placeholders (`1970-01-01`), pre-Twitter dates, and dates in 2024+ are excluded.

## Duplicate handling

- Within a source, uniqueness is enforced by `PRIMARY KEY (source, tweet_id)`. Inserts use `INSERT OR IGNORE`.
- Cross-source `tweet_id` overlap (same ID in both `keyword_tweets` and `timeline`): **42,371**
- Example overlapping IDs: 1080450618148511744, 1080453321209663490, 1080486404197629955, 1080531417715621888, 1080564282864087041, 1080564440741756929, 1080645557914284032, 1080845066472747008, 1080856355718815744, 1081007946593533952
- Overlapping IDs are **kept in both sources** (they are different rows: keyword seed tweet vs timeline copy). Downstream joins on `tweet_id` alone must also filter `source`.

## Language handling

- `timeline.lang`: original `LANG` value, trimmed. Empty/NULL stored as `unknown` (should be rare).
- `keyword_tweets.lang`: always `unknown`. Keyword tweets have **no** `LANG` column. They are **not** assumed to be English.
- Non-linguistic Twitter codes `und`, `qme`, `qam`, `zxx` are preserved as-is on timeline rows and are **not** English.
- A stratified keyword sample (`keyword_lang_sample` table, 2,734 rows) is stored for later language detection or manual inspection. No detector was run in this step.

### Timeline language totals (corpus)

| LANG | Rows | Percent of timeline |
|------|------:|--------------------:|
| `en` | 29,573,764 | 78.1560% |
| `qme` | 1,556,787 | 4.1142% |
| `und` | 1,317,727 | 3.4824% |
| `es` | 838,973 | 2.2172% |
| `zxx` | 536,324 | 1.4174% |
| `in` | 532,144 | 1.4063% |
| `qam` | 388,031 | 1.0255% |
| `tl` | 372,731 | 0.9850% |
| `pt` | 302,938 | 0.8006% |
| `ja` | 241,219 | 0.6375% |
| `fr` | 236,103 | 0.6240% |
| `ko` | 230,417 | 0.6089% |
| `hi` | 160,726 | 0.4248% |
| `ar` | 151,599 | 0.4006% |
| `art` | 119,696 | 0.3163% |
| `de` | 117,677 | 0.3110% |
| `ht` | 106,834 | 0.2823% |
| `it` | 93,505 | 0.2471% |
| `et` | 89,003 | 0.2352% |
| `tr` | 88,517 | 0.2339% |

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

RNG seed for samples: 2026.
