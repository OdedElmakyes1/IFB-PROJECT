# Topic modeling (BERTopic) and topic sentiment

Built: 2026-09-11T18:30:26Z
IFB.db was not opened. Sentiment, emotion, and event detection were not rerun.
Random seed: **2026**.

## Corpus and sampling

| Item | N |
|------|--:|
| English-ready NLP posts ⋈ `post_sentiment` | **742,942** |
| Usable `topic_text` (≥3 tokens) | **638,916** |
| Assigned outlier without embedding (short/empty `topic_text`) | **104,026** |
| Tune / final-fit sample (stratified by source×year) | **64,000** |
| Remaining usable docs transformed in batches of 4,096 | **574,916** |

Keyword posts are a **census** of eligible IFB tweets (weight=1). Timeline posts are a **stratified sample** of English timeline history; `sample_weight` estimates that population. They are never mixed into one unlabeled population total.

## Preprocessing and IFB-token removal

BERTopic reads `topic_text`, not `clean_text`. `topic_text` already lowercases, strips URLs/mentions/emojis, removes IFB collection phrases, drops IFB tokens (`ifb`, `follow`, `f4f`, `followback`, …), drops stopwords, and Porter-stems. The vectorizer adds those tokens to `stop_words` again. No topic is named IFB or follow-for-follow.

## Experiments

| Config | embed | min_size | nn | nc | ngram | reduce | topics | outlier% | c_v | diversity | sec | decision |
|--------|-------|--------:|---:|---:|-------|--------|------:|---------:|----:|----------:|----:|----------|
| C1_min40_nn15_nc5_uni | all-MiniLM-L6-v2 | 40 | 15 | 5 | 1-1 | 0 | 183 | 48.64 | 0.5273 | 0.6419 | 130.2 | rejected |
| C2_min50_nn15_nc5_uni | all-MiniLM-L6-v2 | 50 | 15 | 5 | 1-1 | 0 | 144 | 51.42 | 0.501 | 0.6568 | 96.9 | rejected |
| C3_min80_nn15_nc5_uni | all-MiniLM-L6-v2 | 80 | 15 | 5 | 1-1 | 0 | 94 | 53.53 | 0.4677 | 0.7437 | 96.9 | rejected |
| C4_min50_nn10_nc5_uni | all-MiniLM-L6-v2 | 50 | 10 | 5 | 1-1 | 0 | 170 | 48.7 | 0.505 | 0.6564 | 83.5 | rejected |
| C5_min50_nn30_nc5_uni | all-MiniLM-L6-v2 | 50 | 30 | 5 | 1-1 | 0 | 142 | 53.63 | 0.5128 | 0.6309 | 120.9 | rejected |
| C6_min50_nn15_nc5_bi | all-MiniLM-L6-v2 | 50 | 15 | 5 | 1-2 | 0 | 138 | 48.85 | 0.5219 | 0.6689 | 83.3 | rejected |
| C7_min50_nn15_nc8_uni | all-MiniLM-L6-v2 | 50 | 15 | 8 | 1-1 | 0 | 140 | 51.28 | 0.4924 | 0.6714 | 95.6 | rejected |
| C8_min50_nn15_reduce | all-MiniLM-L6-v2 | 50 | 15 | 5 | 1-1 | 1 | 148 | 0.0 | 0.5027 | 0.7165 | 90.9 | rejected |
| C9_l12_min50_nn15 | all-MiniLM-L12-v2 | 50 | 15 | 5 | 1-1 | 0 | 145 | 50.59 | 0.5192 | 0.6512 | 76.4 | rejected |
| C10_min200_nn15 | all-MiniLM-L6-v2 | 200 | 15 | 5 | 1-1 | 0 | 4 | 3.93 | 0.6955 | 1.0 | 241.0 | rejected |
| C11_min300_nn15 | all-MiniLM-L6-v2 | 300 | 15 | 5 | 1-1 | 0 | 4 | 4.1 | 0.6942 | 1.0 | 172.4 | rejected |
| C12_min80_reduce_nt20 | all-MiniLM-L6-v2 | 80 | 15 | 5 | 1-1 | 1 | 20 | 0.0 | 0.3887 | 0.82 | 122.5 | rejected |
| C13_min50_nn30_reduce_nt24 | all-MiniLM-L6-v2 | 50 | 30 | 5 | 1-1 | 1 | 24 | 0.0 | 0.4353 | 0.8208 | 193.1 | selected |
| C14_min150_reduce | all-MiniLM-L6-v2 | 150 | 15 | 5 | 1-1 | 1 | 5 | 0.0 | 0.7245 | 0.88 | 132.1 | rejected |
| C15_min200_reduce_nt18 | all-MiniLM-L6-v2 | 200 | 15 | 5 | 1-1 | 1 | 4 | 0.0 | 0.7417 | 1.0 | 147.0 | rejected |

