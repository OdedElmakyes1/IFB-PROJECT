# Bot_Detection

Behavioral risk classification — **not verified bot identity**.

- `bot_detection.ipynb` (executed)
- `malicious_detection_flow.pptx` / `.png` — real flowchart with Yes/No arrows
- `labeled_bots_and_not_bots.csv` — 100 reviews, 98 usable ML labels
- `bot_detection_experiments.csv` — 5 algorithms × K=5 + LOOCV; train sizes 78 / 97
- `bot_detection_predictions.csv` — 39,556 rows = 38,576 population + 980 CV rows
- `unlabeled_dataset_results.csv`, `unlabled_dataset.csv` (guideline spelling) — 38,576 each

The 100 users were **stratified on the rule bands**, not sampled at random. High-risk (99 users) was enriched ~136×, so precision 1.00 is a sample diagnostic, not a population rate. The 200-user validation set is **missing and was not fabricated**.

# Excluded from this folder (on purpose)

These files exist in the project but are **not** duplicated here:

| File | Why excluded | Where it lives |
|------|----------------|----------------|
| `IFB.db` (11.89 GB) | Source database, read-only input | project root |
| `data/analysis_corpus.db` (12.37 GB) | Frozen corpus | `data/` |
| `data/nlp_analysis_corpus.db` (1.30 GB) | NLP tables (`clean_text`, `topic_text`, `text_translated_en`, scores) | `data/` |
| `outputs/topic_model.pkl` (480 MB) | Final BERTopic model; reproducible with seed 2026 | `outputs/` |
| `outputs/Posts_sentiment.csv` (314 MB) | 742,942-row dump | `outputs/` |
| `outputs/Posts_emotions.csv` (423 MB) | 742,942-row dump | `outputs/` |
| `outputs/entities_extracted.csv` (193 MB) | Raw NER mentions | `outputs/` |
| `outputs/entities_cleaned.csv` (67 MB) | Cleaned entity table (len≥3) | `outputs/` |

The graded notebooks in this tree verify the shipped **small** CSVs and PNGs.
They do not require the excluded files to open and show results.
