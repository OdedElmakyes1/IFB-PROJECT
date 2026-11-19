# Named entity recognition and entity sentiment

Built: 2026-09-12T04:34:10Z
IFB.db was not opened. Sentiment, emotion, event detection, and BERTopic were not rerun.
Random seed: **2026** (not used for the NER model; extraction is deterministic given spaCy).

## NER model

Library: **spaCy 3.8.14**. Pipeline: **`en_core_web_lg` 3.8.0** (OntoNotes 5 labels).
Course text lists HuggingFace / BERTweet / LLM. BERTweet is the sentiment model already used; public HuggingFace CoNLL-03 NER only has PER/ORG/LOC/MISC and would drop EVENT, NORP, FAC, PRODUCT, and the GPE vs LOC split. `en_core_web_lg` is the best installed spaCy-compatible English model with those labels. GPU was available but this CNN model runs on CPU (`tok2vec` + `ner` only).
Input column: **`original_text`**, never Porter-stemmed `clean_text` / `topic_text`.

## Volume

| Item | N |
|------|--:|
| English-ready posts ⋈ `post_sentiment` ⋈ `post_topic` | **742,942** |
| Raw entity occurrences (target labels) | **777,249** |
| Kept after cleaning | **642,041** |
| Dropped | **135,208** |
| Distinct cleaned (canonical, category) pairs | **256,491** |
| Extract runtime (this process) | 0 sec |

Keyword posts are a census (weight=1). Timeline `sample_weight` is used only for timeline population estimates inside an entity, never as a model-scoring weight.

## Filtering rules

Kept spaCy labels: PERSON, GPE, LOC, ORG, EVENT, NORP, FAC, PRODUCT. Dates, money, percents, and cardinals were not extracted.
Dropped: empty; one-character; numeric-only; punctuation/emoji/symbol-only including **`&`**; URL-like; `@username`; IFB/follow tokens; generic PERSON shells (god, lord, bro, …). Hashtag `#` is stripped before matching. Unicode NFKC, HTML unescape, apostrophe folding.
Course guideline “drop length <3” **is now applied** to the graded cleaned and network outputs. `entities_cleaned.csv` has **255,139** rows after removing **1,352** two-character names (`CW`, `VN`, `EU`, `IG`, `Un`, `AI`, …), preserved in `outputs/entities_dropped_short.csv`. Those tokens are also gone from the co-occurrence graph. The trade-off is stated: legitimate short acronyms (`EU`, `UN`, `US`, `UK`, `NY`) are lost along with the junk. `entities_extracted.csv` remains the unfiltered extraction record. Frequency=1 entities stay in the cleaned CSV (`singleton_flag=1`) so “all entities” files are complete; they are excluded from the bar charts. NER was **not** rerun for this filter — it is applied to the already-extracted table.

Drop reasons:

- `kept`: 642,041
- `username_like`: 45,141
- `url_like`: 25,391
- `one_character`: 24,239
- `junk_token`: 16,514
- `junk_amp_or_symbol`: 15,099
- `punct_or_symbol`: 7,504
- `empty`: 723
- `numeric_only`: 536
- `generic_person`: 61

## Alias merging

Merges are explicit tables, not string-similarity. Different people/countries are not collapsed because names look alike (no `Jordan`→country, no `Musk` alone→Elon, no `Georgia`→the country). Examples:

| original | canonical | reason | confidence |
|----------|-----------|--------|----------:|
| US | United States | country alias / English name | 0.95 |
| Trump | Donald Trump | spaCy often tags the surname Trump as ORG | 0.88 |
| Biden | Joe Biden | distinctive surname in this period | 0.92 |
| twitter | Twitter | platform name, not a person | 0.95 |
| UK | United Kingdom | country alias / English name | 0.95 |
| America | United States | country alias / English name | 0.95 |
| Covid | COVID-19 | COVID surface tagged as PERSON/PRODUCT/ORG | 0.93 |
| Putin | Vladimir Putin | distinctive surname | 0.93 |
| USA | United States | country alias / English name | 0.95 |
| FB | Facebook | abbreviation | 0.8 |
| JUNGKOOK | Jungkook | BTS stage name | 0.95 |
| Obama | Barack Obama | distinctive surname | 0.93 |
| instagram | Instagram | platform name, not a person | 0.95 |
| UMAR RIAZ | Umar Riaz | identity (no merge) | 1.0 |
| stan | Stan | identity (no merge) | 1.0 |
| GB | United Kingdom | uppercase ISO-3166 alpha-2 | 0.88 |
| jungkook | Jungkook | BTS stage name | 0.95 |
| Britain | United Kingdom | country alias / English name | 0.95 |

Full table: `outputs/entity_alias_mapping.csv`.

## Person vs country

PERSON stays person even if the string is also a place name. GPE/LOC become **country** only after an allowlist of English names / ISO codes. Cities and regions stay **location**. Ambiguous GPE strings (Georgia, Jordan, Chad, Mali, Niger, Guinea) are **not** forced into the country chart.

Cleaned category counts: organization=110,078, person=107,478, location=16,281, product=8,737, facility=5,621, norp=5,031, event=3,189, country=76.

## Sentiment methodology

Each mention inherits `sentiment_label` and the three probabilities from `post_sentiment` for that `(source, tweet_id)`. We do not rescore text. Unique-post counts are used for positive / **neutral** / negative so a tweet that repeats a name does not triple its vote. Mention totals are stored separately. Average probabilities are means over unique posts. Green / yellow / red match the rest of the project.

Person chart: top 10 PERSON entities with **≥ 50 unique posts** (unweighted analysis-file mix), sorted by unique posts. Promo fragments (`Drop`, Italian offer copy, `Follow Wayne's`) and generic single tokens (`Joe`, `Jack`) stay in the all-entity CSVs but are excluded from the bar so the figure is interpretable.
Country chart: top 10 canonical countries with **≥ 25 unique posts**, same colors, same sort.

### Top people (unique posts)

