# Language detection and preprocessing report

Built: 2026-09-11T13:31:22Z
Input: `data/analysis_corpus.db` (read-only). `IFB.db` was not opened.
Working sample DB: `data/nlp_working_sample.db` (not a 39-million-row CSV).
Stemming: **Porter stemming (NLTK PorterStemmer); not WordNet lemmatization**.
Language detector: **langdetect** with `DetectorFactory.seed = 2026`, plus Unicode-script overrides.
No sentiment, emotion, BERTopic, NER, network, or bot detection was run.
No bulk translation was run.

## How keyword languages were determined

Keyword tweets have no `LANG` column. They were **not** assumed to be English.

1. Load the stratified table `keyword_lang_sample` (**2,734** rows; ~120 per collection keyword).
2. Strip URLs, @mentions, emojis, and IFB/follow collection phrases/tokens.
3. If the remaining alphabetic signal is too short → status `ifb_dominated` (typical copy-paste “follow for follow” templates).
4. If the original text is dominated by a non-Latin script (Arabic, CJK, Hangul, Hiragana, Cyrillic, Hebrew, Thai, Devanagari) → `script_override`.
5. Otherwise run `langdetect` on the IFB-stripped probe text.
6. A **random reservoir of 8,000** keyword tweets from the full **1,129,607** keyword posts was detected the same way. That random sample is the **population estimate**. The stratified 2,734-row sample is biased toward rare keywords and is used for manual review and per-keyword checks.

### Stratified sample (2,734) — unweighted

| detected_lang | n | percent |
|---------------|--:|--------:|
| `en` | 1,226 | 44.84% |
| `und` | 1,027 | 37.56% |
| `no` | 83 | 3.04% |
| `af` | 69 | 2.52% |
| `ja` | 56 | 2.05% |
| `fr` | 45 | 1.65% |
| `nl` | 39 | 1.43% |
| `es` | 30 | 1.10% |
| `tr` | 26 | 0.95% |
| `de` | 18 | 0.66% |
| `id` | 15 | 0.55% |
| `et` | 14 | 0.51% |
| `it` | 14 | 0.51% |
| `pt` | 10 | 0.37% |
| `so` | 10 | 0.37% |
| `ca` | 9 | 0.33% |
| `da` | 9 | 0.33% |
| `tl` | 6 | 0.22% |
| `sv` | 5 | 0.18% |
| `ro` | 5 | 0.18% |
| `cy` | 4 | 0.15% |
| `pl` | 3 | 0.11% |
| `vi` | 3 | 0.11% |
| `hi` | 2 | 0.07% |
| `ar` | 2 | 0.07% |
| `hu` | 1 | 0.04% |
| `ko` | 1 | 0.04% |
| `zh` | 1 | 0.04% |
| `fi` | 1 | 0.04% |

### Detection status (stratified sample)

| status | n |
|--------|--:|
| ifb_dominated | 1,027 |
| detected | 1,474 |
| low_confidence | 191 |
| script_override | 42 |

### Random keyword sample — estimated distribution of 1,129,607 keyword tweets

| detected_lang | n in sample | estimated % | note |
|---------------|------------:|------------:|------|
| `und` | 3,633 | 45.41% | mostly ifb_dominated / undetectable, not English |
| `en` | 3,043 | 38.04% | English after IFB strip |
| `no` | 248 | 3.10% | translation required later |
| `fr` | 204 | 2.55% | translation required later |
| `ja` | 174 | 2.17% | translation required later |
| `af` | 135 | 1.69% | translation required later |
| `nl` | 125 | 1.56% | translation required later |
| `tr` | 72 | 0.90% | translation required later |
| `ca` | 59 | 0.74% | translation required later |
| `de` | 45 | 0.56% | translation required later |
| `es` | 35 | 0.44% | translation required later |
| `id` | 35 | 0.44% | translation required later |
| `it` | 29 | 0.36% | translation required later |
| `so` | 25 | 0.31% | translation required later |
| `da` | 21 | 0.26% | translation required later |
| `sv` | 20 | 0.25% | translation required later |
| `et` | 19 | 0.24% | translation required later |
| `pt` | 13 | 0.16% | translation required later |
| `ar` | 10 | 0.12% | translation required later |
| `fi` | 7 | 0.09% | translation required later |
| `ro` | 6 | 0.07% | translation required later |
| `tl` | 6 | 0.07% | translation required later |
| `cy` | 5 | 0.06% | translation required later |
| `sw` | 5 | 0.06% | translation required later |
| `vi` | 4 | 0.05% | translation required later |
| `sl` | 4 | 0.05% | translation required later |
| `hr` | 3 | 0.04% | translation required later |
| `hi` | 3 | 0.04% | translation required later |
| `sq` | 3 | 0.04% | translation required later |
| `sk` | 3 | 0.04% | translation required later |
| `zh` | 3 | 0.04% | translation required later |
| `ur` | 2 | 0.03% | translation required later |
| `ru` | 1 | 0.01% | translation required later |

