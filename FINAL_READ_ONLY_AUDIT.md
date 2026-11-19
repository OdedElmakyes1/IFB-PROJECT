# FINAL READ-ONLY AUDIT

> **Pre-fix snapshot (2026-09-12 morning).** The HIGH-priority packaging pass
> that followed is recorded in `FINAL_COMPLIANCE_AUDIT_FINAL.md`.
> Network counts in *this* file (1,126 / 2,665) are the pre-filter figures;
> the canonical post-filter graph is **1,076 nodes / 2,578 edges**.

Audit date: 2026-09-12. Mode: **read-only**. No project file was modified. `IFB.db` was not written. No sentiment, emotion, BERTopic, NER, network, or bot model was rerun. All numbers below were re-derived independently from the SQLite databases, the CSV files, the DOCX/PPTX XML, and the PNG images.

Sources of requirements: `הנחיות פרויקט _V3_Intro_to_Social_Networks_CS_2026_Semester_B (2).pdf` (23 pages), `Intro_to_Social_Networks_Semester_B_2026_Project_Grades_V3 (1).xlsx` (column **J = IFB**, previous score **70**), `INSTRUCTOR_REQUIREMENTS.md`, `PROJECT_COMPLIANCE_CHECKLIST.md`, `PROJECT_RISKS_AND_LIMITATIONS.md`.

---

## 1. Executive verdict

**The analysis is done and it is honest. The packaging is not finished.**

Every named failure in the instructor's IFB column has been fixed, and fixed verifiably:

| Previous IFB failure (workbook column J) | Status now | Hard evidence |
|---|---|---|
| "היה עליכם להוריד מילים כמו IFB, Follow" | **Fixed** | `topic_text` column strips IFB/follow/f4f. `bertopic_experiments.csv` records `ifb_topword_hits = 0` for **all 15** configurations. No topic is named IFB. |
| "אין דבר כזה סנטימנט ביחד" (mixed time series) | **Fixed** | `outputs/sentiment_over_time_monthly.png` is three stacked panels titled "no combined sentiment curve", green / yellow / red. No combined curve exists anywhere. |
| "ניכר שהכנסתם לצ'אט... אני רוצה הוכחות" (chatbot events) | **Fixed** | 7,392 candidate bins → 68 statistical candidates → 4 events. 31 evidence tweets with tweet IDs, usernames, emotion probabilities and window counts in `detected_events.docx` (9 embedded figures). |
| "הישויות הכל בצהוב. באג שלא טופל." | **Fixed** | `person_entities_sentiment.png` and `country_entities_sentiment.png` are green/yellow/red stacked bars with per-bar n and percentages. |
| "& כישות לא הגיוני" | **Fixed for `&`** | 0 `&` entities in `entities_cleaned.csv` and 0 kept `&` mentions in `entity_mention` (`junk_amp_or_symbol` = 15,099 dropped). Other junk remains — see §7. |
| "היה חסר פה מעבר ידני" (no manual bot review) | **Fixed** | 100 reviewed users with free-text evidence on every row, `is_bot` never asserted as 1, deleted accounts never labeled malicious. |
| Report / presentation cells were **empty** for IFB | **Fixed** | 14-chapter Word report with 17 embedded figures and 10 tables; 14-slide deck with a 0:00–15:00 speaker-note plan. |

Data volume is the largest of any project in the workbook that scored below 90: **742,942** scored posts drawn from a documented **38,969,023**-post corpus over **38,576** users.

The intellectual honesty is unusually strong and should be treated as an asset, not a liability: the missing 200-user validation set is disclosed rather than fabricated, bot output is framed as behavioral risk rather than verified identity, the entity graph is labeled co-occurrence in the title, the caption, the report, the deck and the folder README, and every event carries an explicit "not a proven cause" sentence.

**What is not finished is the part a grader touches first.** The ten guideline-named stage folders exist but contain a single one-line README each — not one guideline-named file is actually in its guideline folder, and `Posts_Analysis/` does not exist. All eight notebooks are saved **unexecuted** (`execution_count: null`, empty outputs), so a grader who opens a notebook sees code and no results. There is no `requirements.txt`. The rule flowchart renders as overlapping boxes with no arrows and no Yes/No branches, and that broken image is embedded in both the report and the deck. The deck states "24 named topics" where the shipped assignment has 18.

**Verdict: substantively strong, presentationally incomplete. Not ready to upload today. Roughly half a day of packaging work stands between the current state and a submission that matches the quality of the analysis.**

---

## 2. Full requirement-by-requirement table

Legend — **PASS** = satisfied and verifiable; **PARTIAL** = present but incomplete or misplaced; **FAIL** = absent or wrong; **N/A** = not applicable to this dataset or not a numbered deliverable.

### A. Dataset selection and coverage (guidelines stage 1)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk of losing points | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| A1 | Choose a target population from the project list; English folder name | Workspace | `IFB-project/` | PASS | Topic IFB / follow-for-follow; folder name in English | Low | Folder is `IFB-project`, guidelines example is `Lebaneses_POIs`. Acceptable. | LOW |
| A2 | Report how many posts were analysed (row 2 was **empty** for IFB) | Report + deck | `report/final_project_report.docx` Table 1; PPTX slide 2 | PASS | 742,942 scored; 38,969,023 corpus (1,129,607 + 37,839,416) — verified by `SELECT source, count(*) FROM posts` | Low | None | LOW |
| A3 | Report how many users (row 3 was **empty** for IFB) | Report + deck | Table 1; slide 2 | PASS | 38,576 verified = `count(*) FROM users`; 35,250 scored | Low | None | LOW |
| A4 | Freeze one population; do not dump 39–45M rows to CSV | Corpus build | `data/analysis_corpus.db` (11.5 GiB); `CORPUS_MANIFEST.md` | PASS | SQLite freeze with `users`, `posts`, `corpus` view, 4 indexes; no giant CSV anywhere | Low | None | LOW |
| A5 | Plaintext primary-ID list | Data folder | `data/primary_author_ids.txt` | PASS | Exactly 38,576 lines, verified | Low | None | LOW |
| A6 | Coverage table + duplicate-AUTHOR_ID rule | Report §2 | Report p9; `outputs/data_coverage_report.csv` | PASS | 1,203 ambiguous ID groups dropped, stated in report, deck and `corpus_statistics.csv` | Low | None | LOW |
| A7 | Documented join key | Report §2 | Report p9 | PASS | `CAST(AUTHOR_ID AS TEXT)`; USERNAME explicitly not a join key | Low | None | LOW |
| A8 | Keyword census and timeline sample never merged into one silent population | Everywhere | Report p11–p12, Table 3; slide 2 & 4; every CSV `notes`/`count_note` column | PASS | `sentiment_distribution.csv` carries four separate corpora rows (`keyword_tweets`, `timeline_raw`, `timeline_weighted`, `combined_unweighted`) with explicit notes | Low | None — this is a genuine strength | LOW |

**A subtotal: 8 PASS.**

### B. Translation decision (guidelines stage 2.1)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk of losing points | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| B1 | Column `text_translated_en` exists | NLP corpus | `nlp_posts.text_translated_en` | PASS | 742,942 non-null; **742,942 are byte-identical to `original_text`** (verified by SQL equality count) — an explicit no-op, not a silent MT | Low | None | LOW |
| B2 | `translator.ipynb` exists | Notebooks | `notebooks/translator.ipynb` | PASS | 17 cells, portable `Path("..")` bootstrap | Low | None | LOW |
| B3 | `translator.ipynb` inside `English_Translation/` | — | `English_Translation/` holds only `README.md` | FAIL | `Test-Path English_Translation\translator.ipynb` = False | **Medium** — grader looks in the guideline folder first | Copy the notebook into `English_Translation/` | **HIGH** |
| B4 | `translated_en_posts.csv` | Documented deviation | Report p24 | PARTIAL | Not dumped as a 742k-row CSV; columns live in SQLite. The deviation is stated in the report | Low–Medium | Keep the deviation, but leave a `README.md` in `English_Translation/` naming the SQLite table and column | MEDIUM |
| B5 | `translation_examples.csv` with 10 original/translated pairs | Outputs | `outputs/translation_examples.csv` | PASS | 12 data rows (≥10) | Low | None | LOW |
| B6 | Column order `original_text \| translated_text` | Outputs | same file | PARTIAL | Columns are `original_text`, `text_translated_en` — guideline name is `translated_text` | Low | Cosmetic; mention the column mapping in one sentence | LOW |
| B7 | 10 examples **printed in the report** | Report §4 | Report Table 2 | PARTIAL | Table 2 shows **6** of the 12 rows; guidelines ask for 10 | **Medium** — an explicitly counted deliverable | Extend Table 2 to all 10–12 rows | **HIGH** |
| B8 | Answer: bad translations? hashtags translated correctly? person names preserved? | Report §4 | Report p18–p19 | PARTIAL | The English-only decision is explained well, but the three named questions are never answered as questions | **Medium** — the guidelines phrase them as required answers | Add three short answer sentences (trivially answerable: no MT ran, so hashtags and names are untouched) | **HIGH** |
| B9 | Skip only justified; do not claim "all English"; `und/qme/qam/zxx` not treated as English | Report §4 | Report p19; `full_keyword_language_census.csv` | PASS | 20,302 script-confirmed non-English keyword posts and the entire non-English timeline excluded and disclosed; report says explicitly this is "an English-only analysis decision, not a claim that the raw corpus is entirely English" | Low | None — this directly answers the US-Elections criticism | LOW |
| B10 | Batch translation, save every 500 tweets | — | — | N/A | No translation was performed, so batching does not apply | None | None | — |
| B11 | Disclose language-classifier false positives | Report §4 | Report Table 2 row 1 | PARTIAL | The report's **first** translation example is Portuguese ("Indo dormir... E olha quem está bravo comigo pq ainda não fui dormir") retained with `translation_status = not_required_english`. The Latin-script keyword classifier admits false positives but the report never says so | **Medium–High** — this row invites "why is Portuguese in your English corpus?" | Add one sentence: the keyword classifier is Latin-script ratio based (not langdetect), so Latin-script non-English survives; give the residual rate | **HIGH** |

**B subtotal: 4 PASS, 5 PARTIAL, 1 FAIL, 1 N/A.**

### C. Preprocessing (guidelines stage 2.2)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| C1 | Remove URLs, @mentions, hashtags (keep token), emojis, punctuation, lowercase | Script + column | `src/language_detection_and_preprocessing.py`; `nlp_posts.clean_text` | PASS | 36 before/after rows in `outputs/preprocessing_examples.csv` show all operations | Low | None | LOW |
| C2 | Remove stopwords | same | same | PASS | NLTK stopword list | Low | None | LOW |
| C3 | Stemming or lemmatization | same | same | PASS | Porter stemmer (visible in topic words: `happi`, `pleas`, `beauti`) | Low | None | LOW |
| C4 | `clean_text` as a **saved** column (not notebook memory) | NLP corpus | `nlp_posts.clean_text` | PASS | 744,221 non-null — verified by SQL | Low | None — this is the exact failure that cost HCPs and Israel-Hamas points | LOW |
| C5 | Remove IFB / follow / followback / f4f **before topic modeling** | NLP corpus | `nlp_posts.topic_text` | PASS | `bertopic_experiments.csv` `ifb_topword_hits = 0` across all 15 configs; report p23 explains why `clean_text` keeps the tokens for sentiment and `topic_text` drops them | Low | None — the single most important IFB-column fix | LOW |
| C6 | UTF-8, no gibberish | All CSVs | 38 CSVs scanned | PASS | All decode as UTF-8; 25 carry a BOM so Excel opens them correctly | Low | None | LOW |
| C7 | `posts_cleaned.csv` | Documented deviation | Report p24 | PARTIAL | Not dumped; columns in SQLite; example file provided | Low–Medium | Leave a `README.md` in `Data_Preprocessing/` naming table + column | MEDIUM |
| C8 | `text_preprocessing.ipynb` | — | Does not exist anywhere | FAIL | No such notebook in `notebooks/` or `Data_Preprocessing/` | **Medium** — a named required deliverable with no substitute notebook | Create a thin notebook that loads `preprocessing_examples.csv` and prints before/after | **HIGH** |
| C9 | Before/after examples shown in the report | Report §5 | Report p23 | PARTIAL | Rules are described in prose; **no before/after table or example appears in the Word report** | **Medium** | Add a 5-row before/after table from `preprocessing_examples.csv` | **HIGH** |

**C subtotal: 6 PASS, 2 PARTIAL, 1 FAIL.**

