# Project compliance checklist

Status key: **Not started** = no analysis files yet. Inspection and coverage only.

Canonical population (must be used in every stage): **38,576 users**, **1,129,607** keyword tweets, **37,839,416** timeline tweets. Join on `CAST(AUTHOR_ID AS TEXT)`.

Encoding for every CSV: **UTF-8**.

---

## 0. Dataset freeze (not in the PDF, but required by our coverage decision)

| Field | Content |
|-------|---------|
| Requirement | Freeze one analysis corpus from the triple-intersection users. Sample posts before BERT. Never export all 45M rows. |
| Required output file | `data/analysis_corpus.csv` (or parquet) + `data/primary_author_ids.txt` + codebook |
| Required columns | `tweet_id`, `author_id`, `username`, `created_at` (parsed ISO), `text_original`, `lang`, `source` (`keyword`/`timeline`), `keyword` (trimmed, nullable) |
| Required graph or evidence | Coverage table already in `DATASET_DECISION.md` |
| Report | Population sizes before/after each filter; why 38,576; duplicate AUTHOR_ID rule |
| Presentation | 1 slide: users, keyword tweets, timeline tweets, English share |
| Validation | Row counts match decision doc; no ambiguous AUTHOR_IDs; dates parse |
| Current status | **Done.** `data/analysis_corpus.db` (38,576 users; 1,129,607 keyword; 37,839,416 timeline). NLP file `data/nlp_analysis_corpus.db` scores **742,942** English-ready posts. `data/primary_author_ids.txt` exported from `users`. No 38.9M-row CSV dump. |
| Remaining action | None. Do not rebuild the corpus. |

---

## 1. Topic selection / IFB population

| Field | Content |
|-------|---------|
| Requirement | Analyze the IFB / follow-for-follow target group. Data were collected by keywords, not POI followers. |
| Required output file | Project folder `IFB/` (or this workspace) with stage subfolders |
| Required columns | N/A |
| Required graph or evidence | Short description of keyword collection (`ifb`, `follow for follow`, … 24 trimmed keywords) |
| Report | Collection method; what IFB means; limitation that keyword tweets are self-selected IFB talk |
| Presentation | Slide 1–2: goal |
| Validation | Folder names in English |
| Current status | **Chosen.** Workspace exists. |
| Remaining action | Create stage subfolders when analysis starts. |

---

## 2.1 Translation

| Field | Content |
|-------|---------|
| Requirement | English column `text_translated_en`. Skip only if **all** posts are already English. ~12% non-English was not accepted as a skip. Timeline: 77.5% `en`, 12.3% other languages, 10.2% non-linguistic. Keyword tweets have **no LANG**. |
| Required output file | `English_Translation/translator.ipynb`; `translated_en_posts.csv`; `translation_examples.csv` |
| Required columns | `translated_en_posts.csv`: original text + `text_translated_en`. `translation_examples.csv`: `original_text`, `translated_text` (10 rows) |
| Required graph or evidence | 10 quality examples; answers: bad translations? hashtags? person names preserved? |
| Report | Language census; what was translated vs skipped (`und/qme/qam/zxx` skipped); 10 examples **printed in the report** |
| Presentation | % English / translated / skipped |
| Validation | UTF-8; names not translated; non-linguistic codes not treated as English |
| Current status | **Partial.** English-ready corpus by construction: `text_translated_en` is a copy of `original_text` for 742,942 rows. Non-English posts were excluded, not translated. Examples in `outputs/translation_examples.csv`. Standalone `translated_en_posts.csv` was not dumped. |
| Remaining action | Do not invent translations. Keep the English-only decision in the report. |

---

## 2.2 Preprocessing

| Field | Content |
|-------|---------|
| Requirement | Clean text: URLs, mentions, hashtags (keep token without `#`), emojis, punctuation, lowercase, stopwords, stem **or** lemma. **IFB instructor:** also remove `ifb`, `follow`, `followback`, `follow4follow`, and related seed tokens **before topic modeling**. |
| Required output file | `Data_Preprocessing/text_preprocessing.ipynb`; `posts_cleaned.csv` |
| Required columns | `tweet_id`, `text_translated_en`, **`clean_text`** (mandatory saved column) |
| Required graph or evidence | Before/after examples in report |
| Report | Cleaning rules; IFB-word stoplist; encoding UTF-8 |
| Presentation | One before/after tweet |
| Validation | File opens in Excel/editor without gibberish; `clean_text` present; later stages read `clean_text` |
| Current status | **Partial.** `clean_text` and `topic_text` saved in `nlp_posts`. IFB/follow stripped only in `topic_text`. Examples in `outputs/preprocessing_examples.csv`. Standalone `posts_cleaned.csv` was not dumped. |
| Remaining action | None for scores. Guideline filename remains a pointer, not a 742k CSV. |