**Do not treat `ifb_dominated` as English.** Those posts are mostly collection templates; langdetect would often label the raw string `en` because the template words are English.

**langdetect false friends (manual spot-check):** ISO codes `no`, `af`, `ca`, `so`, `cy`, and often `nl` were assigned to English IFB hashtag spam (e.g. `#follow4follow`, “I’ll follow you back”). Those are **not** reliable translation targets. Script-confirmed Japanese/Arabic/Chinese/Hindi in the random sample is only about **2.4%** (`ja` 174, `ar` 10, `zh` 3, `hi` 3, plus tiny `ur`/`ru`).

**Practical translation volume for keywords (use this, not the raw 16.55%):**

| Estimate | Share of keyword tweets | ~N of 1,129,607 |
|----------|------------------------:|----------------:|
| Upper bound (`translation_required` as coded) | 16.55% | ~186,950 |
| Conservative (non-Latin script + clear ja/ar/zh/hi) | ~2.4% | ~27,000 |
| Recommended next: review `keyword_language_examples.csv` then translate only script-confirmed + high-confidence `fr`/`es`/`pt`/`tr`/`de`/`id` | likely **3–8%** | ~34k–90k |

Do **not** bulk-translate `no`/`af`/`ca`/`so`/`cy`.

## Which posts require translation

| Group | Rule | This phase |
|-------|------|------------|
| Timeline `LANG=en` | Already English | No translation |
| Timeline `und`,`qme`,`qam`,`zxx` | Not languages | **Do not translate**; exclude from NLP |
| Timeline other codes (`es`,`ja`,…) | Real languages | **Translation required** later (batch 500) |
| Keyword `detected`/`script_override` and not `en` | Real non-English | **Translation required** later |
| Keyword `already_english` | Detected English with enough tokens | No translation |
| Keyword `ifb_dominated` / uncertain | No reliable language | **Do not translate** until reviewed |

Estimated keyword tweets needing translation as **coded by the script** (non-`en`, non-`ifb_dominated`): **16.55%** (~186,950). After false-friend review, **do not translate that full set**. Use the conservative / recommended bands above.

Timeline (already counted in the corpus, not re-detected): English 78.2% (no translation); non-linguistic 10.0% (exclude); other languages 11.8% (translation required, using Twitter `LANG` which is more reliable than langdetect on IFB spam).

`text_translated_en` is stored as empty in this phase. Original text is always preserved.

## Which posts are excluded from NLP and why

| nlp_status | Meaning |
|------------|---------|
| retain | Eligible for sentiment/emotion (and topics if `topic_text` has ≥3 tokens) |
| retain_sentiment_exclude_topics | English/IFB leftovers too thin for BERTopic |
| hold_for_translation | Wait until Phase 2.1 translation |
| exclude_non_linguistic | Timeline `und/qme/qam/zxx` |
| exclude_ifb_boilerplate | No language left after IFB strip |
| exclude_too_short | `< 3` tokens after `clean_text` |
| exclude_uncertain_language | Detector failed or `und` |
| exclude_empty | Empty original |

Stratified keyword sample NLP statuses:

| nlp_status | n |
|------------|--:|
| exclude_ifb_boilerplate | 1,027 |
| retain | 1,106 |
| hold_for_translation | 481 |
| retain_sentiment_exclude_topics | 118 |
| exclude_too_short | 2 |

Records processed in this phase (not the full 39M):

