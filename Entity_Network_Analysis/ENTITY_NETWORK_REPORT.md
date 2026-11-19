# Entity co-occurrence network

Rebuilt by `src/postaudit_rebuild_entity_network.py` (post-audit corrective pass).
`IFB.db` was not opened. Sentiment, emotion, events, BERTopic, and NER were **not** rerun.

## Canonical key (read this before comparing any count)

- **Node** = canonical entity name. Category (person / country / organization / location / norp / event / product / facility) is a node **attribute**, not part of node identity.
- **Edge** = unordered pair of two *different* canonical entity names.
- **edge_weight** = number of distinct posts containing both names.

Consequences, all of which are asserted by `validate()` in the rebuild script:

- One row of `entity_network_edges.csv` is exactly one graph edge (2,578 rows = 2578 edges).
- There are **no self-loops** and **no duplicate undirected edges**.
- `sum(degree) / 2` in `entity_network_metrics.csv` equals `n_edges` (2578).

An earlier version keyed the edge file on `(entity_a, category_a, entity_b, category_b)` (2,694 rows) while the graph collapsed endpoints to bare names (2,665 edges), so the shipped edge file and the shipped summary disagreed. That ambiguity is resolved: both files are now generated from the single definition above.

## Minimum entity length

Entities shorter than **3 characters** are excluded, as the guidelines require. This removed two-character tokens such as `CW`, `VN`, `EU`, `IG`, `GM`, `DC`, `LA`, `QB`, `bc`, `Un`, and `AI`. `CW` and `VN` were previously drawn as Top-30 nodes, and the `CW`–`Riverdale` pair was previously the fourth-strongest edge in the graph; both are gone. Dropped entity rows are preserved in `outputs/entities_dropped_short.csv` and the pair-level counts in `outputs/entity_network_filter_provenance.json`.

## Why there is no follower network

`IFB.db` has follower **counts**, not edges. There are no follow/following adjacency lists, no `in_reply_to` / quote IDs, and no retweet-cascade table. The graded network in the course file list is entity co-occurrence. This report does **not** invent user-user edges.

## Thresholds (seed 2026)

| Rule | Value |
|------|------:|
| Minimum entity length (characters) | 3 |
| Minimum unique posts per entity | 20 |
| Maximum eligible entities per post | 8 |
| Minimum distinct posts per edge (final graph) | 5 |
| Visualization | top 30 nodes by weighted degree |
| Layout / Louvain seed | 2026 |
| Graph weight | unweighted post counts only |

Timeline `sample_weight` is stored as `timeline_weighted_estimate` on edges. It is **not** used to build edges or to score centrality.

## Rejection summary

- `pair_rows_before_filter`: 83,438
- `pair_rows_dropped_short_entity`: 7,558
- `pair_rows_dropped_self_pair`: 136
- `pair_rows_after_filter`: 75,744
- `candidate_edges`: 31,840
- `edges_below_min_weight`: 29,262
- `final_edges`: 2,578

## Combined graph (explicit mix warning)

The combined graph counts a keyword post and a timeline post as +1 each. Keyword data are a **census** of eligible IFB tweets; timeline data are a **stratified ~1.7% English sample** (seed 2026). Do not read combined degree as “how often the IFB population tweets these pairs.” Keyword-only and timeline-only rows are in `entity_network_summary.csv`.

| Metric | Combined graph |
|--------|---------------:|
| Nodes | 1076 |
| Edges | 2578 |
| Density | 0.004458 |
| Components | 57 |
| Largest component | 944 |
| Average degree | 4.7918 |
| Average weighted degree | 67.277 |
| Clustering (weighted) | 0.0101 |

Louvain communities (seed 2026): 79 groups; largest sizes [161, 152, 143, 65, 64, 55].

| Community | n | Strongest members |
|-----------|--:|-------------------|
| C0 | 161 | United States, Ukraine, Russia, United Kingdom, Vladimir Putin, China |
| C1 | 152 | Donald Trump, Joe Biden, Republicans, GOP, Democrats, House |
| C2 | 143 | Twitter, YouTube, Facebook, Riverdale, Texas, Instagram |
| C3 | 65 | NFL, NBA, Patriots, Scott K, Cowboys, Lakers |
| C4 | 64 | India, Australia, England, Pakistan, World Cup, South Africa |
| C5 | 55 | Chelsea, Liverpool, Messi, Barcelona, Ronaldo, Brazil |

Community labels are interpretive, not ground truth. A community here means “these names co-occur in text”, never “these users interact”.

## Central nodes

Node size in the figure is **weighted degree** (sum of co-occurring posts). PageRank, betweenness, and closeness are also stored.

### Top weighted degree

