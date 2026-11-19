# HIGH-priority fixes — status after the packaging pass

The items below were the pre-submission list from the morning read-only audit.
**All of them that could be done without rerunning a model or inventing data
are done.** What remains is either an honest gap or optional polish.

## Done (do not redo)

1. **Guideline folder tree** — `Posts_Analysis/` created; all ten stage folders
   hold the real guideline-named files (notebooks, small CSVs, PNGs, DOCX, PPTX).
   Giant dumps and databases are pointed at, not copied.
2. **Flowchart** — real Yes/No arrows, insufficient-evidence path, “not a bot
   identity” title. PNG + `malicious_detection_flow.pptx` rebuilt and re-embedded.
3. **Notebooks** — ten notebooks written as CSV-only verifiers and executed
   (`execution_count` set, outputs + embedded PNGs saved). Includes the two
   that did not exist: `text_preprocessing.ipynb`, `topic_sentiment_analysis.ipynb`.
4. **`requirements.txt`** (pinned versions) and **`HOW_TO_RUN.md`**.
5. **Topic count** — every “24 named topics” claim removed. Report and slides
   say **18 named topics**; 24 is the `nr_topics` parameter; six spam clusters
   merged into −1. Full 15-row experiment table is in the Word report and
   `TOPIC_MODELING_REPORT.md`.
6. **Entity / network** — len&lt;3 filter applied to cleaned + network outputs;
   `CW` / `VN` gone from the Top-30 figure; canonical edge key =
   unordered `(entity_a, entity_b)`; **1,076 nodes / 2,578 edges** in both
   `entity_network_edges.csv` and `entity_network_summary.csv`; no self-loops;
   no duplicate undirected edges. NER was not rerun.
7. **Bot-review disclosure** — stratified-on-rules, 136× high-risk enrichment,
   98 usable labels, 200-user set still missing. Labels **not** rewritten.
8. **Translation** — Latin-script classifier limit stated; Portuguese example kept.
9. **Docs / render** — Word report (17 figures, 19 tables), 14-slide deck
   (0 overflow), `FINAL_COMPLIANCE_AUDIT_FINAL.md`. Stale
   `FINAL_COMPLIANCE_AUDIT.md` is bannered. `Untitled0.ipynb` moved to `scratch/`.

## Do not do

- Do **not** fabricate the 200-user validation set.
- Do **not** fabricate verified bot labels or relabel the 100 reviews.
- Do **not** invent events to raise the count from 4.
- Do **not** rerun sentiment, emotion, BERTopic, NER, or bot models.
- Do **not** write to `IFB.db`.

## Remaining optional items (not required to upload)

These are still PARTIAL / FAIL and are **documented**, not hidden.

| Item | Why it stays | If you have spare time |
|------|----------------|------------------------|
| Entity sentiment over time | No figure was ever produced | One small plot for 3–5 top entities from `entity_mention` / extracted CSV — still no NER rerun |
| 200-user live validation | Data ends 2023-12 | Leave missing |
| Per-tweet `final_topics.csv` | Would be a 742k-row dump | Keep the topic-level file; SQLite `post_topic` holds assignments |
| Emotion plots compressed by `others` | 87.8% class | Optional companion figure with `others` excluded, from existing CSVs |
| `U.S` vs `United States` as location/country | Alias residue | Fold only if you rebuild the lightweight aggregation again |
| Four events / 16 years | Signal-starved corpus | Explain, do not invent |

None of the optional items is a reason to delay upload.
