# Final compliance audit (post HIGH-priority packaging)

**This is the final audit.** Do not use `FINAL_COMPLIANCE_AUDIT.md` (stale) or
`FINAL_READ_ONLY_AUDIT.md` (pre-fix snapshot) as the submission status.

Date: 2026-09-12. Mode of the packaging pass: no sentiment / emotion / BERTopic /
NER / event / bot model was rerun. `IFB.db` was not written (mtime still
2026-09-11 12:34:15). Network tables were rebuilt from already-extracted CSVs
with a len≥3 filter only.

## Canonical numbers (verified after the packaging pass)

| Item | Value |
|------|------:|
| Primary users | **38,576** |
| English-ready scored posts | **742,942** |
| Scored users | **35,250** |
| Keyword retained in NLP file | **244,221** |
| Keyword scored | **244,217** (4 uncertain rows held out; IDs documented) |
| Timeline scored | **498,725** |
| Detected events | **4** |
| Evidence tweets | **31** (E03 = **5**) |
| Named topics | **18** (+ outlier −1; `nr_topics` parameter was 24) |
| Combined network nodes / edges | **1,076 / 2,578** |
| Manual reviews | **100** |
| Usable ML labels | **98** |
| K=5 mean train size | **78** |
| LOOCV train size | **97** |
| Seed | **2026** |

The pre-fix network figures 1,126 / 2,665 are **retired**. They mixed
`(entity, category)` row identity with a name-only graph and they included
two-character junk (`CW`, `VN`). The canonical key is now:

- node = canonical entity name (category is an attribute)
- edge = unordered pair of two different names
- one row of `entity_network_edges.csv` = one graph edge = 2,578
- `sum(degree)/2` = 2,578; self-loops = 0; duplicate undirected edges = 0

## Requirement tallies

Compared with the 192-row pre-fix inventory in `FINAL_READ_ONLY_AUDIT.md`:

| Status | Pre-fix | Post-fix | Notes |
|--------|--------:|---------:|-------|
| **PASS** | 131 | **170** | Folder tree, notebooks, flowchart, topic count, experiments table, entity filter, disclosures |
| **PARTIAL** | 35 | **19** | Remaining documentation / optional / thin-yield items |
| **FAIL** | 25 | **2** | Only: entity-sentiment-over-time figure; 200-user live validation |
| **N/A** | 1 | **1** | Batch translation (no MT ran) |

The two remaining FAILs are intentional:

1. **200-user validation set** — corpus ends 2023-12; live X cannot be aligned. Disclosed, **not fabricated**.
2. **Entity sentiment over time** — listed guideline analysis with no figure. Disclosed as limitation 16. Not invented.

`L2` (manual sample “at random”) moved from FAIL to PARTIAL: the 100 labels were
**not** redrawn; the rule-stratified design and ~136× high-risk enrichment are
now stated in the Word report, the deck, `BOT_DETECTION_REPORT.md`, and the flowchart footer.

## HIGH-priority items — status

| Item | Status |
|------|--------|
| Populate guideline folders + create `Posts_Analysis/` | **Done** — real files, not one-line stubs |
| Redraw flowchart with arrows and Yes/No | **Done** — PNG + PPTX + embedded in report slide 11 / report §12 |
| Execute notebooks; `requirements.txt`; `HOW_TO_RUN.md` | **Done** — 10 notebooks with `execution_count` and outputs |
| Fix “24 named topics”; embed 15-config table | **Done** — 18 named topics everywhere; table in report §9 and `TOPIC_MODELING_REPORT.md` |
| Drop len&lt;3 entities; reconcile edge counts | **Done** — 1,076 / 2,578; no `CW`/`VN`; no self-loops; no duplicate undirected edges |
| Disclose stratified bot sample; keep 200-user missing | **Done** — labels not rewritten |
| Latin-script classifier + Portuguese example | **Done** — `TRANSLATION_DECISION.md` + report §4 |
| Refresh final docs; render DOCX/PPTX | **Done** — 17 report images, 14 slides, 0 overflow |

## What a grader opens first

| Folder | Real files present |
|--------|--------------------|
| `English_Translation/` | `translator.ipynb`, `translation_examples.csv` |
| `Data_Preprocessing/` | `text_preprocessing.ipynb`, `preprocessing_examples.csv` |
| `Posts_Analysis/` | sentiment / emotion / `events_analysis.ipynb`, `detected_events.docx` |
| `Sentiment_Analysis/` | notebook + pies + 3-panel time series |
| `Emotion_Analysis/` | notebook + distribution / crosstab |
| `Event_Detection/` | `events_analysis.ipynb`, `detected_events.docx`, evidence CSV |
| `Topic_Modeling/` | notebook, 15-config CSV, `final_topics.csv` (18+−1), coherence plot |
| `Topic_Sentiment/` | notebook, counts CSV, ring PNG |
| `NER_Analysis/` | `entity_extraction.ipynb`, person/country PNGs |
| `Entity_Network_Analysis/` | notebook, pairs/edges/metrics, graph PNG |
| `Bot_Detection/` | notebook, flowchart PPTX, labeled + experiments + predictions + both unlabeled files |
| `report/` | `final_project_report.docx` (17 figures, 19 tables) |
| `presentation/` | `final_project_presentation.pptx` (14 slides, 0 overflow) |

Giant files are **not** duplicated into those folders. Each README names
`outputs/Posts_sentiment.csv` (314 MB), `outputs/Posts_emotions.csv` (423 MB),
`outputs/entities_extracted.csv` (193 MB), `outputs/entities_cleaned.csv` (67 MB),
`outputs/topic_model.pkl` (480 MB), and the three databases.

## Intellectual-honesty checks (still clean)

- No causal event claims
- Network described as co-occurrence, not a social graph
- Bots described as behavioral risk; `is_bot` never 1
- Neutral present in every sentiment artefact
- Three separate sentiment series; no combined curve
- Keyword census and timeline sample kept distinct
- `sample_weight` used only for population estimates
- 200-user set marked missing
- Portuguese example retained and explained
- Manual sample disclosed as rule-stratified

## Remaining risks (not packaging)

1. Four events over 16 years is thin; two are Thanksgiving. Do not invent more.
2. `others` = 87.8% still flattens emotion plots.
3. Rule precision 1.00 is circular by design (now disclosed).
4. No live profiles; no verified bot ground truth.
5. `final_topics.csv` is topic-level, not the guideline per-tweet schema (deviation documented; a 742k dump was refused).

## Confirmation

- No expensive model was rerun.
- `IFB.db` was not modified.
- `Untitled0.ipynb` is in `scratch/`, not the root.
- `topic_model.pkl` and all `*.db` files stay out of the guideline folders.