## Why the final configuration was selected

Selected **C13_min50_nn30_reduce_nt24** (c_v=0.4353, `nr_topics=24` after `reduce_outliers` + `reduce_topics`, 0.0% outliers on the 64k tune sample). The rule is **not** “highest c_v”: C10/C11/C14/C15 scored 0.69–0.74 but collapsed to 4–5 mega-clusters that cannot be named; C1–C9 had 94–183 topics and ~50% outliers (except C8, which zeroed outliers but still had 148 topics). Remaining interpretable rows (about 18–24 topics, low outlier share) are ranked by c_v + 0.35×diversity. C13 beats C12 on coherence (0.44 vs 0.39) with a similar readable topic count. The green bar in `coherence_plot.png` is therefore not the tallest bar.

### How many topics there are (configured vs final)

`nr_topics = 24` is the **C13 parameter**, not the shipped result. After transform, six follow-spam clusters were merged into the outlier bucket rather than named IFB / follow-for-follow.

| Quantity | Value | Meaning |
|----------|------:|---------|
| Configured topic count (`nr_topics`) | **24** | BERTopic parameter of run C13 |
| Follow-spam clusters merged by hand | **6** | IDs 3, 5, 18, 20, 22, 23 folded into −1 |
| **Final named topics** | **18** | The number reported in the Word report and the slides |
| Outlier bucket | **1** | `topic_id = −1` |
| Distinct `topic_id` values / `final_topics.csv` rows | **19** | 18 named + −1 |
| Posts in −1 | **171,543 (23.09%)** | Mix of original HDBSCAN outliers **and** the six merged spam clusters |

The 15-configuration table above is the full experiment record (`outputs/bertopic_experiments.csv`). It is also embedded in `report/final_project_report.docx` §9. BERTopic was **not** refit for this documentation pass.

Final model pickle: `topic_model.pkl` (480 MB; excluded from the upload). After transform, leftover follow-spam stems (`followbot`, `getrekt`, `folloforfolloback`) were **merged into -1** rather than named IFB / follow-for-follow. 294,595 transform-outliers with usable `topic_text` were assigned to the nearest non-spam topic (cosine ≥ 0.28). Topic IDs live in SQLite `post_topic` (same grain as `post_sentiment`); there is no 742k-row assignment CSV.

## Topics

| ID | Name | N | % | keyword | timeline | words |
|---:|------|--:|--:|--------:|---------:|-------|
| 0 | Twitter chatter, retweets, and livestreams | 183189 | 24.6572 | 62870 | 120319 | retweet, like, twitter, tweet, twitch, live, happi, game, day |
| 1 | Trump / voting talk mixed with music promo | 79454 | 10.6945 | 27735 | 51719 | trump, video, music, vote, work, like, song, get, love |
| 4 | Please-DM / help requests | 70757 | 9.5239 | 20785 | 49972 | dm, us, pleas, thank, jungkook, help, assist, book, hi, email |
| 2 | Everyday conversation | 34772 | 4.6803 | 11154 | 23618 | back, go, like, know, one, let, get, say, pleas, dey |
| 6 | Sports (NBA / NFL) | 34405 | 4.6309 | 17544 | 16861 | game, team, play, win, coach, nba, season, let, year, nfl |
| 8 | Football mixed with flat-earth chatter | 23721 | 3.1928 | 8759 | 14962 | beauti, earth, flat, block, flatearth, much, chelsea, goal, player, pm |
| 7 | Faith and prayer | 23632 | 3.1809 | 8866 | 14766 | thank, account, god, back, much, pray, good, bless, prayer, great |
| 9 | Instagram photography hashtags | 21219 | 2.8561 | 9141 | 12078 | money, photographi, photo, photooftheday, instagood, instagram, instalik, picoftheday, lov |
| 15 | Dogs and city chatter | 17880 | 2.4066 | 5643 | 12237 | dog, steph, toronto, wednesday, fan, pleas, fast, js, morn |
| 11 | Digital marketing hashtags | 14506 | 1.9525 | 4778 | 9728 | namasteui, read, internetmarket, digitalmarket, busi, socialmediamarket, contentmarket, gu |
| 14 | Nigeria talk and Pokémon GO coordinates | 13486 | 1.8152 | 3393 | 10093 | nigeria, nigerian, africa, coord, cp, hundo, level, april, boost |
| 13 | Giveaways and contests | 11626 | 1.5649 | 5429 | 6197 | giveaway, winner, appreci, win, enter, tag, octob, retweet, spin, like |
| 10 | Arguments about truth and lying | 11268 | 1.5167 | 2808 | 8460 | peopl, lie, truth, know, like, automat, think, say, never, see |
| 16 | Templated ‘every minute’ / kindly spam | 9007 | 1.2123 | 2930 | 6077 | liter, info, kindli, everi, news, barnyard, oti, help, minut, back |
| 17 | Crypto / NFTs | 7453 | 1.0032 | 1542 | 5911 | nft, nftcommun, nobodi, nftcollector, nftart, nftartist, opensea, eth, collect, drop |
| 12 | COVID vaccines and Instagram identity hashtags | 7008 | 0.9433 | 2992 | 4016 | covid, vaccin, gay, proud, instaboy, instagay, instadaili, instalov, selfi, infect |
| 21 | K-pop (BTS / Jimin) | 6132 | 0.8254 | 691 | 5441 | jimin, ost, chart, jimin_fac, bt, 지민, soloist, jimtob, debut, come |
| 19 | China and climate change | 1884 | 0.2536 | 183 | 1701 | chang, china, would, climat, like, thing, way, see, happen, name |
| -1 | Outliers / too little topic signal | 171543 | 23.0897 | 46974 | 124569 |  |

