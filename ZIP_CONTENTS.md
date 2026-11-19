# ZIP contents — IFB-project-submission

Built: 2026-09-12 08:55 UTC
Archive: `IFB-project-submission.zip`

## Totals

- Included files: **246**
- ZIP members: **247**
- Uncompressed size: **1542.4 MB** (1,542,379,481 bytes)
- ZIP size: **0.0 MB** (0 bytes)
- Split volumes: **no**

## Included top-level folders / files

- `BOT_DETECTION_REPORT.md` (file)
- `Bot_Detection` (folder)
- `CORPUS_MANIFEST.md` (file)
- `DATABASE_INSPECTION_REPORT.md` (file)
- `DATASET_DECISION.md` (file)
- `Data_Preprocessing` (folder)
- `EMOTION_ANALYSIS_REPORT.md` (file)
- `ENTITY_NETWORK_REPORT.md` (file)
- `EVENT_DETECTION_REPORT.md` (file)
- `Emotion_Analysis` (folder)
- `English_Translation` (folder)
- `Entity_Network_Analysis` (folder)
- `Event_Detection` (folder)
- `FINAL_COMPLIANCE_AUDIT_FINAL.md` (file)
- `FINAL_HIGH_PRIORITY_FIXES.md` (file)
- `FINAL_MISSING_ITEMS.md` (file)
- `FINAL_READ_ONLY_AUDIT.md` (file)
- `FINAL_REPRODUCIBILITY_CHECKLIST.md` (file)
- `FINAL_SUBMISSION_CHECKLIST.md` (file)
- `HOW_TO_RUN.md` (file)
- `INSTRUCTOR_REQUIREMENTS.md` (file)
- `LANGUAGE_AND_PREPROCESSING_REPORT.md` (file)
- `MANUAL_BOT_REVIEW_GUIDE.md` (file)
- `NER_Analysis` (folder)
- `NER_ENTITY_ANALYSIS_REPORT.md` (file)
- `NLP_SAMPLING_PLAN.md` (file)
- `PROJECT_COMPLIANCE_CHECKLIST.md` (file)
- `PROJECT_RISKS_AND_LIMITATIONS.md` (file)
- `Posts_Analysis` (folder)
- `SENTIMENT_ANALYSIS_REPORT.md` (file)
- `SOURCE_DATABASE_NOTE.md` (file)
- `SUBMISSION_EXCLUSIONS.md` (file)
- `Sentiment_Analysis` (folder)
- `TOPIC_MODELING_REPORT.md` (file)
- `TRANSLATION_DECISION.md` (file)
- `Topic_Modeling` (folder)
- `Topic_Sentiment` (folder)
- `create_submission_zip.py` (file)
- `data` (folder)
- `detected_events.docx` (file)
- `malicious_detection_flow.pptx` (file)
- `notebooks` (folder)
- `outputs` (folder)
- `presentation` (folder)
- `project_structure.md` (file)
- `report` (folder)
- `requirements.txt` (file)
- `src` (folder)

## Required files (checklist)

- `src/` — included
- `notebooks/` — included
- `outputs/  (except topic_model.pkl)` — included
- `data/primary_author_ids.txt` — included
- `data/README.md` — included
- `English_Translation/` — included
- `Data_Preprocessing/` — included
- `Posts_Analysis/` — included
- `Sentiment_Analysis/` — included
- `Emotion_Analysis/` — included
- `Event_Detection/` — included
- `Topic_Modeling/` — included
- `Topic_Sentiment/` — included
- `NER_Analysis/` — included
- `Entity_Network_Analysis/` — included
- `Bot_Detection/` — included
- `report/final_project_report.docx` — included
- `presentation/final_project_presentation.pptx` — included
- `detected_events.docx` — included
- `malicious_detection_flow.pptx` — included
- `SOURCE_DATABASE_NOTE.md` — included
- `HOW_TO_RUN.md` — included
- `requirements.txt` — included
- `FINAL_COMPLIANCE_AUDIT_FINAL.md` — included
- `FINAL_SUBMISSION_CHECKLIST.md` — included
- `create_submission_zip.py` — included
- `ZIP_CONTENTS.md` — included

## Excluded files and why

| Path | Reason |
|------|--------|
| `IFB.db` | Original partner source database; opened read-only; not modified; partner already has it |
| `data/*.db` | Large intermediate SQLite artifacts |
| `outputs/topic_model.pkl` | 480 MB derived BERTopic model |
| `scratch/` and `Untitled0.ipynb` | Colab leftover; write-capable IFB.db path |
| `FINAL_COMPLIANCE_AUDIT.md` | Stale audit; superseded by `FINAL_COMPLIANCE_AUDIT_FINAL.md` |
| `__pycache__/`, `.venv/`, `node_modules/`, `.git/`, `.cursor/` | Caches / environments / editor state |
| `*.log`, secrets, credentials | Not part of the graded submission |
| `outputs/topic_model.pkl` | explicit exclude: topic_model.pkl |

## Canonical-number validation

| Claim | Expected | Observed | Pass |
|-------|---------:|---------:|:----:|
| users | 38576 | 38576 | yes |
| scored_posts | 742942 | 742942 | yes |
| scored_users | 35250 | 35250 | yes |
| events | 4 | 4 | yes |
| network_nodes | 1076 | 1076 | yes |
| network_edges | 2578 | 2578 | yes |
| edge_file_rows | 2578 | 2578 | yes |
| named_topics | 18 | 18 | yes |
| manual_reviews | 100 | 100 | yes |
| usable_ml_labels | 98 | 98 | yes |
| k5_train | 78 | 78 | yes |
| loocv_train | 97 | 97 | yes |
| e03_evidence | 5 | 5 | yes |

## Archive validation

- Required-path missing before ZIP: none
- Database files inside ZIP: none
- Stale `FINAL_COMPLIANCE_AUDIT.md` inside ZIP: none
- `scratch/` or `Untitled0.ipynb` inside ZIP: none
- `topic_model.pkl` inside ZIP: none
- `IFB.db` last write time (unchanged): 2026-09-11 12:34:15

## Split-volume instructions

No split volumes were created. The single file `IFB-project-submission.zip` is within a convenient transfer size.

## How this ZIP was built

```
python create_submission_zip.py
```

No analysis model was rerun. `IFB.db` was not opened for writing.