### D. Sentiment analysis (guidelines stage 2.3)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| D1 | `pysentimiento` three-class sentiment | Script | `src/sentiment_analysis.py`; report p26 | PASS | `finiteautomata/bertweet-base-sentiment-analysis` named in report and deck notes | Low | None | LOW |
| D2 | `sentiment_label`, `sentiment_positive`, `sentiment_negative` **plus neutral** | NLP corpus | `post_sentiment` table | PASS | All four columns exist; `sentiment_neutral` present — this is the column Turkey and HCPs were penalised for omitting | Low | None | LOW |
| D3 | `Posts_sentiment.csv` | Outputs | `outputs/Posts_sentiment.csv` | PASS | 742,942 data rows, 15 columns, UTF-8 BOM | Low | None | LOW |
| D4 | Percentages **and** absolute counts for all three classes | Report §6 | Report Table 3 | PASS | 134,936 (18.16%) / 526,377 (70.85%) / 81,629 (10.99%); exact match to `post_sentiment` GROUP BY | Low | None | LOW |
| D5 | Mean sentiment per user summary | Outputs only | `outputs/user_sentiment_summary.csv` | PARTIAL | File exists with 35,250 rows and per-user pct columns, but **neither the report nor the deck presents it** | **Medium** — explicitly listed in the guidelines | Add a 5-row sample or a distribution sentence to report §6 | MEDIUM |
| D6 | Pie of three classes, green / yellow / red | Outputs + report | `outputs/sentiment_distribution.png`; report p29 | PASS | Three pies (keyword census / timeline sample / mixed), correct colours | Low | None | LOW |
| D7 | Monthly time series with **three separate** series | Outputs + report | `outputs/sentiment_over_time_monthly.png`; report p31 | PASS | Visually verified: three stacked panels, title "Separate positive / neutral / negative time series (no combined sentiment curve)", each panel labeled "not mixed with other classes" | Low | None — flagship fix | LOW |
| D8 | Both figures embedded in the report | Report §6 | p29, p31 | PASS | Two inline shapes with captions | Low | None | LOW |
| D9 | No combined "average sentiment" number anywhere | Report §6 | Report p26 | PASS | Report states "There is no combined 'average sentiment' number"; no such figure or column exists | Low | None | LOW |

**D subtotal: 8 PASS, 1 PARTIAL.**

### E. Emotion analysis (guidelines stage 2.4)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| E1 | `create_analyzer(task="emotion", lang="en")` | Script | `src/emotion_analysis.py`; report p34 | PASS | `finiteautomata/bertweet-base-emotion-analysis` | Low | None | LOW |
| E2 | `emotion_label` + all seven probability columns | NLP corpus | `post_emotion` table | PASS | `emotion_joy, anger, sadness, fear, surprise, disgust, others` all present — verified via `PRAGMA table_info` | Low | None — Ukraine lost points for keeping only two | LOW |
| E3 | `Posts_emotions.csv` | Outputs | `outputs/Posts_emotions.csv` | PASS | 742,942 rows, 23 columns | Low | None | LOW |
| E4 | Cumulative scores by week, 2-week, month, 3-month, 6-month, year — **saved numerically** | Outputs | `emotion_over_time_{weekly,biweekly,monthly,quarterly,halfyearly,yearly}.csv` | PASS | 1,778 / 905 / 427 / 151 / 77 / 39 data rows; 33 columns each | Low | None — Turkey lost points for saving only pictures | LOW |
| E5 | A PNG at each of the six resolutions | Outputs | `outputs/emotion_plots/` | PASS | Six time PNGs + distribution + crosstab | Low | None | LOW |
| E6 | Dashed labeled vertical event lines on **every** emotion aggregation | Outputs | `outputs/event_plots/` | PASS | 18 PNGs = 6 resolutions × (combined, keyword, timeline); dashed lines with E01–E04 labels visually confirmed | Low | None — this is the repeated cross-project complaint | LOW |
| E7 | Answer "do you see a relation between sentiment and emotion?" | Report §7 | Report p40; `emotion_sentiment_crosstab.csv` (84 rows) + PNG | PASS | Crosstab figure embedded; neutral remains visible | Low | None | LOW |
| E8 | Emotion figures readable | Outputs | `event_plots/*.png` | PARTIAL | `others` is 87.83% of the file, so the six graded series are compressed into a ~0–10% band and the fear peaks that justify E01/E03 are not visually discernible. Event-line labels overlap where E03 and E04 are close | **Medium** — the instructor's stated purpose of event lines is that the reader can *see* the peak | Add a caption sentence warning about axis compression; optionally regenerate one companion figure with `others` excluded (see fixes doc) | MEDIUM |

**E subtotal: 7 PASS, 1 PARTIAL.**

### F. Event detection (guidelines stage 2.5)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| F1 | Find peaks/drops on the emotion graphs of **this** community | Script | `src/event_detection.py`; `detected_events.docx` p3–p28 | PASS | 7,392 candidates in `event_detection_candidates.csv` → 68 statistical → 64 rejected → 4 selected. Full threshold list published (`z_weekly=2.75`, `z_monthly=2.25`, `min_unique_authors=5`, `max_share_from_one_author=0.45`, `others_not_used_as_signal=True`, …) | Low | None | LOW |
| F2 | Code that takes posts + emotion scores + a date range and returns the top-20 tweets for an emotion | Script | `src/event_detection.py` | PASS | Retrieval + evidence gate implemented | Low | None | LOW |
| F3 | Read the tweets manually and judge whether they really express the emotion | DOCX | `detected_events.docx` per-event sections | PASS | Each quoted tweet carries its emotion probability (e.g. `fear p=0.99`) so the reader can check | Low | None | LOW |
| F4 | Report N posts in the window | CSV + report + docx | `detected_events.csv` `n_posts_window`; report Table 5; docx p31 | PASS | E01 3,720 / E02 597 / E03 3,553 / E04 2,075 — this is exactly what Lebanon was told was missing | Low | None | LOW |
| F5 | 5–20 example tweets per event | Outputs + report + docx | `event_tweet_evidence.csv` | PASS | 31 total: E01=6, E02=10, E03=5, E04=10 — all ≥5, verified by GROUP BY | Low | None | LOW |
| F6 | Explain **why** each event was selected | CSV + docx | `detected_events.csv` `why_selected`; docx per event | PASS | Each string gives share, baseline, z, emotion count, window N, local-peak statement, theme hits and theme fraction | Low | None — answers the Iran comment "למה בחרת דווקא בהם?" | LOW |
| F7 | `detected_events.docx` with figures and tweet proof | Root | `detected_events.docx` | PASS | 9 embedded PNGs, 120 paragraphs, threshold list, per-event tweet evidence with tweet IDs and usernames, external source URLs | Low | None | LOW |
| F8 | Dashed vertical lines with the event name on the emotion graphs | Outputs | `event_plots/` | PASS | Confirmed visually | Low | None | LOW |
| F9 | **E03 has exactly 5 evidence tweets and the keyword tweet is marked contextual, not part of the timeline z-score** | CSV + report | `event_tweet_evidence.csv`; report p44 | PASS | 4 rows `source=timeline` + 1 row `source=keyword_tweets` whose `engagement_note` reads "keyword census, same calendar week as E03". Report p44: "it is not one of the 15 timeline fear posts and was not used in the z-score" | Low | None — the required disclosure is exact | LOW |
| F10 | No unsupported causal claims | Everywhere | `event_external_sources.csv` `causation_claimed` | PASS | All four rows = `no`. Report p101, docx p2, deck slide 7 and slide 13 all deny causation | Low | None | LOW |
| F11 | Optionally use `archive.twitter` / trending data | External sources | `event_external_sources.csv` | PARTIAL | Wikipedia articles used instead of the half-hourly trending archive. The guidelines phrase this as optional ("תוכלו להעזר") | Low | Optional; state that the trending archive was not reachable/used | LOW |
| F12 | Enough events for the corpus period | Report §8 | 4 events over 2007-05 → 2023-11 | PARTIAL | The instructor told Lebanon that two events was "די חלש" and told Iran "נשמע מעט מדיי אירועים לתקופה". Four events across 16 years is thin, and two of the four are the same phenomenon (Thanksgiving 2021 and 2022) | **Medium–High** — a repeated, explicit criticism | Do **not** invent events. Instead state in one paragraph why the count is low: `others` = 87.8%, fear = 0.21%, and the evidence gate rejected 64 of 68 statistical candidates. Optionally lower the theme gate and document any additional evidenced events | **HIGH** |
| F13 | Evidence depth per event | CSV | `event_tweet_evidence.csv` E03 rows | PARTIAL | Two of E03's five rows are the same retweet text (`RT @oioiisogolden`) with different tweet IDs, and one is the contextual keyword tweet — effectively 3 distinct timeline texts. This is disclosed in report p44, so it is honest but thin | Medium | Keep the disclosure. If any further distinct fear tweets exist in that window, add them | MEDIUM |

**F subtotal: 10 PASS, 3 PARTIAL.**

### G. Topic modeling — BERTopic (guidelines stage 3)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| G1 | BERTopic on cleaned English text with IFB tokens removed | Script | `src/topic_modeling.py`; report p54 | PASS | Reads `topic_text`; `ifb_topword_hits = 0` in all 15 configs | Low | None | LOW |
| G2 | 10% tune sample, documented | Report §9 | Report p54 | PASS | 64,000-post stratified sample (source × year), seed 2026 — 8.6% of 742,942, documented | Low | None | LOW |
| G3 | Several `min_topic_size` × `n_neighbors` runs | Outputs | `outputs/bertopic_experiments.csv` | PASS | 15 configurations: `min_topic_size` ∈ {40,50,80,150,200,300}, `n_neighbors` ∈ {10,15,30}, plus n_components, n-gram, embedding-model and reduce_outliers variants | Low | None | LOW |
| G4 | Topic count in the 5–70 band | Outputs | `topic_distribution.csv` | PASS | Target 24, final 18 named topics — inside the band | Low | None | LOW |
| G5 | Use **Coherence**, not bare `u_mass` without rationale | Outputs | `coherence_scores.csv` `coherence_cv` | PASS | `c_v` used throughout — the exact criticism made of the US-Elections project | Low | None | LOW |
| G6 | Plot with configuration/topic count on X and Coherence on Y | Outputs + report | `outputs/coherence_plot.png`; report p57 | PASS | Bar + line chart of `c_v` per configuration; the selected C13 bar is green and the title says "not max-score-only" | Low | None | LOW |
| G7 | Save **each** model with `pickle` | Outputs | `outputs/topic_model.pkl` | PARTIAL | Only the final model is pickled (480 MB). Guidelines say "לכל מודל שהרצתם, שמרו את המודל" | Medium | Explain in one sentence that 15 × 480 MB was not retained and that `bertopic_experiments.csv` + cached embeddings make each run reproducible | MEDIUM |
| G8 | Export the experiments table to a file | Outputs | `bertopic_experiments.csv` (26 cols), `coherence_scores.csv` (10 cols) | PASS | Both exist; Ukraine and Turkey lost points for leaving the DataFrame in the notebook | Low | None | LOW |
| G9 | Experiments table schema: one row per (config, `Topic_num`) with per-topic coherence | Outputs | `bertopic_experiments.csv` | PARTIAL | `Topic_num` is **equal to** `n_topics` on every row — the file holds 15 aggregate rows, not per-topic coherence rows. The guidelines' example table and the Israel-Hamas comment ("חישבתן קוהרנס לכל טופיק, למה לא להציג את הטבלה כנדרש?") both ask for per-topic rows | **Medium** | State the deviation explicitly, or export per-topic `c_v` for the selected model only | MEDIUM |
| G10 | **Show the experiments table inside the report** | — | Not in `final_project_report.docx` | FAIL | The report has the coherence figure but no experiments table. Three separate workbook columns complain about exactly this ("היכן קובץ הניסויים?", "יש לך תוצאות? שימי בדוח") | **High** — cheapest high-value fix in the project | Paste the 15-row config table (name, min_topic_size, n_neighbors, n_topics, c_v, outlier %, selected/reject_reason) into report §9 | **HIGH** |
| G11 | Report outlier %; reduce if >10% | Report §9 | Report p56 | PASS | 171,543 / 742,942 = 23.09% disclosed; `reduce_outliers` used, plus 294,595 transform-outliers reassigned at cosine ≥ 0.28 | Low | None — Lebanon was *praised* for disclosing 19% | LOW |
| G12 | `final_topics.csv` with `tweet_id, created_at, text_translated_en, topic_id, topic_label, probability` | Outputs | `outputs/final_topics.csv` | PARTIAL | The file is **topic-level** (19 rows: topic_id, topic_name, topic_words, topic_size, …), not per-tweet. Per-tweet assignments live in `post_topic` (742,942 rows) | **Medium–High** — a named file with a named per-tweet schema | Export a per-tweet CSV (`tweet_id, created_at, topic_id, topic_name, topic_probability`) or state the deviation and point at `post_topic` | **HIGH** |
| G13 | Representative documents per topic | Outputs | `topic_representative_tweets.csv` | PASS | 152 rows with tweet IDs, usernames and original text | Low | None | LOW |
| G14 | Representative tweets **in the report** | Report §9 | Report p62 | PARTIAL | p62 *describes* what supports topics 0, 4 and 6 but quotes no tweet | Medium | Quote 1–2 representative tweets for the top 3 topics | MEDIUM |
| G15 | Meaningful topic names, not "SAY / YES" | Outputs | `topic_distribution.csv` | PASS | "Twitter chatter, retweets, and livestreams", "Faith and prayer", "Sports (NBA / NFL)", "Crypto / NFTs", "K-pop (BTS / Jimin)" — real labels, and mixed clusters are honestly named as mixed | Low | None | LOW |
| G16 | Table of strongest words **and** post count per topic | Outputs | `final_topics.csv` `topic_words` + `topic_size` | PARTIAL | The data exists but the report's Table 7 shows only ID / name / N / % for the top 6 — **no top-words column and only 6 of 19 rows** | **Medium** | Extend Table 7 to all 19 rows and add a `topic_words` column | **HIGH** |
| G17 | Topic volume over time, ideally with event lines | Outputs + report | `topic_over_time_monthly.png` + CSV (3,845 rows); report p59 | PASS | Dashed E01–E04 lines; keyword and timeline kept separate | Low | None | LOW |
| G18 | Topic count stated consistently across all deliverables | Deck vs data | PPTX slide 8 | **FAIL** | Slide 8 says "**24 named topics**". The shipped assignment has **18** named topics (ids 0,1,2,4,6,7,8,9,10,11,12,13,14,15,16,17,19,21) plus −1; the 6 follow-spam clusters 3,5,18,20,22,23 were merged into −1. `post_topic` confirms 19 distinct ids, 18 ≥ 0. The report never states 18 either | **High** — the instructor asks the topic count in Q&A ("לא הצלחתי להבין כמה נושאים נמצאו") | Change slide 8 to "18 named topics (nr_topics=24 minus 6 merged follow-spam clusters)" and add the same sentence to report §9 | **HIGH** |