| Entity | category | weighted degree | degree | PageRank |
|--------|----------|----------------:|-------:|---------:|
| United States | country | 3712.0 | 181.0 | 0.034499 |
| Donald Trump | person | 3299.0 | 152.0 | 0.030102 |
| Joe Biden | person | 2664.0 | 111.0 | 0.021522 |
| Twitter | organization | 1806.0 | 107.0 | 0.02113 |
| Ukraine | country | 1431.0 | 47.0 | 0.010342 |
| Russia | country | 1303.0 | 45.0 | 0.009589 |
| Florida | location | 1098.0 | 37.0 | 0.007612 |
| Republicans | norp | 1048.0 | 52.0 | 0.008022 |
| GOP | organization | 969.0 | 57.0 | 0.007683 |
| Israel | country | 950.0 | 43.0 | 0.007418 |

### Top betweenness

| Entity | category | betweenness |
|--------|----------|------------:|
| United States | country | 0.297324 |
| Twitter | organization | 0.141713 |
| Donald Trump | person | 0.117722 |
| United Kingdom | country | 0.111116 |
| India | country | 0.063954 |
| Joe Biden | person | 0.060902 |
| NFL | organization | 0.049189 |
| London | location | 0.040864 |

### Strongest edges

| A | B | posts | keyword | timeline raw | timeline weighted (estimate only) |
|---|---|------:|--------:|-------------:|--------------------------------:|
| Florida | Tampa | 509 | 506 | 3 | 177.44 |
| Russia | Ukraine | 347 | 166 | 181 | 10705.82 |
| Donald Trump | Joe Biden | 325 | 99 | 226 | 13367.49 |
| Joe Biden | United States | 228 | 85 | 143 | 8458.29 |
| Donald Trump | United States | 207 | 106 | 101 | 5974.06 |
| Russia | United States | 166 | 75 | 91 | 5382.48 |
| Donald Trump | GOP | 160 | 81 | 79 | 4672.73 |
| Facebook | Twitter | 155 | 104 | 51 | 3020.16 |
| Ukraine | Vladimir Putin | 150 | 70 | 80 | 4731.86 |
| Ukraine | United States | 148 | 75 | 73 | 4317.81 |

## Source-specific and category-filtered graphs

Keyword-only and timeline-only graphs use the same thresholds but only posts from that source. Timeline remains a **stratified sample** (seed 2026, ~1.7% of English timeline). Graph construction never uses `sample_weight`. Category-filtered subgraphs use the node's modal category.

| Graph | nodes | edges | density | components | largest | avg degree | avg weighted degree |
|-------|------:|------:|--------:|-----------:|--------:|-----------:|--------------------:|
| combined_min_edge | 1076 | 2578 | 0.004458 | 57 | 944 | 4.7918 | 67.277 |
| keyword_only | 646 | 1261 | 0.006053 | 52 | 500 | 3.904 | 53.6409 |
| timeline_only_raw | 547 | 1175 | 0.007868 | 40 | 463 | 4.2962 | 54.3218 |
| person_person | 187 | 204 | 0.01173 | 32 | 96 | 2.1818 | 29.2193 |
| person_country | 273 | 473 | 0.01274 | 22 | 228 | 3.4652 | 57.2088 |
| organization | 295 | 374 | 0.008624 | 37 | 196 | 2.5356 | 34.3458 |

## Limitations

- Co-occurrence is not alliance or friendship. Promo templates can still pair a platform with a celebrity.
- Keyword IFB collection over-represents greetings and follow-back copy.
- Timeline is ~1.7% of English timeline; pair rates are sample-dependent.
- High-entity posts were dropped, which removes some news dumps and some genuine listicles.
- Combined counts mix two sampling frames.
- No follower graph can be built from this database.
- Entities shorter than 3 characters are excluded, so legitimate short acronyms (`EU`, `UN`, `NY`) are lost along with the junk. That trade-off follows the guideline rule and is stated rather than silently applied.

## Output checklist

| File | Present |
|------|---------|
| `src/entity_network_analysis.py` | yes |
| `src/postaudit_rebuild_entity_network.py` | yes |
| `notebooks/entity_network_analysis.ipynb` | yes |
| `outputs/entity_pairs.csv` | yes |
| `outputs/entity_network_edges.csv` | yes |
| `outputs/entity_network_nodes.csv` | yes |
| `outputs/entity_network_metrics.csv` | yes |
| `outputs/entity_network_summary.csv` | yes |
| `outputs/entity_network_rejections.csv` | yes |
| `outputs/entity_network_canonical_key.json` | yes |
| `outputs/entity_network_filter_provenance.json` | yes |
| `outputs/entities_dropped_short.csv` | yes |
| `outputs/entity_network_graph.png` | yes |
| `outputs/entity_network_person_person.png` | yes |
| `outputs/entity_network_person_country.png` | yes |
| `outputs/entity_network_organization.png` | yes |
| `ENTITY_NETWORK_REPORT.md` | yes |
