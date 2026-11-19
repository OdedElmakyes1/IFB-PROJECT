# How to run the IFB project

Windows / PowerShell / Cursor. All commands are from the **repository root**
(`IFB-project/`). Paths are relative. Do not open `IFB.db` for writing.

## 1. Install

```powershell
python -m pip install -r requirements.txt
python -m spacy download en_core_web_lg
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"
```

Python 3.11, 64-bit. A CUDA GPU is optional. It only matters if you rerun the
expensive scoring scripts, which this submission does **not** require.

## 2. Required local paths (not in the upload)

| Path | Size | Role |
|------|-----:|------|
| `IFB.db` | 11.89 GB | Read-only source (`authors`, `tweets`, `timeline`) |
| `data/analysis_corpus.db` | 12.37 GB | Frozen 38,576-user corpus |
| `data/nlp_analysis_corpus.db` | 1.30 GB | English-ready NLP tables |
| `outputs/topic_model.pkl` | 480 MB | Final BERTopic model |

These four files are **intentionally excluded from the submission package**.
The graded notebooks do not need them. They read `outputs/*.csv` and `outputs/*.png`.

Confirm the source database was not written:

```powershell
Get-Item IFB.db | Select-Object Length, LastWriteTime
# Expected LastWriteTime: 2026-09-11 12:34:15
```

## 3. Lightweight validation (what a grader should run)

From the repo root, or from any guideline folder:

```powershell
# already-executed notebooks — open them; outputs are saved
# to re-execute without any database or model:
python src/postaudit_write_and_execute_notebooks.py
```

Or open any notebook in `English_Translation/`, `Data_Preprocessing/`,
`Posts_Analysis/`, `Topic_Modeling/`, … and Run All. Each notebook calls
`find_root()` by walking up until it sees `outputs/` and `src/`.

Expected lightweight outputs: printed tables, embedded PNGs, and assertions on

- 38,576 users / 742,942 scored posts / 35,250 scored users
- 18 named topics + −1 (not “24 named topics”)
- 4 events / 31 evidence tweets / E03 = 5
- 1,076 network nodes / 2,578 edges
- 100 manual reviews / 98 usable ML labels
- K=5 train 78 / LOOCV train 97

## 4. Full pipeline execution order (expensive — do not run for grading)

Only if `IFB.db` is present and you intend to rebuild everything.
Every script opens `IFB.db` **read-only** (`mode=ro` + `PRAGMA query_only=ON`).

| # | Command | Expensive? | Writes |
|---|---------|------------|--------|
| 1 | `python src/build_analysis_corpus.py` | I/O on 39M posts | `data/analysis_corpus.db` |
| 2 | `python src/language_detection_and_preprocessing.py` | medium | `nlp_posts.clean_text` / `topic_text` |
| 3 | `python src/sentiment_analysis.py` | **yes — BERT on 742,942 posts** | `post_sentiment`, `Posts_sentiment.csv` |
| 4 | `python src/emotion_analysis.py` | **yes — BERT on 742,942 posts** | `post_emotion`, `Posts_emotions.csv` |
| 5 | `python src/event_detection.py` | no (uses stored emotions) | `detected_events.*` |
| 6 | `python src/topic_modeling.py` | **yes — embeddings + UMAP/HDBSCAN** | `post_topic`, `topic_model.pkl` |
| 7 | topic-sentiment step inside topic script | no | `topic_sentiment_*.csv/png` |
| 8 | `python src/ner_entity_analysis.py` | **yes — spaCy on original_text** | `entity_mention`, entity CSVs |
| 9 | `python src/entity_network_analysis.py` | no | network CSVs / PNG |
| 9b | `python src/postaudit_rebuild_entity_network.py` | no | same, after len≥3 filter |
| 10 | `python src/bot_detection.py` | no on 98 labels | bot CSVs / PNG / pkl |
| 11 | `python src/postaudit_make_flowchart.py` | no | flowchart PNG + PPTX |
| 12 | `python src/build_final_submission_artifacts.py` | no | Word report + slides |
| 13 | `python src/postaudit_write_and_execute_notebooks.py` | no | executed notebooks |
| 14 | `python src/postaudit_populate_guideline_folders.py` | no | guideline folder copies |

Seed **2026** everywhere.

## 5. Packaging / corrective scripts (safe, no model rerun)

```powershell
python src/postaudit_rebuild_entity_network.py
python src/postaudit_make_flowchart.py
python src/build_final_submission_artifacts.py
python src/postaudit_write_and_execute_notebooks.py
python src/postaudit_populate_guideline_folders.py
```

None of these opens `IFB.db` for writing. The entity rebuild reads
`outputs/entities_extracted.csv` and `outputs/entity_pairs.csv` only.

## 6. What this submission contains vs excludes

**Upload:** `src/`, `notebooks/`, `outputs/` (except `topic_model.pkl`),
`data/primary_author_ids.txt`, `data/*.md` metadata, the ten guideline folders,
`report/final_project_report.docx`, `presentation/final_project_presentation.pptx`,
`detected_events.docx`, `malicious_detection_flow.pptx`, `requirements.txt`,
`HOW_TO_RUN.md`, and the project markdown reports.

**Do not upload:** `IFB.db`, `data/*.db`, `outputs/topic_model.pkl`,
`scratch/Untitled0.ipynb`.
