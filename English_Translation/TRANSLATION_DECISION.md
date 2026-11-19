# Translation decision

Built: 2026-09-11T14:29:12Z
Random seed: **2026**
Input: `data/nlp_analysis_corpus.db` only. **`IFB.db` was not opened or modified.**
No translation API was called. Sentiment, emotion, BERTopic, NER, entity network, and bot detection were **not** run.

## What “English-ready” means (and what it does not)

**English-ready is an operational inclusion rule, not a claim that every retained post is native English.**

- Timeline rows enter the NLP file only when Twitter/X `LANG = en`.
- Keyword tweets have **no** `LANG` column. They are kept only when a **rule-based Latin-script / ASCII-ratio classifier** (not langdetect, not fastText) marks them `likely_english` after IFB/follow tokens are stripped.

That classifier reliably drops Arabic, Japanese, Korean, Thai, and Cyrillic. It **cannot** separate English from other Latin-script languages. Portuguese, Spanish, Indonesian, French, and Italian posts therefore survive into the retained file at a low rate. Pair #2 in `outputs/translation_examples.csv` is a **real retained Portuguese post** (“Indo dormir…”) kept exactly as the pipeline kept it — it is not a translation error and it is not hidden.

No machine translation ran. For every `translation_status = not_required_english` row, `text_translated_en` is a byte-for-byte copy of `original_text`.

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
| `likely_english` | 244,221 |
| `ifb_dominated` | 0 |
| `script_non_english` | 0 |
| `uncertain` | 0 |
| `empty` | 0 |

- Script-confirmed non-English remaining in this file (should be ~0) → `requires_translation`. **Not translated.** `text_translated_en` is NULL.
- Residual `uncertain` / `ifb_dominated` / empty / replacement characters → `uncertain`. **Not translated.** `text_translated_en` is NULL.
- `likely_english` with readable UTF-8 → `not_required_english`.

Do **not** treat langdetect codes `no` / `af` / `ca` / `so` / `cy` / `nl` on IFB spam as translation targets (documented in `NLP_SAMPLING_PLAN.md`).

## How many posts were excluded before this corpus was created

Exclusion happened **before** this audit, when `data/nlp_analysis_corpus.db` was built. Those rows are **not** in this file and were **not** sent to a translator.

### Keyword tweets (population 1,129,607)

| Item | N | Role vs translation |
|------|--:|---------------------|
| Retained in NLP corpus | **244,221** | English-ready census |
| Not retained | **885,386** | out of this corpus |
| IFB-dominated templates | 513,390 | not a language to translate |
| Script-confirmed non-English | 20,302 | would need translation; **excluded instead** |
| Uncertain mixed/low-Latin | 20,140 | no reliable target language |
| Likely English before dup/boiler/short filters | 575,775 | many are copy-paste templates |
| Boilerplate hash freq ≥ 5 | 806,651 | duplicate spam, not translated |
| Dropped short `clean_text` | 220 | too little signal |

Exclusion reasons **overlap** (a post can be English-like and still boilerplate). Do not add the rows.

### Timeline posts (primary users: 37,839,416)

| Item | N | Role vs translation |
|------|--:|---------------------|
| `LANG = en` population | **29,573,764** | sampling frame |
| Not `LANG = en` | **8,265,652** | other languages + `und/qme/qam/zxx`; **excluded, not translated** |
| Stratified sample in NLP corpus | **500,000** | English-ready |

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
| `original_text` | present |
| `clean_text` | present |
| `topic_text` | present |
| `created_at` | present |
| `lang` | present |
| `source` | present |
| `sample_weight` | present |

Timeline `lang = en`: **500,000** / 500,000 (non-en = 0).

### `translation_status`

| Status | n | Share | `text_translated_en` |
|--------|--:|------:|----------------------|
| `not_required_english` | 742,942 | 99.8281% | copy of `original_text` |
| `requires_translation` | 63 | 0.0085% | NULL (not translated) |
| `uncertain` | 1,216 | 0.1634% | NULL (not translated) |

