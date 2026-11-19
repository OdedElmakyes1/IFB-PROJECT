# Posts_Analysis

Guideline folder for the scored-post stage. Real files here:

- `sentiment_analysis.ipynb`
- `emotion_analysis.ipynb`
- `events_analysis.ipynb` (guideline name; source is `notebooks/event_detection.ipynb`)
- `detected_events.docx`

`posts.csv` is **not** a 38,969,023-row dump. Posts live in SQLite:
- full freeze: `data/analysis_corpus.db` table `posts`
- English-ready scored file: `data/nlp_analysis_corpus.db` view/tables `nlp_posts` / `post_sentiment` / `post_emotion`

The matching stage folders `Sentiment_Analysis/`, `Emotion_Analysis/`, and `Event_Detection/` hold the same notebooks plus the small figures.

Giant per-post CSVs stay in `outputs/` and are not copied here:
- `outputs/Posts_sentiment.csv` (314 MB, 742,942 rows)
- `outputs/Posts_emotions.csv` (423 MB, 742,942 rows)

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
