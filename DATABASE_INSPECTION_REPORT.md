# IFB.db Database Inspection Report

Read-only inspection of `IFB.db`. The full database was **not** loaded into memory. The file was **not** modified.

## Inspection environment

- Inspected at: 2026-09-11 09:50:42 UTC
- Database path: `IFB.db` (workspace root)
- File size: 11,891,314,688 bytes (11.07 GB)
- SQLite page_size: 4096
- SQLite page_count: 2903153
- Python: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
- sqlite3 library / SQLite: 3.45.1
- Connection: `file:IFB.db?mode=ro` with `PRAGMA query_only = ON`
- Elapsed: 241.49 seconds

## Workspace files verified

| File | Notes |
| --- | --- |
| `IFB.db` | SQLite database; inspected read-only |
| `IFB_database_description.docx.pdf` | Official table descriptions |
| `הנחיות פרויקט _V3_Intro_to_Social_Networks_CS_2026_Semester_B (2).pdf` | Course project guidelines |
| `Untitled0.ipynb` | Old Colab notebook (not used) |

## Schema overview

| Table | Columns | Primary key | Column types |
| --- | --- | --- | --- |
| authors | 15 | *none* | AUTHOR_ID (TEXT), REALNAME (TEXT), USERNAME (TEXT), CREATED_AT (DATETIME), DESCRIPTION (TEXT), LOACATION (TEXT), VERIFIED (BOOLEAN), PROTECTED (BOOLEAN), IMAGE_… |
| timeline | 8 | TWEET_ID | TWEET_ID (VARCHAR), AUTHOR_ID (VARCHAR), CREATED_AT (DATETIME), TWEET (VARCHAR), LANG (VARCHAR), LIKES (INTEGER), REPLIES (INTEGER), RETWEETS (INTEGER) |
| tweets | 5 | TWEET_ID | TWEET_ID (INTEGER), AUTHOR_ID (INTEGER), CREATED_AT (DATETIME), TWEET_CONTENT (TEXT), KEYWORD (TEXT) |

### CREATE TABLE `authors`

```sql
CREATE TABLE authors (
	"AUTHOR_ID" TEXT, 
	"REALNAME" TEXT, 
	"USERNAME" TEXT, 
	"CREATED_AT" DATETIME, 
	"DESCRIPTION" TEXT, 
	"LOACATION" TEXT, 
	"VERIFIED" BOOLEAN, 
	"PROTECTED" BOOLEAN, 
	"IMAGE_URL" TEXT, 
	"FOLLOWERS_COUNT" BIGINT, 
	"FOLLOWING_COUNT" BIGINT, 
	"TWEET_COUNT" BIGINT, 
	"LISTED_COUNT" BIGINT, 
	"FREELANCER" BOOLEAN, 
	"IFB_COUNT" BIGINT
)
```

### CREATE TABLE `timeline`

```sql
CREATE TABLE timeline (
	"TWEET_ID" VARCHAR NOT NULL, 
	"AUTHOR_ID" VARCHAR, 
	"CREATED_AT" DATETIME, 
	"TWEET" VARCHAR, 
	"LANG" VARCHAR, 
	"LIKES" INTEGER, 
	"REPLIES" INTEGER, 
	"RETWEETS" INTEGER, 
	PRIMARY KEY ("TWEET_ID")
)
```

### CREATE TABLE `tweets`

```sql
CREATE TABLE tweets (
	"TWEET_ID" INTEGER NOT NULL, 
	"AUTHOR_ID" INTEGER, 
	"CREATED_AT" DATETIME, 
	"TWEET_CONTENT" TEXT, 
	"KEYWORD" TEXT, 
	PRIMARY KEY ("TWEET_ID")
)
```

## Row counts

| Table | Row count |
| --- | --- |
| authors | 576,190 |
| timeline | 44,968,185 |
| tweets | 7,136,885 |

## Unique authors / users

| Table | Column | Unique AUTHOR_ID |
| --- | --- | --- |
| authors | AUTHOR_ID | 574,971 |
| timeline | AUTHOR_ID | 40,448 |
| tweets | AUTHOR_ID | 2,112,872 |

