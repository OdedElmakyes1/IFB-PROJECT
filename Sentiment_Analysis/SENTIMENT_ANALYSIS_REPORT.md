# Sentiment analysis

Built: 2026-09-11T15:26:35Z
Package: **pysentimiento** (`create_analyzer(task="sentiment", lang="en")`)
Model: **finiteautomata/bertweet-base-sentiment-analysis** (BERTweet-base, 3-class POS/NEU/NEG)
Input column: **`clean_text`** (course instruction). Empty `clean_text` (2,948 posts) scored as `"."`.
Filter: `translation_status = not_required_english` only.
`IFB.db` and `data/analysis_corpus.db` were not opened. Original text was not rewritten.
Weights were **not** used during inference. They are used only for timeline population estimates.

## Processed volume

| Item | N |
|------|--:|
| English-ready posts scored | **742,942** |
| Users with ≥1 scored post | **35,250** |
| Keyword posts (census) | 244,217 |
| Timeline posts (stratified sample) | 498,725 |
| Empty `clean_text` placeholder | 2,948 |
| Duplicate `(source, tweet_id)` | 0 |
| Validation | **PASS** |

Every scored row has `sentiment_label` ∈ {positive, neutral, negative} and three probabilities in [0, 1] that sum to ~1.

## Counts and percentages

There is **no** combined “average sentiment” number. Neutral is kept as its own class.

### Combined file (unweighted mix of two sampling frames)

| Class | Count | Share |
|-------|------:|------:|
| positive | 134,936 | 18.16% |
| neutral | 526,377 | 70.85% |
| negative | 81,629 | 10.99% |
| **total** | **742,942** | 100% |

Do not read the combined pie as “the IFB population’s mood.” It mixes a keyword census with a 1.7% English-timeline sample.

### Keyword tweets (census of eligible English-ready keyword posts)

| Class | Count | Share |
|-------|------:|------:|
| positive | 48,894 | 20.02% |
| neutral | 184,804 | 75.67% |
| negative | 10,519 | 4.31% |

### Timeline — raw sample vs weighted population estimate

English-ready timeline rows: **498,725**. Weighted total ≈ sum of `sample_weight` (≈ 29.50M English timeline posts).

| Class | Raw count (share) | Weighted count (share) |
|-------|-------------------|------------------------|
| positive | 86,042 (17.25%) | 5,089,139.0 (17.25%) |
| neutral | 341,573 (68.49%) | 20,203,183.3 (68.49%) |
| negative | 71,110 (14.26%) | 4,206,029.1 (14.26%) |

Raw shares describe the **500k-scale sample we scored**. Weighted shares estimate the **English timeline population** of the 38,576 primary users. Keyword weights were not applied to timeline rows.

## Monthly trends (three separate series)

Figures: `outputs/sentiment_over_time_monthly.png` — **three panels**, one class each (green / yellow / red). No single mixed sentiment curve.

Peak combined-file monthly **share** (descriptive only):

| Class | Peak month |
|-------|------------|
| positive | 2019-03 (27.8%, n=2,823; months with n<500 ignored) |
| neutral | 2020-03 (79.0%, n=5,824; months with n<500 ignored) |
| negative | 2023-10 (18.1%, n=32,847; months with n<500 ignored) |

Keyword IFB talk is structurally more promotional (follow-back, thanks, growth pitches), so its positive/neutral mix is not comparable to ordinary timeline talk without stating the sampling frame.

## Per-user sentiment summary

`outputs/user_sentiment_summary.csv` — one row per author: counts and percentages. **35,250** users. Mean scored posts per user: 21.1.

Users whose **plurality** class (raw counts, not weights) is:

| Plurality class | Users | Share of users |
|-----------------|------:|---------------:|
| positive | 5,461 | 15.49% |
| neutral | 28,494 | 80.83% |
| negative | 1,295 | 3.67% |

A user with 2 posts is not comparable to a high-activity author. Percentages are within-user; they are not timeline population estimates.

## Replacement-character records

Five posts contain U+FFFD. **Original text was not repaired or rewritten.** They stay in `nlp_posts.original_text` as stored. Sentiment ran only on `not_required_english`; encoding-damaged rows from the translation audit were mostly `uncertain` and therefore **not scored**.

| source | tweet_id | translation_status | scored? |
|--------|----------|--------------------|---------|
| `keyword_tweets` | `1110608490748207104` | uncertain | no (held out as uncertain/non-English) |
| `keyword_tweets` | `1132322951167205376` | uncertain | no (held out as uncertain/non-English) |
| `keyword_tweets` | `1481686488005763072` | uncertain | no (held out as uncertain/non-English) |
| `timeline` | `1384572695057215493` | uncertain | no (held out as uncertain/non-English) |
| `timeline` | `1482044995179790341` | uncertain | no (held out as uncertain/non-English) |

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

Inference this run: 0 newly scored in 0.0s.
