# Dataset decision

Read-only coverage and date-normalization results from `src/data_coverage_and_normalization.py`. `IFB.db` was not modified. Full tables were not loaded into memory. Numeric tables: `outputs/data_coverage_report.csv`, `outputs/date_parsing_report.csv`, `outputs/text_feature_profile.csv`.

## Recommendation

**Primary dataset (use this for every later stage):** users whose `AUTHOR_ID` is present in **all three tables**, after dropping duplicate `AUTHOR_ID` groups.

| Item | Count |
|------|------:|
| Users | **38,576** |
| Keyword IFB tweets (`tweets`) | **1,129,607** |
| Timeline tweets | **37,839,416** |
| Author-profile rows | **38,576** (one row per `AUTHOR_ID`) |

Join key: `CAST(AUTHOR_ID AS TEXT)` on every table. Do not use `USERNAME` to join `tweets` or `timeline` (those tables have no username).

This is the only population that simultaneously has:

- IFB seed tweets (`KEYWORD`)
- broader posting history (`timeline`)
- profile metadata needed for bot / troll features
- parseable timestamps on both tweet tables

**Do not switch populations between stages.** Sentiment, topics, NER, entity networks, and bot detection should all be computed on these 38,576 users (or a documented random subsample of their posts). Using the full 2.1 million keyword authors for text analysis and the 575 thousand profiled authors for bots would mix two different communities.

---

## How the tables actually overlap

IDs were compared after `CAST(AUTHOR_ID AS TEXT)`.

| Comparison | Users | Posts |
|------------|------:|------:|
| `tweets` authors in `authors` | 574,971 | 3,231,249 keyword tweets |
| `tweets` authors **not** in `authors` | 1,537,901 | 3,905,636 keyword tweets |
| `timeline` authors in `authors` | 39,631 | 38,026,664 timeline tweets |
| `timeline` authors **not** in `authors` | 817 | 6,941,521 timeline tweets |
| `tweets` ∩ `timeline` authors | 39,759 | 1,199,479 keyword tweets / 40,594,872 timeline tweets |
| `tweets` authors with no timeline | 2,073,113 | 5,937,406 keyword tweets |
| `timeline` authors with no keyword tweets | 689 | 4,373,313 timeline tweets |
| Triple `authors ∩ tweets ∩ timeline` | 39,631 | 1,198,277 keyword / 38,026,664 timeline |
| Triple, unambiguous `AUTHOR_ID` only | **38,576** | **1,129,607** keyword / **37,839,416** timeline |

Structural facts:

- Every `authors` ID appears in `tweets` (`authors` ⊂ `tweets` authors).
- 535,340 profiled authors have **no** timeline rows.
- About **73%** of keyword-tweet authors have **no** profile row.
- About **98%** of timeline authors do have a profile row.

So the 45 million timeline rows are almost entirely a dense history for ~40 thousand people, not a history for the 2.1 million IFB tweeters.

---

## Canonical user identifier

| Key | Unique in `authors`? | Present in `tweets` / `timeline`? |
|-----|----------------------|-----------------------------------|
| `USERNAME` | Yes (576,190 / 576,190; 0 collisions) | No |
| `AUTHOR_ID` | No (574,971 unique IDs in 576,190 rows) | Yes |

Duplicate `AUTHOR_ID` investigation:

- 1,203 IDs appear more than once (2,422 rows; max group size 3).
- In **every** group the usernames are different.
- In **every** group `CREATED_AT` is identical.
- These are not repeated snapshots of one profile. They look like ID collisions or renamed/cloned handles sharing a scraped ID.
- All 1,203 ambiguous IDs appear in `tweets` (77,465 keyword tweets). 1,055 also appear in `timeline` (187,248 timeline tweets).

**Rule:** join tables on `CAST(AUTHOR_ID AS TEXT)`. For user-level analysis (bots, per-user sentiment, account-age features) **drop the 1,203 ambiguous IDs**. `USERNAME` may be used as a display label only.

---

## Date parsing (`tweets.CREATED_AT`)

Parser supports Unix milliseconds/seconds, `YY-MM-DD Weekday HH:MM:SS` (locale-independent), and ISO datetimes. Placeholders (`1970-01-01`), pre-Twitter dates, and dates after 2023-12-31 are excluded.

