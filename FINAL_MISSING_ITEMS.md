# Final missing items

Audit date: 2026-09-12  
Nothing in this list was invented. Empty validation sets were left empty.

## MISSING (cannot be completed from stored data without new labeling or translation)

| Item | Why it is missing | What must not be done | What to do before submission |
|------|-------------------|------------------------|------------------------------|
| 200-user second validation set for the rule classifier | Course asks for 200 random predicted users labeled after the rules. Only the original 100 reviews exist | Do **not** copy rules into fake labels. Do **not** sample 200 users and mark them from the model | Leave the gap in the report and slides. If time remains, a human can label 200 users from snapshot + posts using `MANUAL_BOT_REVIEW_GUIDE.md` |
| Live X/Twitter inspection of the 100 reviewed users | Labels used the 2023 snapshot profile and original posts. `live_profile_inspected` is not a live-page oracle | Do **not** treat deleted/unavailable accounts as bots | Optional post-audit live check. Keep deleted accounts as `insufficient_evidence` |
| Machine translation of excluded non-English posts | ~20,302 script-confirmed non-English keyword posts and timeline non-`en` rows were excluded when the NLP file was built | Do **not** pretend they were translated. Do **not** add them to the 742,942 scored universe | Keep the English-only decision. Translating them would change later counts |

## PARTIAL artifacts (analysis exists; guideline name or completeness gap)

| Item | Actual location | Why PARTIAL | Safe correction |
|------|-----------------|-------------|-----------------|
| `data/primary_author_ids.txt` | IDs are in `data/analysis_corpus.db` table `users` (38,576) | Guideline asked for a plaintext list | Export the existing IDs (done in this audit). Does not change results |
| `translated_en_posts.csv` | `nlp_posts.text_translated_en` (copy of `original_text` for 742,942 English-ready rows) | Standalone 742k-row CSV was not dumped | Do not dump a giant CSV. Examples: `outputs/translation_examples.csv` |
| `posts_cleaned.csv` | `nlp_posts.clean_text` and `topic_text` | Standalone 742k-row CSV was not dumped | Do not dump. Examples: `outputs/preprocessing_examples.csv` |
| `Data_Preprocessing/text_preprocessing.ipynb` | `src/language_detection_and_preprocessing.py`, `notebooks/translator.ipynb` | No notebook with the guideline name | Pointer folder + existing script |
| Guideline stage folders | `src/`, `notebooks/`, `outputs/` | Course tree was not the working tree | README pointers only; do not duplicate 200–500 MB CSVs |
| E03 evidence (closed) | 5 real fear tweets now stored | Was 3; topped up from existing SQLite rows | Do not add more unless they already exist in the window |
| Topic-over-time + event lines (closed) | `outputs/topic_over_time_monthly.png` from existing `post_topic` | Built without rerunning BERTopic | Do not refit topics |
| Sentiment time series event overlays | `outputs/sentiment_over_time_monthly.png` is three class panels without event lines | Event overlays were drawn on emotion plots | Cosmetic only; not a mixed-sentiment failure |
| 4 keyword rows (explained) | IDs `1110608490748207104`, `1132322951167205376`, `1325385083428237312`, `1481686488005763072` are `uncertain` encoding-damage rows | Not scored; not missing-text; not duplicate keys | Cite 244,217 as the scored keyword census |

## Explicitly not missing (do not invent these products)

| Product | Status |
|---------|--------|
| Follower / following graph | **Not in `IFB.db`.** Counts only. Not a graded missing file |
| Reply / quote / conversation tree | No `in_reply_to` / quote IDs |
| True retweet-cascade network | No retweet-edge table. `RT @` is text only |
| Verified bot identities | Impossible with this schema. Risk labels only |
| Full 37,839,416-post BERT scoring | Intentionally sampled. Timeline English sample is 498,725 rows |

## After this audit, these are no longer missing

- `report/final_project_report.docx`
- `presentation/final_project_presentation.pptx`
- `data/primary_author_ids.txt` (export of existing IDs)
- Embedded copies of the graded figures inside the Word file and the slides