| Entity | posts | +% | neu% | −% |
|--------|-----:|---:|-----:|---:|
| Donald Trump | 4212 | 5.32 | 58.83 | 35.85 |
|  |  |  |  | _How true this statement us. God is our only hope but God have us Trump for a reason. Together they will lead but we must follow!_ |
| Joe Biden | 2910 | 5.88 | 66.56 | 27.56 |
|  |  |  |  | _Trump is far too busy to follow you back and care about you. I hear all the time. But I see he has plenty of time to talk bad about actors and singers. Bette Mi_ |
| Jungkook | 1543 | 19.18 | 79.59 | 1.23 |
|  |  |  |  | _4 Moments When BTS’s Jimin Cared For Jungkook Follow Us on @iwmbuzz #BFF #BTS #BTSBoyband #Jimin #Jungkook #kpop https://t.co/KTsN36PC9c_ |
| Jesus | 931 | 16.86 | 69.39 | 13.75 |
|  |  |  |  | _#New #ChristianLife #Christians #Disciples #FollowersOfJesus #Jesus #Christ #Bible #God https://t.co/7anFhKkFgQ Jesus' disciples will ONLY follow Him: “The shee_ |
| Vladimir Putin | 673 | 3.42 | 57.21 | 39.38 |
|  |  |  |  | _Republicans are owned by Putin, not only Trump! We have every reason to believe they’re #traitors under bribery! #FBR party Join me 1. Like❤️ 2. Follow👍🏽 3. Ret_ |
| Elon Musk | 467 | 6.64 | 78.8 | 14.56 |
|  |  |  |  | _Elon Musk: Humanity Is a Kind of 'Biological Boot Loader' for AI [Follow us for more #Technews] https://t.co/fqTf7Bfzfy_ |
| Jimin | 391 | 24.81 | 74.17 | 1.02 |
|  |  |  |  | _Drop your fave photos of JIMIN here! Follow me and I'll follow you back!💖 And don't forget to use this tag! Let's vote more! We can do it!!!💖💖💖🎉 #BBMAsTopSocial_ |
| Messi | 372 | 30.91 | 63.71 | 5.38 |
|  |  |  |  | _Am about to hit 1000 followers.💥💥 Abeg help a brother to follow, and I will follow you back ehn.🙏🙏🙏 Good morning my beautiful people. God of Ronaldo and Messi s_ |
| Barack Obama | 310 | 12.26 | 58.39 | 29.35 |
| Peter Obi | 290 | 7.59 | 83.45 | 8.97 |
|  |  |  |  | _@EdogaChux been retweeting almost all your Peter Obi tweets and still waiting to follow you back ASAP when you do the needful. Proudly ObiDient._ |

### Top countries (unique posts)

| Entity | posts | +% | neu% | −% |
|--------|-----:|---:|-----:|---:|
| United States | 5809 | 12.95 | 65.09 | 21.97 |
| United Kingdom | 2180 | 13.21 | 72.8 | 13.99 |
| India | 1291 | 13.09 | 78.31 | 8.6 |
| Ukraine | 1255 | 3.67 | 69.08 | 27.25 |
| Russia | 1140 | 2.19 | 68.07 | 29.74 |
| Israel | 1098 | 2.55 | 47.63 | 49.82 |
| Nigeria | 1066 | 11.07 | 64.35 | 24.58 |
| China | 1038 | 3.76 | 77.36 | 18.88 |
| Canada | 745 | 12.08 | 70.34 | 17.58 |
| Australia | 670 | 12.54 | 73.73 | 13.73 |

## Keyword vs timeline

`entity_sentiment_by_source.csv` splits every cleaned entity. Timeline `n_weighted` / `w_*` estimate the English timeline population mentioning that entity. Keyword rows are a census. Do not add the two frames into one unlabeled population.

## Interpretation

This is an IFB (follow-back) community sample, not a news wire. The highest-count **organizations** are platforms (Twitter, Instagram, YouTube, Facebook) plus sports leagues — that is plausible here. People are a mix of US politicians (Trump, Biden, Obama), BTS members (Jungkook, Jimin), sports (Messi), and Nigerian politics (Peter Obi). Trump/Biden/Putin have large **red** slices; K-pop and Messi are more green/yellow cheer. Israel is the most negative large country (~50% negative). Neutral still dominates because the parent sentiment file is ~71% neutral; bars are not “all yellow.”

## Limitations

- Timeline is a ~1.7% English sample (seed 2026); entity mix is sample-dependent.
- Keyword language labels are rule-based, not Twitter LANG.
- spaCy news-trained NER misfires on hashtags, handle fragments, and promo copy. Cleaning removes the worst junk; it cannot fix every wrong PERSON.
- `Trump`→Donald Trump is a documented high-confidence alias; a handful of other Trumps could be absorbed.
- Georgia/Jordan-style GPE strings were left out of the country chart rather than guessed.
- Combined keyword+timeline percentages describe the analysis file, not one social-media population.
- Entity co-occurrence network is **not** in this phase.

## Output checklist

| File | Present |
|------|---------|
| `src/ner_entity_analysis.py` | yes |
| `notebooks/ner_entity_analysis.ipynb` | yes |
| `outputs/entities_extracted.csv` | yes |
| `outputs/entities_cleaned.csv` | yes |
| `outputs/entity_sentiment_distribution.csv` | yes |
| `outputs/entity_sentiment_by_source.csv` | yes |
| `outputs/entity_alias_mapping.csv` | yes |
| `outputs/person_entities_sentiment.png` | yes |
| `outputs/country_entities_sentiment.png` | yes |
| `NER_ENTITY_ANALYSIS_REPORT.md` | yes |
