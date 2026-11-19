# Instructor requirements

Sources: course guidelines PDF (`הנחיות פרויקט _V3_...`), instructor grading workbook (`Intro_to_Social_Networks_Semester_B_2026_Project_Grades_V3 (1).xlsx`), `DATABASE_INSPECTION_REPORT.md`, `DATASET_DECISION.md`, and `IFB_database_description.docx.pdf`.

The workbook’s **IFB** column is a previous submission of this same topic. It scored **70**. Several IFB-specific comments are mandatory for our run, not optional style notes.

---

## What the IFB column said

| Stage | Instructor comment (IFB column) | What we must do |
|-------|---------------------------------|-----------------|
| 2.1 Translation | “בוצע” | Translate non-English posts or justify an English-only corpus. Do not skip translation just because most posts are English (US Elections was criticized for skipping 12% non-English). |
| 2.2 Preprocessing | Encoding gibberish. **Must remove words such as IFB and Follow**, because every post contains them and topics otherwise collapse. | Save UTF-8. `clean_text` required. For topic modeling, strip IFB / follow / follow-back variants. |
| 2.3 Sentiment | Time graphs mixed positive+negative+neutral into one series. “אין דבר כזה סנטימנט ביחד.” | Three separate series (and a pie). Neutral is required. |
| 2.4 Emotions | “בוצע כנדרש” | Keep all emotion probability columns and multi-resolution plots. |
| 2.5 Events | Events looked ChatGPT-generated. **Want proof: example tweets or tweet groups supporting each event.** | `detected_events.docx` with screenshots/examples and counts. Vertical lines on emotion graphs. |
| 3 Topic modeling | Same IFB/Follow cleaning. Must run **several BERTopic configurations** and explain why the chosen split is best. | Coherence vs parameters, pickle models, representative tweets, meaningful topic names. |
| 3.2 Topic sentiment | “בוצע” | Word cloud + green/yellow/red sentiment ring. |
| 4 NER | “הישויות הכל בצהוב. באג שלא טופל.” | Fix coloring. Interpret entities; merge variants. |
| 4.2 Entity network | Entities poorly built; **`&` treated as an entity**. Must clean. | Normalize entities; edge weights; centrality-sized nodes. |
| 5 Features | “בוצע” | Metadata + tweet-derived features. |
| 5 Manual labeling | **Missing manual review.** Features ≠ proof someone is a bot. | Label 100 users by inspecting profiles. |
| 5 Flowchart / ML | “בוצע” | Still must put the flowchart in the report and report training sizes. |
| 6 Report / 7 Presentation | Empty for IFB; other projects were hit hard here | Embed results in the Word report. Presentation must know numbers and package names. |
| **Score** | **70** | Previous IFB work is a warning, not a template to copy. |

---

## Repeated comments across all projects

These appear in multiple columns (Ukraine, Turkey, Israel, Lebanon, France, US Elections, Iran, HCPs, Doctors, Israel-Hamas), not only IFB.