| Set | Processed | Retained for later English NLP (`retain` + `retain_sentiment_exclude_topics`) |
|-----|----------:|----------------------------------:|
| Stratified keyword sample | 2,734 | 1,224 |
| Random keyword sample | 8,000 | 3,038 |
| Timeline working sample | 4,779 | 3,177 |
| **Total working rows written** | 15,492 | 7,428 |

Full corpus still lives only in `data/analysis_corpus.db`. Cleaning functions are applied to working samples so later stages can reuse the same code on chunks.

## Duplicate / boilerplate IFB text

Normalized duplicate key: lowercase, URLs/mentions/emojis removed, whitespace collapsed.

| Corpus slice | Exact extra rows | Duplicate groups |
|--------------|-----------------:|-----------------:|
| Stratified keyword sample (2,734) | 184 | 105 |
| All keyword tweets hashed (1,129,607) | 831,377 | 36,381 |

Top normalized templates in the stratified sample:

| copies | text preview |
|-------:|--------------|
| 7 | 'Follow for follow back 💙\nFollow for follow back 💙\n@saltion01 @saltion01 @salt |
| 7 | "@MlayJackson1 . Drop your handle let's follow you we follow back quickly @Alqui |
| 7 | '#IFollowAll         ?             #Follow4Follow          ?' |
| 6 | "@MlayJackson1 Drop your handle let's follow you I follow back quickly @mlayjack |
| 6 | '相互フォローを希望する方の支援を目的としたアカウントです。リツイート機能でご紹介いただけると幸です。#followme#sougofollow #follow |
| 6 | "@F_rida_h Breaking News!  If we're not following each other You just gained one |
| 5 | "N'oublier pas de follow direct @alexcreationpsd si vous voulez que je vous foll |
| 5 | '@F_rida_h Follow for follow back 💙\nFollow for follow back 💙\n@saltion01 @salti |

These templates should not drive topics. `topic_text` is designed to empty them out.

## How IFB / follow terms were removed for topic modeling

`clean_text` (sentiment/emotion): lowercase; drop URLs, @mentions, emojis, punctuation; keep hashtag tokens without `#`; drop English stopwords (NLTK, 198 words); **Porter stem**. Collection words such as “follow” are **kept** here because they are the tweet content.

`topic_text` (BERTopic later): the same steps, **plus**:

1. Phrase deletion (longest first), including: follow me and i will follow you, follow me and i follow you, following all that follows, following whoever follows, follow for follow back, follow for follow, i follow you back, drop your handle, …
2. Token deletion of the collection lexicon (42 tokens), including: f4f, ff, fff, follow, follow4follow, followback, followbacks, followdaibosyu, followed, follower, followers, followforfollow, followforfollowback, followfriday, following, followme, followmeandifollowyou, follows, followtrain, followtrick, gain, gains, gaintrain, ifb, ifbdrive, ifbs, ifollowall, ifollowback, ifollowyouback, l4l, like4like, likeforlike, refollow, rt, s4s, sougofollow, sub4sub, teamfollowback, unfollow, unfollowed, …
3. Hashtags whose token is in that lexicon (`#ifb`, `#followforfollow`, `#f4f`, …)

Original text is never overwritten.

## Preprocessing examples

See `outputs/preprocessing_examples.csv` (36 before/after rows) and `outputs/keyword_language_examples.csv` (120 curated review rows; ≥100).

## Limitations and likely detector errors

- Short IFB English templates are labeled `ifb_dominated`, not `en`. That is intentional.
- Mixed tweets (French/Japanese + English “follow back”) may still be classified as the majority remaining script or as `en` if many English words survive.
- `langdetect` is unstable on very short strings; seed 2026 makes this run reproducible but not perfectly accurate.
- Indonesian (`id`/`in`) vs English confusion is possible on Latin-alphabet spam.
- Keyword population percentages are **estimates from 8,000 random posts**, not a full 1.13M detection pass.
- Timeline language uses Twitter `LANG` from the corpus; this phase does not re-detect timeline text.
- Porter stemming is crude (`follow` → `follow` already; `following` → `follow`). It is deterministic and does not need a POS tagger.
- No Google Translate / googletrans calls were made.

## Next phase (not done)

Translate only `translation_status = translation_required` rows, in batches of 500, after reviewing `outputs/keyword_language_examples.csv`. Then run sentiment on English + translated text, never on `und/qme/qam/zxx`.