---

## 2.3 Sentiment

| Field | Content |
|-------|---------|
| Requirement | `pysentimiento` 3-class sentiment on `clean_text` / English text. |
| Required output file | `Sentiment_Analysis/sentiment_analysis.ipynb`; `Posts_sentiment.csv`; pie PNG; time-series PNG |
| Required columns | `sentiment_label` ∈ {positive, neutral, negative}; `sentiment_positive`; `sentiment_negative`; **instructor also expects neutral probability** → add `sentiment_neutral` |
| Required graph or evidence | Pie of 3 classes (green / yellow / red). **Monthly (or similar) time series with three separate lines**, not one mixed “sentiment” line. Optional: mean sentiment per user table. |
| Report | Counts and % for all 3 classes; both figures embedded; interpretation |
| Presentation | Pie + one time chart with 3 series |
| Validation | Neutral not missing; colors correct; time chart has 3 series |
| Current status | **Done.** 742,942 posts; 35,250 users; 134,936 / 526,377 / 81,629. Three-class pie + three monthly panels (green / yellow / red). `outputs/Posts_sentiment.csv`. |
| Remaining action | Do not rescore. |

---

## 2.4 Emotions

| Field | Content |
|-------|---------|
| Requirement | `pysentimiento` emotion analyzer (`task="emotion", lang="en"`). |
| Required output file | `Emotion_Analysis/emotion_analysis.ipynb`; `Posts_emotions.csv`; PNG per aggregation |
| Required columns | `emotion_label`; `emotion_joy`; `emotion_anger`; `emotion_sadness`; `emotion_fear`; `emotion_surprise`; `emotion_disgust`; `emotion_others` |
| Required graph or evidence | Time plots at **week, 2-week, month, 3-month, 6-month, year**. Save the numeric series, not only pictures. Later: dashed vertical event lines on **every** plot. |
| Report | Emotion–sentiment relationship; all aggregations or a representative set **plus** statement that all resolutions exist as files |
| Presentation | One multi-emotion time chart with events |
| Validation | CSV has all probability columns; PNGs exist; no “only pos/neg emotion” shortcut |
| Current status | **Done.** 742,942 posts; seven probability columns; week / 2-week / month / quarter / half-year / year CSVs and PNGs in `outputs/emotion_plots/`. Event-annotated copies in `outputs/event_plots/`. |
| Remaining action | Do not rescore. |

---

## 2.5 Events

| Field | Content |
|-------|---------|
| Requirement | Find peaks/drops on emotion graphs; pull top 20 tweets in that window for the emotion; **manual** reading; optional Twitter archive trending; **vertical labeled lines** on emotion (and later topic) graphs. IFB column: do **not** invent events via chatbot. |
| Required output file | `Event_Detection/events_analysis.ipynb`; `detected_events.docx`; event-annotated PNGs |
| Required columns / contents | For each event: date range, emotion that spiked, **N posts in window**, 5–20 example tweets, why it is a real world/community event |
| Required graph or evidence | Dashed vertical lines + event name on all emotion aggregations |
| Report | Method (peak → tweets → event), not a dumped news list. Embed tweet examples. |
| Presentation | 2–4 evidenced events |
| Validation | Every named event has tweet quotes; lines appear on graphs |
| Current status | **Done.** 4 tweet-supported events; 31 evidence tweets; E03 has 5 real fear tweets. `detected_events.docx` updated. Statistics (z, theme_hits) unchanged. |
| Remaining action | Do not invent a fifth event. |

---

## 3. Topic modeling (BERTopic)