By source:

| Source | not_required_english | requires_translation | uncertain |
|--------|---------------------:|---------------------:|----------:|
| keyword_tweets | 244,217 | 0 | 4 |
| timeline | 498,725 | 63 | 1,212 |

Posts used for later English NLP = `translation_status = not_required_english` (**742,942**). Residual `requires_translation` / `uncertain` rows stay in SQLite for audit but must not be treated as translated English.

Residual **inside** this file (not back-filled from excluded populations):

- **63** timeline posts with Twitter `LANG=en` but **script-confirmed non-Latin** text (Arabic, Urdu, Korean hashtags). Status `requires_translation`. `text_translated_en` is NULL — they were not silently treated as English.
- **1,216** `uncertain` (1,212 timeline, 4 keyword). The **four keyword** rows are the entire 244,221 − 244,217 gap. They were not scored. Exact IDs (also in `outputs/keyword_unscored_four_rows.csv`):
  - `1110608490748207104` (`abigailpollak`, 2019-03-26): `uncertain` because `original_text` contains U+FFFD (`Henri-Fr�d�ric Amiel`). `text_translated_en` is NULL. Not a duplicate key and not empty text.
  - `1132322951167205376` (`seometadaten`, 2019-05-25): `uncertain` because `original_text` contains U+FFFD (`J�rgens`). `text_translated_en` is NULL.
  - `1325385083428237312` (`OfferteToste`, 2020-11-08): `uncertain` because `original_text` contains a legacy control/encoding byte (`Pique\x92`). `text_translated_en` is NULL. Italian promo; not a missing-text drop.
  - `1481686488005763072` (`AceKace_`, 2022-01-13): `uncertain` because `original_text` contains U+FFFD plus invisible U+2063 separators. `text_translated_en` is NULL.
  Timeline `uncertain` / `requires_translation` rows are mixed-script or unreadable characters on otherwise `LANG=en` rows.
- The keyword rule is a **Latin-script ratio**, not an English dictionary. A small number of Romance-language posts (Portuguese, French) can still be `not_required_english`. They are copies of the original, not translations. Pair #2 below is Portuguese on purpose.

## Quality checks (original text)

| Check | Posts |
|-------|------:|
| UTF-8 round-trip OK and no U+FFFD | 744,216 |
| Replacement character U+FFFD | 5 |
| Unreadable control/surrogate chars | 16 |
| Contains hashtag `#` | 202,786 |
| Contains username `@` | 484,741 |
| Contains URL | 259,870 |
| Empty `original_text` | 0 |
| Empty `clean_text` | 2,948 |
| Empty `topic_text` | 5,086 |

Hashtags, @usernames, and URLs are **unchanged** in `text_translated_en` because that column is a copy of `original_text` for English-ready rows (not a translator that might drop entities).

`original_text` was never rewritten. Fingerprint before/after: True.

## Raw counts vs weighted timeline estimates

Keyword posts are a **census** (`sampling_probability = 1`, `sample_weight = 1`). Timeline posts are a **probability sample** of the English timeline.

| Source | Raw rows in NLP file | Sum of `sample_weight` | What the weight estimates |
|--------|---------------------:|-----------------------:|---------------------------|
| keyword_tweets | 244,221 | 244,221.0 | same as raw (census) |
| timeline | 500,000 | 29,573,764.0 | English timeline population (~29,573,764) |
| **total** | 744,221 | 29,817,985.0 | mixed; do not treat as one population |

Use **raw rows** for model fitting (sentiment on English-ready texts). Use **`sample_weight`** only when estimating how common a timeline phenomenon is among the 29.6M English timeline posts. Restricting to `not_required_english` leaves **498,725** timeline rows whose weights sum to **~29,498,351** (the 63 + 1,212 residual timeline posts are held out of English NLP). Do not apply keyword weights to timeline questions or the reverse.

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