Note: unique counts are computed with `COUNT(DISTINCT AUTHOR_ID)` inside SQLite. `AUTHOR_ID` types differ across tables (`TEXT` / `INTEGER` / `VARCHAR`).

## Date ranges

| Table | Column | Minimum | Maximum |
| --- | --- | --- | --- |
| authors | CREATED_AT | 1970-01-01 00:00:00.000000 | 2022-12-29 00:00:00.000000 |
| timeline | CREATED_AT | 2007-05-11 22:13:23 | 2023-12-03 04:50:17 |
| tweets | CREATED_AT | 1609530189000 | 23-01-05 Thu 23:59:56 |

SQLite `MIN`/`MAX` on `CREATED_AT` are lexicographic on the stored text, not a parsed datetime.

- `authors.CREATED_AT` looks ISO-like, but the minimum `1970-01-01` is the Unix epoch and is almost certainly a placeholder, not a real Twitter signup date. Maximum is `2022-12-29`.
- `timeline.CREATED_AT` looks consistently ISO (`YYYY-MM-DD HH:MM:SS`) from 2007-05-11 to 2023-12-03.
- `tweets.CREATED_AT` is **mixed and unusable as-is**. The stored minimum `1609530189000` is Unix time in milliseconds (~2021-01-01). Sample rows use strings such as `19-01-01 Tue 00:00:03`. The stored maximum `23-01-05 Thu 23:59:56` is another custom format. Dates must be parsed/normalized before any time-series work.

## Missing values

Text columns: `NULL` or blank/whitespace. Numeric and boolean columns: SQL `NULL` only.

### `authors`

| Column | Missing rows | Percent |
| --- | --- | --- |
| AUTHOR_ID | 0 | 0.0% |
| REALNAME | 124 | 0.0215% |
| USERNAME | 0 | 0.0% |
| CREATED_AT | 0 | 0.0% |
| DESCRIPTION | 39,776 | 6.9033% |
| LOACATION | 165,552 | 28.7322% |
| VERIFIED | 0 | 0.0% |
| PROTECTED | 0 | 0.0% |
| IMAGE_URL | 120 | 0.0208% |
| FOLLOWERS_COUNT | 0 | 0.0% |
| FOLLOWING_COUNT | 0 | 0.0% |
| TWEET_COUNT | 0 | 0.0% |
| LISTED_COUNT | 0 | 0.0% |
| FREELANCER | 0 | 0.0% |
| IFB_COUNT | 0 | 0.0% |

### `timeline`

| Column | Missing rows | Percent |
| --- | --- | --- |
| TWEET_ID | 0 | 0.0% |
| AUTHOR_ID | 0 | 0.0% |
| CREATED_AT | 0 | 0.0% |
| TWEET | 0 | 0.0% |
| LANG | 0 | 0.0% |
| LIKES | 0 | 0.0% |
| REPLIES | 0 | 0.0% |
| RETWEETS | 0 | 0.0% |

### `tweets`

| Column | Missing rows | Percent |
| --- | --- | --- |
| TWEET_ID | 0 | 0.0% |
| AUTHOR_ID | 0 | 0.0% |
| CREATED_AT | 0 | 0.0% |
| TWEET_CONTENT | 0 | 0.0% |
| KEYWORD | 0 | 0.0% |

## Duplicate IDs

### `authors`

No primary key declared.

| Column | Unique values | Extra rows beyond unique | Status |
| --- | --- | --- | --- |
| AUTHOR_ID | 574,971 | 1,219 | DUPLICATES FOUND |
| USERNAME | 576,190 | 0 | OK (unique) |

Duplicate examples for `AUTHOR_ID`:

| AUTHOR_ID | count |
| --- | --- |
| 284818409 | 3 |
| 2297662476 | 3 |
| 1559537905110028291 | 3 |
| 1461423131701174277 | 3 |
| 1408350430996799491 | 3 |
| 1405137391594180609 | 3 |
| 1397902098273013773 | 3 |
| 1394612807740575745 | 3 |
| 1391911916008783872 | 3 |
| 1389308831713439747 | 3 |

### `timeline`

Declared primary key: `TWEET_ID`.