| Table | Records | Success | Excluded | Usable range |
|-------|--------:|--------:|---------:|--------------|
| `tweets` | 7,136,885 | **100%** (7,088,060 weekday + 48,825 Unix ms) | **0** | 2019-01-01 00:00:03 → 2023-01-05 23:59:56 |
| `timeline` | 44,968,185 | **100%** ISO | **0** | 2007-05-11 22:13:23 → 2023-12-03 04:50:17 |
| `authors` | 576,190 | 99.9997% | **2** epoch placeholders | (account created dates) |

Keyword IFB discourse is 2019–early 2023. Timeline history for the same users can start much earlier.

---

## Text and language profile (samples, not full export)

Keyword tweets (43,955 posts, stratified by trimmed `KEYWORD`):

- 33% contain a hashtag (mean 2.48; median 0 — heavy-tailed IFB tag spam)
- 64% contain a mention
- 26% contain a URL
- Almost none are classic `RT @` retweets (0.04%)
- ~8% extra rows in the sample are exact duplicate text (copy-paste IFB templates)
- Mean length ~132 characters / 18 tokens
- 26 raw `KEYWORD` values collapse to **24** after `TRIM`

Timeline (40,000 posts, stratified by language bucket):

- 14% hashtags, 74% mentions, 34% URLs
- **22%** start with `RT @` (usable weak retweet feature; there is still no retweet-graph ID)
- Duplicate text in the sample is rare (~0.4%)
- Mean length ~87 characters

Language census of **all** 44,968,185 timeline rows (`und`, `qme`, `qam`, `zxx` are **not** English):

| Bucket | Rows | Share |
|--------|-----:|------:|
| English (`en` only) | 34,868,834 | 77.5% |
| Other real/misc language codes | 5,516,620 | 12.3% |
| Non-linguistic (`und`, `qme`, `qam`, `zxx`) | 4,582,731 | 10.2% |

Later translation should use `LANG = 'en'` as English, skip non-linguistic codes, and treat other codes as translation candidates. Twitter private-use codes `qst`, `qht`, and `art` currently sit in “other language” (~290k rows) and should also be excluded from translation/NLP.

---

## What the course requirements can and cannot do

On the **38,576-user primary set**:

| Stage | Feasible? | Notes |
|-------|-----------|--------|
| Sentiment / emotion / hate | Yes | Prefer English timeline text; sample before BERT. Keyword tweets need language detection first (`tweets` has no `LANG`). |
| Topic modeling (BERTopic) | Yes | Must subsample; 37.8M posts cannot be embedded in full. |
| NER + entity sentiment over time | Yes | Timeline dates are clean; keyword dates are now parsed. |
| Entity co-occurrence network | Yes | This is the network the guidelines actually specify. |
| Bot / troll / malicious users | Yes | Followers/following, statuses, account age, bio, verified, plus timeline posting rate, hours, `RT @` rate, mention/hashtag rates, copy-paste. |
| Psychological profile of the group | Yes | IFB / follow-for-follow community with metadata. |
| User follow-graph network | **No** | Only follower *counts*, no edges. |
| Reply/quote conversation spread | **No** | No `in_reply_to` / quoted IDs. |
| True retweet cascade graph | **No** | Only a text `RT @` indicator (~22% of timeline sample). |

Heavy models should run on a **sample** of English posts from these users (for example 100k–500k), not on a CSV dump of the database.

---

## Populations that were rejected as the primary set

1. **All 7.1M keyword tweets / 2.1M authors** — largest IFB discourse, but 1.54M authors have no metadata, so bot detection and account-level analysis are not defensible.
2. **All 574,971 profiled authors / 3.23M keyword tweets** — good metadata and IFB seed text, but 535,340 of them have no timeline, so posting-behavior features are thin.
3. **All 40,448 timeline authors / 45M posts** — includes 817 users with no profile (6.9M posts) and 1,055 ambiguous IDs.

Those sets may be used only as *sensitivity checks*, not as the main pipeline.

---

## Working rules for the next phase

1. Keep `IFB.db` read-only. Derive ID lists and samples in `data/` or `outputs/`, never a full CSV dump.
2. Canonical user key: unambiguous `AUTHOR_ID` text.
3. Canonical IFB keywords: `TRIM(KEYWORD)` (24 values).
4. Parse `tweets.CREATED_AT` with the project parser; use timeline timestamps as-is.
5. English = `LANG = 'en'` only.
6. Do not install sentiment / BERTopic / NER packages until the sampled primary set is frozen.
