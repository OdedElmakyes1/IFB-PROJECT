# Emotion analysis

Built: 2026-09-11T16:14:18Z
Package: **pysentimiento** (`create_analyzer(task="emotion", lang="en")`)
Model: **finiteautomata/bertweet-base-emotion-analysis**
Input: **`clean_text`**. Empty `clean_text` (2,948 posts) scored as `"."`.
Universe: `translation_status = not_required_english` ⋈ `post_sentiment` (**742,942** posts). Sentiment was **not** rerun.
`IFB.db` was not opened. Original text was not rewritten.
Sample weights were **not** used for scoring. They are used only for timeline population estimates.

## Events (not this phase)

**No events are claimed in this emotion scoring run.** Peak dates on the emotion series are descriptive only. Event Detection later wrote four tweet-supported events and dashed labeled overlays in `outputs/event_plots/` (weekly through yearly; keyword and timeline panels). The PNGs in `outputs/emotion_plots/` are the pre-event snapshots from this run (event lines = 0 at scoring time). Use `outputs/event_plots/` for the annotated figures. Do not reread this sentence as “no events exist.”

## Processed volume

| Item | N |
|------|--:|
| Posts scored | **742,942** |
| Users | **35,250** |
| Keyword | 244,217 |
| Timeline | 498,725 |
| Empty `clean_text` placeholder | 2,948 |
| Duplicate `(source, tweet_id)` | 0 |
| Validation | **PASS** |

All seven labels appear as argmax at least once.

Every row has `emotion_label` ∈ {joy, anger, sadness, fear, surprise, disgust, others} and seven probabilities in [0, 1] that sum to ~1. There is **no** single mixed “emotion score.”

## Distribution of every emotion

### Combined file (unweighted mix — not a population)

| Emotion | Count / estimate | Share |
|---------|------------------:|------:|
| joy | 49,667 | 6.69% |
| anger | 8,169 | 1.10% |
| sadness | 3,760 | 0.51% |
| fear | 1,543 | 0.21% |
| surprise | 1,826 | 0.25% |
| disgust | 25,476 | 3.43% |
| others | 652,501 | 87.83% |

### Keyword census

| Emotion | Count / estimate | Share |
|---------|------------------:|------:|
| joy | 12,933 | 5.30% |
| anger | 1,290 | 0.53% |
| sadness | 270 | 0.11% |
| fear | 284 | 0.12% |
| surprise | 67 | 0.03% |
| disgust | 2,441 | 1.00% |
| others | 226,932 | 92.92% |

### Timeline raw sample

| Emotion | Count / estimate | Share |
|---------|------------------:|------:|
| joy | 36,734 | 7.37% |
| anger | 6,879 | 1.38% |
| sadness | 3,490 | 0.70% |
| fear | 1,259 | 0.25% |
| surprise | 1,759 | 0.35% |
| disgust | 23,035 | 4.62% |
| others | 425,569 | 85.33% |

### Timeline weighted (English timeline population)

| Emotion | Count / estimate | Share |
|---------|------------------:|------:|
| joy | 2,172,623.7 | 7.37% |
| anger | 406,884.8 | 1.38% |
| sadness | 206,438.7 | 0.70% |
| fear | 74,470.4 | 0.25% |
| surprise | 104,046.1 | 0.35% |
| disgust | 1,362,518.5 | 4.62% |
| others | 25,171,369.4 | 85.33% |

`others` is large because Porter-stemmed, stopword-stripped IFB talk is often not a clear Ekman emotion. That is a limitation, not a reason to collapse the six other series.

## Time resolutions

Numeric series (raw counts/shares and timeline weighted estimates) are saved for **all** of:

| Resolution | CSV | PNG |
|------------|-----|-----|
| weekly (Monday start) | `outputs/emotion_over_time_weekly.csv` | `outputs/emotion_plots/emotion_over_time_weekly.png` |
| biweekly (14-day bins from 2007-01-01) | `outputs/emotion_over_time_biweekly.csv` | `outputs/emotion_plots/emotion_over_time_biweekly.png` |
| monthly | `outputs/emotion_over_time_monthly.csv` | `outputs/emotion_plots/emotion_over_time_monthly.png` |
| quarterly | `outputs/emotion_over_time_quarterly.csv` | `outputs/emotion_plots/emotion_over_time_quarterly.png` |
| half-yearly | `outputs/emotion_over_time_halfyearly.csv` | `outputs/emotion_plots/emotion_over_time_halfyearly.png` |
| yearly | `outputs/emotion_over_time_yearly.csv` | `outputs/emotion_plots/emotion_over_time_yearly.png` |

