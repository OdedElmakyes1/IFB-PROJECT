# Topic_Modeling

- `topic_modeling.ipynb` (executed)
- `final_topics.csv` — **18 named topics + −1** (19 rows)
- `bertopic_experiments.csv` — all 15 configurations
- `coherence_plot.png`

`nr_topics = 24` is the C13 **parameter**. Six follow-spam clusters (3, 5, 18, 20, 22, 23) were merged into −1. The reported topic count is **18 named topics**.

`outputs/topic_model.pkl` (480 MB) is excluded from this folder and from the upload. It can be rebuilt with seed 2026; BERTopic is not refit for submission.

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