## Quality sample (12 pairs)

`original_text` and `text_translated_en` are the same string. That is the verification that translation was skipped on purpose.

| # | source | tweet_id | original (preview) | text_translated_en (preview) | identical |
|---|--------|----------|--------------------|------------------------------|-----------|
| 1 | keyword_tweets | `1467523980533932038` | #follow4follow #followback #followbot #getrekt #mlg December 05, 2021 at 05:59PM | #follow4follow #followback #followbot #getrekt #mlg December 05, 2021 at 05:59PM | true |
| 2 | keyword_tweets | `1333981581610979329` | Indo dormir... E olha quem está bravo comigo pq ainda não fui dormir... #Bimo #Cat #Gato … | Indo dormir... E olha quem está bravo comigo pq ainda não fui dormir... #Bimo #Cat #Gato … | true |
| 3 | keyword_tweets | `1412175975941611526` | @alidzr @withFND @fa_khoshkhoo good luck for the auction! gonna follow you now for support | @alidzr @withFND @fa_khoshkhoo good luck for the auction! gonna follow you now for support | true |
| 4 | keyword_tweets | `1310620975076192257` | @Belhomme_sexyy I m a professional graphic designer for Dm or follow me back so we can ha… | @Belhomme_sexyy I m a professional graphic designer for Dm or follow me back so we can ha… | true |
| 5 | keyword_tweets | `1288975118136418305` | Okay, weekly PSA: If you are following me and I have not followed you yet, PLEASE let me… | Okay, weekly PSA: If you are following me and I have not followed you yet, PLEASE let me… | true |
| 6 | keyword_tweets | `1478790785776685057` | ☕️☕️☕️Wednesday Afternoon Gains🛕🛕🛕FOLLOW ALL RT's AND STEPH for a swift FOLLOW back | ☕️☕️☕️Wednesday Afternoon Gains🛕🛕🛕FOLLOW ALL RT's AND STEPH for a swift FOLLOW back | true |
| 7 | timeline | `1707358757297041692` | RT @WKRN: WEATHER ALERT: Flood Advisory for the area in green. Stay tuned to #wkrn. Inter… | RT @WKRN: WEATHER ALERT: Flood Advisory for the area in green. Stay tuned to #wkrn. Inter… | true |
| 8 | timeline | `1525190396548096000` | Have you noticed that your power bill has gone up? Well, a handful of corporate driven po… | Have you noticed that your power bill has gone up? Well, a handful of corporate driven po… | true |
| 9 | timeline | `1393996450821021700` | @Dynule Of course as always. [&gt;A motion towards the main stairs. Down this time. Fu… | @Dynule Of course as always. [&gt;A motion towards the main stairs. Down this time. Fu… | true |
| 10 | timeline | `1230339942129250304` | RT @Domaniacc: How do I get these balloons off my twitter 😏😏😏 https://t.co/BhGLxmPbep | RT @Domaniacc: How do I get these balloons off my twitter 😏😏😏 https://t.co/BhGLxmPbep | true |
| 11 | timeline | `1621248103662641152` | Disease outbreak news from the WHO: https://t.co/Op3jbwWhT1 | Disease outbreak news from the WHO: https://t.co/Op3jbwWhT1 | true |
| 12 | timeline | `1532505288774979591` | I think I’ve been too chill on him, I need to ruin his life. Then he’ll act right 😎 | I think I’ve been too chill on him, I need to ruin his life. Then he’ll act right 😎 | true |

Full strings: `outputs/translation_examples.csv`.

## Files

- `src/translation_audit.py`
- `notebooks/translator.ipynb`
- `data/nlp_analysis_corpus.db` — added `translation_status`, `text_translated_en`, table `translation_quality`
- `outputs/translation_examples.csv`
- `TRANSLATION_DECISION.md`