**G subtotal: 10 PASS, 6 PARTIAL, 2 FAIL.**

### H. Sentiment per topic (guidelines stage 3.2)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| H1 | Join topics with sentiment and aggregate by `topic_id` | Outputs | `topic_sentiment_distribution.csv` | PASS | 19 rows; positive + neutral + negative sum to `n_raw`; all rows sum to 742,942 (verified) | Low | None | LOW |
| H2 | Columns `topic, positive, neutral, negative` (counts) | Outputs | same file | PASS | Exact guideline column names present, plus `topic_id`, `topic_name`, percentages | Low | None | LOW |
| H3 | Top-6 topics: word cloud in the centre, three-colour sentiment ring outside, slice ∝ counts | Outputs | `outputs/topic_sentiment_visualization.png` | PASS | Visually verified — six panels, centred word clouds, green/yellow/red rings, per-panel n and percentages, shared legend. This is precisely the figure Ukraine, Israel and Iran were told was missing | Low | None — a standout deliverable | LOW |
| H4 | `topic_sentiment_visualization.png` | Outputs | same | PASS | 2488×1753 px | Low | None | LOW |
| H5 | Figure in the report | Report §9 | Report p63 | PASS | Embedded with a caption naming the colour contract | Low | None | LOW |
| H6 | `topic_sentiment_analysis.ipynb` | — | Does not exist | FAIL | Not in `notebooks/` or `Topic_Sentiment/`; `Topic_Sentiment/` holds only a README | **Medium** — a named required deliverable | Create a thin notebook that loads `topic_sentiment_distribution.csv` and displays the PNG | **HIGH** |
| H7 | Topic × sentiment **counts table** in the report | — | Not in the report | PARTIAL | Only the ring figure is embedded; the guidelines show an explicit `topic / positive / neutral / negative` table | Medium | Paste the 19-row table (or top 6 + −1) into report §9 | **HIGH** |
| H8 | Check whether negative topics relate to the detected events | Report §9 | — | PARTIAL | Not examined. The data supports it: topic 15 "Dogs and city chatter" and topic 14 "Nigeria talk / Pokémon GO" are the most negative non-outlier topics, and none coincide with E01–E04 | Low–Medium | Add two sentences (a negative finding is a valid answer) | MEDIUM |

**H subtotal: 5 PASS, 2 PARTIAL, 1 FAIL.**

### I. NER and entity sentiment (guidelines stage 4)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| I1 | Run an NER model for PERSON / LOCATION / ORGANIZATION / COUNTRY / EVENT | Script | `src/ner_entity_analysis.py`; report p66 | PASS | spaCy `en_core_web_lg` 3.8.0 on `original_text` (never on stemmed text); `normalized_category` covers person, organization, location, country, event, norp, product, facility | Low | Guidelines suggested HuggingFace/BERTweet; the report justifies spaCy. Fine | LOW |
| I2 | `entities_extracted.csv`, one row per entity per tweet | Outputs | `outputs/entities_extracted.csv` | PASS | 777,249 data rows; matches `entity_mention` exactly | Low | None | LOW |
| I3 | Guideline column names `entity`, `entity_type` | Outputs | same file | PARTIAL | Columns are `entity_text`, `entity_label`, `normalized_category`; `entities_cleaned.csv` does provide `entity` and `entity_type` | Low | Note the column mapping in the README | LOW |
| I4 | Attach `sentiment_label` to each mention | Outputs | same file | PASS | `sentiment_label` + three probabilities per mention | Low | None | LOW |
| I5 | Aggregate by entity name | Outputs | `entities_cleaned.csv`, `entity_sentiment_distribution.csv` | PASS | 256,491 rows with pos/neu/neg counts and percentages | Low | None | LOW |
| I6 | **Drop entities shorter than 3 characters** | — | Not implemented as a filter | **FAIL** | `entity_mention` retains **19,049 kept mentions** with `length(canonical_entity) < 3`; only `one_character` (24,239) was dropped. `entities_cleaned.csv` contains **1,352** such rows — `Un`, `un`, `IG`, `GM`, `EU`, `TL`, `CW`, `DC`, `LA`, `QB`, `bc`, `AI`, `tf`, `xx` … And `CW` and `VN` are **visible nodes in the Top-30 network figure** | **High** — this is the same class of defect as the `&` complaint that helped cost IFB its 70 | Filter `len(entity) < 3` in the aggregation and the network, or at minimum disclose the residue and remove `CW`/`VN` from the drawn graph | **HIGH** |
| I7 | Drop entities that appear only once | Flag only | `entities_cleaned.csv` `singleton_flag` | PARTIAL | 211,325 of 256,491 rows are flagged singletons but are **retained** in the file. Charts and the network apply frequency floors (min 50 / min 25 / min 20 posts), so no graded figure is affected | Medium | Either ship a filtered companion table or state clearly that `singleton_flag` marks rows the guidelines would drop | MEDIUM |
| I8 | Strip `@` and `#` from inside entities | Outputs | `drop_reason` | PASS | `username_like` 45,141 and `url_like` 25,391 dropped | Low | None | LOW |
| I9 | Merge identical variants (USA / U.S.) | Outputs | `entity_alias_mapping.csv` | PARTIAL | A real 19,947-row alias table exists (US/USA/America → United States; Trump → Donald Trump; UK/Britain/GB → United Kingdom), and ambiguous strings (Georgia, Jordan, Chad, Mali) are deliberately excluded from the country chart. **But** `Un` and `un` are separate rows, `U.S` survives as a top-10 *location* alongside `United States` as a top-10 *country*, and six names (`Chelsea`, `Fauci`, `Kurang`, `Pokemon`, `Fox`, `Arsenal`) exist as multiple graph nodes under different categories | **Medium–High** — "תאחדו את הישות" is a repeated instructor demand | Disclose the category-split duplication; fold `U.S` into `United States`; merge case variants | **HIGH** |
| I10 | `entities_cleaned.csv` | Outputs | present | PASS | 256,491 rows, 30 columns | Low | None | LOW |
| I11 | Separate person and country/location tables | Outputs | `entity_sentiment_by_source.csv` + category column | PASS | `normalized_category` splits person (107,478), organization (110,078), location (16,281), country (76), norp, event, product, facility | Low | None | LOW |
| I12 | Top-10 PERSON stacked bar, green / yellow / red | Outputs + report | `person_entities_sentiment.png`; report p68 | PASS | Visually verified: Donald Trump, Joe Biden, Jungkook, Jesus, Vladimir Putin, Elon Musk, Jimin, Messi, Barack Obama, Peter Obi. Junk names (`Drop`, an Italian marketing phrase) are excluded by a min-50-posts floor plus a denylist | Low | None | LOW |
| I13 | Top-10 COUNTRY/LOCATION stacked bar, same colours | Outputs + report | `country_entities_sentiment.png`; report p70 | PASS | United States, United Kingdom, India, Ukraine, Russia, Israel, Nigeria, China, Canada, Australia | Low | None | LOW |
| I14 | Not all-yellow (the IFB bug) | Outputs | both PNGs | PASS | Every bar shows three coloured segments with a legend; Israel −50% and Ukraine −27% are clearly red-heavy | Low | None | LOW |
| I15 | No `&` entity | Outputs + DB | `entities_cleaned.csv`, `entity_mention` | PASS | 0 in both — independently verified. `junk_amp_or_symbol` = 15,099 dropped | Low | None | LOW |
| I16 | Interpret the entities: who are they, is the result plausible for an IFB community, discuss surprises | Report §10 | Report p66–p71 | PARTIAL | §10 covers the model, the drop counts and the alias policy, but barely interprets. There is no discussion of *why* two K-pop idols and Jesus outrank Elon Musk in a follow-farm corpus, or of Israel at −50% vs Jungkook at −1%. This is the single most repeated NER complaint in the workbook ("מי הם אותם ישויות? האם הגיוני?", asked of Ukraine, Turkey, Iran and Israel-Hamas) | **High** — cheap to fix, repeatedly graded | Add a 6–10 sentence interpretation paragraph to report §10 | **HIGH** |
| I17 | State whether bars are sorted by frequency or polarity | Outputs | PNG titles | PASS | Titles state the frequency floor; bars are ordered by unique posts, annotated with n and percentages | Low | None | LOW |
| I18 | **Sentiment toward entities over time** | — | Not produced | **FAIL** | No `entity_sentiment_over_time` CSV or PNG exists; no report section. `entities_cleaned.csv` has only `date_min`/`date_max`. This is an explicit bullet in the stage-4 goals ("כיצד הסנטימנט כלפי ישות מסוימת משתנה לאורך זמן") | **Medium** — a listed analysis with no deliverable | Produce one small figure for 3–5 top entities from `entity_mention` (no model rerun needed), or state the omission in Limitations | **HIGH** |
| I19 | `entity_extraction.ipynb` | Notebooks | `notebooks/ner_entity_analysis.ipynb` | PARTIAL | Equivalent notebook exists under a different name and is not in `NER_Analysis/` | Medium | Copy into `NER_Analysis/`, ideally aliased to the guideline name | **HIGH** |

**I subtotal: 12 PASS, 5 PARTIAL, 2 FAIL.**

### J. Entity co-occurrence network (guidelines stage 4.2 / "stage 3" in the PDF)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| J1 | Build all entity pairs per tweet | Outputs | `outputs/entity_pairs.csv` | PASS | 83,438 pair rows from 44,352 usable posts; full funnel published in `entity_network_rejections.csv` (posts scanned 319,710 → single-entity 131,239 → no-entity 144,100 → too-many-entities 19) | Low | None | LOW |
| J2 | Edge weight = number of co-occurring tweets | Outputs | `entity_network_edges.csv` `edge_weight` | PASS | Integer, min 5, max 509. Ukraine explicitly lost points for omitting this | Low | None | LOW |
| J3 | Build the graph with `networkx` | Script | `src/entity_network_analysis.py` | PASS | Undirected graph; Louvain communities with seed 2026 | Low | None | LOW |
| J4 | At least three centralities | Outputs | `entity_network_metrics.csv` | PASS | Six: degree, weighted degree, betweenness, closeness, PageRank, eigenvector | Low | None | LOW |
| J5 | Node size ∝ centrality, edge width ∝ weight | Outputs | `entity_network_graph.png` | PASS | Visually verified; legend states "edge width = co-occurring posts"; caption states "Node size = weighted degree" | Low | None | LOW |
| J6 | Filter to Top-30 or min frequency 20 | Outputs + report | report p73, p75 | PASS | Both applied: entities need ≥20 unique posts, edges ≥5, and the figure draws the top 30 of the largest component | Low | None | LOW |
| J7 | Four required files: `entity_pairs.csv`, `entity_network_edges.csv`, `entity_network_metrics.csv`, `entity_network_graph.png` | Outputs | all four present | PASS | Plus `entity_network_nodes.csv`, `_summary.csv`, `_rejections.csv` and three sub-graph PNGs | Low | None | LOW |
| J8 | No junk tokens as nodes | Outputs | `entity_network_graph.png` | **FAIL** | The Top-30 figure contains `CW` and `VN` — two-letter organisation tokens. This is the direct descendant of the `&` complaint | **High** | Apply a `len ≥ 3` node filter, or remove those two nodes from the drawn figure | **HIGH** |
| J9 | Node and edge counts consistent across every shipped file | Outputs | three files disagree | **FAIL** | `entity_network_summary.csv` says 1,126 nodes / **2,665** edges (and `sum(degree)/2 = 2,665` confirms the graph). `entity_network_edges.csv` has **2,694 data rows** — 29 name-pairs duplicated across category combinations (e.g. `Jungkook–Spotify` appears as person–organization w=62 **and** person–location w=26). `entity_network_rejections.csv` states `final_edges = 2694`. `entity_network_nodes.csv` has 1,126 rows but only **1,114 distinct names** (6 names appear 3× under different categories). A grader loading the edge list with `nx.from_pandas_edgelist(df,'entity_a','entity_b')` gets 1,114 nodes and 2,665 edges — not the reported 1,126 | **High** — two shipped CSVs contradict each other on a headline number | Add one sentence to report §11 and the `Entity_Network_Analysis/README.md`: the graph key is **(entity, category)**, hence 1,126 nodes and 2,665 unique pairs while the edge list carries 2,694 category-typed rows. Also reconcile `final_edges` in the rejections CSV | **HIGH** |
| J10 | Described as entity co-occurrence, never as a follower or social graph | Everywhere | figure title, caption, report p72–p74, deck slide 10, README, every CSV `note` column | PASS | Figure title is literally "Entity Co-occurrence Network"; caption: "Not a follower / user-user network. IFB.db has no follow, reply, or retweet-cascade edges." Deck slide title: "Entity co-occurrence network — not a social graph" | Low | None — exemplary | LOW |
| J11 | Discuss which entities are central and why | Report §11 | Report p75 | PASS | United States, Donald Trump, Joe Biden, Twitter, Ukraine, Russia; density 0.004208; 67 components; largest component 974 | Low | Could go deeper, but the requirement is met | LOW |
| J12 | Graph readable, not crowded | Outputs | `entity_network_graph.png` | PASS | 2226×1717 px, 30 labeled nodes, category colour legend, readable | Low | None | LOW |