| Column | Unique values | Extra rows beyond unique | Status |
| --- | --- | --- | --- |
| TWEET_ID | 44,968,185 | 0 | OK (PRIMARY KEY enforces uniqueness) |

### `tweets`

Declared primary key: `TWEET_ID`.

| Column | Unique values | Extra rows beyond unique | Status |
| --- | --- | --- | --- |
| TWEET_ID | 7,136,885 | 0 | OK (PRIMARY KEY enforces uniqueness) |

## Language distribution (`timeline`)

- English (`en`): 34,868,834
- Non-English (non-empty, not `en`): 10,099,351

| LANG | Rows |
| --- | --- |
| en | 34868834 |
| und | 1786679 |
| qme | 1745270 |
| es | 1148815 |
| zxx | 610259 |
| in | 581046 |
| qam | 440523 |
| pt | 435736 |
| tl | 432397 |
| ja | 384649 |
| fr | 289015 |
| ko | 235808 |
| hi | 164928 |
| ar | 161236 |
| de | 148808 |

## Keyword distribution (`tweets`)

| KEYWORD | Rows |
| --- | --- |
| ifb | 1057788 |
| follow 4 follow | 1035565 |
|  follow_for_follow_back | 1020708 |
| follow for follow | 909593 |
|  i follow you back | 848381 |
| follow-for-follow | 610203 |
| follow-4-follow | 411165 |
| followforfollow-back | 298649 |
| followforfollowback | 281501 |
| follow-you-back | 232583 |
| Following whoever follows | 164851 |
| follow me and i follow you | 155462 |
| Following all that follows | 57296 |
| follow4follow | 26695 |
| follow-for-follow-back | 4542 |
| i follow you back | 3512 |
| follow_for_follow_back | 3383 |
| followforfollow | 2524 |
| follow_for_follow | 2485 |
| follow_4_follow | 2022 |

## Five sample rows per table

### `authors`

| AUTHOR_ID | REALNAME | USERNAME | CREATED_AT | DESCRIPTION | LOACATION | VERIFIED | PROTECTED | IMAGE_URL | FOLLOWERS_COUNT | FOLLOWING_COUNT | TWEET_COUNT | LISTED_COUNT | FREELANCER | IFB_COUNT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1216379074299301888 | santy | darlingsuzue | 2020-01-12 00:00:00.000000 | #TOBIO : a little moody after being used | she / her • 18 | 0 | 0 | https://pbs.twimg.com/profile_images/1557325804719439872/HNdW3tKG_normal.jpg | 1040 | 995 | 57302 | 30 | 0 | 15 |
| 1338230063356137474 | g 🍭 | obviousshe | 2020-12-13 00:00:00.000000 | she/her • black • 20 | tati ♡  | 0 | 0 | https://pbs.twimg.com/profile_images/1587592862241361920/0Q1VwDil_normal.jpg | 870 | 864 | 32025 | 17 | 0 | 0 |
| 1066610765283635200 | niss | neyseisinebak | 2018-11-25 00:00:00.000000 | ÜCRETLİ RT, REKLAM VE İŞ BİRLİĞİ İÇİN DM 📩 | O’19.05 | 0 | 0 | https://pbs.twimg.com/profile_images/1636440004279844889/GePU4IHC_normal.jpg | 25076 | 24130 | 6401 | 91 | 0 | 0 |
| 1300626198943404033 | briony ! | brionylewiss | 2020-09-01 00:00:00.000000 | Boner Bones?? 🩻 | 🇬🇧, she/her ⋒ | 0 | 0 | https://pbs.twimg.com/profile_images/1558623600386740224/1tHatCVk_normal.jpg | 560 | 630 | 8523 | 15 | 0 | 4 |
| 1304445845992099840 | lizzyᴴ LOVES JADE \| milf era | nipplerry | 2020-09-11 00:00:00.000000 | • • • himalayan salted dark chocolate almonds • • • # she her¡ | harrys dimple | 0 | 0 | https://pbs.twimg.com/profile_images/1376223097091719174/AGA8m0P3_normal.jpg | 222 | 292 | 6132 | 9 | 0 | 6 |

### `timeline`