## Representative tweets (manually inspected)

Names come from c-TF-IDF stems **and** original tweets that overlap those stems, after dropping IFB/follow hashtag walls. Nearest-topic reassignment inflated some clusters, so a random tweet from a large topic is not always on-theme; the rows below are the inspected matches.

**Topic 0 — Twitter chatter, retweets, and livestreams**
- Rule #2 There is so much noise and crap on Twitter people are selective as to what they want in their timeline. So clean up your page before you follow people because 35-50% of users check your page for the kind of tweet
- Can we all just reply to follow for follow tweets with "No can do. I'm into real networking" or something like that. Im sick of seeing these tweet flood my twitter!

**Topic 1 — Trump / voting talk mixed with music promo**
- @adamlevitan 2016: VOTE FOR ME AND I'LL BRING BACK COAL + MANUFACTURING!!! trump runs the ship into an iceberg and our ghosts wander the bottom of the ocean for eternity 2019: *sea demon wanders up* FOLLOW ME DOWN THIS M
- @NewYorkTimes reports Trump pays $750 in taxes Who's paying America's bills? We are. It’s time we Stand For Better. Stand for #BidenHarris2020. Follow-retweet-comment The premiere of our latest video: #DonTheBilker https

**Topic 4 — Please-DM / help requests**
- @LLCOOL_D Hi Leon, thanks for contacting ESPN. Apologies for the trouble. Please follow us back and send us DM us, so we can assist you further. We will need a link to the league in question, so we can help you out. ~DS
- @white_haydon Hi Haydon, sorry for the delayed reply, as we have been busy trying to follow up with the high volume of player contacts. If you are currently experiencing an issue downloading Modern Warfare, please send u

**Topic 2 — Everyday conversation**
- @gainbtsmuttuals Follow every one who likes your comment then they will follow you back in return. No cheating. Let's go!✌
- Man. My only escape from bitching and complaining was going to work for 10 hrs in 100 + whatever degrees. Only to come back home to it….ima stop there before I get started. Everyone entitled to bad days but 1 after anoth

**Topic 6 — Sports (NBA / NFL)**
- Need a Basketball Handicapper? Follow us and you'll need need another one ever again! What have we done for you lately? Last 3 Days: 11-6 +$5,150 at $1K/Game WINNING STREAKS: #NBA Plays: 19-8 last 27 #NHL Plays: 25-10 la
- With the drive to win the #StanleyCup two years in a row, the Bolts have made a name for themselves — even the White House is Team Lightning ⚡️ Follow this 🧵 to prep before Game 2 tonight. #GoBolts https://t.co/ClKzclvgx

**Topic 8 — Football mixed with flat-earth chatter**
- @jaysonstreet Looking out with wonder and excitement for earth’s beauty?
- @Stray_Kids Thank you so much for giving us so amazing performances and content in this comeback!! Thank you for working so hard our skz!! This comeback will be unforgettable!! All the memories that we made together were

