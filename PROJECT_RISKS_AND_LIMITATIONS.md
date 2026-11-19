# Project risks and limitations

This document maps instructor requirements onto the actual `IFB.db` constraints. Numbers are from `DATASET_DECISION.md`. Nothing here authorizes skipping a graded file; it only states how to implement or how to disclose a gap.

Primary working set:

- **38,576** users with unambiguous `AUTHOR_ID` in all three tables
- **1,129,607** keyword IFB tweets
- **37,839,416** timeline tweets
- Mixed schemas (`AUTHOR_ID` TEXT / INTEGER / VARCHAR; `LOACATION` typo; `tweets` has no `LANG` / likes)
- No follower edges, no conversation IDs, no native retweet-cascade IDs

---

## What can be completed (graded pipeline)

These stages are feasible on the 38,576-user set if we **sample posts** for neural models and keep that sample documented.

| Requirement | How it can be completed | Honest reporting |
|-------------|-------------------------|------------------|
| Translation | Timeline `LANG=en` (77.5%) needs no translation. Translate real non-English languages. Skip `und/qme/qam/zxx`. Language-detect keyword tweets (no `LANG` column). | State % already English vs translated vs skipped. Do not claim “all English” (US Elections lost points for skipping 12%). |
| Preprocessing + `clean_text` | Standard cleaning on the analysis corpus. Extra IFB stoplist for topics. UTF-8. | Show the stoplist. Previous IFB failed for leaving IFB/Follow in. |
| Sentiment 3-class | `pysentimiento` on sampled English `clean_text`. Pie + **three** time series, green/yellow/red. | Report sample N vs full 37.8M. Neutral required. |
| Emotions + aggregations | Same sample; save all emotion probability columns; week…year plots. | Same sample N. |
| Events | Detect peaks on **this community’s** emotion series; retrieve tweets in-window; quote them. | Events may be IFB/Twitter-platform events, not wars. If a world event does not appear in tweets, do not draw it. |
| BERTopic | Tune on 10% of the **analysis corpus** (not 10% of 37.8M unless we freeze that corpus first). Grid `min_topic_size` / `n_neighbors`; Coherence; pickle; representative docs. | Corpus N, tune N, final N, outlier %, why IFB words were removed. |
| Topic × sentiment rings | Join on `tweet_id`; Top-6 word cloud + 3-color ring. | Neutral slice visible. |
| NER + cleaning | Run NER on English sample; merge aliases; drop junk (`&`, length&lt;3, freq=1). | IFB discourse may yield platforms and influencers, not statesmen. Interpret that. |
| Entity network | Co-occurrence in the same tweet; weights; ≥3 centralities; Top-30 plot. | This **is** the course network. Label it “entity co-occurrence,” never “follower network.” |
| Bot features | `authors` metadata + timeline-derived RT@ rate, hours, variance, hashtags, mentions, copy-paste; `IFB_COUNT`, `FREELANCER`. | Define `rt_rate` as text `RT @` and/or engagement `RETWEETS`; there is no `is_retweet` flag. |
| Manual 100 labels | Sample 38,576 usernames; inspect live profiles. | Deleted/suspended → `unknown`, not bot. |
| Rule flowchart + 200 validation | After labels exist. | Put PPTX **and** the figure in the Word report. |
| ML (5 models, K=5, LOOCV) | Train only on **manually labeled** rows (plus rule-validated if documented). Predict 38,576. | Write N_train per class. LOOCV on ~100 rows is the labeled set, not 38k. |
| Report + presentation | Embed every graded figure; one population throughout. | Open with coverage numbers so the instructor is not surprised by “only” 38k users vs 2.1M keyword authors. |

---

## What cannot be completed **exactly** as a naive reading of the intro PDF

The intro bullet list mentions user-group networks and discourse spread. The **file checklist** does not require a follower graph. Do not fail the project by promising those products.

