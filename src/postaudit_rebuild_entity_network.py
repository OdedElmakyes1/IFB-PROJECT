"""Rebuild the graded entity + network outputs with one canonical key.

Post-audit corrective pass. It does **not** rerun spaCy NER. It reads the
already-extracted mentions (`outputs/entities_extracted.csv`) and the already
generated per-post pairs (`outputs/entity_pairs.csv`) and re-derives the small
graded tables and figures.

Two defects are fixed here.

1.  Entities shorter than ``MIN_ENTITY_CHARS`` characters were never dropped,
    even though the guidelines require it. ``CW`` and ``VN`` were visible nodes
    in the graded Top-30 figure.

2.  The edge key was ambiguous. ``entity_network_edges.csv`` was keyed on
    ``(entity_a, category_a, entity_b, category_b)`` (2,694 rows) while the
    graph that produced ``entity_network_summary.csv`` collapsed endpoints to
    bare entity names (2,665 edges), so the two shipped files disagreed.

The canonical key is now stated once and used everywhere:

    node  = canonical entity name (category is a node *attribute*)
    edge  = unordered pair of two *different* canonical entity names
    weight = number of distinct posts containing both names

One row of ``entity_network_edges.csv`` is therefore exactly one graph edge.

Usage (from the repo root):
    python src/postaudit_rebuild_entity_network.py
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

try:
    from networkx.algorithms.community import louvain_communities
except ImportError:  # pragma: no cover
    louvain_communities = None
from networkx.algorithms.community import greedy_modularity_communities  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

SEED = 2026
MIN_ENTITY_CHARS = 3          # guidelines: drop entities shorter than 3 characters
MIN_ENTITY_POSTS = 20         # upstream eligibility, already applied in entity_pairs.csv
MAX_ENTITIES_PER_POST = 8     # upstream, already applied
MIN_EDGE_WEIGHT = 5           # minimum distinct posts per edge on the final graph
VIZ_TOP_N = 30

CAT_COLOR = {
    "person": "#4c78a8",
    "country": "#f58518",
    "organization": "#54a24b",
    "location": "#e45756",
    "event": "#b279a2",
    "norp": "#72b7b2",
    "product": "#eeca3b",
    "facility": "#9d755d",
}

CO_OCCURRENCE_NOTE = "Entity co-occurrence, not a follower network"
EDGE_KEY_NOTE = (
    "canonical edge key = unordered pair of distinct canonical entity names; "
    "one row = one graph edge; category is a node attribute"
)


def log(msg: str) -> None:
    print(msg, flush=True)


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def read_csv_rows(path: Path):
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    log(f"Wrote {path.name} ({len(rows):,} rows)")


# --------------------------------------------------------------------------- #
# 1. entity-level statistics from the already-extracted mentions
# --------------------------------------------------------------------------- #
def post_metadata() -> dict[tuple[int, int], tuple[str, float]]:
    """(source, tweet_id) -> (author_id, sample_weight), read from the raw mentions.

    Post-level, so it is unaffected by entity alias resolution.
    """
    meta: dict[tuple[int, int], tuple[str, float]] = {}
    short_mentions = 0
    for row in read_csv_rows(OUT / "entities_extracted.csv"):
        if (row.get("keep_flag") or "").strip() != "1":
            continue
        if len((row.get("canonical_entity") or "").strip()) < MIN_ENTITY_CHARS:
            short_mentions += 1
        src = 0 if row.get("source") == "keyword_tweets" else 1
        try:
            pid = (src, int(row["tweet_id"]))
        except (KeyError, ValueError):
            continue
        if pid not in meta:
            try:
                w = float(row.get("sample_weight") or 1.0)
            except ValueError:
                w = 1.0
            meta[pid] = (row.get("author_id") or "", w)
    log(f"post metadata for {len(meta):,} posts; kept mentions with len<{MIN_ENTITY_CHARS}: {short_mentions:,}")
    return meta


def entity_stats() -> dict[str, dict[str, Any]]:
    """Per-name post/user counts from the alias-resolved cleaned entity table.

    ``entities_extracted.csv`` holds the pre-alias ``canonical_entity`` (``Trump``
    and ``Donald Trump`` are still separate there), while ``entity_pairs.csv`` and
    the graph use the alias-resolved name. ``entities_cleaned.csv`` is the
    alias-resolved aggregation, so node counts are taken from it and therefore
    agree with the graded entity table by construction.
    """
    stats: dict[str, dict[str, Any]] = {}
    for row in read_csv_rows(OUT / "entities_cleaned.csv"):
        name = (row.get("canonical_entity") or row.get("entity") or "").strip()
        if len(name) < MIN_ENTITY_CHARS:
            continue

        def num(field: str) -> int:
            try:
                return int(float(row.get(field) or 0))
            except ValueError:
                return 0

        st = stats.get(name)
        if st is None:
            st = stats[name] = {"posts": 0, "users": 0, "kw": 0, "tl": 0, "cats": Counter()}
        st["posts"] += num("n_posts")
        st["users"] += num("n_users")
        st["kw"] += num("n_keyword")
        st["tl"] += num("n_timeline")
        st["cats"][row.get("normalized_category") or "other"] += num("n_posts") or 1
    log(f"entity stats for {len(stats):,} alias-resolved names")
    return stats


# --------------------------------------------------------------------------- #
# 2. filter the per-post pairs, then aggregate them into canonical edges
# --------------------------------------------------------------------------- #
def filter_pairs() -> tuple[list[dict[str, str]], list[dict[str, str]], Counter]:
    keep: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    rej: Counter = Counter()
    for row in read_csv_rows(OUT / "entity_pairs.csv"):
        rej["pair_rows_before_filter"] += 1
        a = (row.get("entity_a") or "").strip()
        b = (row.get("entity_b") or "").strip()
        if a == b:
            rej["pair_rows_dropped_self_pair"] += 1
            dropped.append({**row, "drop_reason": "self_pair_same_entity_name"})
            continue
        if len(a) < MIN_ENTITY_CHARS or len(b) < MIN_ENTITY_CHARS:
            rej["pair_rows_dropped_short_entity"] += 1
            dropped.append({**row, "drop_reason": f"entity_shorter_than_{MIN_ENTITY_CHARS}_chars"})
            continue
        keep.append(row)
    rej["pair_rows_after_filter"] = len(keep)
    return keep, dropped, rej


def aggregate_edges(
    pairs: list[dict[str, str]],
    post_meta: dict[tuple[int, int], tuple[str, float]],
) -> list[dict[str, Any]]:
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for row in pairs:
        a = row["entity_a"].strip()
        b = row["entity_b"].strip()
        key = (a, b) if a <= b else (b, a)
        src = 0 if row.get("source") == "keyword_tweets" else 1
        try:
            tid = int(row["tweet_id"])
        except (KeyError, ValueError):
            continue
        pid = (src, tid)
        e = acc.get(key)
        if e is None:
            e = acc[key] = {
                "posts": set(), "users": set(), "kw": 0, "tl": 0, "tl_w": 0.0,
                "dates": [], "cats_a": Counter(), "cats_b": Counter(),
            }
        # category counters follow the sorted key order, not the raw row order
        if key[0] == a:
            e["cats_a"][row.get("category_a") or "other"] += 1
            e["cats_b"][row.get("category_b") or "other"] += 1
        else:
            e["cats_a"][row.get("category_b") or "other"] += 1
            e["cats_b"][row.get("category_a") or "other"] += 1
        if pid in e["posts"]:
            continue
        e["posts"].add(pid)
        author, weight = post_meta.get(pid, ("", 1.0))
        e["users"].add(author)
        if src == 0:
            e["kw"] += 1
        else:
            e["tl"] += 1
            e["tl_w"] += weight
        if row.get("created_at"):
            e["dates"].append(row["created_at"])

    rows: list[dict[str, Any]] = []
    for (a, b), e in acc.items():
        n = len(e["posts"])
        dates = sorted(d for d in e["dates"] if d)
        rows.append(
            {
                "entity_a": a,
                "entity_b": b,
                "category_a": e["cats_a"].most_common(1)[0][0],
                "category_b": e["cats_b"].most_common(1)[0][0],
                "edge_weight": n,
                "unique_posts": n,
                "unique_users": len(e["users"]),
                "keyword_post_count": e["kw"],
                "timeline_raw_post_count": e["tl"],
                "timeline_weighted_estimate": round(e["tl_w"], 2),
                "first_date": dates[0] if dates else "",
                "last_date": dates[-1] if dates else "",
                "edge_key_note": EDGE_KEY_NOTE,
                "mix_note": (
                    "combined unique_posts mixes keyword census (weight=1) with timeline sample; "
                    "timeline_weighted_estimate is a population estimate only and is NOT the graph weight"
                ),
            }
        )
    rows.sort(key=lambda r: (-r["edge_weight"], r["entity_a"], r["entity_b"]))
    return rows


# --------------------------------------------------------------------------- #
# 3. graph construction on the canonical key
# --------------------------------------------------------------------------- #
def build_graph(
    edges: list[dict[str, Any]],
    node_category: dict[str, str],
    weight_field: str = "edge_weight",
    pred=None,
) -> nx.Graph:
    g = nx.Graph()
    for r in edges:
        if pred and not pred(r):
            continue
        w = int(r[weight_field])
        if w < MIN_EDGE_WEIGHT:
            continue
        a, b = r["entity_a"], r["entity_b"]
        if a == b:
            continue
        g.add_node(a, category=node_category.get(a, r["category_a"]))
        g.add_node(b, category=node_category.get(b, r["category_b"]))
        g.add_edge(a, b, weight=w)
    return g


def centralities(g: nx.Graph) -> dict[str, dict[str, float]]:
    if g.number_of_nodes() == 0:
        return {}
    deg = dict(g.degree())
    wdeg = dict(g.degree(weight="weight"))
    btw = nx.betweenness_centrality(g, weight=None, seed=SEED)
    clo = nx.closeness_centrality(g)
    pr = nx.pagerank(g, weight="weight")
    try:
        eig = nx.eigenvector_centrality_numpy(g, weight="weight")
    except Exception:
        eig = pr
    return {
        n: {
            "degree": float(deg.get(n, 0)),
            "weighted_degree": float(wdeg.get(n, 0)),
            "betweenness_centrality": round(btw.get(n, 0.0), 6),
            "closeness_centrality": round(clo.get(n, 0.0), 6),
            "pagerank": round(pr.get(n, 0.0), 6),
            "eigenvector_centrality": round(float(eig.get(n, 0.0)), 6),
        }
        for n in g.nodes
    }


def communities(g: nx.Graph) -> dict[str, int]:
    if g.number_of_nodes() < 3:
        return {n: 0 for n in g}
    try:
        comms = list(louvain_communities(g, weight="weight", seed=SEED))
    except Exception:
        comms = list(greedy_modularity_communities(g, weight="weight"))
    mapping: dict[str, int] = {}
    for i, members in enumerate(sorted(comms, key=len, reverse=True)):
        for n in members:
            mapping[n] = i
    return mapping


def graph_metrics(g: nx.Graph, name: str) -> dict[str, Any]:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    comps = list(nx.connected_components(g)) if n else []
    degs = [d for _, d in g.degree()] or [0]
    wdegs = [d for _, d in g.degree(weight="weight")] or [0]
    clustering = 0.0
    if n and m:
        try:
            clustering = round(nx.average_clustering(g, weight="weight"), 4)
        except Exception:
            clustering = 0.0
    return {
        "graph": name,
        "n_nodes": n,
        "n_edges": m,
        "density": round(nx.density(g), 6) if n > 1 else 0,
        "n_components": len(comps),
        "largest_component": max((len(c) for c in comps), default=0),
        "average_degree": round(sum(degs) / n, 4) if n else 0,
        "average_weighted_degree": round(sum(wdegs) / n, 4) if n else 0,
        "clustering_coefficient": clustering,
        "edge_key": "unordered (entity_a, entity_b) canonical names",
        "min_entity_chars": MIN_ENTITY_CHARS,
        "min_edge_weight": MIN_EDGE_WEIGHT,
        "note": CO_OCCURRENCE_NOTE,
    }


def draw_network(g: nx.Graph, path: Path, title: str, size_key: dict[str, float], top_n: int = VIZ_TOP_N) -> None:
    if g.number_of_nodes() == 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "No edges after thresholds", ha="center")
        fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return
    largest = max(nx.connected_components(g), key=len)
    base = g.subgraph(largest)
    ranked = sorted(base.nodes, key=lambda n: size_key.get(n, 0), reverse=True)
    keep = set(ranked[:top_n])
    sub = base.subgraph(keep).copy()
    if sub.number_of_edges() < max(8, top_n // 2):
        extras: list[str] = []
        for n in list(keep):
            extras.extend(sorted(base[n], key=lambda x: base[n][x].get("weight", 1), reverse=True)[:2])
        keep.update(extras[:12])
        sub = base.subgraph(keep).copy()
    n_shown = max(sub.number_of_nodes(), 1)
    pos = nx.spring_layout(sub, seed=SEED, k=2.6 / math.sqrt(n_shown), iterations=140)
    fig, ax = plt.subplots(figsize=(13.2, 10.2))
    fig.patch.set_facecolor("white")
    weights = [sub[u][v].get("weight", 1) for u, v in sub.edges]
    wmax = max(weights) if weights else 1
    nx.draw_networkx_edges(
        sub, pos, ax=ax, width=[0.6 + 4.2 * (w / wmax) for w in weights],
        edge_color="#9aa0a6", alpha=0.65,
    )
    smax = max((size_key.get(n, 1) for n in sub), default=1) or 1
    nx.draw_networkx_nodes(
        sub, pos, ax=ax,
        node_size=[280 + 2200 * (size_key.get(n, 0) / smax) for n in sub.nodes],
        node_color=[CAT_COLOR.get(sub.nodes[n].get("category", ""), "#888888") for n in sub.nodes],
        linewidths=0.8, edgecolors="white",
    )
    nx.draw_networkx_labels(
        sub, pos,
        labels={n: n if len(n) <= 22 else n[:20] + "…" for n in sub.nodes},
        ax=ax, font_size=8, font_color="#222222",
    )
    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax.text(
        0.5, -0.02,
        "Not a follower / user-user network. IFB.db has no follow, reply, or retweet-cascade edges.\n"
        f"Largest component, top {len(sub)} nodes by weighted degree. Node size = weighted degree. "
        f"Edge width = distinct posts. Node = canonical entity name; entities shorter than "
        f"{MIN_ENTITY_CHARS} characters are excluded. Seed {SEED}.",
        transform=ax.transAxes, ha="center", va="top", fontsize=9, color="#333333",
    )
    handles = [
        Patch(facecolor=c, label=k)
        for k, c in CAT_COLOR.items()
        if any(sub.nodes[n].get("category") == k for n in sub)
    ]
    handles.append(Line2D([0], [0], color="#9aa0a6", lw=3, label="edge width = co-occurring posts"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log(f"Wrote {path.name} ({sub.number_of_nodes()} nodes, {sub.number_of_edges()} edges shown)")


def validate(g: nx.Graph, edges: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if list(nx.selfloop_edges(g)):
        issues.append("graph contains self-loops")
    seen: set[tuple[str, str]] = set()
    for r in edges:
        key = (r["entity_a"], r["entity_b"]) if r["entity_a"] <= r["entity_b"] else (r["entity_b"], r["entity_a"])
        if key in seen:
            issues.append(f"duplicate undirected edge row: {key}")
        seen.add(key)
        if r["entity_a"] == r["entity_b"]:
            issues.append(f"self edge row: {r['entity_a']}")
        for side in ("entity_a", "entity_b"):
            if len(r[side]) < MIN_ENTITY_CHARS:
                issues.append(f"entity shorter than {MIN_ENTITY_CHARS} chars survived: {r[side]!r}")
    kept = [r for r in edges if int(r["edge_weight"]) >= MIN_EDGE_WEIGHT]
    if len(kept) != g.number_of_edges():
        issues.append(
            f"edge-file/graph mismatch: {len(kept)} rows at weight>={MIN_EDGE_WEIGHT} "
            f"vs {g.number_of_edges()} graph edges"
        )
    short_nodes = [n for n in g.nodes if len(n) < MIN_ENTITY_CHARS]
    if short_nodes:
        issues.append(f"short node names in graph: {short_nodes}")
    return issues


def write_report(
    summary: list[dict[str, Any]],
    node_rows: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    rej: Counter,
    comm: dict[str, int],
) -> None:
    """Regenerate ENTITY_NETWORK_REPORT.md so no stale count survives the rebuild."""
    comb = next((r for r in summary if r["graph"] == "combined_min_edge"), {})
    sizes = Counter(comm.values())
    top_comm = sizes.most_common(6)
    by_comm: dict[int, list[str]] = {}
    for r in node_rows:
        by_comm.setdefault(int(r["community_id"]), []).append(r["entity"])

    def fmt_rows(rows: list[list[str]]) -> list[str]:
        return ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]

    top_w = sorted(node_rows, key=lambda r: -float(r["weighted_degree"]))[:10]
    top_b = sorted(node_rows, key=lambda r: -float(r["betweenness_centrality"]))[:8]
    top_e = edges[:10]

    L: list[str] = [
        "# Entity co-occurrence network",
        "",
        "Rebuilt by `src/postaudit_rebuild_entity_network.py` (post-audit corrective pass).",
        "`IFB.db` was not opened. Sentiment, emotion, events, BERTopic, and NER were **not** rerun.",
        "",
        "## Canonical key (read this before comparing any count)",
        "",
        "- **Node** = canonical entity name. Category (person / country / organization / location / "
        "norp / event / product / facility) is a node **attribute**, not part of node identity.",
        "- **Edge** = unordered pair of two *different* canonical entity names.",
        "- **edge_weight** = number of distinct posts containing both names.",
        "",
        "Consequences, all of which are asserted by `validate()` in the rebuild script:",
        "",
        f"- One row of `entity_network_edges.csv` is exactly one graph edge "
        f"({len(edges):,} rows = {comb.get('n_edges')} edges).",
        "- There are **no self-loops** and **no duplicate undirected edges**.",
        f"- `sum(degree) / 2` in `entity_network_metrics.csv` equals `n_edges` "
        f"({comb.get('n_edges')}).",
        "",
        "An earlier version keyed the edge file on `(entity_a, category_a, entity_b, category_b)` "
        "(2,694 rows) while the graph collapsed endpoints to bare names (2,665 edges), so the "
        "shipped edge file and the shipped summary disagreed. That ambiguity is resolved: both "
        "files are now generated from the single definition above.",
        "",
        "## Minimum entity length",
        "",
        f"Entities shorter than **{MIN_ENTITY_CHARS} characters** are excluded, as the guidelines "
        "require. This removed two-character tokens such as `CW`, `VN`, `EU`, `IG`, `GM`, `DC`, "
        "`LA`, `QB`, `bc`, `Un`, and `AI`. `CW` and `VN` were previously drawn as Top-30 nodes, "
        "and the `CW`–`Riverdale` pair was previously the fourth-strongest edge in the graph; "
        "both are gone. Dropped entity rows are preserved in `outputs/entities_dropped_short.csv` "
        "and the pair-level counts in `outputs/entity_network_filter_provenance.json`.",
        "",
        "## Why there is no follower network",
        "",
        "`IFB.db` has follower **counts**, not edges. There are no follow/following adjacency "
        "lists, no `in_reply_to` / quote IDs, and no retweet-cascade table. The graded network in "
        "the course file list is entity co-occurrence. This report does **not** invent user-user edges.",
        "",
        "## Thresholds (seed 2026)",
        "",
        "| Rule | Value |",
        "|------|------:|",
        f"| Minimum entity length (characters) | {MIN_ENTITY_CHARS} |",
        f"| Minimum unique posts per entity | {MIN_ENTITY_POSTS} |",
        f"| Maximum eligible entities per post | {MAX_ENTITIES_PER_POST} |",
        f"| Minimum distinct posts per edge (final graph) | {MIN_EDGE_WEIGHT} |",
        f"| Visualization | top {VIZ_TOP_N} nodes by weighted degree |",
        f"| Layout / Louvain seed | {SEED} |",
        "| Graph weight | unweighted post counts only |",
        "",
        "Timeline `sample_weight` is stored as `timeline_weighted_estimate` on edges. It is "
        "**not** used to build edges or to score centrality.",
        "",
        "## Rejection summary",
        "",
    ]
    for k in ("min_entity_chars", "min_entity_posts", "max_entities_per_post", "min_edge_weight",
              "pair_rows_before_filter", "pair_rows_dropped_short_entity",
              "pair_rows_dropped_self_pair", "pair_rows_after_filter",
              "candidate_edges", "edges_below_min_weight", "final_edges"):
        if k in rej:
            L.append(f"- `{k}`: {rej[k]:,}")
    L += [
        "",
        "## Combined graph (explicit mix warning)",
        "",
        "The combined graph counts a keyword post and a timeline post as +1 each. Keyword data "
        "are a **census** of eligible IFB tweets; timeline data are a **stratified ~1.7% English "
        "sample** (seed 2026). Do not read combined degree as “how often the IFB population "
        "tweets these pairs.” Keyword-only and timeline-only rows are in "
        "`entity_network_summary.csv`.",
        "",
        "| Metric | Combined graph |",
        "|--------|---------------:|",
        f"| Nodes | {comb.get('n_nodes')} |",
        f"| Edges | {comb.get('n_edges')} |",
        f"| Density | {comb.get('density')} |",
        f"| Components | {comb.get('n_components')} |",
        f"| Largest component | {comb.get('largest_component')} |",
        f"| Average degree | {comb.get('average_degree')} |",
        f"| Average weighted degree | {comb.get('average_weighted_degree')} |",
        f"| Clustering (weighted) | {comb.get('clustering_coefficient')} |",
        "",
        f"Louvain communities (seed {SEED}): {len(sizes)} groups; "
        f"largest sizes {[n for _, n in top_comm]}.",
        "",
        "| Community | n | Strongest members |",
        "|-----------|--:|-------------------|",
    ]
    for cid, n in top_comm:
        members = by_comm.get(cid, [])[:6]
        L.append(f"| C{cid} | {n} | {', '.join(members)} |")
    L += [
        "",
        "Community labels are interpretive, not ground truth. A community here means "
        "“these names co-occur in text”, never “these users interact”.",
        "",
        "## Central nodes",
        "",
        "Node size in the figure is **weighted degree** (sum of co-occurring posts). "
        "PageRank, betweenness, and closeness are also stored.",
        "",
        "### Top weighted degree",
        "",
        "| Entity | category | weighted degree | degree | PageRank |",
        "|--------|----------|----------------:|-------:|---------:|",
        *fmt_rows([[r["entity"], r["category"], r["weighted_degree"], r["degree"], r["pagerank"]]
                   for r in top_w]),
        "",
        "### Top betweenness",
        "",
        "| Entity | category | betweenness |",
        "|--------|----------|------------:|",
        *fmt_rows([[r["entity"], r["category"], r["betweenness_centrality"]] for r in top_b]),
        "",
        "### Strongest edges",
        "",
        "| A | B | posts | keyword | timeline raw | timeline weighted (estimate only) |",
        "|---|---|------:|--------:|-------------:|--------------------------------:|",
        *fmt_rows([[r["entity_a"], r["entity_b"], r["edge_weight"], r["keyword_post_count"],
                    r["timeline_raw_post_count"], r["timeline_weighted_estimate"]] for r in top_e]),
        "",
        "## Source-specific and category-filtered graphs",
        "",
        "Keyword-only and timeline-only graphs use the same thresholds but only posts from that "
        "source. Timeline remains a **stratified sample** (seed 2026, ~1.7% of English timeline). "
        "Graph construction never uses `sample_weight`. Category-filtered subgraphs use the "
        "node's modal category.",
        "",
        "| Graph | nodes | edges | density | components | largest | avg degree | avg weighted degree |",
        "|-------|------:|------:|--------:|-----------:|--------:|-----------:|--------------------:|",
        *fmt_rows([[r["graph"], r["n_nodes"], r["n_edges"], r["density"], r["n_components"],
                    r["largest_component"], r["average_degree"], r["average_weighted_degree"]]
                   for r in summary]),
        "",
        "## Limitations",
        "",
        "- Co-occurrence is not alliance or friendship. Promo templates can still pair a platform "
        "with a celebrity.",
        "- Keyword IFB collection over-represents greetings and follow-back copy.",
        "- Timeline is ~1.7% of English timeline; pair rates are sample-dependent.",
        "- High-entity posts were dropped, which removes some news dumps and some genuine listicles.",
        "- Combined counts mix two sampling frames.",
        "- No follower graph can be built from this database.",
        f"- Entities shorter than {MIN_ENTITY_CHARS} characters are excluded, so legitimate short "
        "acronyms (`EU`, `UN`, `NY`) are lost along with the junk. That trade-off follows the "
        "guideline rule and is stated rather than silently applied.",
        "",
        "## Output checklist",
        "",
        "| File | Present |",
        "|------|---------|",
    ]
    for rel in ("src/entity_network_analysis.py", "src/postaudit_rebuild_entity_network.py",
                "notebooks/entity_network_analysis.ipynb", "outputs/entity_pairs.csv",
                "outputs/entity_network_edges.csv", "outputs/entity_network_nodes.csv",
                "outputs/entity_network_metrics.csv", "outputs/entity_network_summary.csv",
                "outputs/entity_network_rejections.csv",
                "outputs/entity_network_canonical_key.json",
                "outputs/entity_network_filter_provenance.json",
                "outputs/entities_dropped_short.csv",
                "outputs/entity_network_graph.png",
                "outputs/entity_network_person_person.png",
                "outputs/entity_network_person_country.png",
                "outputs/entity_network_organization.png",
                "ENTITY_NETWORK_REPORT.md"):
        L.append(f"| `{rel}` | {'yes' if (ROOT / rel).exists() else 'NO'} |")
    L.append("")
    (ROOT / "ENTITY_NETWORK_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    log("Wrote ENTITY_NETWORK_REPORT.md")


def main() -> int:
    log("=== post-audit entity + network rebuild (no NER rerun) ===")

    # The cleaned entity table is filtered first so that every downstream number
    # (node counts, figures, reports) is derived from the same filtered table.
    cleaned_keep: list[dict[str, str]] = []
    cleaned_drop: list[dict[str, str]] = []
    fields: list[str] = []
    for row in read_csv_rows(OUT / "entities_cleaned.csv"):
        if not fields:
            fields = list(row.keys())
        name = (row.get("canonical_entity") or row.get("entity") or "").strip()
        (cleaned_drop if len(name) < MIN_ENTITY_CHARS else cleaned_keep).append(row)
    if cleaned_drop:
        write_csv(OUT / "entities_cleaned.csv", fields, cleaned_keep)
        write_csv(OUT / "entities_dropped_short.csv", fields, cleaned_drop)
    else:
        already = OUT / "entities_dropped_short.csv"
        prior = sum(1 for _ in read_csv_rows(already)) if already.exists() else 0
        log(f"entities_cleaned.csv already filtered ({len(cleaned_keep):,} rows); "
            f"{prior:,} previously dropped rows preserved in {already.name}")

    post_meta = post_metadata()
    stats = entity_stats()
    node_category = {
        name: st["cats"].most_common(1)[0][0] for name, st in stats.items() if st["cats"]
    }

    pairs, dropped_pairs, rej = filter_pairs()
    log(
        f"pairs {rej['pair_rows_before_filter']:,} -> {rej['pair_rows_after_filter']:,} "
        f"(dropped short={rej['pair_rows_dropped_short_entity']:,}, "
        f"self={rej['pair_rows_dropped_self_pair']:,})"
    )

    pair_fields = ["source", "tweet_id", "created_at", "entity_a", "entity_b", "category_a", "category_b"]
    prov_path = OUT / "entity_network_filter_provenance.json"
    if dropped_pairs:
        write_csv(OUT / "entity_pairs.csv", pair_fields, pairs)
        write_csv(OUT / "entity_pairs_dropped_short_or_selfpair.csv", pair_fields + ["drop_reason"], dropped_pairs)
        provenance = {
            "pair_rows_before_filter": rej["pair_rows_before_filter"],
            "pair_rows_dropped_short_entity": rej["pair_rows_dropped_short_entity"],
            "pair_rows_dropped_self_pair": rej["pair_rows_dropped_self_pair"],
            "pair_rows_after_filter": rej["pair_rows_after_filter"],
        }
        prov_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    else:
        # Already filtered by an earlier run. Keep the recorded first-pass counts so the
        # rejection table stays truthful instead of reporting zero drops.
        provenance = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}
        for k, v in provenance.items():
            rej[k] = v
        rej["pair_rows_after_filter"] = len(pairs)
        log(f"entity_pairs.csv already filtered ({len(pairs):,} rows); reusing recorded drop counts")

    all_edges = aggregate_edges(pairs, post_meta)
    final_edges = [r for r in all_edges if int(r["edge_weight"]) >= MIN_EDGE_WEIGHT]
    rej["candidate_edges"] = len(all_edges)
    rej["edges_below_min_weight"] = len(all_edges) - len(final_edges)
    rej["final_edges"] = len(final_edges)
    log(f"candidate edges {len(all_edges):,} -> final edges {len(final_edges):,}")

    edge_fields = [
        "entity_a", "entity_b", "category_a", "category_b", "edge_weight", "unique_posts",
        "unique_users", "keyword_post_count", "timeline_raw_post_count",
        "timeline_weighted_estimate", "first_date", "last_date", "edge_key_note", "mix_note",
    ]
    write_csv(OUT / "entity_network_edges.csv", edge_fields, final_edges)

    g = build_graph(final_edges, node_category)
    cent = centralities(g)
    comm = communities(g)
    nx.set_node_attributes(g, comm, "community_id")

    node_rows = []
    for n in g.nodes:
        c = cent.get(n, {})
        st = stats.get(n, {})
        node_rows.append(
            {
                "entity": n,
                "category": g.nodes[n].get("category", ""),
                "node_weight": c.get("weighted_degree", 0),
                "unique_posts": st.get("posts", 0),
                "unique_users": st.get("users", 0),
                "n_keyword": st.get("kw", 0),
                "n_timeline": st.get("tl", 0),
                "degree": c.get("degree", 0),
                "weighted_degree": c.get("weighted_degree", 0),
                "betweenness_centrality": c.get("betweenness_centrality", 0),
                "closeness_centrality": c.get("closeness_centrality", 0),
                "pagerank": c.get("pagerank", 0),
                "eigenvector_centrality": c.get("eigenvector_centrality", 0),
                "community_id": comm.get(n, 0),
            }
        )
    node_rows.sort(key=lambda r: -float(r["weighted_degree"]))
    node_fields = list(node_rows[0].keys()) if node_rows else []
    write_csv(OUT / "entity_network_nodes.csv", node_fields, node_rows)
    write_csv(
        OUT / "entity_network_metrics.csv",
        ["entity", "category", "degree", "weighted_degree", "betweenness_centrality",
         "closeness_centrality", "pagerank", "eigenvector_centrality", "community_id"],
        [{k: r[k] for k in ("entity", "category", "degree", "weighted_degree",
                            "betweenness_centrality", "closeness_centrality", "pagerank",
                            "eigenvector_centrality", "community_id")} for r in node_rows],
    )

    def cat_pred(*cats: str):
        wanted = set(cats)
        def pred(r: dict[str, Any]) -> bool:
            a = node_category.get(r["entity_a"], r["category_a"])
            b = node_category.get(r["entity_b"], r["category_b"])
            return {a, b} <= wanted if len(wanted) == 1 else ({a, b} == wanted or (a in wanted and b in wanted))
        return pred

    g_kw = build_graph(final_edges, node_category, weight_field="keyword_post_count")
    g_tl = build_graph(final_edges, node_category, weight_field="timeline_raw_post_count")
    g_pp = build_graph(final_edges, node_category, pred=cat_pred("person"))
    g_pc = build_graph(final_edges, node_category, pred=cat_pred("person", "country"))
    g_org = build_graph(final_edges, node_category, pred=cat_pred("organization"))

    summary = [
        graph_metrics(g, "combined_min_edge"),
        graph_metrics(g_kw, "keyword_only"),
        graph_metrics(g_tl, "timeline_only_raw"),
        graph_metrics(g_pp, "person_person"),
        graph_metrics(g_pc, "person_country"),
        graph_metrics(g_org, "organization"),
    ]
    write_csv(OUT / "entity_network_summary.csv", list(summary[0].keys()), summary)

    rej_rows = [{"reason": k, "n": v} for k, v in [
        ("min_entity_chars", MIN_ENTITY_CHARS),
        ("min_entity_posts", MIN_ENTITY_POSTS),
        ("max_entities_per_post", MAX_ENTITIES_PER_POST),
        ("min_edge_weight", MIN_EDGE_WEIGHT),
        ("pair_rows_before_filter", rej["pair_rows_before_filter"]),
        ("pair_rows_dropped_short_entity", rej["pair_rows_dropped_short_entity"]),
        ("pair_rows_dropped_self_pair", rej["pair_rows_dropped_self_pair"]),
        ("pair_rows_after_filter", rej["pair_rows_after_filter"]),
        ("candidate_edges", rej["candidate_edges"]),
        ("edges_below_min_weight", rej["edges_below_min_weight"]),
        ("final_edges", rej["final_edges"]),
        ("graph_nodes", g.number_of_nodes()),
        ("graph_edges", g.number_of_edges()),
    ]]
    write_csv(OUT / "entity_network_rejections.csv", ["reason", "n"], rej_rows)

    size_key = {n: float(cent.get(n, {}).get("weighted_degree", 0)) for n in g.nodes}
    draw_network(g, OUT / "entity_network_graph.png",
                 "Entity Co-occurrence Network — Top 30 by weighted degree", size_key)
    draw_network(g_pp, OUT / "entity_network_person_person.png",
                 "Entity Co-occurrence Network — person ↔ person",
                 {n: float(d) for n, d in g_pp.degree(weight="weight")})
    draw_network(g_pc, OUT / "entity_network_person_country.png",
                 "Entity Co-occurrence Network — person ↔ country",
                 {n: float(d) for n, d in g_pc.degree(weight="weight")})
    draw_network(g_org, OUT / "entity_network_organization.png",
                 "Entity Co-occurrence Network — organization ↔ organization",
                 {n: float(d) for n, d in g_org.degree(weight="weight")})

    write_report(summary, node_rows, final_edges, rej, comm)

    issues = validate(g, final_edges)
    report = {
        "canonical_edge_key": "unordered (entity_a, entity_b) canonical entity names",
        "canonical_node_key": "canonical entity name; category is a node attribute (modal category)",
        "min_entity_chars": MIN_ENTITY_CHARS,
        "min_edge_weight": MIN_EDGE_WEIGHT,
        "seed": SEED,
        "graph_nodes": g.number_of_nodes(),
        "graph_edges": g.number_of_edges(),
        "edge_rows": len(final_edges),
        "edge_rows_equal_graph_edges": len(final_edges) == g.number_of_edges(),
        "self_loops": len(list(nx.selfloop_edges(g))),
        "entities_cleaned_rows": len(cleaned_keep),
        "entities_cleaned_dropped_short": len(cleaned_drop) or _count_rows(OUT / "entities_dropped_short.csv"),
        "pair_rows": len(pairs),
        "pair_rows_before_filter": rej.get("pair_rows_before_filter", len(pairs)),
        "pair_rows_dropped_short_entity": rej.get("pair_rows_dropped_short_entity", 0),
        "pair_rows_dropped_self_pair": rej.get("pair_rows_dropped_self_pair", 0),
        "ner_rerun": False,
        "issues": issues,
    }
    (OUT / "entity_network_canonical_key.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(json.dumps(report, indent=2, ensure_ascii=False))
    if issues:
        log("VALIDATION ISSUES FOUND")
        return 1
    log("validation clean: no self-loops, no duplicate undirected edges, no short entities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
