# IFB Project Structure

Local workspace for the course **Introduction to Social Networks** (CS, 2026 Semester B). All work stays in this Cursor project. Google Colab and Google Drive are not used.

## Source files already in the workspace

| File | Role |
|------|------|
| `IFB.db` | SQLite database (~11.1 GB). Do not modify, rename, copy, or load entirely into memory. |
| `IFB_database_description.docx.pdf` | Official description of the three tables (`authors`, `tweets`, `timeline`). |
| `הנחיות פרויקט _V3_Intro_to_Social_Networks_CS_2026_Semester_B (2).pdf` | Course project guidelines (sentiment, topics, NER, bots, networks). |
| `Untitled0.ipynb` | Old Colab notebook (Drive mounts). Kept for reference only; do not run it. |

## Working layout

```
IFB-project/
├── IFB.db
├── IFB_database_description.docx.pdf
├── הנחיות פרויקט _V3_Intro_to_Social_Networks_CS_2026_Semester_B (2).pdf
├── Untitled0.ipynb
├── database_inspection.py
├── DATABASE_INSPECTION_REPORT.md
├── project_structure.md
├── .cursorignore
├── data/                 # derived tables only (never a copy of IFB.db)
├── src/                  # reusable Python modules
├── notebooks/            # analysis notebooks (local Jupyter / Cursor)
├── outputs/              # figures, metrics, small result files
├── report/               # written project report
└── presentation/         # slides
```

## Rules

- Inspect and query `IFB.db` with `sqlite3` in **read-only** URI mode (`file:IFB.db?mode=ro`).
- Stream aggregations in SQL (`COUNT`, `MIN`, `MAX`, `LIMIT`). Never `SELECT *` without `LIMIT` / chunking.
- Do not install large machine-learning packages until a later stage (sentiment, emotion, BERTopic, NER, bot classifiers).
- `.cursorignore` keeps the database, virtualenvs, models, caches, and large exports out of Cursor indexing.

## Inspection status

Schema, row counts, date ranges, missing values, and duplicate IDs are documented in `DATABASE_INSPECTION_REPORT.md`, produced by `database_inspection.py`.