**Topic 7 — Faith and prayer**
- @ElPasoTom Thank you for the follow, I just followed you back. From one brother in blue to another, thank you for your service, God Bless you.
- @POTATO_INMYASS @Meta Biggest bum ever! I deleted that shit and ain’t going back. Go figure that outage happened, they sold our data and some asshat the next day tried to hack my fidelity account the next day. Thanks #Me

**Topic 9 — Instagram photography hashtags**
- RT @KatanaHugo: Your owl for tonight! #photos #photography #birds #owls https://t.co/x77Wqklk7W
- Drone filming/photography is already a big business, and is only going to get bigger. Particularly as the creator economy shows no sign of slowing - all those tiktokers and youtubers and instagram models need camerapeopl

**Topic 15 — Dogs and city chatter**
- ☕️☕️☕️Wednesday Morning Very Early Gains Time🏸🏸🏸Follow all RT's and STEPH for a quick follow back
- @onlyforgreys69 @MIFarmSB @CalltoActivism Thank you for reading all the detail and coming to the conclusion that “just throwing something” would have deescalated the entire situation, thus saving the dogs life. Delusiona

**Topic 11 — Digital marketing hashtags**
- @robertalives @jimaggie93 Noah @ 12 weeks read his story only. So tell me this is not a baby. https://t.co/UagcfWcjXa
- The marketing funnel misses the point. Check out @KlientBoost's blog post to see why your strategy needs a serious update so you can reach new customers AND retain existing customers. https://t.co/m1YTOXpZjd #DigitalMark

**Topic 14 — Nigeria talk and Pokémon GO coordinates**
- RT @DejiAdesogan: One of the brightest of the Nigerian Army, #Nigeria’s Former Counter Insurgency Commander, Chief of Operations &amp; Training…
- RT @EmirSirdam: Dear Nigerian Judiciary The only anarchy that is bound to befall Nigeria is when the Tribunal Justices rule on ‘technicali…

**Topic 13 — Giveaways and contests**
- #PrisonGames 2/2023 #GIVEAWAY Each 10 Retweets =+1 WINNER! 🏆 Ends 03.02.23 🎉 To Enter: 1⃣ Like ♥️ &amp; Retweet🔁this post 2⃣ Follow @PrisonGames_ &amp; @GameDev_Freak 3⃣ Tag friends 🤼‍♀️🤼 4⃣ Comment a game you want to wi
- 🐯TREASURE ISLAND GIVEAWAY🐯 1 winner will win a pass for 15 mins of unlimited trips to Odd Eye Treasure Island! To Enter 🌿Retweet this tweet! 🌿 Follow me + @dvwnic 🌿Tag a Friend / Reply with a Gif! Ends in 24 hours! GOOD 

**Topic 10 — Arguments about truth and lying**
- I like how people disagree with guesses. Okay. You don't think my guess is correct. That's fine. Your guess might be right. That's fine too. We won't know until it's over.
- I can’t explain why, but knowing what people look like in real life and seeing them catfish on social media makes me wanna vomit

**Topic 16 — Templated ‘every minute’ / kindly spam**
- Every 15 minutes a person of color in Arkansas is bullied by Otis from Back at the Barnyard. You can help by tweeting at Trixie Mattel. Follow a BTS stan account for more info on this incredibly troubling news. ((image))
- Every 45 minutes a person of color in Alabama is bullied by a Nigerian Prince. You can help by standing up for them. Follow Wayne's World for more info on this incredibly disheartening news. ((image))

**Topic 17 — Crypto / NFTs**
- #NFTartists, Let me see some @opensea #NFTs!🤩🤙 I want to give someone their FIRST SALE!🥳 🔥Like &amp; Retweet 🔥Follow 🔥Drop your link or someone else's below! (Tag someone waiting for their FIRST SALE!) I'd Rather Give Ba
- RT @HYPEALIENS: Who wants WL? Just RT + Follow 🔥 #NFTCommunity #NFTdrop #NFTartist #nftcollector #NFT https://t.co/sHj3SkzRNj

**Topic 12 — COVID vaccines and Instagram identity hashtags**
- @raywert @uTobian @scottsantens @billmaher He's not talking solely about the Covid shots. It's the definition that's the problem. He needs to clarify what he means by 'placebo'. Most people think of an inert substance li
- What's really perplexing is both extremes fail to deal with reality. China the most restrictive nation on the planet couldn't "restrict" COVID out of existence. Living with COVID is a fact of life. Period. Vaccines have 