Each PNG has two panels (keyword census; timeline raw + dotted weighted) and **seven separate lines**. Dashed event lines are wired but unused until Event Detection.

## Sentiment–emotion relationship

Row shares are P(emotion | sentiment) on the combined unweighted file:

| Sentiment \ Emotion | joy | anger | sadness | fear | surprise | disgust | others |
|---------------------|-----|-------|---------|------|----------|---------|--------|
| positive | 46,106 (34.2%) | 23 (0.0%) | 299 (0.2%) | 16 (0.0%) | 411 (0.3%) | 156 (0.1%) | 87,925 (65.2%) |
| neutral | 3,388 (0.6%) | 1,258 (0.2%) | 1,429 (0.3%) | 956 (0.2%) | 1,110 (0.2%) | 6,626 (1.3%) | 511,610 (97.2%) |
| negative | 173 (0.2%) | 6,888 (8.4%) | 2,032 (2.5%) | 571 (0.7%) | 305 (0.4%) | 18,694 (22.9%) | 52,966 (64.9%) |

Full tables including timeline weighted: `outputs/emotion_sentiment_crosstab.csv`. Heatmap: `outputs/emotion_plots/emotion_sentiment_crosstab.png`.

Positive sentiment should load on **joy** more than anger/sadness; negative on anger/sadness/fear/disgust. Residual mass in `others` is expected with stemmed IFB templates.

## Per-user emotion summary

`outputs/user_emotion_summary.csv` — **35,250** users, mean 21.1 scored posts.

| Plurality emotion | Users | Share |
|-------------------|------:|------:|
| joy | 1,310 | 3.72% |
| anger | 246 | 0.70% |
| sadness | 61 | 0.17% |
| fear | 30 | 0.09% |
| surprise | 40 | 0.11% |
| disgust | 471 | 1.34% |
| others | 33,092 | 93.88% |

Percentages are within-user raw counts. Timeline weights are not applied at user level.

## Replacement-character records

Five U+FFFD posts. **Original text was not repaired.** They remain `uncertain` and are **not** in `post_emotion`.

| source | tweet_id | translation_status | scored? |
|--------|----------|--------------------|---------|
| `keyword_tweets` | `1110608490748207104` | uncertain | no (held out) |
| `keyword_tweets` | `1132322951167205376` | uncertain | no (held out) |
| `keyword_tweets` | `1481686488005763072` | uncertain | no (held out) |
| `timeline` | `1384572695057215493` | uncertain | no (held out) |
| `timeline` | `1482044995179790341` | uncertain | no (held out) |

## Limitations

1. **Porter stemming + English stopword removal** on `clean_text` strip many emotion cues (“happy”, “angry” may be stemmed; function words gone). This inflates `others` and flattens the six Ekman series.
2. **Language filter.** Only `not_required_english` ∩ sentiment-scored rows. Latin-script Portuguese/French can still be in the set; the English emotion head may mis-label them.
3. **Sampling.** Keyword = eligible census (promotional IFB talk). Timeline = stratified ~1.7% of English timeline; use `sample_weight` only for population shares, never for scoring.
4. **Combined plots/tables mix two frames** and are not a population parameter.
5. **Empty clean_text** (2,948) used a placeholder period.
6. **No events yet.** Do not treat monthly wiggles as world events without tweet evidence.

## Files

- `src/emotion_analysis.py` — GPU batches, SQLite checkpoint `post_emotion`, `add_event_lines()`
- `notebooks/emotion_analysis.ipynb`
- `data/nlp_analysis_corpus.db` table `post_emotion`
- `outputs/Posts_emotions.csv` (UTF-8 BOM)
- `outputs/emotion_distribution.csv`
- six `outputs/emotion_over_time_*.csv`
- `outputs/emotion_sentiment_crosstab.csv`
- `outputs/user_emotion_summary.csv`
- `outputs/emotion_plots/`

Inference this run: 742,942 newly scored in 2222.0s.