1. **Colors are graded.** Positive = green, negative = red, neutral = yellow. Blue-for-negative and all-yellow NER bars lost points.
2. **Neutral cannot be dropped.** Pie charts, feature CSVs, stacked bars, and time series must include positive, neutral, and negative.
3. **Sentiment over time must be three lines/panels**, never one combined “sentiment” curve.
4. **Save files as UTF-8.** Hebrew/Turkish/etc. showing as gibberish was penalized even when the analysis was done.
5. **`clean_text` must exist as a saved column**, not only in notebook memory.
6. **Put graphs inside the report.** “למה לא הדפסתן את התמונות.” Linking to a folder is not enough.
7. **The report must contain the results**, not a map of where files live. Israel-Hamas and Doctors lost points for “short stages + go look at the code.”
8. **Event vertical lines on every relevant time graph** (emotions at all aggregations; preferably topics too). Dashed lines with event names.
9. **Events need evidence:** how they were found (peaks, not random), example tweets, and ideally how many posts in the window match.
10. **BERTopic:** several `(min_topic_size, n_neighbors)` runs; Coherence (not only u_mass without rationale); scatter/line of coherence vs configuration; pickle each model; export the experiments table; representative tweets; topic titles that are real labels (“Politics”, not “SAY/YES”).
11. **Outliers (`topic = -1`).** If >10%, reduce them (`reduce_outliers`, drop short texts, retune). Lebanon was praised for reporting 19% outliers and considering a second pass.
12. **Entity normalization.** Merge Erdoğan/Erdogan, USA/U.S.; drop `&`, `god` if nonsense; interpret whether the result is plausible (Netanyahu relatively positive; almost-no-positive in a war dataset).
13. **Network:** edge `weight` = co-occurrence count; node size = centrality; edge width = weight; Top-30 if crowded.
14. **Bots: manual labels first.** A rule formula is not validation. Then flowchart, then ML. Report **how many labeled rows** were used to train.
15. **Presentation:** do not read off a tablet; know the package (`pysentimiento`), topic count, train-set size per class.
16. **Folder structure** matching the guidelines (Translation / Preprocessing / Sentiment / Emotion / Events / Topics / NER / Network / Bots / Report / Presentation).

Israel (95) and US Elections (94) were praised when they: kept three sentiment classes, documented translation decisions, put evidence in the report, and ran coherent topic experiments.

---

## Pipeline the instructor actually grades

```
posts (same user population)
  → translate to English (or document English-only)
  → clean_text  [IFB/follow stripped before topics]
  → sentiment (3 classes) + emotion + time plots
  → events from emotion peaks + tweet evidence + vertical lines
  → BERTopic on clean_text (configs, coherence, outliers, pickle)
  → topic × sentiment (word cloud + ring)
  → NER → clean/normalize → person/country bars
  → entity co-occurrence network (weights + ≥3 centralities)
  → bot features → 100 manual labels → flowchart → rules → 200 validation
  → ML (5 algorithms, K=5 + LOOCV) → predictions → filter high-confidence bad actors
  → Word report with figures embedded + 15-minute presentation
```

The guidelines’ intro mentions “user-group networks” and “discourse spread.” The **graded** network is **entity co-occurrence**, not a follower graph. Discourse spread has no dedicated deliverable file; do not invent a retweet cascade from missing IDs.

---

## Required color and visualization contract

| Element | Rule |
|---------|------|
| Positive | Green |
| Neutral | Yellow |
| Negative | Red |
| Sentiment pie | All three slices |
| Sentiment over time | Three separate series (monthly at minimum) |
| Emotion over time | Week, 2-week, month, 3-month, 6-month, year; dashed vertical event lines on **all** |
| Topic sentiment | Center = word cloud; ring = 3-color sentiment, slice size ∝ counts; Top-6 topics |
| Person / country bars | Stacked, green/yellow/red, Top-10, preferably sorted by polarity |
| Entity network | Node size ∝ centrality; edge width ∝ weight; Top-30 or min-frequency 20 |

---

## Dataset we must describe in every later document

From `DATASET_DECISION.md`:

- Primary users: **38,576** unambiguous IDs in `authors ∩ tweets ∩ timeline`
- Keyword IFB tweets: **1,129,607**
- Timeline tweets: **37,839,416**
- Join: `CAST(AUTHOR_ID AS TEXT)`
- Collection: hashtag/keyword IFB (not POI-follower crawl)
- English timeline: 77.5% `LANG=en`; do not treat `und/qme/qam/zxx` as English

Do not switch populations between stages. Do not dump `IFB.db` to a full CSV.

---

## Grading weights (workbook)

Workbook components: Translation, Preprocessing, Sentiment, Emotions, Events, Topic Modeling, Sentiment per topic, NER, Entity Network, Bad-actor features, Manual labeling, Flowchart, ML classifiers, Report, Presentation, folder structure. Project is **60% of the course grade**. Previous IFB = 70. Target: satisfy the IFB-column failures first (cleaning, three-class time series, event evidence, BERTopic configs, entity cleanup, manual bot labels, complete report).