| Field | Content |
|-------|---------|
| Requirement | BERTopic on `clean_text` **after IFB/follow tokens are removed**. 10% sample to tune if N is large, then apply best params to the analysis corpus. Guidelines: if only tens of thousands of posts, tune on all. Our corpus will still be large after sampling — document the 10% (or stratified) tune set. |
| Required output file | Topic notebook; experiments CSV/XLSX; **pickle of each (or at least the final) model**; `final_topics.csv` / `topics_final.csv`; representative-docs file; coherence plot PNG |
| Required columns | Experiments: `min_topic_size`, `n_neighbors`, `n_topics`, `Topic_num`, `coherence`. Final: `tweet_id`, `created_at`, `text_translated_en`, `topic_id`, `topic_label`, `probability` |
| Required graph or evidence | X = configuration or topic count, Y = **Coherence**. Topic volume over time with event lines. Table of top words + post counts. Meaningful names (not “SAY”). |
| Report | Why this config wins (coherence + outlier rate + manual inspection). Outlier %; if >10%, `reduce_outliers` / retune. Representative tweets per topic **in the report**. |
| Presentation | Topic count, outlier %, top topics with proportions |
| Validation | IFB/follow not dominating topic words; several configs recorded; pickle loadable; Coherence used (if u_mass, justify) |
| Current status | **Done (2026-09-11).** Tune sample 64,000 (seed 2026); selected C13 (`min_topic_size=50`, `n_neighbors=30`, `reduce_outliers` + `nr_topics=24`) by coherence **and** interpretability, not max c_v. Assignments in SQLite `post_topic`; pickle `outputs/topic_model.pkl`. Outliers reported (topic -1, 23.1%). |
| Remaining action | None for this phase. Do not rerun sentiment/emotion/events. |

---

## 3.2 Sentiment per topic

| Field | Content |
|-------|---------|
| Requirement | Join topics with sentiment; counts of positive / **neutral** / negative per topic. |
| Required output file | `topic_sentiment_analysis.ipynb`; `topic_sentiment_distribution.csv`; `topic_sentiment_visualization.png` |
| Required columns | `topic`, `positive`, `neutral`, `negative` (counts) |
| Required graph or evidence | **Top-6 topics:** center word cloud, outer ring 3-color sentiment, slice ∝ counts. Green/yellow/red. |
| Report | Figure in report; link negative topics to events if true |
| Presentation | 2–3 topic rings |
| Validation | Neutral slice present; not only pos vs neg |
| Current status | **Done (2026-09-11).** Unweighted counts + keyword vs timeline split; timeline weights labeled as population estimates inside each topic. Top-6 word-cloud + green/yellow/red rings: `outputs/topic_sentiment_visualization.png`. |
| Remaining action | None for this phase. |

---

## 4. NER and entity sentiment

| Field | Content |
|-------|---------|
| Requirement | NER (HuggingFace / BERTweet / LLM) for PERSON, LOCATION/GPE/LOC/COUNTRY, ORGANIZATION, EVENT. Attach tweet `sentiment_label`. Clean: drop length <3, drop freq=1, strip `#@`, merge aliases. Split people vs countries. Interpret whether results make sense (previous IFB: all yellow bug; `&` as entity). |
| Required output file | `NER_Analysis/entity_extraction.ipynb`; `entities_extracted.csv`; `entities_cleaned.csv`; `person_entities_sentiment.png`; `country_entities_sentiment.png` |
| Required columns | Extracted: `tweet_id`, `entity`, `entity_type`, `sentiment_label`. Cleaned: `entity`, `entity_type`, `Count` plus pos/neu/neg counts |
| Required graph or evidence | Top-10 people stacked bar; Top-10 countries stacked bar; green/yellow/red. Sort by polarity or frequency and say which. |
| Report | Who are the people/places and is it plausible for an IFB community (influencers, platforms, countries of users — not necessarily Netanyahu). Discuss surprises. |
| Presentation | Two bar charts |
| Validation | No `&` nodes; colors not all yellow; aliases merged |
| Current status | **Done (2026-09-12).** spaCy `en_core_web_lg` 3.8.0 on `original_text` for 742,942 posts. `&` dropped. Person/country stacked bars are green/yellow/red, not all-yellow. Assignments in SQLite `entity_mention`; CSVs + `NER_ENTITY_ANALYSIS_REPORT.md`. |
| Remaining action | Do not rerun NER. Entity network is complete. |

---

## 4.2 Entity co-occurrence network

| Field | Content |
|-------|---------|
| Requirement | Pairs of entities in the same tweet; weight = number of tweets; graph via `networkx`; **at least three** of Degree, Betweenness, Closeness, PageRank. Visual: node size = centrality, edge width = weight. Filter Top-30 or min count 20. **This is the graded “network analysis.”** There is no follower-edge table. |
| Required output file | `entity_network_analysis.ipynb`; `entity_pairs.csv`; `entity_network_edges.csv`; `entity_network_metrics.csv`; `entity_network_graph.png` |
| Required columns | Pairs: `tweet_id`, entity list or `entity_1`,`entity_2`. Edges: `entity_1`, `entity_2`, `weight`. Metrics: `entity` + centrality columns |
| Required graph or evidence | Readable Top-30 graph; weights must not be missing (Ukraine lost points for this) |
| Report | Who is central and why; embed graph |
| Presentation | Network figure |
| Validation | `weight` ≥ 1 integer; no junk tokens as nodes |
| Current status | **Done (2026-09-12).** Undirected entity co-occurrence only (`networkx`). `edge_weight` = distinct posts. Degree, weighted degree, betweenness, closeness, PageRank, eigenvector. Top-30 graph titled “Entity Co-occurrence Network”; caption states this is not a follower network. Keyword census vs timeline sample kept separate. `IFB.db` not opened. |
| Remaining action | Bot/malicious-user detection is complete. Do **not** invent a follower graph. |