| Desired product | Why it cannot be done exactly | What to deliver instead | How to report |
|-----------------|------------------------------|-------------------------|---------------|
| User follow / following **graph** | `authors` has counts only (`FOLLOWERS_COUNT`, `FOLLOWING_COUNT`). No edge list. | Ratio and counts as **bot features**. Entity co-occurrence as **the network chapter**. | One limitations paragraph: “IFB.db has no follow edges. Network analysis is entity co-occurrence as specified in stage 4.2.” |
| Conversation / reply tree | No `in_reply_to_status_id`, no quoted ID. | Mentions (`@user`) as text features only. | “No conversation IDs; we cannot reconstruct threads.” |
| Native retweet **cascade** | `timeline.RETWEETS` is a count on the tweet, not a graph of who retweeted whom. Keyword tweets have no engagement fields. ~22% of a timeline sample start with `RT @`. | `rt_rate` feature; optional weak mention of `RT @` targets, clearly labeled as incomplete. | “No retweet-edge table; cascades are out of scope.” |
| BERTopic / pysentimiento on **all 37.8M** timeline rows | Compute and memory. Guidelines already allow a 10% tune sample; they assume “full data” on the order of tens/hundreds of thousands, not 45 million. | Freeze a documented analysis corpus (English, primary users, size chosen before modeling — e.g. 100k–500k). Tune on 10% of **that**. | Report corpus rule and N. Do not silently analyze 20k and write as if it were 38M. |
| Bot detection on 2.1M keyword authors | 1.54M have no `authors` row. | Only the 38,576 with metadata + timeline. | “Keyword-only authors lack profiles; they are excluded so bot and text stages share one population.” |
| `USERNAME` as join key | Unique in `authors`, absent from `tweets`/`timeline`. | `CAST(AUTHOR_ID AS TEXT)`; drop 1,203 colliding IDs. | Duplicate-ID appendix. |
| Exact guideline column `LOCATION` | DB column is `LOACATION`. | Query `LOACATION`. | Schema typo note. |
| Keyword-tweet language from `LANG` | Column missing on `tweets`. | Detect language or restrict keyword tweets to users whose timeline is mostly `en`. | Method sentence. |
| Default-profile-image boolean | Only `IMAGE_URL` string. | Heuristic (empty / default Twitter URL patterns) or “unknown.” | Do not fake a Boolean from nothing. |
| Live Twitter labeling of 100 users | Data end ~2023-12; many IFB accounts churn. | Label what still exists; `unknown` otherwise; do not replace inspection with the rule engine (previous IFB scored down for that). | Report how many profiles were still reachable. |
| Psychological questionnaires / synchronized campaigns | Mentioned as optional extras at the end of the PDF, not as numbered deliverables. | Skip unless time remains after graded files. | Optional. |

---

## Requirement-by-requirement limitation notes (for the final report)

Copy these sentences into the Word report rather than hiding them.

1. **Population.** “We analyze 38,576 users present in authors, keyword tweets, and timeline after dropping 1,203 duplicate AUTHOR_ID groups. This is smaller than 2.1 million keyword authors because most keyword authors have no profile or timeline. We keep one population for all stages.”
2. **Scale.** “Timeline contains 37.8 million posts for these users. Sentiment, emotion, NER, and BERTopic run on a frozen English sample of N = ____ drawn with seed ____. Aggregations that are exact (language census, coverage) used SQL on the full tables.”
3. **IFB tautology.** “Keyword tweets were collected with follow/IFB strings. Those tokens are removed before topic modeling so topics are not ‘IFB / follow back’.”
4. **Network.** “No follower graph is stored. The network chapter is entity co-occurrence with edge weights and centrality, as required.”
5. **Spread.** “No reply/quote/retweet IDs. We do not present a cascade graph.”
6. **Events.** “Events are those that move emotions **in this sample**, evidenced by tweets, not a chat-generated world timeline.”
7. **Bots.** “Follow graphs are missing so bot features use ratios, rates, and text patterns. Manual labels inspect profiles; unreachable accounts are unknown.”
8. **Colors and classes.** “All sentiment visuals use green / yellow / red and include neutral.”

---

## Process risks (can still fail a doable project)

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Repeating the previous IFB (score 70) | Same topic already lost points on IFB-word cleaning, mixed sentiment time series, chatbot events, weak BERTopic docs, yellow NER, `&` entities, no manual bot pass, incomplete report | Treat the IFB column as a punch list |
| Sampling too small or undocumented | Instructor grades “amount of data analyzed” | Publish N and the sampling rule before fitting models |
| Switching populations mid-pipeline | Text on 2.1M users, bots on 38k | Forbidden by `DATASET_DECISION.md` |
| Loading `IFB.db` into pandas | 11 GB file | Read-only SQLite, chunks, samples only |
| Encoding | IFB column: gibberish CSV | UTF-8 with BOM if Excel must open it |
| Topic names and outliers | “SAY/YES” titles and missing coherence plots were penalized | Manual labeling of topics; export experiments |
| Event hallucination | Explicit IFB comment | Peak → retrieve tweets → then name the event |
| Manual labeling blocked | Accounts gone | `unknown` + still do 100 rows of attempt log |
| Report as a link farm | Doctors / Israel-Hamas / Iran comments | Embed figures in Word |

---

## Is the dataset suitable for the **complete** course project?

**Yes, with sampling and honest limitations.**

`IFB.db` supports every **numbered, file-bearing** stage in the guidelines: translation, clean_text, sentiment, emotion, events, BERTopic, topic sentiment, NER, entity network, bot features, manual labels, flowchart, and ML. It does **not** support a follower network or a retweet cascade; those are not in the required-file list and must be disclosed rather than faked.

The dataset is a poor fit only if we insist on analyzing all 2.1 million keyword authors or all 45 million timeline rows in BERT. The defensible complete project is: **38,576 users + frozen English post sample + full SQL-backed metadata/features + complete graded artifacts + a limitations chapter.**