**J subtotal: 10 PASS, 2 FAIL.**

### K. Bad actors — feature extraction (guidelines stage 5a)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| K1 | Metadata features: followers/following ratio, statuses_count, account age, posts/day, default profile image, bio length, verified | Outputs | `outputs/user_bot_features.csv` | PASS | `followers_following_ratio`, `tweet_count`, `account_age_days`, `posts_per_day_profile`, `default_profile_image`, `bio_length`, `verified` (301 verified users), plus IFB-specific `ifb_count` and `freelancer` | Low | None | LOW |
| K2 | Tweet features: retweet rate, posting hour, inter-tweet variance, mean hashtags, mean mentions, copy-paste rate | Outputs | same file | PASS | `rt_at_ratio`, `hour_concentration`, `dow_concentration`, `burstiness`, `hashtag_ratio`, `mention_ratio`, `duplicate_template_ratio`, `boilerplate_ratio`, `unique_text_ratio` — 45 modelled features total | Low | None | LOW |
| K3 | One row per unambiguous AUTHOR_ID | Outputs | same file | PASS | 38,576 rows, 38,576 distinct `author_id`, `profile_row_found = 1` for all | Low | None | LOW |
| K4 | Document the `rt_rate` definition (no native `is_retweet`) | Report §12 | Report p81 | PASS | Stated as text `RT @` only | Low | None | LOW |
| K5 | Feature distributions (bots vs humans after labeling) | Outputs + report | `bot_feature_distributions.png`; report p93 | PASS | Embedded; `bot_feature_importance.csv` ranks 45 features (top: duplicate_template_ratio 0.110, boilerplate_ratio 0.106, unique_text_ratio 0.096) | Low | None | LOW |
| K6 | Feature definitions and missing-field caveats in the report | Report §12 | Report p81 | PASS | Names the source of every block and states that `timeline_weighted_post_estimate` is not a model feature | Low | None | LOW |

**K subtotal: 6 PASS.**

### L. Manual labeling of 100 users (guidelines stage 5b)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| L1 | 100 users from the filtered target population | Outputs | `labeled_bots_and_not_bots.csv` | PASS | 100 rows, 100 distinct `author_id` | Low | None | LOW |
| L2 | Sample **at random** | Report §12 | Report p82 | **FAIL** | The 100 are **stratified on the rule-engine output** (35 low / 30 medium / 35 high). Only 99 users in the whole population are `high_risk`, so 35 of 99 high-risk users were selected — an enrichment factor of ~136×. The guidelines say "דגמו באקראי 100 משתמשים". More seriously, using the rule output to choose the users on which the rule is later validated makes `precision = 1.00` partly circular | **High** — it weakens the independence that the whole manual-review requirement exists to provide | Do **not** relabel. Disclose plainly in report §12 and Limitations: the sample is rule-stratified, not simple-random; therefore rule precision/recall on these 98 users is optimistic and is not an unbiased population estimate. Report the band sizes (21,516 / 1,988 / 99 / 14,973) so the reader can see the enrichment | **HIGH** |
| L3 | Enter the live X/Twitter profile and inspect it | Outputs | `live_profile_inspected` | PARTIAL | `no` for all 100; `review_source` = "IFB.db authors snapshot + NLP original posts (not live X)" on all 100. Honest, and unavoidable since the data ends 2023-12 | Medium (unavoidable) | Keep the disclosure; state the date gap as the reason | MEDIUM |
| L4 | Columns `is_bot`, `is_troll`, `is_malicious`, optional `comments` | Outputs | same file | PASS | All four present (`evidence` serves as comments); non-empty on all 100 rows | Low | None | LOW |
| L5 | Label only users you are completely certain about | Outputs | same file | PASS | `is_bot` is never 1 (39 × `0`, 61 × `unknown`); `reviewer_confidence` high 61 / medium 38 / low 1; 2 `insufficient_evidence` | Low | None — exactly the right posture | LOW |
| L6 | `labeled_bots_and_not_bots.csv` (guideline filename) | Outputs | present, plus identical `manual_bot_labels.csv` | PASS | Byte-identical duplicate, verified | Low | None | LOW |
| L7 | Accounts deleted since 2023 are `unknown`, not bots | Outputs + report | report p82 | PASS | "Deleted or empty accounts are insufficient_evidence, not malicious" | Low | None | LOW |
| L8 | Report the 1/0/unknown counts and the criteria | Report §12 + deck | report p82; slide 11 | PASS | 39 / 30 / 29 / 2 in both | Low | None | LOW |
| L9 | Quote profile notes or screenshots for a few examples in the report | — | Not in the report | PARTIAL | `manual_review_examples.csv` holds 16 quotable rows (e.g. "Official Evernote support replies with unique how-to text; brand helpdesk, not a follow farm") but the Word report quotes **none** | **Medium** — the guidelines ask for example evidence in the report | Paste 4–6 evidence quotes into report §12 | **HIGH** |
| L10 | Label columns internally consistent | Outputs | same file | PARTIAL | `is_malicious = 1` on **30** rows while `manual_label = likely_malicious` on **29** — one `suspicious` user also carries `is_malicious = 1`. The report quotes only the `manual_label` counts, so no published number is wrong | Low | One clarifying footnote, or leave as is | LOW |

**L subtotal: 6 PASS, 3 PARTIAL, 1 FAIL.**

### M. Rule flowchart and rule classifier (guidelines stage 5c)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| M1 | Build the flowchart **from** the manual review | Report + PPTX | report p84; `malicious_detection_flow.pptx` slide 2 | PARTIAL | The chart exists and its caption correctly says "Manual review is the label. The rule score is not ground truth", but nothing traces a rule back to a specific reviewed user | Medium | One sentence linking two or three thresholds to review observations | MEDIUM |
| M2 | `malicious_detection_flow.pptx` | Root | present | PASS | 3 slides: framing, chart, "why this is not a bot identity system" | Low | Also copy into `Bot_Detection/` | MEDIUM |
| M3 | The flowchart shows a decision **sequence** with branches | PPTX + PNG | slide 2; `outputs/malicious_detection_flow.png` | **FAIL** | Neither version is a flowchart. The PPTX has 8 rounded rectangles with **no connector arrows and no Yes/No branch labels**. The PNG is worse: boxes overlap horizontally (the `insufficient_evidence` box overlaps `IFB boilerplate / duplicate templates?`, and `low_risk` / `medium_risk` / `high_risk` overlap), there are no arrows, and there is no branch logic. This broken PNG is embedded in **both** the Word report (p83) and deck slide 11. Two separate workbook rows are graded on the flowchart | **High** — a graded artefact that currently does not communicate its content, in a phase where the instructor already wrote "לא הבנתי את שיקול הדעת" | Redraw with arrows and Yes/No labels, then re-embed in the report and the deck | **HIGH** |
| M4 | Translate the chart into readable, commented Python | Script | `src/bot_detection.py` | PASS | Named threshold constants with comments | Low | None | LOW |
| M5 | Apply the rules to the whole target population | Outputs | `rule_based_bot_scores.csv` | PASS | 38,576 rows, 60 columns; `rule_label` low 21,516 / insufficient_posts 14,973 / medium 1,988 / high 99 | Low | None | LOW |
| M6 | Sample **200** classified users and verify the labels manually; report rule accuracy on them | — | Does not exist | **FAIL (honestly disclosed)** | Disclosed in report p82, p105, p112, deck slide 11 and slide 13, and in `FINAL_MISSING_ITEMS.md`. Correctly **not fabricated** | **Medium** — a required deliverable is genuinely absent | Do **not** fabricate. Keep the explicit disclosure and state why (data ends 2023-12; live profiles unavailable) | MEDIUM |
| M7 | Report the rule classifier's accuracy | Report §12 | report Table 9; `rule_based_summary.csv` | PASS | Precision 1.00, recall 0.5932, F1 0.7447, balanced accuracy 0.7966, TN 39 / FP 0 / FN 24 / TP 35 — all verified | Low | Pair with the L2 circularity caveat | LOW |
| M8 | Flowchart **inside** the Word report, not only in the PPTX | Report §12 | report p83 | PASS | Embedded — answers the Iran comment "עשית flow chart, למה לא להכניס לדוח?" | Low | None (but see M3 about its quality) | LOW |
| M9 | Rationale for each rule threshold | PPTX footer only | slide 2 footer | PARTIAL | Thresholds are listed (`boilerplate≥0.45, duplicate≥0.55, unique≤0.40, RT@≥0.50, IFB_COUNT≥20, burst≥2.2 & hour conc.≥0.35`) but only in the PPTX footer, not in the Word report, and with no justification for the values | Medium | Move the threshold list into report §12 with one clause of rationale each | MEDIUM |

**M subtotal: 5 PASS, 2 PARTIAL, 2 FAIL.**

### N. ML classifiers (guidelines stage 5d)

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| N1 | Binary bot / non-bot task | Outputs | `bot_detection_experiments.csv` `target_column` | PASS | `risk_positive` on all 40 rows, honestly named as risk rather than bot | Low | None | LOW |
| N2 | Logistic Regression, Decision Tree, Random Forest, SVM, XGBoost | Outputs | same file | PASS | Exactly 8 rows each for all five algorithms | Low | None | LOW |
| N3 | K-Fold with K=5 | Outputs | same file | PASS | `kfold_k5_fold1..fold5` + `_pooled` + `_mean` per algorithm | Low | None | LOW |
| N4 | LOOCV | Outputs | same file | PASS | `loocv_pooled` for all five | Low | None | LOW |
| N5 | `bot_detection_experiments.csv` with `target_column, algorithm, feature_set, training_type, K, balanced, accuracy, precision, recall, F1, AUC` | Outputs | same file | PASS | All 11 guideline columns present, plus `n_train`, `n_train_pos`, `n_train_neg`, `balanced_accuracy`, `PR_AUC`, tn/fp/fn/tp, runtime, seed, note | Low | None | LOW |
| N6 | Apply the best model to the whole target population | Outputs | `unlabeled_dataset_results.csv` | PASS | 38,576 rows, model `Random Forest_full_labeled_fit` | Low | None | LOW |
| N7 | `bot_detection_predictions.csv` with `username, predicted_class, confidence_level, prob_0, prob_1` | Outputs | present | PASS | All five guideline columns present | Low | None | LOW |
| N8 | Predictions file row count explained | — | Not explained anywhere | PARTIAL | The file has **39,556** rows = 38,576 population predictions + 980 CV evaluation rows (5 algorithms × 196 fold predictions). `author_id` is unique across the 38,576 population rows but repeats for CV rows, and `predicted_class` is empty on 980 rows. No document mentions 39,556 | Medium | One sentence in report §12 or the `Bot_Detection/README.md` explaining the mixed content | MEDIUM |
| N9 | `unlabeled_dataset_results.csv` and `unlabled_dataset.csv` (guideline spellings) | Outputs | both present | PASS | 38,576 rows each; the guidelines' typo `unlabled` is reproduced deliberately | Low | None | LOW |
| N10 | Remove `confidence_level ≥ 0.8` bad actors and continue on the cleaned population | Outputs only | `unlabeled_dataset_results.csv` | PARTIAL | The data supports it — **893** users are `predicted_class = 1` with `confidence_level ≥ 0.8` (9,719 predicted class 1 overall) — but neither number appears in the report or the deck, and no cleaned-population artefact exists | **Medium–High** — an explicit numbered step | State 893 and 9,719 in report §12; describe the filter as a suggestion (which the report already frames correctly) | **HIGH** |
| N11 | **Summary table of users filtered by category (bot / troll / malicious)** | — | Does not exist | **FAIL** | Explicitly listed under "תוצרים נדרשים" in the guidelines. No such table in any CSV, the report, or the deck. Note that `is_troll` is `0`/`unknown` for all 100 reviewed users, so the troll row would legitimately be zero/not-modelled | **Medium–High** | Add a 3-row table: bot = not asserted (is_bot never 1), troll = not modelled (no positive labels), risk-positive ≥0.8 = 893 of 38,576 | **HIGH** |
| N12 | Report the number of training records per class | Report + deck | report p86, Table 10; deck slide 12 + notes | PASS | K=5 mean train 78 (47 pos / 31 neg per fold), LOOCV 97 (59 pos / 39 neg) — all verified against the experiments CSV. This is the instructor's most repeated ML demand | Low | None | LOW |
| N13 | Metric comparison table or chart | Outputs + report | `bot_model_comparison.png`, `bot_confusion_matrices.png`; report Table 10, p89, p91 | PASS | Table plus two figures; best K=5 pooled RF F1 0.8852 / bal. acc. 0.8422 / AUC 0.93 — verified | Low | None | LOW |

**N subtotal: 10 PASS, 2 PARTIAL, 1 FAIL.**

