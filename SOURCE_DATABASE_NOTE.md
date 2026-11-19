# Source database note

`IFB.db` is the original source database supplied by the project partner. It contains the three collection tables `authors`, `tweets`, and `timeline`.

It was opened **read-only** for this project (`sqlite3` URI `mode=ro` plus `PRAGMA query_only = ON`). It was **not modified**. Its last-write time on the analysis machine remains **2026-09-11 12:34:15**.

`IFB.db` is **intentionally not included in this ZIP** because the partner already has the original file. Do not replace the partner’s copy with a reconstructed file.

The derived SQLite databases are also excluded from this submission package because they are large intermediate artifacts:

| Excluded database | Role |
|-------------------|------|
| `IFB.db` (~11.89 GB) | Original source; partner already has it |
| `data/analysis_corpus.db` (~12.37 GB) | Frozen 38,576-user corpus |
| `data/nlp_analysis_corpus.db` (~1.30 GB) | English-ready NLP tables |
| `data/nlp_working_sample.db` | QA sample only |

`outputs/topic_model.pkl` (~480 MB) is likewise excluded as a large derived model file. It can be rebuilt with seed 2026; BERTopic does not need to be refit to read the shipped topic tables.

The reports, `HOW_TO_RUN.md`, and `FINAL_REPRODUCIBILITY_CHECKLIST.md` explain the project structure and the reproducibility limits that follow from excluding those files. The graded notebooks in this ZIP read the shipped CSVs and PNGs and do not require the databases.
