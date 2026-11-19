# Event detection

Built: 2026-09-11T16:52:55Z
IFB.db was not opened. Sentiment and emotion scores were not recomputed.
No chatbot news list. No causation claims.

## Input row counts

| Item | N |
|------|--:|
| English-ready NLP posts with sentiment+emotion | **742,942** |
| Weekly series bins scanned (keyword+timeline × 6 emotions) | 5,964 |
| Monthly series bins scanned | 1,428 |
| Statistical candidates (`pass_stats` before evidence) | 68 |
| Selected events | **4** |
| Evidence tweets | **31** |

## Detection parameters

- `min_n_weekly`: 160
- `min_n_monthly`: 400
- `min_emotion_count_weekly`: 12
- `min_emotion_count_monthly`: 15
- `z_weekly`: 2.75
- `z_monthly`: 2.25
- `rolling_windows`: 12
- `refractory_days_weekly`: 21
- `refractory_days_monthly`: 45
- `min_unique_authors`: 5
- `min_unique_texts`: 8
- `max_share_from_one_author`: 0.45
- `others_not_used_as_signal`: True
- `timeline_weighted_z_confirm`: 1.5
- `drops_scanned_not_auto_selected`: True
- `theme_min_hits`: 8
- `theme_alt_hits`: 5
- `theme_alt_fraction`: 0.2
- `theme_rare_hits`: 4
- `theme_rare_n_max`: 25
- `ifb_boilerplate_max_share`: 0.3
- `untimed_high_z_not_selected`: True

## Candidate rejection criteria

| Reason | N |
|--------|--:|
| n_raw<160 | 3162 |
| |z|<2.75_drop | 927 |
| n_raw<400 | 660 |
| z<2.75 | 579 |
| not_local_peak_or_drop | 531 |
| |z|<2.25_drop | 227 |
| n_fear<12 | 226 |
| n_anger<12 | 196 |
| n_sadness<12 | 184 |
| n_surprise<12 | 146 |
| n_disgust<12 | 136 |
| z<2.25 | 124 |
| n_fear<15 | 66 |
| n_surprise<15 | 54 |
| n_sadness<15 | 53 |
| no_coherent_named_theme | 52 |
| n_anger<15 | 30 |
| too_close_to_stronger_peak | 17 |
| n_disgust<15 | 6 |
| ifb_followback_templates | 5 |
| too_few_emotion_tweets_in_window;low_author_or_text_diversity;dominated_by_one_author | 4 |
| too_few_emotion_tweets_in_window | 3 |

## Selected events

| ID | Date | Emotion | Source | z | Window N | Emotion N | Theme | Evidence tweets |
|----|------|---------|--------|--:|--------:|----------:|-------|----------------:|
| E01 | 2022-03-01 | fear | keyword_tweets | 4.5856 | 3720 | 19 | Official flood warnings (eastern Australia / NSW) | 6 |
| E02 | 2022-11-21 | joy | keyword_tweets | 4.9515 | 597 | 61 | Thanksgiving greetings in user timelines | 10 |
| E03 | 2022-02-21 | fear | timeline | 3.4695 | 3553 | 15 | Posts mentioning the 2022 Russia–Ukraine war | 5 |
| E04 | 2021-11-22 | joy | timeline | 5.2194 | 2075 | 221 | Thanksgiving greetings in user timelines | 10 |

## E03 evidence top-up (2026-09-12 corrective pass)

The detection statistics were **not** recomputed (z=3.4695; 15 fear posts among 3,553 timeline posts; `theme_hits`=4). Two additional **existing** fear tweets from the same calendar week were added to `event_tweet_evidence.csv` so E03 has **5** stored examples:

| tweet_id | source | Why it was added |
|----------|--------|------------------|
| 1497370141889376258 | timeline | Second user in the E03 window quoting the same Ukraine / explosion text already counted in `theme_hits`. Different `tweet_id`, not a copied row. |
| 1496560010545016833 | keyword_tweets | Same week (2022-02-23). Fear-labeled post that names a Ukraine attack warning. This row is **not** one of the 15 timeline fear posts and was **not** used in the z-score. It is extra tweet-level illustration from the keyword census. |

E03 remains a **subset** claim: 4 of 15 timeline fear posts mention Ukraine or explosions. Other fear tweets that week are about other scares. This is not proof that the invasion caused the IFB sample’s fear share.

## Limitations

- Sampled timeline (~1.7% of English timeline): weekly bins especially can spike from a handful of users.
- Keyword language is rule-based, not Twitter LANG; IFB/follow templates contaminate joy and also pull in official 'follow SES advice' weather alerts.
- No conversation IDs or follower graph in the released tables, so amplification paths cannot be shown.
- Missing engagement fields on `nlp_posts` (likes/replies/retweets were not copied).
- External pages are encyclopedic context only, attached when tweets already name the thing. Correlation is not causation.
- `others` is the majority emotion class and was not used as a detection signal.

## Output checklist

| File | Present |
|------|---------|
| `src/event_detection.py` | yes |
| `notebooks/event_detection.ipynb` | yes |
| `outputs/detected_events.csv` | yes |
| `outputs/event_tweet_evidence.csv` | yes |
| `outputs/event_statistics.csv` | yes |
| `outputs/event_external_sources.csv` | yes |
| `outputs/event_detection_candidates.csv` | yes |
| `outputs/detected_events.json` | yes |
| `detected_events.docx` | yes |
| `EVENT_DETECTION_REPORT.md` | yes |
| `event_plots/weekly` | yes |
| `event_plots/weekly_keyword` | yes |
| `event_plots/weekly_timeline` | yes |
| `emotion_plots/weekly_annotated` | yes |
| `event_plots/biweekly` | yes |
| `event_plots/biweekly_keyword` | yes |
| `event_plots/biweekly_timeline` | yes |
| `emotion_plots/biweekly_annotated` | yes |
| `event_plots/monthly` | yes |
| `event_plots/monthly_keyword` | yes |
| `event_plots/monthly_timeline` | yes |
| `emotion_plots/monthly_annotated` | yes |
| `event_plots/quarterly` | yes |
| `event_plots/quarterly_keyword` | yes |
| `event_plots/quarterly_timeline` | yes |
| `emotion_plots/quarterly_annotated` | yes |
| `event_plots/halfyearly` | yes |
| `event_plots/halfyearly_keyword` | yes |
| `event_plots/halfyearly_timeline` | yes |
| `emotion_plots/halfyearly_annotated` | yes |
| `event_plots/yearly` | yes |
| `event_plots/yearly_keyword` | yes |
| `event_plots/yearly_timeline` | yes |
| `emotion_plots/yearly_annotated` | yes |

Every selected event has ≥1 tweet in `event_tweet_evidence.csv` that exists in SQLite. Plots include dashed labeled vertical lines. `others` was not used as the detection signal.
