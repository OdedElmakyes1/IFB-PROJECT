# FINAL REPRODUCIBILITY CHECKLIST

What a third party needs in order to re-run this project, what is already in place, and what is missing. Verified read-only on 2026-09-12.

---

## 1. Current reproducibility status

| Item | Status | Detail |
|---|---|---|
| Global random seed | **In place** | 2026 everywhere — recorded in `bot_detection_experiments.csv`, `bertopic_experiments.csv`, the BERTopic tune sample, and the Louvain community call |
| Source database read-only | **In place** | Every production path opens `IFB.db` with `mode=ro` + `PRAGMA query_only = ON` |
| `IFB.db` unmodified | **Verified** | mtime 2026-09-11T12:34:15 (before the pipeline's first write ~13:11); `journal_mode = delete`; `freelist_count = 0`; no `-wal` / `-shm` / `-journal` sidecar; `PRAGMA quick_check = ok`; schema intact (`authors`, `tweets`, `timeline`) |
| Scripts target the right databases | **In place** | `analysis_corpus.db` for corpus work, `nlp_analysis_corpus.db` for NLP, `nlp_working_sample.db` for QA only |
| Notebook paths portable | **In place** | All 8 notebooks in `notebooks/` bootstrap via a relative `Path` walk to the repo root |
| Notebooks contain outputs | **MISSING** | All 8 saved with `execution_count: null` and empty `outputs` |
| `requirements.txt` | **MISSING** | No dependency manifest anywhere in the workspace |
| `environment.yml` | **MISSING** | — |
| Documented run order | **MISSING** | No `HOW_TO_RUN.md`; no ordered script sequence |
| spaCy model download command | **MISSING** | `en_core_web_lg` is required and never mentioned as an install step |
| Corpus documentation | **In place** | `CORPUS_MANIFEST.md` documents the database layout, tables and sizes |
| Saved models | **In place** | `outputs/topic_model.pkl` (480 MB), `bot_model_random_forest.pkl`, `bot_scaler.pkl`, `bot_feature_list.json` |
| No giant CSV required | **Verified** | The 38,969,023-post corpus stays in SQLite; largest CSV is `entities_extracted.csv` at 777,249 rows / ~219 MB |
| Non-portable paths | **One offender** | Root-level `Untitled0.ipynb` is Colab scratch hard-coded to `/content/drive/MyDrive/IFB/IFB.db`, and it holds the only write-capable `IFB.db` connection in the workspace |

---

## 2. Create `requirements.txt`

Versions below reflect what the project documents and what the artefacts record. Pin the two that matter most (spaCy and its model must agree; the sentence-transformer model name must match the pickled BERTopic model).

```
# Core
pandas
numpy
scipy
python-dateutil

# NLP — sentiment and emotion
pysentimiento
transformers
torch
# models used: finiteautomata/bertweet-base-sentiment-analysis
#              finiteautomata/bertweet-base-emotion-analysis

# NLP — preprocessing
nltk

# NER
spacy==3.8.0
# model: en_core_web_lg (see the download step below)

# Topic modeling
bertopic
sentence-transformers
umap-learn
hdbscan
scikit-learn
gensim          # c_v coherence
# embedding model: sentence-transformers/all-MiniLM-L6-v2
# (all-MiniLM-L12-v2 was used in one comparison configuration)

# Machine learning
xgboost

# Network
networkx
python-louvain

# Figures
matplotlib
wordcloud

# Documents
python-docx
python-pptx
openpyxl

# Notebooks
jupyter
ipykernel
```

After installing, download the spaCy model — it is not a pip dependency of `spacy`:

```
python -m spacy download en_core_web_lg
```

And the NLTK data used by the preprocessing step:

```
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"
```

---

## 3. Create `HOW_TO_RUN.md`

It must contain the four things a third party cannot infer: the environment setup, the input the pipeline needs, the ordered script sequence, and the expected runtime and disk cost.

**Prerequisites**

- Python 3.10 or newer, 64-bit.
- `pip install -r requirements.txt`, then the two download commands in §2.
- A CUDA GPU is optional but strongly recommended — the sentiment, emotion and embedding passes over 742,942 posts are the dominant cost.
- Roughly **26 GB of free disk** for the databases (`IFB.db` 11.89 GB + `analysis_corpus.db` 12.37 GB + `nlp_analysis_corpus.db` 1.30 GB + the working sample) plus ~1 GB for `outputs/`.

**Input**

- `IFB.db` (11.89 GB) placed in the repo root. It is **read-only input** and is never written. Tables: `authors`, `tweets`, `timeline`.

**Ordered execution sequence**

Run from the repo root so the relative path resolution works.

```
python src/build_analysis_corpus.py              # IFB.db  -> data/analysis_corpus.db
python src/language_detection_and_preprocessing.py   # clean_text + topic_text -> data/nlp_analysis_corpus.db
python src/sentiment_analysis.py                 # post_sentiment
python src/emotion_analysis.py                   # post_emotion
python src/event_detection.py                    # detected_events.csv, event_tweet_evidence.csv, event_plots/
python src/topic_modeling.py                     # post_topic, bertopic_experiments.csv, topic_model.pkl
python src/topic_sentiment.py                    # topic_sentiment_distribution.csv + visualization
python src/ner_entity_analysis.py                # entity_mention, entities_extracted/cleaned.csv, entity charts
python src/entity_network_analysis.py            # entity_pairs, edges, metrics, graph.png
python src/bot_detection.py                      # features, rule scores, experiments, predictions
python src/build_report.py                       # report/final_project_report.docx
python src/build_presentation.py                 # presentation/final_project_presentation.pptx
```

Confirm the exact script filenames against `src/` before publishing this list, and mark any step that is expensive enough that a grader should skip it.

**Expected runtime** — state the real figures. The sentiment and emotion passes over 742,942 posts and the BERTopic embedding pass are the long steps; the corpus freeze over 38.97M posts is I/O-bound.

**Reproducibility notes to include**

- Seed 2026 is set globally; UMAP and HDBSCAN are seeded, so topic assignments are reproducible on the same library versions.
- `IFB.db` is opened read-only with `PRAGMA query_only = ON` and is never written.
- The 742,942-post text columns live in SQLite rather than in `translated_en_posts.csv` and `posts_cleaned.csv`; the deviation and the table/column names are documented in report §4 and §5.
- Only the **final** BERTopic model is pickled (480 MB). The other 14 configurations are reproducible from `bertopic_experiments.csv`, which records every parameter and the fixed seed.

---

## 4. Notebook checklist

| Notebook | Location | Portable paths | Has outputs | Action |
|---|---|---|---|---|
| `translator.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `English_Translation/` |
| `text_preprocessing.ipynb` | **does not exist** | — | — | **Create** (thin, loads `preprocessing_examples.csv`), execute, place in `Data_Preprocessing/` |
| `sentiment_analysis.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Posts_Analysis/` |
| `emotion_analysis.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Posts_Analysis/` |
| `event_detection.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Posts_Analysis/` as `events_analysis.ipynb` |
| `topic_modeling.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Topic_Modeling/` |
| `topic_sentiment_analysis.ipynb` | **does not exist** | — | — | **Create** (thin, loads `topic_sentiment_distribution.csv`), execute, place in `Topic_Sentiment/` |
| `ner_entity_analysis.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `NER_Analysis/` as `entity_extraction.ipynb` |
| `entity_network_analysis.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Entity_Network_Analysis/` |
| `bot_detection.ipynb` | `notebooks/` | Yes | **No** | Execute and save; copy to `Bot_Detection/` |
| `Untitled0.ipynb` | **repo root** | **No** — `/content/drive/MyDrive/IFB/IFB.db` | n/a | **Move to `scratch/` or delete.** Colab scratch; holds the only write-capable `IFB.db` connection in the workspace |

Executing these notebooks reruns **no** model — they read shipped CSVs and display shipped PNGs. If a cell would open a database or load a model, replace it with a read of the corresponding CSV in `outputs/` before executing.

---

## 5. Data artefacts and what to ship

| Artefact | Size | Ship? |
|---|---|---|
| `IFB.db` | 11.89 GB | **No** — document its schema and size; it is input, not output |
| `data/analysis_corpus.db` | 12.37 GB | **No** — rebuildable from step 1 |
| `data/nlp_analysis_corpus.db` | 1.30 GB | **No** — rebuildable from step 2 onward |
| `data/nlp_working_sample.db` | small | **No** — QA only |
| `data/primary_author_ids.txt` | 38,576 lines | **Yes** |
| `CORPUS_MANIFEST.md` | small | **Yes** |
| `outputs/topic_model.pkl` | 480 MB | **No** unless asked — note its size and that it is reproducible with seed 2026 |
| `outputs/bot_model_random_forest.pkl`, `bot_scaler.pkl`, `bot_feature_list.json` | small | **Yes** |
| All 38 CSVs in `outputs/` | ~250 MB total, largest `entities_extracted.csv` at ~219 MB | **Yes** — if there is an upload limit, drop only `entities_extracted.csv` and say so |
| All PNGs in `outputs/`, `event_plots/`, `emotion_plots/` | small | **Yes** |
| `report/final_project_report.docx`, `presentation/final_project_presentation.pptx`, `detected_events.docx`, `malicious_detection_flow.pptx` | small | **Yes** |

---

## 6. Verification steps a third party can run without any model

These confirm the headline claims from shipped files alone.

```
# 38,576 users
wc -l data/primary_author_ids.txt

# 742,942 scored posts, and the three classes summing to it
python -c "import pandas as pd; d=pd.read_csv('outputs/Posts_sentiment.csv'); print(len(d)); print(d.sentiment_label.value_counts())"

# 19 topics, 18 named, class columns summing to 742,942
python -c "import pandas as pd; d=pd.read_csv('outputs/topic_sentiment_distribution.csv'); print(len(d), d[['positive','neutral','negative']].values.sum())"

# 4 events, 31 evidence tweets, E03 = 4 timeline + 1 contextual keyword tweet
python -c "import pandas as pd; e=pd.read_csv('outputs/event_tweet_evidence.csv'); print(len(e)); print(e.groupby('event_id').size()); print(e[e.event_id=='E03'][['source','engagement_note']])"

# Network: 1,076 nodes / 2,578 edges; sum(degree)/2 must equal the edge-file row count
python -c "import pandas as pd; m=pd.read_csv('outputs/entity_network_metrics.csv'); e=pd.read_csv('outputs/entity_network_edges.csv'); print(len(m), int(m.degree.sum()//2), len(e))"

# 100 manual reviews, is_bot never asserted as 1
python -c "import pandas as pd; d=pd.read_csv('outputs/labeled_bots_and_not_bots.csv'); print(len(d)); print(d.is_bot.value_counts()); print(d.manual_label.value_counts())"

# Training sizes: K=5 mean 78, LOOCV 97
python -c "import pandas as pd; d=pd.read_csv('outputs/bot_detection_experiments.csv'); print(d[d.training_type.isin(['kfold_k5_mean','loocv_pooled'])][['algorithm','training_type','n_train','n_train_pos','n_train_neg']])"

# IFB token removal: zero hits across all 15 BERTopic configurations
python -c "import pandas as pd; d=pd.read_csv('outputs/bertopic_experiments.csv'); print(len(d), d.ifb_topword_hits.sum())"
```

---

## 7. Reproducibility gaps that will remain

These persist even after everything above is done, and should be stated rather than hidden.

1. **Model weights are downloaded at runtime** from Hugging Face (`finiteautomata/bertweet-base-*`, `all-MiniLM-L6-v2`). If those repositories change, results can drift. Record the resolved revision hashes if you want a hard pin.
2. **UMAP and HDBSCAN are seeded but library-version-sensitive.** Topic assignments are reproducible on the same versions; a different `umap-learn` or `hdbscan` build can shift cluster boundaries.
3. **GPU versus CPU** can produce tiny floating-point differences in transformer inference, which can flip a handful of borderline sentiment or emotion labels.
4. **`IFB.db` itself is not redistributable** at 11.89 GB, so full end-to-end reproduction depends on the grader already having the source database.
5. **Only one of the 15 BERTopic models is pickled.** The other 14 are re-derivable from the recorded parameters and the seed, but not byte-identical without a rerun.