| TWEET_ID | AUTHOR_ID | CREATED_AT | TWEET | LANG | LIKES | REPLIES | RETWEETS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1563654668512858113 | 1409211653858660354 | 2022-08-27 22:28:18.000000 | @Miss_Prresident Peer pressure | en | 1 | 0 | 0 |
| 1537185570664767488 | 1409211653858660354 | 2022-06-15 21:29:34.000000 | @Hon_wajackoyah_ Positive vibes. | en | 0 | 0 | 0 |
| 1526770321377869825 | 1409211653858660354 | 2022-05-18 03:43:05.000000 | @zero_mind0 Portrmore | und | 0 | 0 | 0 |
| 1525591691629043714 | 1409211653858660354 | 2022-05-14 21:39:38.000000 | Rate my art??💯 https://t.co/URgR7KcN6A | en | 0 | 0 | 0 |
| 1525591651263123460 | 1409211653858660354 | 2022-05-14 21:39:28.000000 | https://t.co/yOCYYM2uZF | zxx | 0 | 1 | 0 |

### `tweets`

| TWEET_ID | AUTHOR_ID | CREATED_AT | TWEET_CONTENT | KEYWORD |
| --- | --- | --- | --- | --- |
| 1079889954510123013 | 1037753237984751616 | 19-01-01 Tue 00:00:03 | For new years, for tonight only, if you want a follow on twitch, like this tweet and put your twitch name below and I will follow, if you would like to follow b… | followforfollow-back |
| 1079891061240197121 | 1029306676464295936 | 19-01-01 Tue 00:04:27 | i Follow back! .IFB follow me. IFB IFB ifb #IFB #follow #followforfollow #likeforfolow #follo4follo #IFBDrive #airdrop #freetokens #teamfollow | followforfollow-back |
| 1079891138000142338 | 1934697522 | 19-01-01 Tue 00:04:45 | @MistahFAB Hit me back if you're feeling this https://t.co/tZZKGkU2hv Plenty more on my channel https://t.co/dqxtfqUQt6 #FollowForFollow | followforfollow-back |
| 1079891248519892992 | 1024013730877661184 | 19-01-01 Tue 00:05:11 | YouTube channel #youtuber #youtubevideos #youtubeaddicts #followforfollowback #followuswefollowyouwinwin #youtubevideos #freepsychiceye #freecardpullwhenyoufoll… | followforfollowback |
| 1079891313657556994 | 878874258277109761 | 19-01-01 Tue 00:05:27 | @FortniteGame @Ninja I'm following everyone who follows me (no joke, i actually will follow you back!!) |  i follow you back |

## Other SQLite objects

| Type | Name | Table |
| --- | --- | --- |
| index | sqlite_autoindex_timeline_1 | timeline |

There are no user-created secondary indexes. `authors` and `tweets` have none; `timeline` has only the primary-key autoindex.

## Problems and missing fields vs. project requirements

Mapped against `IFB_database_description.docx.pdf` and the course guidelines (sentiment, emotion, topics, NER, bot detection, entity networks). No sentiment / topic / NER / network / bot analysis was run.

### Confirmed schema issues

1. **`LOACATION` typo** in `authors`. The description PDF names this field `LOCATION`. Queries and reports should use `LOACATION`.
2. **`AUTHOR_ID` type mismatch**: `authors.AUTHOR_ID` is `TEXT`, `tweets.AUTHOR_ID` is `INTEGER`, `timeline.AUTHOR_ID` is `VARCHAR`. Joins must cast IDs to a common type.
3. **`TWEET_ID` type mismatch**: `tweets.TWEET_ID` is `INTEGER PRIMARY KEY`; `timeline.TWEET_ID` is `VARCHAR PRIMARY KEY`.
4. **`authors` has no primary key and no indexes.** Duplicate `AUTHOR_ID` values are possible at the schema level and were checked in SQL.
5. **`tweets` has no secondary indexes.** Keyword filters and author lookups will need full scans unless indexes are added later (adding indexes would modify the DB; do not do that without an explicit decision).

### Fields the course guidelines expect that this database does not store

