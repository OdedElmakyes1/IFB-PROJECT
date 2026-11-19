# Entity_Network_Analysis

This is an **entity co-occurrence** network, not a follower or social graph.

Canonical key:
- node = canonical entity name (category is an attribute)
- edge = unordered pair of two different names
- one row of `entity_network_edges.csv` = one graph edge

Combined graph after the len≥3 filter: **1,076 nodes / 2,578 edges**. No self-loops, no duplicate undirected edges, no `CW` / `VN` / `&`.

The earlier 1,126 / 2,665 (and 2,694 category-typed rows) disagreement is resolved: those files mixed `(entity, category)` identity with a name-only graph. Both files are now generated from the single definition above.

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
