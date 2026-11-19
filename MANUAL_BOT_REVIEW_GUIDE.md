# Manual bot / malicious-user review guide

This review is a **behavioral risk** judgment from the 2023 IFB snapshot. It is **not** a verified bot identity.

## What we can see

- Profile fields stored in `IFB.db.authors` at collection time (followers, following, tweets, IFB_COUNT, bio, verified, created date).
- Representative **original posts** from the English NLP corpus (keyword IFB tweets + stratified timeline sample).

## What we cannot see

- Live X/Twitter pages in 2026 (many IFB accounts churned after 2023).
- Follower / following graphs, reply trees, or native retweet cascades.
- A vendor `is_bot` score.

Deleted, suspended, or empty snapshots are labeled **`insufficient_evidence`**, never malicious.

## Labels

| Label | Meaning |
|-------|---------|
| `likely_normal` | Varied original posts and a plausible profile. Still may use IFB hashtags. |
| `suspicious` | Strong automation / follow-farm signals, but a human IFB user remains possible. |
| `likely_malicious` | Repeated spam, commercial follow-gain scripts, or RT-only amplification with almost no original voice. Still not a proven bot. |
| `insufficient_evidence` | Too few posts, missing profile, epoch signup date, or mixed/unreadable evidence. |

Also store course flags: `is_bot` ∈ {0,1,unknown}, `is_troll`, `is_malicious`, reviewer confidence (`high`/`medium`/`low`), and a short evidence note.

## Sampling (seed 2026)

100 users, stratified on the **unlabeled** rule score (35 low / 30 medium / 35 high). Rules are **not** copied as labels.

## Process

1. Read username, bio, follower/following/IFB counts, account age.
2. Read 4–6 original posts (keyword and timeline when both exist).
3. Ask: is the text a copy-paste follow-back machine, a normal IFB hobbyist, or unclear?
4. Write evidence quotes. Do not use the rule score as the label.

## Mapping used for ML

Training uses a binary **risk** target, not “is bot”:

- positive = `likely_malicious` or `suspicious`
- negative = `likely_normal`
- `insufficient_evidence` is excluded from training

There is **no** second 200-user manual validation set. Creating 200 extra labels without another real review would be fabrication.
