# NER_Analysis

- `entity_extraction.ipynb` (guideline name; source `notebooks/ner_entity_analysis.ipynb`)
- `person_entities_sentiment.png`, `country_entities_sentiment.png`
- `entities_dropped_short.csv` — 1,352 rows removed by the len<3 rule (`CW`, `VN`, `EU`, …)

`entities_extracted.csv` (193 MB) and `entities_cleaned.csv` (67 MB) stay in `outputs/` and are not duplicated here. The cleaned table has **zero** entities shorter than 3 characters and **zero** `&` entities. NER was not rerun for this packaging pass.

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