---

## 5. Bad actors — features

| Field | Content |
|-------|---------|
| Requirement | Metadata features + tweet features for the **38,576** users. |
| Required output file | Feature table (e.g. `user_features.csv`) + notebook |
| Required columns | `followers_following_ratio`; `statuses_count` (`TWEET_COUNT`); `account_age_days`; `posts_per_day`; default-profile-image flag (best-effort from `IMAGE_URL`); `bio_length`; `verified`; plus from posts: `rt_rate` (text `RT @` and/or `RETWEETS` count — **document which**); posting-hour mean; inter-tweet time variance; mean hashtags; mean mentions; copy-paste rate. Optional IFB-specific: `IFB_COUNT`, `FREELANCER`. |
| Required graph or evidence | Feature distributions (bots vs humans after labeling) |
| Report | Feature definitions and missing-field caveats (no native is_retweet) |
| Presentation | Feature list |
| Validation | One row per unambiguous AUTHOR_ID |
| Current status | **Done (2026-09-12).** `outputs/user_bot_features.csv` has 38,576 rows. Profile from `authors` (IFB.db read-only). Behavior from NLP corpus. `rt_at_ratio` is text `RT @` only (no native retweet flag). |
| Remaining action | Do not rerun. |

---

## 5. Manual labeling

| Field | Content |
|-------|---------|
| Requirement | Random **100** users from the target set. Inspect live X/Twitter profile. Label only if certain. IFB column failed this. |
| Required output file | `labeled_bots_and_not_bots.csv` (guidelines also mention this name) |
| Required columns | `username` (and `author_id`); `is_bot` ∈ {1,0,unknown}; `is_troll`; `is_malicious`; `comments` |
| Required graph or evidence | Screenshots or quoted profile notes in report for a few examples |
| Report | How many 1/0/unknown; criteria; **accounts deleted since 2023** counted as unknown, not bots |
| Presentation | Label counts |
| Validation | 100 rows; not inferred only from the rule formula |
| Current status | **Done (2026-09-12).** 100 users, seed 2026, stratified on unlabeled rule bands. Labels from snapshot profile + original posts (not live X). 39 likely_normal / 30 suspicious / 29 likely_malicious / 2 insufficient_evidence. Deleted/unavailable not used as malicious. `is_bot` is 0 or unknown — never claimed as proven software bots. |
| Remaining action | Do not invent a second 200-label set. |

---

## 5. Rule flowchart + rule classifier

| Field | Content |
|-------|---------|
| Requirement | Flowchart from the manual review; implement in readable Python; apply to all 38,576; **validate on 200 random predicted users**; report accuracy of the rules. |
| Required output file | `malicious_detection_flow.pptx`; rule-classifier notebook/script; validation table |
| Required columns | Rule outputs per user + validation labels |
| Required graph or evidence | Flowchart **inside the report**, not only PPTX |
| Report | Each rule with threshold rationale; 200-user accuracy |
| Presentation | Flowchart slide |
| Validation | PPTX exists; 200 labeled; accuracy reported |
| Current status | **Done (2026-09-12).** Rules applied to all 38,576. Flowchart in `malicious_detection_flow.pptx` and `outputs/malicious_detection_flow.png`. Rule vs manual (98 usable): precision 1.00, recall 0.59, F1 0.74. **200 extra validation labels were not fabricated.** |
| Remaining action | 200-user live validation remains a disclosed limitation. |

---

## 5. ML classifiers