- **No follow graph.** There is no table of follower/following edges. Network analysis of *users* cannot be built from who-follows-whom; the official IFB description also does not include it. Course network work is specified mainly as **entity co-occurrence networks** from NER, which can still be done from tweet text.
- **No structured mention / hashtag / URL / is_retweet columns.** Bot-detection features such as average mentions per tweet, hashtags per tweet, and retweet *rate* must be parsed from tweet text. `timeline` has `RETWEETS` (count of how often a tweet was retweeted), not a flag that the row itself is a retweet.
- **No reply/quote conversation graph** (`in_reply_to_status_id`, `quoted_status_id`). Discourse-spread analysis cannot use native Twitter conversation edges.
- **`tweets` has no `LANG`, `LIKES`, `REPLIES`, or `RETWEETS`.** Keyword IFB tweets lack engagement and language metadata. Those fields exist only on `timeline`.
- **`timeline` has no `KEYWORD`.** Broader author activity is not tagged with the IFB seed keywords.
- **No `listed_count` alternative names / default-profile flags** beyond `IMAGE_URL` and `DESCRIPTION`. Default vs custom avatar cannot be known for sure from URL alone, but empty/missing image URLs can be used.
- **No precomputed English translations** (`text_translated_en`). Guidelines require translating posts to English before later text analysis.

### Implications for later stages (not performed yet)

- **Translation / sentiment / emotion / topics / NER:** depend on tweet text (`tweets.TWEET_CONTENT`, `timeline.TWEET`) plus `timeline.LANG`. Non-English rows will need translation.
- **Bot / troll features available now:** `FOLLOWERS_COUNT`, `FOLLOWING_COUNT`, `TWEET_COUNT`, account `CREATED_AT`, `DESCRIPTION`, `IMAGE_URL`, `VERIFIED`, `PROTECTED`, `IFB_COUNT`, `FREELANCER`, and timeline timestamps / engagement counts.
- **Bot features that must be derived:** posting-hour patterns, inter-tweet variance, copy-paste rate, mention/hashtag rates, retweet-as-content rate.
- **Scale:** `timeline` is tens of millions of rows. Later stages should sample or aggregate in SQL rather than loading the table into pandas.

### Author coverage (important)

The three tables do **not** share the same user set:

| Table | Rows | Unique `AUTHOR_ID` |
| --- | --- | --- |
| authors | 576,190 | 574,971 |
| tweets | 7,136,885 | 2,112,872 |
| timeline | 44,968,185 | 40,448 |

- `tweets` has about **2.11 million** distinct authors, but `authors` only stores **~575 thousand**. Most keyword-tweet authors have **no profile row**.
- `timeline` covers only **~40 thousand** authors — a small subset of `authors`, and a tiny subset of `tweets` authors.
- The description PDF says authors were extracted from keyword tweets, then extra tweets were collected into `timeline`. The counts do not match that story cleanly. Profile metadata (followers, bio, verified, `IFB_COUNT`) is missing for the majority of tweet authors.
- `authors` has **1,219 extra rows** from duplicated `AUTHOR_ID`s (usernames are unique). Deduplicate before joining.

### Other data-quality notes

- Several `tweets.KEYWORD` values have **leading spaces** (e.g. ` follow_for_follow_back`, ` i follow you back`). Keyword grouping must `TRIM` first.
- `timeline.LANG` includes Twitter non-language codes: `und` (undetermined), `qme` / `qam` (mostly media or mentions), `zxx` (no linguistic content). These are not real spoken languages and should be filtered before translation.
- About **10.1 million** timeline rows are not `en` and will need translation if those posts are used for sentiment/topics/NER.

### Inspection highlights

- `authors` rows: 576,190
- Duplicate `AUTHOR_ID` extra rows in `authors`: 1,219
- Missing `LOACATION`: 165,552 (28.7322%)
- Missing `DESCRIPTION`: 39,776 (6.9033%)
- `tweets` rows: 7,136,885
- `tweets.CREATED_AT` is mixed-format (Unix ms and `YY-MM-DD Weekday HH:MM:SS`); stored MIN/MAX are not chronological
- `timeline` rows: 44,968,185
- `timeline.CREATED_AT` range: 2007-05-11 22:13:23 → 2023-12-03 04:50:17
- `timeline` English rows: 34,868,834; non-English: 10,099,351

