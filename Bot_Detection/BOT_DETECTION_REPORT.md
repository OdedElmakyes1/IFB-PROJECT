# Bot / malicious-user detection

Built: 2026-09-12T05:04:35Z

**This is a behavioral risk classification, not verified bot identity.**

IFB.db was opened **read-only** for `authors` metadata only and was not modified. Sentiment, emotion, events, BERTopic, NER, and the entity network were not rerun.

## Operational definition

A user is treated as **suspicious / likely malicious** when snapshot metadata and original posts show follow-farm automation, copy-paste IFB templates, or RT-@ amplification with little original voice. That is **not** proof the account is a software bot. Humans run IFB campaigns.

## Why bot status cannot be proven

- No follower graph, no reply/quote IDs, no native retweet flag or cascade.
- Profiles are a 2023 snapshot. Live X pages were not used as a required oracle.
- Timeline text is a stratified ~1.7% English sample (seed 2026), not a full history.
- Deleted or empty accounts are **insufficient_evidence**, not bots.

## Population

- Primary triple-intersection users: **38,576**
- Users with English NLP posts (behavior features): **35,250**
- Keyword features and timeline features are stored as separate counts. Combined `n_posts` is labeled as mixed frames.
- `timeline_weighted_post_estimate` is a population estimate only and is **not** a model feature or training weight.

## Features

Profile: followers, following, tweet_count, listed_count, IFB_COUNT, verified, protected, freelancer, account age (to 2023-12-03), missing-field count, bio length, default-image heuristic, followers/(following+1).

Behavior (NLP corpus only): post counts by source, IFB-collection share, duplicate-template ratio, boilerplate ratio, unique-text ratio, mean length, URL/mention/hashtag ratios, active days, posts/active day, burstiness (CV of daily counts), hour/day-of-week concentration, sentiment and emotion shares, topic outlier/top-share/entropy, text `RT @` ratio.

Not used as model features: `user_id`, `username`, `tweet_id`, raw post text, the manual label, `sample_weight`.

Missing values: median imputed **inside each training fold**. Trees skip scaling; linear/SVM use StandardScaler fit on the train fold only. Epoch `1970-01-01` ages are treated as missing. NLP `created_at` values use ISO-8601 (`T` separator) and are parsed that way for burstiness and hour/day concentration. Extreme counts stay in the table; models see raw values after median/scale. `rt_at_ratio` uses detectable `RT @` text only.

## Manual review

100 users, seed 2026. Labels: {'suspicious': 30, 'likely_normal': 39, 'likely_malicious': 29, 'insufficient_evidence': 2}. Usable for ML: **98** (pos=59, neg=39). The two `insufficient_evidence` users are excluded from every model, which is why the ML dataset is 98 rows and not 100. `is_bot` is 0 or unknown — never 1. See `MANUAL_BOT_REVIEW_GUIDE.md` and `outputs/manual_review_examples.csv`.

**This is not a simple random sample.** The 100 users were **stratified on the rule engine’s own output** (35 `low_risk` / 30 `medium_risk` / 35 `high_risk`). The guidelines ask for a random draw; this design is disclosed rather than hidden, and the 100 labels were not redrawn.

| Rule band | Population N | % of 38,576 | Drawn into the 100 | Enrichment |
|-----------|-------------:|------------:|-------------------:|-----------:|
| low_risk | 21,516 | 55.8% | 35 | ~0.6× |
| medium_risk | 1,988 | 5.2% | 30 | ~5.8× |
| high_risk | 99 | 0.26% | 35 | **~136×** |
| insufficient_posts | 14,973 | 38.8% | 0 | excluded from review |

Because the high-risk band was enriched by two orders of magnitude, and because the rule output selected the users on which the rule is then scored, **precision 1.00 / recall 0.59 / F1 0.74 / balanced accuracy 0.80 are diagnostics on a rule-selected sample. They are not unbiased population estimates** and must not be read as a population error rate.

There is **no 200-user second manual set**. Extra labels were not invented. Live X profiles cannot be aligned to a corpus that ends in 2023-12. The gap is marked missing, not fabricated.

## Rule thresholds

| Rule | Threshold | Why | FP risk |
|------|-----------|-----|---------|
| IFB boilerplate | ≥ 0.45 of posts | Collection copy is the IFB tell | Honest IFB hobbyists |
| Duplicate templates | ≥ 0.55 | Scripted repetition | Quote-heavy humans |
| Unique text | ≤ 0.40 | Thin original voice | Short-form posters |
| Keyword share | ≥ 0.75 (≥8 posts) | Almost only IFB tweets in the sample | Users rare in the timeline sample |
| `RT @` text | ≥ 0.50 | Amplifiers; no native retweet flag | Heavy conversational RT users |
| Burst + hour lock | burst ≥ 2.2 and hour conc. ≥ 0.35 | Scheduler-like timing | Event-day humans |
| IFB_COUNT | ≥ 20 | Database follow-back counter | Active community members |
| Symmetric mass follow | following ≥ 2000 and ratio 0.7–1.4 | Follow-for-follow farms | Popular IFB accounts |

Rule score is **not** ground truth.