| Field | Content |
|-------|---------|
| Requirement | Binary bot/non-bot (repeat for troll/malicious if labels allow). Algorithms: Logistic Regression, Decision Tree, Random Forest, SVM, XGBoost. **K-Fold K=5 and LOOCV.** Choose best; predict all users; drop `confidence ≥ 0.8` bad actors from “clean” population. |
| Required output file | `bot_detection_experiments.csv`; `bot_detection_predictions.csv`; also listed: `unlabeled_dataset_results.csv`, `unlabled_dataset.csv` |
| Required columns | Experiments: `target_column`, `algorithm`, `feature_set`, `training_type`, `K`, `balanced`, `accuracy`, `precision`, `recall`, `F1`, `AUC`. Predictions: `username`, `predicted_class`, `confidence_level`, `prob_0`, `prob_1` |
| Required graph or evidence | Metric comparison table/chart; **training N per class** (instructor repeated this) |
| Report | Best model, N_train pos/neg, CV type, who was filtered |
| Presentation | Best algorithm + scores + train size |
| Validation | All 5 algorithms; both CV types; sample sizes written |
| Current status | **Done (2026-09-12).** Five algorithms, K=5 and LOOCV, user-level splits, seed 2026. Train on 98 labeled users only (59 pos / 39 neg; mean n_train 78 in K=5). Best K=5 pooled: Random Forest F1 0.885 / bal. acc. 0.842 / AUC 0.93. Predictions written for all 38,576. |
| Remaining action | Word report / presentation still open. |

---

## 6. Word report

| Field | Content |
|-------|---------|
| Requirement | Word document following the same chapter structure as the stages. **All required numbers, tables, and figures inside the file.** Secondary extras can be in appendices. Not a “see Drive folder” memo. |
| Required output file | `report/` Word file |
| Required columns / contents | Dataset description (users, posts, filters); each stage method + results + examples; limitations |
| Required graph or evidence | Every graded PNG embedded |
| Report | This file **is** the report |
| Presentation | N/A |
| Validation | Instructor can grade without opening notebooks |
| Current status | **Done (2026-09-12).** `report/final_project_report.docx` with embedded figures, tables, limitations, and the canonical counts. |
| Remaining action | Visual pass before Moodle upload. |

---

## 7. Presentation

| Field | Content |
|-------|---------|
| Requirement | 15 minutes including questions (guidelines: last class 12/06/2026; upload by 31/05/2026 23:59 — dates as printed). Slides: goal (1–2), full method, results (N posts/users after each filter, best model, train sizes, topic proportions), conclusions (1–2). |
| Required output file | `presentation/` slides; upload to Moodle boxes named in the PDF |
| Required graph or evidence | Same color rules; do not read from a tablet |
| Report | N/A |
| Presentation | Partners must know `pysentimiento`, topic count, train N |
| Validation | Dry-run Q&A |
| Current status | **Done (2026-09-12).** `presentation/final_project_presentation.pptx` — 14 slides, embedded charts, speaker notes with a 15-minute plan. |
| Remaining action | Dry-run Q&A. Do not add causal claims. |

---

## Folder structure (graded)

```
IFB/
  Posts_Analysis/posts.csv
  English_Translation/translated_en_posts.csv, translator.ipynb, translation_examples.csv
  Data_Preprocessing/text_preprocessing.ipynb, posts_cleaned.csv
  Sentiment_Analysis/sentiment_analysis.ipynb, Posts_sentiment.csv, *.png
  Emotion_Analysis/emotion_analysis.ipynb, Posts_emotions.csv, *.png
  Event_Detection/events_analysis.ipynb, detected_events.docx, *.png
  Topic_Modeling/ (experiments, pickle, final_topics.csv, coherence plot)
  Topic_Sentiment/topic_sentiment_analysis.ipynb, topic_sentiment_distribution.csv, topic_sentiment_visualization.png
  NER_Analysis/entity_extraction.ipynb, entities_extracted.csv, entities_cleaned.csv, person_*.png, country_*.png
  Entity_Network_Analysis/entity_network_analysis.ipynb, entity_pairs.csv, entity_network_edges.csv, entity_network_metrics.csv, entity_network_graph.png
  Bot_Detection/malicious_detection_flow.pptx, labeled_bots_and_not_bots.csv, bot_detection_experiments.csv, bot_detection_predictions.csv
  report/, presentation/
```

| Field | Content |
|-------|---------|
| Current status | **Partial.** Working tree remains `data/ src/ notebooks/ outputs/`. Guideline folders exist as README pointers to canonical files. Giant CSVs were not duplicated. `IFB.db` stays read-only. |
| Remaining action | Optional: copy small notebooks into stage folders if Moodle expects that tree. |

---

## Explicitly not required as user-follow or cascade networks

The intro PDF lists “network of user groups” and “discourse spread.” Graded files are **entity** networks only. Status: **will report as limitation**, not as a missing homework file. See `PROJECT_RISKS_AND_LIMITATIONS.md`.