**Topic 21 — K-pop (BTS / Jimin)**
- RT @chartdata: #AgustD's 'D-DAY' ties #JIMIN's 'FACE' as the highest charting album by a Korean soloist in Billboard 200 history (US). http…
- RT @billboardcharts: Debuts on this week's #WorldAlbums chart: No. 1, #Jimin FACE No. 5, @NMIXX_official Expérgo No. 8, @BABYMETAL_JAPAN T…

**Topic 19 — China and climate change**
- It sounded like ‘Climate Change is Real…’ https://t.co/4PpQFuYiRC
- @LabordeSheila @Lorraine0164 I wonder if climate change will keep me from freezing my but off this winter. God I hope so. Run the hell out of those V8's.

## Outliers

Topic **-1** is **171,543 / 742,942 = 23.1%** of the analysis file:

- **104,026 (14.0%)** never entered BERTopic: `topic_text` shorter than 3 tokens after IFB/follow stripping.
- The rest are residual unclustered posts, plus six small follow-spam clusters that were merged into -1 so they would not become a named “IFB” topic.
- On the tune sample, C13’s `reduce_outliers` reached 0%. Transforming the other ~575k docs still left many HDBSCAN outliers; those with usable text were mapped to the nearest non-spam topic when cosine ≥ 0.28.

That share is above the informal 10% wish, but it is reported rather than hidden. Most of it is short IFB-stripped text, not a mystery cluster.

## Topic sentiment

Positive / **neutral** / negative are counted separately (raw counts in `topic_sentiment_distribution.csv`). Neutral dominates every large topic (typically 65–75%), shown as **yellow** in `topic_sentiment_visualization.png` (green = positive, red = negative). Sports and faith are relatively less negative; the mixed football/flat-earth cluster has a large positive slice because many posts are cheer/hashtag stacks rather than arguments. Keyword vs timeline splits are in `topic_sentiment_by_source.csv`. Timeline `n_weighted` / `w_*` columns estimate the English timeline **population inside that topic only**. Keyword rows use weight=1 (census). Do not add the two sources into one unlabeled population total.

## Keyword vs timeline

Keyword posts were collected on IFB strings, so even after stripping, leftover language is often greetings, politics, and self-promo. Timeline posts are ordinary user history and usually dominate larger topical clusters. Do not read a keyword-heavy topic as “what IFB users tweet about all day” without the timeline split.

## Limitations

- Timeline is ~1.7% of English timeline (seed 2026); topic mix is sample-dependent.
- Keyword language labels are rule-based, not Twitter LANG.
- Duplicate/boilerplate IFB templates were dropped before this corpus existed; that removes tautological ‘follow’ topics on purpose.
- `topic_text` is stemmed, so c-TF-IDF words look clipped (`pleas`, `happi`, `vaccin`); names were set from representative **original** tweets plus those terms.
- Nearest-topic assignment of transform-outliers mixed some loosely related posts into large clusters; names follow dominant terms, not every member.
- No conversation IDs or follower graph, so topics are bags of posts, not diffusion paths.
- Combined keyword+timeline percentages describe the analysis file, not one social-media population.

## Topic over time (existing assignments; BERTopic not rerun)

`outputs/topic_over_time_monthly.png` plots monthly shares of the six largest named C13 topics from the stored `post_topic` table. Keyword and timeline are separate panels. Dashed labeled lines mark E01–E04 (correlation, not causation). Numeric series: `outputs/topic_over_time_monthly.csv`. BERTopic was not refit.

## Output checklist

| File | Present |
|------|---------|
| `src/topic_modeling.py` | yes |
| `notebooks/topic_modeling.ipynb` | yes |
| `outputs/bertopic_experiments.csv` | yes |
| `outputs/coherence_scores.csv` | yes |
| `outputs/coherence_plot.png` | yes |
| `outputs/final_topics.csv` | yes |
| `outputs/topic_representative_tweets.csv` | yes |
| `outputs/topic_distribution.csv` | yes |
| `outputs/topic_sentiment_distribution.csv` | yes |
| `outputs/topic_sentiment_by_source.csv` | yes |
| `outputs/topic_sentiment_visualization.png` | yes |
| `outputs/topic_over_time_monthly.png` | yes |
| `outputs/topic_over_time_monthly.csv` | yes |
| `outputs/topic_model.pkl` | yes |
| `TOPIC_MODELING_REPORT.md` | yes |