## Rule vs manual labels (100 reviewed users only)

| metric | value |
|--------|------:|
| n_reviewed_usable | 98 |
| rule_high_risk_as_positive_accuracy | 0.7551 |
| rule_precision | 1.0 |
| rule_recall | 0.5932 |
| rule_f1 | 0.7447 |
| rule_balanced_accuracy | 0.7966 |
| tn | 39 |
| fp | 0 |
| fn | 24 |
| tp | 35 |
| note | Rules evaluated only on manual labels; not ground truth |

## Machine learning

Algorithms: Logistic Regression, Decision Tree, Random Forest, SVM, XGBoost

Training rows: **98** users (positive 59, negative 39). K=5 stratified CV and LOOCV. User-level splits; overlap check raises an error. Seed 2026. Preprocessing fit on the training fold only. Class weights / XGBoost `scale_pos_weight`.

Accuracy is reported with precision, recall, F1, balanced accuracy, ROC-AUC and PR-AUC where both classes exist. Best K=5 pooled model: **Random Forest** (F1 0.885, balanced accuracy 0.842, AUC 0.93). Full-population predictions use that family; `confidence ≥ 0.8` risk_positive is a filter suggestion, not a ban list.

### K=5 pooled

| Algorithm | n_train (mean) | n_test | pos/neg test | accuracy | precision | recall | F1 | bal. acc. | AUC |
|-----------|---------------:|-------:|-------------:|---------:|----------:|-------:|---:|----------:|----:|
| Logistic Regression | 78 | 98 | 59/39 | 0.7755 | 0.7937 | 0.8475 | 0.8197 | 0.7571 | 0.9074 |
| Decision Tree | 78 | 98 | 59/39 | 0.7653 | 0.8333 | 0.7627 | 0.7965 | 0.766 | 0.8036 |
| Random Forest | 78 | 98 | 59/39 | 0.8571 | 0.8571 | 0.9153 | 0.8852 | 0.8422 | 0.93 |
| SVM | 78 | 98 | 59/39 | 0.7755 | 0.8136 | 0.8136 | 0.8136 | 0.7658 | 0.8561 |
| XGBoost | 78 | 98 | 59/39 | 0.8163 | 0.8361 | 0.8644 | 0.85 | 0.804 | 0.9144 |

### LOOCV pooled

| Algorithm | n_train | n_test | F1 | bal. acc. | AUC |
|-----------|--------:|-------:|---:|----------:|----:|
| Logistic Regression | 97 | 98 | 0.8547 | 0.8212 | 0.9335 |
| Decision Tree | 97 | 98 | 0.8793 | 0.8553 | 0.8677 |
| Random Forest | 97 | 98 | 0.8689 | 0.8209 | 0.9322 |
| SVM | 97 | 98 | 0.8421 | 0.817 | 0.8727 |
| XGBoost | 97 | 98 | 0.8718 | 0.8425 | 0.9348 |

## Important features (Random Forest full labeled fit)

| Feature | importance |
|---------|-----------:|
| duplicate_template_ratio | 0.1098 |
| boilerplate_ratio | 0.1064 |
| unique_text_ratio | 0.0959 |
| n_keyword | 0.0441 |
| ifb_collection_share | 0.0413 |
| pct_others | 0.0390 |
| topic_entropy | 0.0370 |
| pct_negative | 0.0328 |
| pct_neutral | 0.0312 |
| pct_disgust | 0.0292 |
| posts_per_active_day | 0.0267 |
| account_age_days | 0.0257 |

## False positives and false negatives

False positives are mostly ordinary IFB users whose bios and posts are follow-back templates. False negatives are accounts that look conversational in the sampled timeline posts even if keyword tweets are promotional. High-confidence (`≥ 0.8`) risk_positive predictions are a **filter suggestion**, not a ban list.

## Limitations

- No live profile confirmation in this environment.
- No follower graph, conversation IDs, or native retweet flag.
- Timeline is a stratified sample; keyword is a census of IFB tweets.
- 100 labels is a small, imbalanced set. Metrics have wide uncertainty.
- 200-user rule validation was **not** fabricated.

## Output checklist

| File | Present |
|------|---------|
| `src/bot_detection.py` | yes |
| `notebooks/bot_detection.ipynb` | yes |
| `outputs/user_bot_features.csv` | yes |
| `outputs/manual_bot_labels.csv` | yes |
| `outputs/manual_review_examples.csv` | yes |
| `outputs/rule_based_bot_scores.csv` | yes |
| `outputs/rule_based_summary.csv` | yes |
| `outputs/bot_detection_experiments.csv` | yes |
| `outputs/bot_detection_predictions.csv` | yes |
| `outputs/bot_feature_importance.csv` | yes |
| `outputs/bot_confusion_matrices.png` | yes |
| `outputs/bot_model_comparison.png` | yes |
| `outputs/bot_feature_distributions.png` | yes |
| `malicious_detection_flow.pptx` | yes |
| `MANUAL_BOT_REVIEW_GUIDE.md` | yes |
| `BOT_DETECTION_REPORT.md` | yes |
| `xgboost` | yes |
