# NLP sampling plan

Built: 2026-09-11T14:05:47Z
Random seed: **2026**
QA sample `data/nlp_working_sample.db` (**7,428 retained rows**) was **not** used as the analysis corpus. It remains a debug file only.
`IFB.db` and `data/analysis_corpus.db` were not modified.

## Why this sample is large enough for the course

The course BERTopic instructions say: if you have only tens of thousands of posts, tune on all of them; otherwise tune on 10% then apply. This corpus has **744,221** English NLP posts (244,221 keyword + 500,000 timeline). That is:

- larger than typical course datasets in the grading workbook (often 100k–400k posts);
- small enough to run `pysentimiento` and BERTopic on a further 10% tune split;
- drawn from **all 38,576** primary users’ keyword stream (census of eligible tweets) plus a **probability sample** of their English timeline history.

A 7k QA sample cannot support topic modeling, event detection, or bot-text features. Half a million+ timeline posts plus every eligible keyword tweet can.

## User-selection and sources

Same 38,576 unambiguous triple-intersection users as `CORPUS_MANIFEST.md`.

| Source | Rule |
|--------|------|
| Keyword tweets | **Census** of posts classified `likely_english`, excluding IFB-dominated templates, hash-boilerplate (freq ≥ 5), and extra copies of duplicated text. `sampling_probability = 1`, `sample_weight = 1`. |
| Timeline | **Only `LANG = en`**. Stratified sample, target 500,000. |

## Exact counts

| Item | N |
|------|--:|
| Eligible keyword posts in NLP corpus | **244,221** (of which **244,217** are `not_required_english` and scored; 4 `uncertain` encoding-damage rows are listed in `outputs/keyword_unscored_four_rows.csv`) |
| Sampled English timeline posts | **500,000** |
| **Total NLP posts** | **744,221** |
| Users with ≥1 NLP post | **35,256** |
| Users with ≥1 keyword NLP post | 30,707 |
| Users with ≥1 timeline NLP post | 24,620 |

## Keyword census (all 1,129,607 keyword tweets)

Deterministic rules (Unicode script + IFB-stripped remainder). **langdetect was not used for these counts.**

| category | n | pct | notes |
|----------|--:|----:|-------|
| all_keyword_tweets | 1,129,607 | 100.0% | full scan |
| ifb_dominated | 513,390 | 45.4485% | too little signal after IFB/follow strip |
| likely_english | 575,775 | 50.9713% | Latin remainder after IFB strip; not langdetect |
| script_non_english | 20,302 | 1.7973% | Unicode script confirmed |
| uncertain | 20,140 | 1.7829% | mixed/low Latin ratio |
| empty | 0 | 0.0% | empty original |
| duplicate_extra_rows | 831,377 | 73.5988% | normalized hash extras (count-1) |
| duplicate_groups | 36,381 | 3.2207% | hashes with freq>=2 |
| boilerplate_posts_freq_ge5 | 806,651 | 71.4099% | all copies excluded from NLP (freq>=5) |
| boilerplate_groups_freq_ge5 | 10,503 | 0.9298% |  |
| eligible_keyword_written | 244,221 | 21.62% | likely_english, not boiler, not dup extra, clean>=3 |
| eligible_dropped_short_clean | 220 | 0.0195% | likely english but clean_text < 3 tokens |

Duplicate handling: normalized SHA1 of lowercase text without URLs/mentions/emojis. Groups with frequency ≥ 5 are **boilerplate** (all copies dropped). Groups of size 2–4 keep **one** tweet (lowest `tweet_id`) if it is `likely_english`.

## Timeline sampling method

1. Count English (`LANG=en`) posts per author.
2. Split authors into activity tertiles: low / mid / high (cuts at 34 and 445 English timeline posts).
3. Count posts in each stratum `timeline|{quarter}|{activity}`.
4. Allocate 500,000 seats **proportional** to stratum size (at least 1 if the stratum is non-empty).
5. Second pass: sequential sampling with exact quota, `random.Random(2026)`.
6. `sampling_probability = n_sampled / n_population` within the stratum; `sample_weight = 1 / p`.

Quarters are used instead of months so 2007–2010 sparse months are not empty cells. Source is encoded in the stratum prefix (`timeline` vs `keyword`).

English timeline population: **29,573,764**. Sample fraction ≈ 1.6907%.

## Exclusions

| Reason | Where |
|--------|--------|
| IFB-dominated (too little signal after removing follow/IFB terms) | Keyword census, not in NLP corpus |
| Script-confirmed non-English | Keyword census only; no translation this phase |
| Uncertain Latin/mixed | Keyword census, not in NLP corpus |
| Duplicate extras / boilerplate templates | Keyword, not in NLP corpus |
| `clean_text` fewer than 3 tokens | Dropped at write time (220 keyword). Timeline posts were kept even if `clean_text`/`topic_text` is empty after URL/mention stripping (2,948 empty `clean_text`; 5,086 empty `topic_text`) so the probability sample is not conditioned on text length. |
| Timeline not `LANG=en` | Never sampled (`und/qme/qam/zxx` and other languages excluded from English NLP) |
| Ambiguous AUTHOR_IDs / non-primary users | Already absent from `analysis_corpus.db` |

## Language uncertainty

- Keyword `lang` in the NLP table is set to `en` **only** for the rule-based `likely_english` class (Latin remainder after IFB strip).
- langdetect **false friends** (`no`, `af`, `ca`, `so`, `cy`, `nl`, …) on IFB spam are documented in the 5,000-row benchmark: 388 false-friend vs 2894 `en` vs 406 other among 5000 benchmark rows. Those codes are **not** used to include/exclude the full 1.13M.
- Timeline English uses Twitter `LANG=en` only.

## Benchmark

5000 keyword rows: 22.4s (4.47 ms/row). Estimated classify+clean over 1.13M ≈ 84 minutes (order of magnitude; hashing-only pass is faster).

## Files

- `data/nlp_analysis_corpus.db` — analysis corpus (SQLite)
- `data/nlp_working_sample.db` — QA only, unchanged
- `outputs/full_keyword_language_census.csv`
- `outputs/nlp_corpus_statistics.csv`

Primary key is `(source, tweet_id)` so the 42,371 cross-source ID overlaps stay distinct rows.
