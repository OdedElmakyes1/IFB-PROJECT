# Final submission checklist

Use **`FINAL_COMPLIANCE_AUDIT_FINAL.md`** as the status document.
Do not upload `FINAL_COMPLIANCE_AUDIT.md` as if it were current.

## Canonical numbers (must match the Word report and the slides)

- Primary users: **38,576**
- Full keyword tweets: **1,129,607**
- Full timeline tweets: **37,839,416**
- English-ready scored posts: **742,942**
  - Keyword retained in NLP file: **244,221**
  - Keyword scored: **244,217** (4 uncertain rows held out)
  - Timeline scored: **498,725**
- Users with scored sentiment/emotion: **35,250**
- Sentiment: 134,936 positive / 526,377 neutral / 81,629 negative
- Detected events: **4** (31 evidence tweets; **E03 = 5**)
- Named topics: **18** + outlier −1 (`nr_topics` parameter = 24; 6 spam clusters merged)
- Network (combined entity co-occurrence): **1,076** nodes, **2,578** edges
- Manual reviews: **100**; usable ML labels: **98** (59 / 39)
- K=5 mean train size: **78**
- LOOCV train size: **97**
- Best K=5 pooled model: Random Forest, F1 **0.885**, balanced accuracy **0.842**, AUC **0.93**
- Seed: **2026**
- Package: **pysentimiento**

## Exact upload contents

**Include**

```
src/
notebooks/          (executed .ipynb)
outputs/            EXCEPT topic_model.pkl
data/primary_author_ids.txt
data/*.md
English_Translation/
Data_Preprocessing/
Posts_Analysis/
Sentiment_Analysis/
Emotion_Analysis/
Event_Detection/
Topic_Modeling/
Topic_Sentiment/
NER_Analysis/
Entity_Network_Analysis/
Bot_Detection/
report/final_project_report.docx
presentation/final_project_presentation.pptx
detected_events.docx
malicious_detection_flow.pptx
requirements.txt
HOW_TO_RUN.md
SUBMISSION_EXCLUSIONS.md
INSTRUCTOR_REQUIREMENTS.md
PROJECT_COMPLIANCE_CHECKLIST.md
PROJECT_RISKS_AND_LIMITATIONS.md
CORPUS_MANIFEST.md
DATASET_DECISION.md
TRANSLATION_DECISION.md
TOPIC_MODELING_REPORT.md
BOT_DETECTION_REPORT.md
ENTITY_NETWORK_REPORT.md
NER_ENTITY_ANALYSIS_REPORT.md
EVENT_DETECTION_REPORT.md
SENTIMENT_ANALYSIS_REPORT.md
EMOTION_ANALYSIS_REPORT.md
LANGUAGE_AND_PREPROCESSING_REPORT.md
FINAL_COMPLIANCE_AUDIT_FINAL.md
FINAL_HIGH_PRIORITY_FIXES.md
FINAL_SUBMISSION_CHECKLIST.md
FINAL_REPRODUCIBILITY_CHECKLIST.md
```

**Exclude**

| File | Reason |
|------|--------|
| `IFB.db` (11.89 GB) | source DB; mtime 2026-09-11 12:34:15 |
| `data/analysis_corpus.db` | 12.37 GB rebuildable corpus |
| `data/nlp_analysis_corpus.db` | 1.30 GB NLP tables |
| `data/nlp_working_sample.db` | QA only |
| `outputs/topic_model.pkl` | 480 MB; seed 2026 |
| `scratch/Untitled0.ipynb` | Colab leftover with a write-capable `IFB.db` path |
| `FINAL_COMPLIANCE_AUDIT.md` | stale; superseded by `_FINAL` |

## Claims that must appear in both the report and the slides

- Keyword posts = **census**; timeline posts = **sample**.
- `sample_weight` = population estimate only, never a model weight.
- Combined 742,942 is a **mixed file**.
- Network = **entity co-occurrence**, not a social graph. Canonical count **1,076 / 2,578**.
- Bot output = **behavioral risk**, not verified identity. `is_bot` never 1.
- Manual 100 is **rule-stratified**, not random; metrics are not population rates.
- ML used **98** labels. Train sizes **78** and **97**.
- 200-user validation is **missing** and was not fabricated.
- **18 named topics** (24 was `nr_topics`; 6 spam clusters → −1).
- “English-ready” is an inclusion rule, not native-English proof.
- No causal claims about floods, Thanksgiving, or the war.

## Last visual pass (completed 2026-09-12)

- [x] Word file opens; **17** figures embedded; **19** tables; no “see the outputs folder”
- [x] No empty pages / no broken image refs
- [x] Slides: **14**; **0** overflow; speaker notes include a 15-minute plan
- [x] Flowchart has arrows and Yes/No labels
- [x] All required guideline folders contain real files
- [x] Databases, `topic_model.pkl`, and `Untitled0.ipynb` excluded from the package tree
- [x] `IFB.db` LastWriteTime unchanged: 2026-09-11 12:34:15
- [x] No expensive model rerun