### O. Final Word report

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| O1 | A written report exists (IFB's cell was **empty**) | Root | `report/final_project_report.docx` | PASS | 14 chapters, 112 paragraphs, 10 tables, 17 embedded PNGs, 1 section, 0 page breaks, 0 empty pages | Low | None | LOW |
| O2 | Every graded figure embedded in the document | Report | 17 inline images | PASS | Verified by counting `<pic:pic` elements: sentiment pie, three-panel time series, emotion distribution, 6 emotion aggregations with event lines, coherence, topic-over-time, topic-sentiment rings, person/country entity bars, network graph, flow chart, model comparison, confusion matrices, feature distributions | Low | None | LOW |
| O3 | Do not write "see the outputs folder" | Report §1 | report p7 | PASS | The report states the opposite explicitly: "This report embeds the graded figures. It does not ask the reader to open an outputs folder in order to see the results." No such deferral appears anywhere in the 112 paragraphs | Low | None — directly answers a repeated criticism | LOW |
| O4 | Numbers in the report match the CSVs | Report + CSVs | all tables | PASS | Every canonical number re-derived from SQL/CSV and matched — see §4 below | Low | None | LOW |
| O5 | Explain decisions and limitations | Report §13 | report p105–p112 | PASS | 12 numbered limitations, including English-only, no follow graph, no 200-user validation, no live profiles, `others` dominance, topic outliers, `sample_weight` scope, no causal inference | Low | None | LOW |
| O6 | Explain **why** analytical choices were made, not just what | Report throughout | p18, p23, p26, p54, p66, p72, p81 | PASS | Each chapter opens with a rationale paragraph | Low | None | LOW |
| O7 | No broken figure references or missing images | Report | all 17 images | PASS | All resolve; no placeholder or "image not found" | Low | None | LOW |
| O8 | Report presents results rather than only describing method | Report | 10 tables | PARTIAL | Strong overall, but four things a grader will look for are described and not tabulated: the BERTopic experiments table (G10), topic top-words (G16), the topic × sentiment counts table (H7), and preprocessing before/after (C9) | **Medium** | Add those four tables | **HIGH** |

**O subtotal: 7 PASS, 1 PARTIAL.**

### P. Final presentation

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| P1 | A presentation exists (IFB's cell was **empty**) | Root | `presentation/final_project_presentation.pptx` | PASS | 14 slides, 11 media files, 13.33 × 7.50 in | Low | None | LOW |
| P2 | 15-minute plan | Speaker notes | slide 1 notes | PASS | Explicit 0:00 → 15:00 timing block | Low | None | LOW |
| P3 | Covers all phases | slides 2–13 | — | PASS | Data, translation/preprocessing, sentiment, emotion, events, topics, topic sentiment, entities, network, bots, ML, limitations | Low | None | LOW |
| P4 | Key figures embedded | 11 media files | — | PASS | All graded visuals present | Low | None | LOW |
| P5 | No overflow, off-slide, or empty slides | all 14 | — | PASS | Every shape geometrically checked against slide bounds — **zero** overflow or off-slide shapes; no empty slide | Low | None | LOW |
| P6 | Consistent headline numbers on every slide | footer | all 14 | PASS | "38,576 users · 742,942 scored posts · N/14" | Low | None | LOW |
| P7 | Limitations slide | slide 13 | — | PASS | Names the 200-user gap, no live profiles, English-only, no follow graph, no causal claims | Low | None | LOW |
| P8 | Bot results framed as risk, not identity | slides 11–12 | — | PASS | "behavioral risk classification, not verified bot identification" | Low | None | LOW |
| P9 | Network framed as co-occurrence | slide 10 | — | PASS | Title says "not a social graph" | Low | None | LOW |
| P10 | Topic count consistent with the data | slide 8 | — | **FAIL** | "24 named topics" vs 18 actual — see G18 | **High** | Fix the slide text | **HIGH** |
| P11 | Flowchart slide legible | slide 11 | — | **FAIL** | Embeds the broken `malicious_detection_flow.png` — see M3 | **High** | Re-embed after redrawing | **HIGH** |

**P subtotal: 9 PASS, 2 FAIL.**

### Q. Reproducibility, folder organization and code cleanliness

| # | Requirement | Where satisfied | Exact file / section | Status | Evidence | Risk | Recommended action | Priority |
|---|---|---|---|---|---|---|---|---|
| Q1 | Project root named after the population, in English | Workspace | `IFB-project/` | PASS | — | Low | None | LOW |
| Q2 | Folder `English_Translation/` with its deliverables | — | README only | FAIL | 0 of 3 guideline files present | **Medium** | Populate | **HIGH** |
| Q3 | `Data_Preprocessing/` | — | README only | FAIL | 0 of 2 | **Medium** | Populate | **HIGH** |
| Q4 | `Posts_Analysis/` with `sentiment_analysis.ipynb`, `Posts_sentiment.csv`, `emotion_analysis.ipynb`, `Posts_emotions.csv`, `events_analysis.ipynb`, `detected_events.docx` | — | **The folder does not exist at all** | FAIL | `Test-Path Posts_Analysis` = False | **Medium–High** | Create and populate | **HIGH** |
| Q5 | `Topic_Modeling/` | — | README only | FAIL | 0 of 2 | **Medium** | Populate | **HIGH** |
| Q6 | `Topic_Sentiment/` | — | README only | FAIL | 0 of 3 | **Medium** | Populate | **HIGH** |
| Q7 | `NER_Analysis/` | — | README only | FAIL | 0 of 4 | **Medium** | Populate | **HIGH** |
| Q8 | `Entity_Network_Analysis/` | — | README only | FAIL | 0 of 4 | **Medium** | Populate | **HIGH** |
| Q9 | `Bot_Detection/` | — | README only | FAIL | 0 of 5 | **Medium** | Populate | **HIGH** |
| Q10 | All guideline-named files present **somewhere** | `outputs/`, `notebooks/`, root | — | PASS | 31 of 33 exist somewhere; only `text_preprocessing.ipynb` and `topic_sentiment_analysis.ipynb` are genuinely missing (C8, H6) | — | See C8, H6 | **HIGH** |
| Q11 | Notebooks contain **executed** output | `notebooks/*.ipynb` | 8 notebooks | **FAIL** | Every code cell has `execution_count: null` and an empty `outputs` array in all 8 notebooks. A grader opening any notebook sees code and no results. "קוד נקי" and "בהירות ההצגה" are explicit grading criteria | **High** | Execute each notebook once (they read CSVs and PNGs, so this reruns no model) and save with outputs | **HIGH** |
| Q12 | Notebooks use portable relative paths | `notebooks/*.ipynb` | — | PASS | All 8 use a `Path.cwd()` / `Path("..")` bootstrap and resolve `outputs/` relatively | Low | None | LOW |
| Q13 | Scripts point at the correct databases | `src/*.py` | — | PASS | `analysis_corpus.db` for corpus work, `nlp_analysis_corpus.db` for NLP, `nlp_working_sample.db` for QA only | Low | None | LOW |
| Q14 | **`IFB.db` not modified** | Root | `IFB.db` | PASS | mtime 2026-09-11T12:34:15 — **before** the pipeline started (~13:11). `journal_mode = delete`, `freelist_count = 0`, no `-wal`/`-shm`/`-journal` sidecars, `PRAGMA quick_check = ok`, schema intact (`authors`, `tweets`, `timeline`). Every production path opens it `mode=ro` + `PRAGMA query_only = ON` | Low | None | LOW |
| Q15 | No giant 39M-row CSV required | Data folder | — | PASS | Largest CSV is `entities_extracted.csv` at 777,249 rows / 219 MB. The 38.97M posts stay in SQLite | Low | None | LOW |
| Q16 | Source DB paths portable or documented | `CORPUS_MANIFEST.md`, READMEs | — | PARTIAL | `src/` resolves paths relative to the repo root, but `Untitled0.ipynb` at the root is Colab scratch hard-coded to `/content/drive/MyDrive/IFB/IFB.db` and holds the **only write-capable** `IFB.db` connection in the workspace | Medium | Move it to `scratch/` or delete it before submission | MEDIUM |
| Q17 | Dependency manifest / run commands | — | No `requirements.txt` or `environment.yml` anywhere | **FAIL** | A grader cannot reconstruct the environment. Pinned versions are known and documented in prose (spaCy 3.8.0, `en_core_web_lg`, pysentimiento, BERTopic, sentence-transformers, XGBoost, networkx, python-docx, python-pptx) | **High** | Add `requirements.txt` and a `HOW_TO_RUN.md` with the ordered `python src/*.py` sequence | **HIGH** |
| Q18 | Internal audit documents accurate | Root | `FINAL_COMPLIANCE_AUDIT.md` | PARTIAL | **Stale**: line 26 says "29 evidence tweets" (canonical is **31**) and line 38 says `primary_author_ids.txt` "was not exported" when it exists with 38,576 lines. If the grader reads it, the project appears to contradict itself | Medium | Update or remove it from the submitted bundle | MEDIUM |
| Q19 | Saved models exported | `outputs/` | — | PASS | `topic_model.pkl` (480 MB), `bot_model_random_forest.pkl`, `bot_scaler.pkl`, `bot_feature_list.json` — Ukraine and Turkey lost points for not saving models | Low | None | LOW |
| Q20 | Global seed | all scripts | seed 2026 | PASS | Recorded in `bot_detection_experiments.csv`, `bertopic_experiments.csv` and the Louvain call | Low | None | LOW |

**Q subtotal: 8 PASS, 2 PARTIAL, 10 FAIL (8 of the 10 FAILs are the same single defect: the stage folders are stubs).**

---

### Requirement table totals

| Group | PASS | PARTIAL | FAIL | N/A | Rows |
|---|---|---|---|---|---|
| A. Dataset | 8 | 0 | 0 | 0 | 8 |
| B. Translation | 4 | 5 | 1 | 1 | 11 |
| C. Preprocessing | 6 | 2 | 1 | 0 | 9 |
| D. Sentiment | 8 | 1 | 0 | 0 | 9 |
| E. Emotion | 7 | 1 | 0 | 0 | 8 |
| F. Events | 10 | 3 | 0 | 0 | 13 |
| G. BERTopic | 10 | 6 | 2 | 0 | 18 |
| H. Topic sentiment | 5 | 2 | 1 | 0 | 8 |
| I. NER | 12 | 5 | 2 | 0 | 19 |
| J. Network | 10 | 0 | 2 | 0 | 12 |
| K. Bot features | 6 | 0 | 0 | 0 | 6 |
| L. Manual labeling | 6 | 3 | 1 | 0 | 10 |
| M. Rule flowchart | 5 | 2 | 2 | 0 | 9 |
| N. ML | 10 | 2 | 1 | 0 | 13 |
| O. Word report | 7 | 1 | 0 | 0 | 8 |
| P. Presentation | 9 | 0 | 2 | 0 | 11 |
| Q. Reproducibility | 8 | 2 | 10 | 0 | 20 |
| **TOTAL** | **131** | **35** | **25** | **1** | **192** |

Of the 25 FAILs, **8** are the single stage-folder-stub defect (Q2–Q9) and **1** is the honestly-disclosed, deliberately-not-fabricated 200-user validation set (M6). The remaining 16 are individually small and individually fixable **without rerunning a single model**.

---
## 3. Phase-by-phase audit

**Phase 1 — Dataset selection and coverage. Verdict: strong.** `IFB.db` is 11.89 GB with `authors`, `tweets` and `timeline`. The freeze into `data/analysis_corpus.db` produced 38,576 unambiguous users and 38,969,023 posts (1,129,607 keyword + 37,839,416 timeline), with 1,203 ambiguous `AUTHOR_ID` groups dropped and documented. The census/sample separation is designed correctly and, crucially, is carried through every downstream artefact: `sample_weight = 1` for keyword posts, Horvitz-Thompson weights across 174 strata (quarter × activity tertile) for the timeline sample, and weights used **only** for population estimates — never as model weights, never as a sentiment denominator. This directly answers row 2 and row 3 of the workbook, which were blank for IFB last time.

**Phase 2 — Translation. Verdict: acceptable, with one loose thread.** The decision not to translate is defensible and well argued: the corpus is overwhelmingly English, pysentimiento's BERTweet is English-trained, and MT on 742k short informal posts would add noise. `text_translated_en` exists and is byte-identical to `original_text` on all 742,942 rows, which is an honest no-op rather than a fake column. The loose thread is that the report's own first translation example is Portuguese, retained as `not_required_english`. The Latin-script ratio classifier that admits it is never described, so the reader is handed the counter-example without the explanation. One sentence fixes this. Separately, the report shows 6 examples where 10 are required, and the three guideline questions (bad translations? hashtags? names?) are never answered as questions even though all three answers are trivially "no MT ran".

**Phase 3 — Preprocessing. Verdict: strong in substance, thin in presentation.** The two-column design is the most important single decision in the project and it is correct: `clean_text` keeps IFB/follow tokens because they carry sentiment, and `topic_text` strips them because they destroyed the previous submission's topic model. `bertopic_experiments.csv` proves the strip worked with `ifb_topword_hits = 0` on all 15 runs. Both columns are **persisted in SQLite**, not left in notebook memory — the exact failure that cost other projects points. What is missing is presentational: no before/after table in the report and no `text_preprocessing.ipynb`.

**Phase 4 — Sentiment. Verdict: strong.** Three-class output with neutral retained, absolute counts and percentages for all three (134,936 / 526,377 / 81,629), three genuinely separate time series in a figure whose own title says "no combined sentiment curve", and a report sentence stating that no combined average exists. This phase fully closes "אין דבר כזה סנטימנט ביחד". The only gap is that `user_sentiment_summary.csv` (35,250 rows) is never surfaced in the report.

**Phase 5 — Emotion. Verdict: strong in data, weak in legibility.** All seven emotion probabilities are persisted, six temporal aggregations are exported as **both** CSV and PNG (Turkey lost points for pictures only), and dashed labeled event lines appear on all 18 event plots. The problem is purely visual: `others` is 87.83% of the corpus, so on a shared 0–100% axis the six graded emotions collapse into a thin band and the fear spikes that justify E01 and E03 are invisible. The instructor's stated reason for wanting event lines is that the reader can *see* the peak; here the reader cannot. A caption warning, or one companion figure with `others` excluded, would resolve it.

**Phase 6 — Event detection. Verdict: strong methodology, thin yield.** This phase is the most improved part of the project. The funnel is fully published: 7,392 candidate bins → 68 statistical candidates → 64 rejected with named reasons → 4 selected, 31 evidence tweets. Every event carries N-in-window, z-score, baseline share, a local-peak check, a theme fraction, real tweets with tweet IDs and per-tweet emotion probabilities, an external Wikipedia source, and an explicit `causation_claimed = no`. E03's fifth tweet is correctly marked as keyword-census contextual evidence outside the z-score, both in the CSV's `engagement_note` and in report p44. Nothing here looks like it came from a chatbot. The weakness is the yield: 4 events over 16 years, two of them the same Thanksgiving phenomenon in consecutive years, and E03's five tweets reduce to about three distinct texts. The instructor has criticised low event counts twice in this workbook. The right response is not to invent events but to explain the low count from the data — `others` at 87.8%, fear at 0.21%, and an evidence gate that rejected 64 of 68 candidates.

**Phase 7 — BERTopic. Verdict: strong pipeline, inconsistent reporting.** 15 configurations, `c_v` coherence (not bare `u_mass`), a selection that explicitly is not max-score-only, 23.09% outliers disclosed and then reduced, meaningful topic names, and IFB tokens verifiably absent from every top-word list. But the reporting has three defects that a grader will hit immediately: the experiments table exists as a CSV and is **not** in the Word report (three separate workbook columns complain about exactly this); the topic count is stated as 24 on deck slide 8 when the shipped assignment has 18 named topics plus an outlier bucket; and `final_topics.csv` is topic-level rather than the per-tweet schema the guidelines name. Also, `Topic_num` equals `n_topics` on every row of the experiments CSV, so it is an aggregate table, not the per-topic coherence table the guidelines illustrate.

**Phase 8 — Topic sentiment. Verdict: strong.** `topic_sentiment_distribution.csv` has the exact guideline columns and its 19 rows sum to 742,942. The visualization is the best single figure in the project: six panels, word cloud in the centre, three-colour sentiment ring outside, slice proportional to counts, per-panel n and percentages. Three other projects were penalised for not producing this. Missing: the counts table itself in the report, the notebook, and the "do negative topics relate to the events?" answer (which the data says is "no" — a perfectly acceptable answer).

**Phase 9 — NER. Verdict: acceptable, and the weakest of the mature phases.** The all-yellow bug is definitively fixed — both entity figures are genuine three-colour stacked bars with per-bar n. `&` is gone (0 occurrences), and a real 19,947-row alias table merges US/USA/America and Trump/Donald Trump while deliberately excluding ambiguous names like Georgia and Jordan. Three problems remain. First, the guidelines require dropping entities under 3 characters and this was never implemented: 19,049 kept mentions and 1,352 cleaned rows are 1–2 characters (`Un`, `IG`, `EU`, `CW`, `bc`, `xx`), and `CW` and `VN` are visible nodes in the graded network figure. That is the same class of defect as the `&` complaint. Second, 211,325 singletons are flagged but retained. Third — and most costly relative to effort — §10 barely interprets the entities. The workbook asks "מי הם אותם ישויות? האם הגיוני?" of four different projects. Nobody explains why two K-pop idols and Jesus outrank Elon Musk in a follow-farm corpus, or why Israel sits at −50% while Jungkook sits at −1%. Six to ten sentences would convert a PARTIAL into a PASS. Finally, entity sentiment over time is a listed goal with no deliverable at all.

**Phase 10 — Entity sentiment. Verdict: strong for the static view, absent for the temporal view.** See I12–I14 (PASS) and I18 (FAIL).

**Phase 11 — Entity co-occurrence network. Verdict: strong framing, inconsistent numbers.** The framing is exemplary and repeated in five independent places: figure title, figure caption, report §11, deck slide 10, folder README — always "co-occurrence", always "not a follower / user-user network", always with the reason (`IFB.db` has no follow, reply or retweet-cascade edges). Six centralities, Louvain communities with a fixed seed, edge weight = co-occurring tweet count, both the Top-30 and min-frequency-20 filters applied, and a full rejection funnel. Two defects: junk two-letter nodes in the drawn figure, and a genuine numeric contradiction between shipped files. `entity_network_summary.csv` reports 2,665 edges and `sum(degree)/2` confirms it, but `entity_network_edges.csv` has 2,694 rows and `entity_network_rejections.csv` says `final_edges = 2694`. The cause is that the graph key is **(entity, category)**, so `Jungkook–Spotify` appears twice under different category pairs; `entity_network_nodes.csv` likewise has 1,126 rows over only 1,114 distinct names. This is explainable in one sentence, but right now a grader who reloads the edge list gets different numbers from the ones the report claims.

**Phase 12 — Bot / malicious-user detection. Verdict: acceptable, with the project's two sharpest risks.** The feature work is genuinely good: 45 features spanning profile metadata and NLP behaviour, one row per unambiguous author for all 38,576 users, an importance ranking led by `duplicate_template_ratio`, `boilerplate_ratio` and `unique_text_ratio` — which is exactly what a follow-farm signal should look like. The ML block is complete and correctly reported: five algorithms × (K=5 stratified CV + LOOCV), all 11 guideline columns, and — critically — the training-set sizes stated in the report, the table and the deck (K=5 mean 78, LOOCV 97). That is the instructor's single most repeated ML demand. The manual review is honest in the right way: `is_bot` is never asserted as 1, deleted accounts are `insufficient_evidence` rather than bots, and every one of the 100 rows carries free-text evidence.

The two sharp risks are these. **First, the flowchart is not a flowchart.** Both the PPTX version and the PNG have no connector arrows and no Yes/No branch labels, and the PNG additionally has boxes that overlap each other. That broken PNG is embedded in the Word report and in the deck. Two workbook rows are graded on the flowchart, in a phase where the instructor has already written "לא הבנתי את שיקול הדעת". **Second, the 100 manual labels are stratified on the rule engine's own output** (35 low / 30 medium / 35 high), drawing 35 users from a high-risk band of only 99 — an enrichment of roughly 136×. The guidelines ask for a random sample. Because the rule output selected the users on which the rule is then scored, the reported precision of 1.00 is partly circular. The fix is disclosure, not relabeling.

Three smaller gaps: the required summary table of users filtered by category does not exist; the 893 users at `confidence_level ≥ 0.8` (of 9,719 predicted positive) are never stated anywhere; and `bot_detection_predictions.csv` has 39,556 rows — 38,576 population predictions plus 980 CV rows with a blank `predicted_class` — which no document explains.

**Phase 13 — Final Word report. Verdict: strong.** 14 chapters, 112 paragraphs, 10 tables, 17 embedded figures, no page breaks, no empty pages, no broken image references, every number matching its source CSV, and 12 numbered limitations. Paragraph 7 states outright that the report embeds its figures and does not ask the reader to open an outputs folder — the direct answer to a criticism made of several other projects. The gap is four tables that are described in prose but never tabulated (BERTopic experiments, topic top-words, topic × sentiment counts, preprocessing before/after) plus the entity interpretation paragraph.

**Phase 14 — Final presentation. Verdict: strong, with two specific errors.** 14 slides, 11 media files, a real 0:00–15:00 speaker-note plan, consistent footer numbers, correct framing of both the network and the bot results, and — verified geometrically against the 13.33 × 7.50 in slide — **zero** overflow or off-slide shapes and no empty slides. Two errors: slide 8's "24 named topics" and slide 11's broken flowchart image.

**Phase 15 — Reproducibility and folder organization. Verdict: weak. This is the project's worst phase and the cheapest to fix.** `IFB.db` is provably untouched and every production path opens it read-only with `PRAGMA query_only = ON`. Scripts target the right databases, notebooks use portable relative paths, models are pickled, and the seed is 2026 everywhere. But: the ten graded stage folders contain one-line READMEs and **not one** guideline-named file; `Posts_Analysis/` does not exist at all; all eight notebooks are saved unexecuted so a grader sees code with no output; there is no `requirements.txt` or `HOW_TO_RUN.md`; `Untitled0.ipynb` sits in the root as Colab scratch with a hard-coded `/content/drive/MyDrive/IFB/IFB.db` path and the only write-capable `IFB.db` connection in the workspace; and `FINAL_COMPLIANCE_AUDIT.md` is stale (it says 29 evidence tweets where the canonical figure is 31, and claims `primary_author_ids.txt` was not exported when it exists with 38,576 lines).

---

## 4. Cross-file consistency results

Every canonical number was re-derived from the primary source, not copied from the project's own reports.

| Canonical claim | Independently verified value | Source of verification | Result |
|---|---|---|---|
| 38,576 users | 38,576 | `SELECT count(*) FROM users` in `analysis_corpus.db`; `nlp_users`; `user_bot_features.csv`; `primary_author_ids.txt` line count | **MATCH** |
| 742,942 English-ready scored posts | 742,942 | `count(*) FROM post_sentiment`; `post_emotion`; `post_topic`; `Posts_sentiment.csv`; `Posts_emotions.csv` | **MATCH** |
| 35,250 scored users | 35,250 | `count(DISTINCT author_id)` over scored posts; `user_sentiment_summary.csv` rows | **MATCH** |
| 4 events | 4 | `detected_events.csv`; `detected_events.docx`; report Table 5; deck slide 7 | **MATCH** |
| 1,126 network nodes | 1,126 (over 1,114 distinct names) | `entity_network_nodes.csv`; `entity_network_summary.csv` | **MATCH**, with the (entity, category) caveat |
| 2,665 network edges | 2,665 unique unordered name pairs; `sum(degree) = 5,330` | `entity_network_summary.csv` + degree column arithmetic | **MATCH**, but `entity_network_edges.csv` has 2,694 rows and `entity_network_rejections.csv` says 2,694 — **internal contradiction, see J9** |
| 100 manual reviews | 100 rows, 100 distinct authors | `labeled_bots_and_not_bots.csv` and its identical twin `manual_bot_labels.csv` | **MATCH** |
| 98 usable ML labels | 98 | 100 minus 2 `insufficient_evidence`; confirmed by `n_train_pos + n_train_neg` in LOOCV | **MATCH** |
| K=5 mean train size 78 | 78 (47 pos / 31 neg) | `bot_detection_experiments.csv` `n_train` on `kfold_k5_mean` rows | **MATCH** |
| LOOCV train size 97 | 97 (59 pos / 38 neg) | same file, `loocv_pooled` rows | **MATCH** |
| Sentiment 134,936 / 526,377 / 81,629 | identical | `post_sentiment` GROUP BY vs report Table 3 vs `sentiment_distribution.csv` | **MATCH** (sums to 742,942) |
| 244,221 retained vs 244,217 scored keyword rows | 4-row gap, all four `tweet_id`s listed | report paragraph 13 | **MATCH and explained** |
| E03 evidence: 5 tweets, keyword tweet contextual | 4 `timeline` + 1 `keyword_tweets` marked "keyword census, same calendar week as E03"; report p44 says it "was not used in the z-score" | `event_tweet_evidence.csv`; report p44 | **MATCH — disclosure is exact** |
| 31 evidence tweets total | E01=6, E02=10, E03=5, E04=10 | `event_tweet_evidence.csv` GROUP BY | **MATCH** in the report, docx and deck — but `FINAL_COMPLIANCE_AUDIT.md` line 26 still says **29** | **STALE FILE** |
| Topic count | 19 distinct `topic_id` in `post_topic`, 18 of them ≥ 0 | `SELECT count(DISTINCT topic_id) FROM post_topic` | **MISMATCH** — deck slide 8 says "24 named topics" |
| 200-user validation gap disclosed | Disclosed in report p82, p105, p112, deck slide 11, deck slide 13, `FINAL_MISSING_ITEMS.md` | direct read | **DISCLOSED, not fabricated** |
| No unsupported causal claims | `causation_claimed = no` on all 4 rows; report p101, docx p2, deck slides 7 and 13 all deny causation | `event_external_sources.csv` + text scan | **CLEAN** |
| Keyword census vs timeline sample kept distinct | 4 separate corpus rows in `sentiment_distribution.csv`; separate figures; separate report columns; separate network subgraphs (keyword 662/1,320; timeline 567/1,200) | direct read | **CLEAN** |
| `sample_weight` used only for population estimates | Never a model weight, never a sentiment denominator; report §13 limitation 7 states the scope | code + text scan | **CLEAN** |
| Entity graph described as co-occurrence | figure title, caption, report §11, deck slide 10, folder README | direct read | **CLEAN** |
| Bot output described as behavioral risk | `target_column = risk_positive`; report §12; deck slides 11–12 | direct read | **CLEAN** |
| Neutral sentiment present everywhere | `sentiment_neutral` column, pie, all three panels, topic rings, entity bars, crosstab | direct read | **CLEAN** |
| Manual `is_malicious` count | 30 rows with `is_malicious = 1` vs 29 `likely_malicious` — one `suspicious` row also flagged | `labeled_bots_and_not_bots.csv` | **MINOR INCONSISTENCY**, no published number affected |
| `primary_author_ids.txt` | Exists, 38,576 lines | file read | **`FINAL_COMPLIANCE_AUDIT.md` line 38 is wrong** |

**Summary:** of 25 cross-file checks, 20 match exactly, 3 reveal genuine inconsistencies (network edge/node counts across CSVs, the 24-vs-18 topic count, the stale `FINAL_COMPLIANCE_AUDIT.md`), and 2 are minor bookkeeping notes. All headline numbers in the Word report and the deck are correct; the contradictions live in secondary CSVs and one slide.

---
## 5. Technical validation results

**Guideline-named file existence — 31 of 33 exist somewhere, 0 of 33 are in their guideline folder.**

| Guideline file | Exists? | Where it actually is | In its guideline folder? |
|---|---|---|---|
| `translator.ipynb` | Yes | `notebooks/` | No |
| `translated_en_posts.csv` | No | SQLite column instead (documented) | No |
| `translation_examples.csv` | Yes | `outputs/` | No |
| `text_preprocessing.ipynb` | **No** | — | No |
| `posts_cleaned.csv` | No | SQLite column instead (documented) | No |
| `sentiment_analysis.ipynb` | Yes | `notebooks/` | No — and `Posts_Analysis/` does not exist |
| `Posts_sentiment.csv` | Yes | `outputs/` | No |
| `emotion_analysis.ipynb` | Yes | `notebooks/` | No |
| `Posts_emotions.csv` | Yes | `outputs/` | No |
| `events_analysis.ipynb` | Yes | `notebooks/event_detection.ipynb` | No |
| `detected_events.docx` | Yes | root | No |
| `final_topics.csv` | Yes (wrong grain) | `outputs/` | No |
| `topic_sentiment_analysis.ipynb` | **No** | — | No |
| `topic_sentiment_distribution.csv` | Yes | `outputs/` | No |
| `topic_sentiment_visualization.png` | Yes | `outputs/` | No |
| `entity_extraction.ipynb` | Yes | `notebooks/ner_entity_analysis.ipynb` | No |
| `entities_extracted.csv` | Yes | `outputs/` | No |
| `entities_cleaned.csv` | Yes | `outputs/` | No |
| `person_entities_sentiment.png` | Yes | `outputs/` | No |
| `country_entities_sentiment.png` | Yes | `outputs/` | No |
| `entity_network_analysis.ipynb` | Yes | `notebooks/` | No |
| `entity_pairs.csv` | Yes | `outputs/` | No |
| `entity_network_edges.csv` | Yes | `outputs/` | No |
| `entity_network_metrics.csv` | Yes | `outputs/` | No |
| `entity_network_graph.png` | Yes | `outputs/` | No |
| `malicious_detection_flow.pptx` | Yes | root | No |
| `labeled_bots_and_not_bots.csv` | Yes | `outputs/` | No |
| `bot_detection_experiments.csv` | Yes | `outputs/` | No |
| `bot_detection_predictions.csv` | Yes | `outputs/` | No |
| `unlabeled_dataset_results.csv` | Yes | `outputs/` | No |
| `unlabled_dataset.csv` | Yes | `outputs/` (guideline typo reproduced) | No |

**CSV headers and row counts — 38 CSVs scanned, all UTF-8 decodable, 25 with a BOM.** Every file has a non-empty header, a consistent column count across all rows, and no ragged rows. Key counts: `Posts_sentiment.csv` 742,942 × 15; `Posts_emotions.csv` 742,942 × 23; `entities_extracted.csv` 777,249 × 15; `entities_cleaned.csv` 256,491 × 30; `entity_pairs.csv` 83,438; `entity_network_edges.csv` 2,694; `entity_network_nodes.csv` 1,126; `entity_network_metrics.csv` 1,126; `user_bot_features.csv` 38,576 × 52; `rule_based_bot_scores.csv` 38,576 × 60; `unlabeled_dataset_results.csv` 38,576; `unlabled_dataset.csv` 38,576; `bot_detection_predictions.csv` 39,556; `bot_detection_experiments.csv` 40; `bertopic_experiments.csv` 15; `labeled_bots_and_not_bots.csv` 100; `detected_events.csv` 4; `event_tweet_evidence.csv` 31; `topic_sentiment_distribution.csv` 19; `final_topics.csv` 19; `translation_examples.csv` 12; `preprocessing_examples.csv` 36; `manual_review_examples.csv` 16; `topic_representative_tweets.csv` 152; `emotion_over_time_weekly.csv` 1,778.

**Duplicate keys.** `users.author_id` unique across 38,576. `user_bot_features.author_id` unique. `unlabeled_dataset_results.author_id` unique. `labeled_bots_and_not_bots.author_id` unique across 100. `post_sentiment`, `post_emotion` and `post_topic` are 1:1 with `nlp_posts` on `tweet_id`. **`bot_detection_predictions.csv` intentionally repeats `author_id`** because it stacks 38,576 population rows with 980 cross-validation rows — unique within the population block, but the mixed grain is undocumented (N8). **`entity_network_edges.csv` has 29 duplicate unordered name pairs** and **`entity_network_nodes.csv` has 12 duplicate names**, both because the key is (entity, category) (J9).

**Referenced figures and tables.** All 17 images referenced by the Word report resolve to real PNGs. All 9 images in `detected_events.docx` resolve. All 11 media parts in the deck resolve. No placeholder, no "image not found", no dangling table reference. Every PNG has a valid IHDR and non-trivial dimensions (checked by parsing the header directly): `entity_network_graph.png` 2226×1717, `topic_sentiment_visualization.png` 2488×1753, `person_entities_sentiment.png` and `country_entities_sentiment.png` both large enough to read at full page width, `coherence_plot.png` legible, `sentiment_over_time_monthly.png` legible.

**Figures embedded, not linked.** All 17 report images and all 11 deck images are embedded parts inside the OOXML package (counted as `<pic:pic>` elements and media parts), so the files travel intact.

**DOCX render check.** `final_project_report.docx`: 112 paragraphs, 10 tables, 1 section, **0** explicit page breaks, **0** empty pages, **0** empty tables, **0** broken references. `detected_events.docx`: 120 paragraphs, 9 images, structured threshold list, no empty pages.

**PPTX render check.** `final_project_presentation.pptx`: 14 slides on a 13.33 × 7.50 in canvas. Every shape's `left`, `top`, `width` and `height` was compared against the slide bounds — **zero** shapes with negative offsets and **zero** shapes extending past the right or bottom edge. No empty slide, no orphan placeholder. `malicious_detection_flow.pptx`: 3 slides, 8 rounded rectangles, all in bounds — but **no connector shapes at all**, which is why it does not read as a flowchart.

**The one genuinely broken image.** `outputs/malicious_detection_flow.png` has horizontally overlapping boxes (`insufficient_evidence` over `IFB boilerplate / duplicate templates?`; `low_risk` / `medium_risk` / `high_risk` over one another), no arrows and no Yes/No labels. It is embedded in the Word report at p83 and on deck slide 11.

**Notebook paths.** All 8 notebooks in `notebooks/` bootstrap with a relative `Path` walk to the repo root and resolve `outputs/` relatively — portable. **All 8 are saved unexecuted** (`execution_count: null`, `outputs: []` on every code cell). The exception is root-level `Untitled0.ipynb`, which is Colab scratch hard-coded to `/content/drive/MyDrive/IFB/IFB.db` and contains the only write-capable `IFB.db` connection in the workspace.

**Database targeting.** `src/*.py` consistently uses `analysis_corpus.db` for corpus operations, `nlp_analysis_corpus.db` for NLP tables, and `nlp_working_sample.db` for QA only. No script writes to `IFB.db`.

**`IFB.db` integrity — confirmed unmodified.** Size 11.89 GB. mtime **2026-09-11T12:34:15**, which is *before* the analysis pipeline's first write (~13:11). `journal_mode = delete`, `freelist_count = 0`, no `-wal`, `-shm` or `-journal` sidecar exists, `PRAGMA quick_check` returns `ok`, and the schema is intact with `authors`, `tweets` and `timeline` all present and populated. Every production read path uses `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` followed by `PRAGMA query_only = ON`.

> Note on a false alarm raised and resolved during this audit: an early inspection script reused a single sqlite3 cursor for both the `sqlite_master` iteration and the per-table `count(*)`, which invalidated the outer iterator and made it appear that tables had been dropped from all three databases. Re-verified with separate cursors, a full `sqlite_master` dump and `quick_check` on each file: **all three databases are fully intact and no table was ever dropped.**

**No giant CSV required.** The 38,969,023-post corpus stays in SQLite. The largest exported CSV is `entities_extracted.csv` at 777,249 rows / ~219 MB. Nothing in the pipeline needs a 39M-row flat file.

**Portability of source paths.** `src/` resolves everything relative to the repo root, and `CORPUS_MANIFEST.md` documents the database layout and sizes. The only non-portable path in the workspace is `Untitled0.ipynb`'s Colab mount.

**Missing for reproducibility.** No `requirements.txt`, no `environment.yml`, no `HOW_TO_RUN.md`, no documented script execution order, and no `python -m spacy download en_core_web_lg` instruction — even though the exact versions are known (spaCy 3.8.0 with `en_core_web_lg`, pysentimiento, BERTopic with `all-MiniLM-L6-v2`, sentence-transformers, UMAP, HDBSCAN, gensim, scikit-learn, XGBoost, networkx, python-docx, python-pptx, matplotlib, wordcloud). See `FINAL_REPRODUCIBILITY_CHECKLIST.md`.

---

## 6. Report and presentation quality review

**Word report — strong.** Structurally it is what the guidelines ask for: a self-contained document that presents results rather than pointing at a folder. 14 chapters flow from population definition through to limitations. Ten tables carry the graded numbers, seventeen figures carry the graded visuals, and paragraph 7 explicitly commits to embedding rather than deferring. Every number I checked matched its source. Table 6 is unusually good practice — it reproduces all 31 event evidence tweets inside the report, so a grader never has to open a CSV to audit the event claims. Chapter 13's twelve numbered limitations are specific and unflattering, which is the right posture.

The report's weakness is that four things exist as data but not as tables in the document: the BERTopic configuration comparison, the per-topic top-words list, the topic × sentiment counts, and the preprocessing before/after examples. In each case the CSV is shipped and the figure may be embedded, but the instructor's repeated instruction across this workbook is "יש לך תוצאות? שימי בדוח". Adding four tables is copy-paste work with no analysis behind it, and it converts four PARTIALs. The report also under-interprets the entity results, which is the highest-value paragraph currently missing from the document.

**Presentation — strong, with two defects.** 14 slides, a real timing plan in the speaker notes, a consistent footer that repeats the two headline numbers on every slide, and clean geometry: I checked every shape against the slide bounds and found no overflow, nothing off-slide, and no empty slides. The framing discipline carries over from the report — slide 10 says the network is not a social graph, slides 11–12 say the bot output is behavioral risk rather than verified identity, and slide 13 lists the limitations including the missing 200-user validation.

The two defects are both single-fix items. Slide 8 states "24 named topics", which is the `nr_topics` parameter rather than the shipped result of 18 named topics plus an outlier bucket; since the instructor asks the topic count in Q&A, an incorrect number on the slide is a live risk. Slide 11 embeds the broken flowchart PNG, so the one slide that has to explain the bot decision logic is the one slide whose central image does not communicate.

**`detected_events.docx` — strong.** This document does the single thing the instructor demanded most loudly ("אני רוצה הוכחות"). It publishes the full threshold configuration as a bullet list, states the funnel in one line ("Statistical candidates: 68. Rejected: 64. Selected: 4. Evidence tweets: 31."), and then gives per-event tweet evidence with usernames, tweet IDs, per-tweet emotion probabilities, window sentiment breakdowns and external source URLs, across nine embedded figures. Nothing about it reads as generated.

**`malicious_detection_flow.pptx` — weak.** Three slides with correct framing text, but the middle slide is eight disconnected rectangles. Without arrows and Yes/No labels it does not express a decision sequence, and the thresholds appear only in a small footer with no rationale.

---
## 7. Instructor-specific risk assessment

Each item below is a grading emphasis the instructor stated explicitly, either in the IFB column or in another project's column of the same workbook.

| Instructor emphasis | Where it was stated | Current state | Residual risk |
|---|---|---|---|
| Remove IFB / follow words before topic modeling | IFB 2.2 and IFB 3 | `topic_text` strips them; `ifb_topword_hits = 0` in all 15 configs; no IFB topic name | **None** |
| Never combine positive + neutral + negative in one series | IFB 2.3 | Three-panel figure whose title says "no combined sentiment curve"; report states no combined average exists | **None** |
| Include neutral sentiment | Turkey, HCPs | `sentiment_neutral` column plus neutral in every pie, panel, ring, bar and crosstab | **None** |
| Dashed labeled event lines on emotion graphs | Ukraine, Turkey, Lebanon | 18 event plots, all six aggregations × three corpora, dashed with E01–E04 labels | **Low** — present, but `others` at 87.8% compresses the axis so the peak is hard to see |
| Prove events with real tweets and counts | IFB 2.5, Lebanon | 31 tweets with IDs, usernames, emotion probabilities; `n_posts_window` per event; funnel published | **None** |
| Explain why each event was selected | Iran | `why_selected` per event with share, baseline, z, local-peak, theme fraction | **None** |
| Run several BERTopic constellations and justify the choice | IFB 3 | 15 configs, `c_v` coherence, non-max-score selection rationale | **Low** on method — but the table is **not in the report**, which is what three columns complained about |
| Report the topic count clearly | Israel ("לא הצלחתי להבין כמה נושאים") | Deck says 24, data says 18 | **HIGH** |
| Show the coherence-per-topic table as required | Israel-Hamas | Aggregate table only (`Topic_num = n_topics`) | **Medium** |
| Clean junk NER entities such as `&` | IFB 4.2 | `&` fully eliminated (0 occurrences) — but 1,352 sub-3-character entities remain and `CW` / `VN` are visible nodes in the graded network figure | **HIGH** — same defect class as the original complaint |
| Entity charts must not be all-yellow | IFB 4 | Both charts are genuine three-colour stacked bars with per-bar n | **None** |
| Merge aliases carefully | Ukraine, Turkey, Israel | 19,947-row alias table; ambiguous names deliberately excluded — but `U.S` survives beside `United States`, `Un`/`un` are separate, and six names appear as multiple graph nodes under different categories | **Medium** |
| Explain who the entities are and whether the result is plausible | Ukraine, Turkey, Iran, Israel-Hamas | §10 barely interprets | **HIGH** — four separate projects were asked this |
| Inspect profiles when labeling bots | IFB manual-labeling row | 100 reviews with per-row evidence; live profiles unavailable and honestly disclosed | **Low** (unavoidable) |
| Deleted accounts are not automatically bots | IFB, general | `insufficient_evidence`, never malicious; `is_bot` never asserted as 1 | **None** |
| Sample the manual set randomly | Guidelines 5b | Stratified on the rule output; 35 of only 99 high-risk users | **HIGH** — and it makes precision 1.00 partly circular |
| Include saved models and exported tables | Ukraine, Turkey | `topic_model.pkl`, `bot_model_random_forest.pkl`, `bot_scaler.pkl`, `bot_feature_list.json`, all experiment CSVs | **None** |
| Embed figures in the Word report | Iran ("למה לא להכניס לדוח?") | 17 embedded figures including the flowchart | **None** on embedding; the flowchart's *content* is the problem |
| Do not write "see the outputs folder" | multiple | Report paragraph 7 explicitly commits to the opposite | **None** |
| Show training-set sizes | repeated, most emphasised ML demand | K=5 mean 78 (47/31), LOOCV 97 (59/38) in the report, Table 10 and the deck | **None** |
| Explain decisions and limitations clearly | grading criterion | 12 numbered limitations; rationale paragraph opening each chapter | **None** |
| "כמות הנתונים המנותחים" (volume) | grading criterion | 742,942 scored posts from 38.97M, 38,576 users | **None** — a strength |
| "בהירות ההצגה, קוד נקי" | grading criterion | Report and deck are clear; but notebooks ship with no outputs, there is no `requirements.txt`, and the graded folder tree is empty | **HIGH** |

**The five biggest remaining risks to the grade, in order.**

1. **The graded folder tree is empty.** Ten stage folders contain a one-line README each, `Posts_Analysis/` does not exist, and not one of the 33 guideline-named files sits in its guideline folder. A grader who navigates the required tree finds nothing and can mark component after component "לא נמצא", regardless of what is in `outputs/`. This is the highest-expected-loss item in the project and it requires only file copies.

2. **The flowchart is not a flowchart.** No arrows, no Yes/No branches, overlapping boxes, embedded in both the report and the deck. Two workbook rows grade this artefact, in the phase where the instructor already wrote that the decision logic was unclear.

3. **Unexecuted notebooks and no dependency manifest.** All eight notebooks have `execution_count: null` and empty outputs, so opening one shows code and nothing else. With no `requirements.txt` and no documented run order, "קוד נקי" and reproducibility both take a hit. Executing the notebooks reruns no model — they read CSVs and display PNGs.

4. **The topic-count contradiction plus the missing experiments table.** The deck asserts 24 named topics where 18 shipped, and the 15-configuration comparison that justifies the model choice lives only in a CSV. The instructor asks the topic count directly in Q&A and has complained three times about experiment tables not being in the report.

5. **Entity cleanliness and the network count contradiction.** Sub-3-character entities were never dropped as the guidelines require, `CW` and `VN` are visible in the graded Top-30 figure, and three shipped network files disagree on the edge and node counts (2,665 vs 2,694; 1,126 rows vs 1,114 names). Given that the previous submission lost points specifically for a junk entity, junk still being visible in a graded figure is a pointed risk.

**Risks that are rubric risks (fixable) versus dataset limitations (not fixable).** Items 1–5 above are all rubric risks: every one is a packaging, wording or filtering fix that requires no new modelling and no new data. The unavoidable limitations are listed separately in §8 and should not be conflated with them — in particular, the missing 200-user live validation and the absence of verified bot labels are **data-availability facts**, correctly disclosed, and must not be fabricated.

---

## 8. Unavoidable dataset limitations

These are properties of `IFB.db` and of the collection method. They cannot be fixed by more work on this project, they are already disclosed in report chapter 13 and on deck slide 13, and they should be presented as understood constraints rather than apologised for.

1. **No follow / reply / retweet-cascade edges exist.** `IFB.db` has `authors`, `tweets` and `timeline` — no edge table. A user-user social network is therefore impossible, which is exactly why the entity co-occurrence graph is the network deliverable and why it is labeled as such in five places.
2. **The corpus ends in December 2023.** Live X/Twitter profile inspection in 2026 cannot be aligned to the 2023 snapshot, so the required 200-user live verification and true live profile review are unavailable. Disclosed, not fabricated.
3. **No verified bot ground truth exists.** No platform suspension list, no verified-bot dataset, no third-party labels. Everything is therefore framed as behavioral risk rather than bot identity, and `is_bot` is never asserted as 1.
4. **`others` dominates the emotion distribution at 87.83%.** BERTweet's emotion head assigns most short follow-farm posts to `others`, which both compresses every emotion plot's readable range and starves event detection of signal (fear is 0.21% of the corpus). This is a model-behaviour limitation, not an analysis error, and it is the honest explanation for why only 4 events survived the evidence gate.
5. **The collection is keyword/hashtag based, not a POI-follower crawl.** The population is defined by IFB-related keyword usage, so it is a discourse sample rather than a bounded social community. Representativeness claims are correspondingly limited.
6. **The timeline portion is a stratified sample, not a census.** 174 strata with Horvitz-Thompson weights. Population estimates are valid; per-post counts from the timeline are not census counts, which is why every table keeps the two corpora on separate rows.
7. **1,203 ambiguous `AUTHOR_ID` groups had to be dropped** because the identifier was not unique, costing a small amount of coverage that no amount of care can recover.
8. **Language identification is imperfect.** The keyword classifier is Latin-script-ratio based, so Latin-script non-English (Portuguese, Spanish, Indonesian) survives into the "English-ready" corpus at a low rate. Perfect language separation on short informal social text is not achievable.
9. **Follow-farm text is intrinsically low-content.** Short, templated, emoji-heavy posts limit what NER, topic modeling and sentiment can extract — a 23.09% topic-outlier rate is a property of the corpus, not a tuning failure.
10. **No engagement or impression metrics** are available for most posts, so influence cannot be measured directly and centrality must stand in for it.

---

## 9. Conservative overall assessment

**Qualitative verdict by dimension.**

| Dimension | Assessment | Reasoning |
|---|---|---|
| Data volume analysed | **Strong** | 742,942 scored posts from a 38,969,023-post corpus over 38,576 users; the two workbook rows that were blank for IFB are now answered with verified numbers |
| Methodological correctness | **Strong** | Census/sample separation maintained throughout, weights confined to population estimates, `c_v` coherence, stratified CV plus LOOCV, fixed seed, read-only source database |
| Quality of results | **Strong** | Every named IFB-column failure is fixed and independently verifiable; the topic-sentiment ring figure and the 31-tweet event evidence are above the standard of the projects that scored in the low 90s |
| Intellectual honesty | **Strong** | Missing validation disclosed rather than invented; bots framed as risk; network framed as co-occurrence; causation explicitly denied; 12 specific limitations |
| Written report | **Strong** | Self-contained, 17 embedded figures, 10 tables, all numbers verified, no folder deferral — with four tables and one interpretation paragraph missing |
| Presentation | **Strong** | Clean geometry, real timing plan, correct framing — with one wrong number and one broken image |
| Entity cleanliness | **Acceptable** | `&` eliminated and aliases genuinely merged, but the sub-3-character rule was never applied and junk is visible in a graded figure |
| Bot methodology rigour | **Acceptable** | Excellent features and correct ML reporting, undermined by a rule-stratified "random" sample and an unreadable flowchart |
| Reproducibility | **Weak** | No dependency manifest, no run order, all notebooks unexecuted |
| Folder organization | **Weak** | The graded tree is stub-only; one required folder does not exist |

**Overall: substantively strong, presentationally incomplete.**

**Uncertain grade band — explicitly a guess, not a promise.** I cannot promise a grade. The following band is an estimate with stated assumptions, and it should be read as uncertain.

- **As the project stands today: roughly 78–88.** Assumptions: the grader awards full credit for data volume and for the fixed 2.2 / 2.3 / 2.5 / 3 / 4 / 4.2 / manual-labeling items visible in `outputs/` and in the report; the report and presentation cells, empty last time, are now scored positively; but the grader deducts for the empty folder tree, the unreadable flowchart, the unexecuted notebooks, the 24-vs-18 topic contradiction and the residual junk entities. The width of this band is driven almost entirely by how strictly the grader treats the folder tree — a grader who marks "לא נמצא" per missing file lands near the bottom, one who explores `outputs/` lands near the top.
- **After the HIGH-priority fixes in `FINAL_HIGH_PRIORITY_FIXES.md`: roughly 86–93.** Assumptions: the stage folders are populated, the flowchart is redrawn with arrows and branch labels, the notebooks are executed, `requirements.txt` exists, the four missing tables and the entity interpretation paragraph are added to the report, the topic count is corrected, and sub-3-character entities are filtered or explicitly disclosed. The remaining ceiling is set by two things that cannot be fixed: the absent 200-user validation and the thin event yield.

Both bands assume the collaboration criterion ("שיתוף הפעולה") is not a deduction and that the grader accepts SQLite columns in place of the 742k-row CSV dumps, which the report documents.

**What raises the floor most cheaply:** populating the folder tree and executing the notebooks. Neither requires any analysis. Together they address the two grading criteria the instructor names explicitly ("בהירות ההצגה, קוד נקי") and remove the most likely source of "not found" deductions.

---

## 10. Exact final submission checklist

Work through in order. Items 1–9 are the HIGH-priority set; see `FINAL_HIGH_PRIORITY_FIXES.md` for the detailed instructions and `FINAL_REPRODUCIBILITY_CHECKLIST.md` for the environment work.

**Before submitting**

1. Populate all ten guideline stage folders with copies of the guideline-named files, and create `Posts_Analysis/` (it does not exist).
2. Create the two missing notebooks: `text_preprocessing.ipynb` and `topic_sentiment_analysis.ipynb` (thin notebooks that load the existing CSVs — no model rerun).
3. Execute all notebooks once and save them **with outputs**.
4. Add `requirements.txt` and `HOW_TO_RUN.md` with the ordered script sequence and the `en_core_web_lg` download command.
5. Redraw `malicious_detection_flow.png` with connector arrows and Yes/No branch labels and no overlapping boxes; re-embed it in the Word report (p83) and on deck slide 11; rebuild `malicious_detection_flow.pptx` slide 2 the same way.
6. Fix deck slide 8: "18 named topics (nr_topics = 24, 6 follow-spam clusters merged into the outlier bucket)". Add the same sentence to report §9.
7. Add to the Word report: the 15-row BERTopic experiments table; a top-words column and all 19 rows in the topic table; the topic × sentiment counts table; a 5-row preprocessing before/after table; 4 more translation examples to reach 10; the three translation questions answered; a 6–10 sentence entity interpretation paragraph; 4–6 manual-review evidence quotes; the rule thresholds with rationale; the 893 / 9,719 filtering numbers; and the users-filtered-by-category summary table.
8. Filter entities with `len < 3` out of the aggregation and the network figure (removing `CW` and `VN`), or disclose the residue explicitly.
9. Add the one-sentence explanations for: the (entity, category) graph key that reconciles 2,665 vs 2,694 and 1,126 vs 1,114; the rule-stratified manual sample and its effect on the precision of 1.00; the 39,556-row `bot_detection_predictions.csv`; the Latin-script language-classifier false positives; and why only 4 events survived.
10. Update or remove `FINAL_COMPLIANCE_AUDIT.md` (it says 29 evidence tweets, not 31, and claims `primary_author_ids.txt` was not exported).
11. Move `Untitled0.ipynb` out of the root into `scratch/` or delete it.

**Files to upload**

- The whole `IFB-project/` tree **after** the folder-tree fix, including `src/`, `notebooks/`, `outputs/`, `data/` metadata, and the ten populated stage folders.
- `report/final_project_report.docx`
- `presentation/final_project_presentation.pptx`
- `detected_events.docx`
- `malicious_detection_flow.pptx`
- `INSTRUCTOR_REQUIREMENTS.md`, `PROJECT_COMPLIANCE_CHECKLIST.md`, `PROJECT_RISKS_AND_LIMITATIONS.md`, `CORPUS_MANIFEST.md`
- `requirements.txt` and `HOW_TO_RUN.md` (to be created)
- **Do not upload** `IFB.db` (11.89 GB), `data/analysis_corpus.db` (12.37 GB), `data/nlp_analysis_corpus.db` (1.30 GB), `data/nlp_working_sample.db`, or `outputs/topic_model.pkl` (480 MB) unless the instructor asks. Document their sizes and how to rebuild them in `HOW_TO_RUN.md`.
- **Do not upload** `Untitled0.ipynb` or a stale `FINAL_COMPLIANCE_AUDIT.md`.

---

*This audit was performed read-only. No project file was created, modified or deleted other than the three audit documents (`FINAL_READ_ONLY_AUDIT.md`, `FINAL_HIGH_PRIORITY_FIXES.md`, `FINAL_REPRODUCIBILITY_CHECKLIST.md`). `IFB.db` was opened read-only and is provably unmodified. No sentiment, emotion, BERTopic, NER, network or bot model was rerun. Every inspection script used during this audit was written outside the project directory.*
