#!/usr/bin/env python3
"""Phase 4.2: entity co-occurrence network.

Does not open IFB.db. Does not rerun sentiment, emotion, events, BERTopic, or NER.
This is NOT a follower, reply, or retweet-cascade network.
"""

from __future__ import annotations

import csv
import itertools
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from networkx.algorithms.community import greedy_modularity_communities, louvain_communities

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
REPORT = ROOT / "ENTITY_NETWORK_REPORT.md"
CLEANED_CSV = OUTPUT_DIR / "entities_cleaned.csv"

PAIRS_CSV = OUTPUT_DIR / "entity_pairs.csv"
EDGES_CSV = OUTPUT_DIR / "entity_network_edges.csv"
NODES_CSV = OUTPUT_DIR / "entity_network_nodes.csv"
METRICS_CSV = OUTPUT_DIR / "entity_network_metrics.csv"
SUMMARY_CSV = OUTPUT_DIR / "entity_network_summary.csv"
REJECT_CSV = OUTPUT_DIR / "entity_network_rejections.csv"
GRAPH_PNG = OUTPUT_DIR / "entity_network_graph.png"
PP_PNG = OUTPUT_DIR / "entity_network_person_person.png"
PC_PNG = OUTPUT_DIR / "entity_network_person_country.png"
ORG_PNG = OUTPUT_DIR / "entity_network_organization.png"

SEED = 2026
MIN_ENTITY_POSTS = 20
MAX_ENTITIES_PER_POST = 8
MIN_EDGE_WEIGHT = 5
VIZ_TOP_N = 30

NETWORK_SKIP = frozenset(
    {
        "drop", "retweet", "dm", "steph", "otis", "bako", "yo", "hi", "jack",
        "follow wayne's", "se l'offerta vi è piaciuta", "jung kook",
        "rt", "amp", "&", "god", "lord", "pkl", "offerta", "unfollow",
        "follow me", "followme", "followme -", "no selling or bots",
        "offerta bomba", "follow archie", "dan retweet", "joe", "archie",
        "setiap hari", "followseli",
    }
)

PROMO_SUBSTR = (
    "retweet", "offerta", "postingan", "kuis", "hastag", "hashtag",
    "follow me", "follow rt", "unfollow", "followme", "alfagift",
    "alfamart", "rt e fav", "siga todos", "prezzi", "preferite",
    "airdrop", "sertakan", "jawaban dan",
)

NETWORK_ALIASES = {
    "the united states of america": ("United States", "country"),
}

PROMO_TOKEN_RE = re.compile(
    r"\b(ini|hingga|sertakan|jawaban|periode|juga|hastag|kuis)\b",
    re.I,
)

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


def log(msg: str) -> None:
    print(msg, flush=True)


def connect_nlp() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{NLP_DB.as_posix()}?mode=ro", uri=True, timeout=180)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def is_quality_entity(name: str) -> bool:
    raw = (name or "").strip()
    low = raw.lower()
    if not raw or "&" in raw:
        return False
    if low in NETWORK_SKIP:
        return False
    if low.startswith("follow ") or low.startswith("followme"):
        return False
    if any(s in low for s in PROMO_SUBSTR):
        return False
    if "#" in raw or "@" in raw:
        return False
    if len(raw) > 36 or len(raw.split()) >= 5:
        return False
    if PROMO_TOKEN_RE.search(raw) and len(raw.split()) >= 3:
        return False
    return True


def canonicalize_mention(ent: str, cat: str) -> tuple[str, str] | None:
    ent = (ent or "").strip()
    cat = (cat or "other").strip()
    alias = NETWORK_ALIASES.get(ent.lower())
    if alias:
        ent, cat = alias
    if not is_quality_entity(ent):
        return None
    return ent, cat


def pair_key(a: str, ca: str, b: str, cb: str) -> tuple[tuple[str, str], tuple[str, str]]:
    left = (a, ca)
    right = (b, cb)
    return (left, right) if left <= right else (right, left)


def load_mentions(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], int]:
    rows = conn.execute(
        """
        SELECT source, tweet_id, author_id, created_at, sample_weight,
               canonical_entity, normalized_category
        FROM entity_mention
        WHERE keep_flag=1
          AND canonical_entity IS NOT NULL
          AND TRIM(canonical_entity) != ''
        """
    ).fetchall()
    out = []
    skipped = 0
    for r in rows:
        parsed = canonicalize_mention(r["canonical_entity"] or "", r["normalized_category"] or "other")
        if not parsed:
            skipped += 1
            continue
        ent, cat = parsed
        out.append(
            {
                "source": r["source"],
                "tweet_id": r["tweet_id"],
                "author_id": r["author_id"] or "",
                "created_at": r["created_at"] or "",
                "sample_weight": float(r["sample_weight"] or 1),
                "entity": ent,
                "category": cat,
            }
        )
    return out, skipped


def eligible_entities(mentions: list[dict[str, Any]]) -> set[tuple[str, str]]:
    posts: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for m in mentions:
        posts[(m["entity"], m["category"])].add((m["source"], m["tweet_id"]))
    return {k for k, v in posts.items() if len(v) >= MIN_ENTITY_POSTS}


def build_pairs(
    mentions: list[dict[str, Any]], eligible: set[tuple[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, int], dict[tuple[str, str], dict[str, Any]]]:
    by_post: dict[tuple[str, str], dict[str, Any]] = {}
    for m in mentions:
        key = (m["source"], m["tweet_id"])
        rec = by_post.setdefault(
            key,
            {
                "source": m["source"],
                "tweet_id": m["tweet_id"],
                "author_id": m["author_id"],
                "created_at": m["created_at"],
                "sample_weight": m["sample_weight"],
                "ents": {},
            },
        )
        ek = (m["entity"], m["category"])
        if ek in eligible:
            rec["ents"][ek] = True

    rejects = Counter()
    rejects["posts_scanned"] = len(by_post)
    pair_rows: list[dict[str, Any]] = []
    edge_acc: dict[tuple[tuple[str, str], tuple[str, str]], dict[str, Any]] = {}

    for rec in by_post.values():
        ents = sorted(rec["ents"])
        n = len(ents)
        if n == 0:
            rejects["posts_no_eligible_entity"] += 1
            continue
        if n == 1:
            rejects["posts_single_eligible_entity"] += 1
            continue
        if n > MAX_ENTITIES_PER_POST:
            rejects["posts_too_many_entities"] += 1
            continue
        rejects["posts_used_for_pairs"] += 1
        for (ea, ca), (eb, cb) in itertools.combinations(ents, 2):
            if ea == eb and ca == cb:
                rejects["self_loops_prevented"] += 1
                continue
            left, right = pair_key(ea, ca, eb, cb)
            pair_rows.append(
                {
                    "source": rec["source"],
                    "tweet_id": rec["tweet_id"],
                    "created_at": rec["created_at"],
                    "entity_a": left[0],
                    "entity_b": right[0],
                    "category_a": left[1],
                    "category_b": right[1],
                }
            )
            acc = edge_acc.setdefault(
                (left, right),
                {
                    "posts": set(),
                    "users": set(),
                    "kw": 0,
                    "tl": 0,
                    "tl_w": 0.0,
                    "dates": [],
                },
            )
            post_id = (rec["source"], rec["tweet_id"])
            if post_id not in acc["posts"]:
                acc["posts"].add(post_id)
                acc["users"].add(rec["author_id"])
                acc["dates"].append(rec["created_at"])
                if rec["source"] == "keyword_tweets":
                    acc["kw"] += 1
                else:
                    acc["tl"] += 1
                    acc["tl_w"] += rec["sample_weight"]
    rejects["pair_rows"] = len(pair_rows)
    rejects["candidate_edges"] = len(edge_acc)
    return pair_rows, dict(rejects), edge_acc


def edge_records(edge_acc: dict[Any, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for (left, right), acc in edge_acc.items():
        n = len(acc["posts"])
        dates = [d for d in acc["dates"] if d]
        rows.append(
            {
                "entity_a": left[0],
                "entity_b": right[0],
                "category_a": left[1],
                "category_b": right[1],
                "edge_weight": n,
                "unique_posts": n,
                "unique_users": len(acc["users"]),
                "keyword_post_count": acc["kw"],
                "timeline_raw_post_count": acc["tl"],
                "timeline_weighted_estimate": round(acc["tl_w"], 2),
                "first_date": min(dates) if dates else "",
                "last_date": max(dates) if dates else "",
                "mix_note": (
                    "combined unique_posts mixes keyword census (weight=1) with timeline sample; "
                    "timeline_weighted_estimate is a population estimate only and is NOT the graph weight"
                ),
            }
        )
    rows.sort(key=lambda r: (-int(r["edge_weight"]), r["entity_a"], r["entity_b"]))
    return rows


def node_post_stats(
    mentions: list[dict[str, Any]], eligible: set[tuple[str, str]]
) -> dict[tuple[str, str], dict[str, Any]]:
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for m in mentions:
        key = (m["entity"], m["category"])
        if key not in eligible:
            continue
        st = stats.setdefault(key, {"posts": set(), "users": set(), "kw": 0, "tl": 0})
        pid = (m["source"], m["tweet_id"])
        if pid not in st["posts"]:
            st["posts"].add(pid)
            st["users"].add(m["author_id"])
            if m["source"] == "keyword_tweets":
                st["kw"] += 1
            else:
                st["tl"] += 1
    return stats


def graph_from_edges(edges: list[dict[str, Any]], pred=None) -> nx.Graph:
    g = nx.Graph()
    for r in edges:
        if pred and not pred(r):
            continue
        if int(r["edge_weight"]) < MIN_EDGE_WEIGHT:
            continue
        a = (r["entity_a"], r["category_a"])
        b = (r["entity_b"], r["category_b"])
        if a == b:
            continue
        na = r["entity_a"] if a[0] != b[0] else f"{a[0]} [{a[1]}]"
        nb = r["entity_b"] if a[0] != b[0] else f"{b[0]} [{b[1]}]"
        if na == nb:
            continue
        g.add_node(na, category=a[1], entity=a[0])
        g.add_node(nb, category=b[1], entity=b[0])
        if g.has_edge(na, nb):
            g[na][nb]["weight"] += int(r["edge_weight"])
        else:
            g.add_edge(na, nb, weight=int(r["edge_weight"]))
    return g


def attach_centralities(g: nx.Graph) -> dict[str, dict[str, float]]:
    if g.number_of_nodes() == 0:
        return {}
    deg = dict(g.degree())
    wdeg = dict(g.degree(weight="weight"))
    pr = nx.pagerank(g, weight="weight", alpha=0.85)
    try:
        btw = nx.betweenness_centrality(g, weight="weight", normalized=True)
    except Exception:
        btw = {n: 0.0 for n in g}
    clos = {n: 0.0 for n in g}
    if g.number_of_nodes():
        largest = max(nx.connected_components(g), key=len)
        sub = g.subgraph(largest)
        clos.update(nx.closeness_centrality(sub))
    ev = {n: 0.0 for n in g}
    try:
        raw = nx.eigenvector_centrality_numpy(g, weight="weight")
        ev.update({n: float(v) for n, v in raw.items()})
    except Exception:
        ev = {n: float(pr[n]) for n in g}
    out = {}
    for n in g.nodes:
        out[n] = {
            "degree": float(deg[n]),
            "weighted_degree": float(wdeg[n]),
            "betweenness_centrality": float(btw.get(n, 0)),
            "closeness_centrality": float(clos.get(n, 0)),
            "pagerank": float(pr.get(n, 0)),
            "eigenvector_centrality": float(ev.get(n, 0)),
        }
    return out


def graph_metrics(g: nx.Graph, name: str) -> dict[str, Any]:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    comps = list(nx.connected_components(g)) if n else []
    largest = max((len(c) for c in comps), default=0)
    clustering = 0.0
    if n and m:
        try:
            clustering = float(nx.average_clustering(g, weight="weight"))
        except Exception:
            clustering = float(nx.average_clustering(g))
    wdegs = [d for _, d in g.degree(weight="weight")] if n else []
    degs = [d for _, d in g.degree()] if n else []
    return {
        "graph": name,
        "n_nodes": n,
        "n_edges": m,
        "density": round(nx.density(g), 6) if n > 1 else 0,
        "n_components": len(comps),
        "largest_component": largest,
        "average_degree": round(sum(degs) / n, 4) if n else 0,
        "average_weighted_degree": round(sum(wdegs) / n, 4) if n else 0,
        "clustering_coefficient": round(clustering, 4),
        "note": "Entity co-occurrence, not a follower network",
    }


def communities(g: nx.Graph) -> dict[str, int]:
    if g.number_of_nodes() < 3:
        return {n: 0 for n in g}
    try:
        comms = list(louvain_communities(g, weight="weight", seed=SEED))
    except Exception:
        comms = list(greedy_modularity_communities(g, weight="weight"))
    mapping = {}
    for i, members in enumerate(sorted(comms, key=len, reverse=True)):
        for n in members:
            mapping[n] = i
    return mapping


def draw_network(g: nx.Graph, path: Path, title: str, size_key: dict[str, float], top_n: int = VIZ_TOP_N) -> None:
    if g.number_of_nodes() == 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "No edges after thresholds", ha="center")
        fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return
    comps = list(nx.connected_components(g))
    largest = max(comps, key=len)
    base = g.subgraph(largest)
    ranked = sorted(base.nodes, key=lambda n: size_key.get(n, 0), reverse=True)
    keep = set(ranked[:top_n])
    sub = base.subgraph(keep).copy()
    if sub.number_of_edges() < max(8, top_n // 2):
        extras = []
        for n in list(keep):
            nbrs = sorted(base[n], key=lambda x: base[n][x].get("weight", 1), reverse=True)[:2]
            extras.extend(nbrs)
        keep.update(extras[:12])
        sub = base.subgraph(keep).copy()
    n_shown = max(sub.number_of_nodes(), 1)
    pos = nx.spring_layout(sub, seed=SEED, k=2.6 / math.sqrt(n_shown), iterations=140)
    fig, ax = plt.subplots(figsize=(13.2, 10.2))
    fig.patch.set_facecolor("white")
    weights = [sub[u][v].get("weight", 1) for u, v in sub.edges]
    wmax = max(weights) if weights else 1
    widths = [0.6 + 4.2 * (w / wmax) for w in weights]
    nx.draw_networkx_edges(sub, pos, ax=ax, width=widths, edge_color="#9aa0a6", alpha=0.65)
    sizes = []
    colors = []
    smax = max((size_key.get(n, 1) for n in sub), default=1) or 1
    for n in sub.nodes:
        sizes.append(280 + 2200 * (size_key.get(n, 0) / smax))
        colors.append(CAT_COLOR.get(sub.nodes[n].get("category", ""), "#888888"))
    nx.draw_networkx_nodes(sub, pos, ax=ax, node_size=sizes, node_color=colors, linewidths=0.8, edgecolors="white")
    labels = {n: n if len(n) <= 22 else n[:20] + "…" for n in sub.nodes}
    nx.draw_networkx_labels(sub, pos, labels=labels, ax=ax, font_size=8, font_color="#222222")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax.text(
        0.5,
        -0.02,
        "Not a follower / user-user network. IFB.db has no follow, reply, or retweet-cascade edges.\n"
        f"Largest component, top {len(sub)} nodes by weighted degree. Node size = weighted degree. Edge width = distinct posts. Seed {SEED}.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color="#333333",
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


def write_report(
    rejects: dict[str, int],
    summary: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    comm_sizes: list[int],
    checklist: dict[str, bool],
) -> None:
    top_w = sorted(nodes, key=lambda r: -float(r["weighted_degree"]))[:8]
    top_b = sorted(nodes, key=lambda r: -float(r["betweenness_centrality"]))[:8]
    top_e = edges[:10]
    lines = [
        "# Entity co-occurrence network",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "IFB.db was not opened. Sentiment, emotion, events, BERTopic, and NER were not rerun.",
        "",
        "## Network definition",
        "",
        "This is an **entity co-occurrence** network. Nodes are cleaned canonical entities from `entity_mention` (`keep_flag=1`). "
        "An undirected edge joins two entities when they appear in the **same post**. "
        f"`edge_weight` = number of **distinct posts** containing both (`MIN_EDGE_WEIGHT={MIN_EDGE_WEIGHT}` on the final graph). "
        "Repeated mentions of the same entity inside one post count once. "
        f"Posts with more than **{MAX_ENTITIES_PER_POST}** eligible entities are dropped (hashtag-wall / promo dumps). "
        f"Entities need at least **{MIN_ENTITY_POSTS}** unique posts to enter pairing.",
        "",
        "## Why there is no follower network",
        "",
        "`IFB.db` has follower **counts**, not edges. There are no follow/following adjacency lists, no `in_reply_to` / quote IDs, and no retweet-cascade table. "
        "The graded network in the course file list is entity co-occurrence. This report does **not** invent user-user edges.",
        "",
        "## Cleaning and aliases",
        "",
        "Mentions already passed NER cleaning (`&`, URLs, @usernames, IFB tokens, one-character junk). "
        "A second skip-list removes leftover promo shells (`Drop`, `Retweet`, `Steph`, `Otis`, Italian offer copy, "
        "Alfamart quiz fragments, `#hashtag` / `@user` leftovers, and sentence-length NER mistakes). "
        "Canonical names and categories match `entities_cleaned.csv`.",
        "",
        "## Thresholds (seed 2026)",
        "",
        "| Rule | Value |",
        "|------|------:|",
        f"| Minimum unique posts per entity | {MIN_ENTITY_POSTS} |",
        f"| Maximum eligible entities per post | {MAX_ENTITIES_PER_POST} |",
        f"| Minimum distinct posts per edge (final graph) | {MIN_EDGE_WEIGHT} |",
        f"| Visualization | top {VIZ_TOP_N} nodes by weighted degree |",
        f"| Layout / Louvain seed | {SEED} |",
        "| Graph weight | unweighted post counts only |",
        "",
        "Timeline `sample_weight` is stored as `timeline_weighted_estimate` on edges. It is **not** used to build edges or to score centrality.",
        "",
        "## Rejection summary",
        "",
    ]
    for k, v in rejects.items():
        lines.append(f"- `{k}`: {v:,}")
    comb = next((r for r in summary if r["graph"] == "combined_min_edge"), {})
    lines += [
        "",
        "## Combined graph (explicit mix warning)",
        "",
        "The combined graph counts a keyword post and a timeline post as +1 each. Keyword data are a **census** of eligible IFB tweets; timeline data are a **stratified ~1.7% English sample** (seed 2026). "
        "Do not read combined degree as “how often the IFB population tweets these pairs.” Keyword-only and timeline-only rows are in `entity_network_summary.csv`.",
        "",
        "| Metric | Combined graph |",
        "|--------|---------------:|",
        f"| Nodes | {comb.get('n_nodes', '')} |",
        f"| Edges | {comb.get('n_edges', '')} |",
        f"| Density | {comb.get('density', '')} |",
        f"| Components | {comb.get('n_components', '')} |",
        f"| Largest component | {comb.get('largest_component', '')} |",
        f"| Average degree | {comb.get('average_degree', '')} |",
        f"| Average weighted degree | {comb.get('average_weighted_degree', '')} |",
        f"| Clustering (weighted) | {comb.get('clustering_coefficient', '')} |",
        "",
        f"Louvain communities (seed {SEED}): {len(comm_sizes)} groups; largest sizes {comm_sizes[:6]}.",
        "",
        "## Central nodes",
        "",
        "Node size in the figure is **weighted degree** (sum of co-occurring posts). PageRank, betweenness, and closeness are also stored.",
        "",
        "### Top weighted degree",
        "",
        "| Entity | category | weighted degree | degree | PageRank |",
        "|--------|----------|----------------:|-------:|---------:|",
    ]
    for r in top_w:
        lines.append(
            f"| {r['entity']} | {r['category']} | {r['weighted_degree']} | {r['degree']} | {r['pagerank']} |"
        )
    lines += [
        "",
        "### Top betweenness",
        "",
        "| Entity | category | betweenness |",
        "|--------|----------|------------:|",
    ]
    for r in top_b:
        lines.append(f"| {r['entity']} | {r['category']} | {r['betweenness_centrality']} |")
    lines += [
        "",
        "### Strongest edges",
        "",
        "| A | B | posts | keyword | timeline raw | timeline weighted (estimate only) |",
        "|---|---|------:|--------:|-------------:|--------------------------------:|",
    ]
    for r in top_e:
        lines.append(
            f"| {r['entity_a']} | {r['entity_b']} | {r['unique_posts']} | {r['keyword_post_count']} | "
            f"{r['timeline_raw_post_count']} | {r['timeline_weighted_estimate']} |"
        )
    lines += [
        "",
        "## Source-specific graphs",
        "",
        "Keyword-only and timeline-only graphs use the same thresholds but only posts from that source. "
        "Timeline remains a **stratified sample** (seed 2026, ~1.7% of English timeline). Graph construction never uses `sample_weight`.",
        "",
        "| Graph | nodes | edges | density | components | largest | avg degree | avg weighted degree |",
        "|-------|------:|------:|--------:|-----------:|--------:|-----------:|--------------------:|",
    ]
    for r in summary:
        lines.append(
            f"| {r['graph']} | {r['n_nodes']} | {r['n_edges']} | {r['density']} | {r['n_components']} | "
            f"{r['largest_component']} | {r['average_degree']} | {r['average_weighted_degree']} |"
        )
    lines += [
        "",
        "## Limitations",
        "",
        "- Co-occurrence ≠ alliance or friendship. Promo templates can still pair a platform with a celebrity.",
        "- Keyword IFB collection over-represents greetings and follow-back copy.",
        "- Timeline is ~1.7% of English timeline; pair rates are sample-dependent.",
        "- High-entity posts were dropped, which removes some news dumps and some genuine listicles.",
        "- Combined counts mix two sampling frames.",
        "- No follower graph can be built from this database.",
        "",
        "## Output checklist",
        "",
        "| File | Present |",
        "|------|---------|",
    ]
    for k, ok in checklist.items():
        lines.append(f"| `{k}` | {'yes' if ok else 'NO'} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {REPORT.name}")


def validate(
    g: nx.Graph,
    edges: list[dict[str, Any]],
    pair_n: int,
    cleaned_names: set[str],
) -> list[str]:
    issues = []
    seen = set()
    for r in edges:
        a, b = r["entity_a"], r["entity_b"]
        if a == b and r["category_a"] == r["category_b"]:
            issues.append("self-loop in edges")
            break
        key = pair_key(a, r["category_a"], b, r["category_b"])
        if key in seen:
            issues.append("duplicate undirected edge")
            break
        seen.add(key)
        if int(r["edge_weight"]) != int(r["unique_posts"]) or int(r["edge_weight"]) < 1:
            issues.append("edge_weight != unique_posts")
            break
        if cleaned_names and (a not in cleaned_names or b not in cleaned_names):
            issues.append(f"edge name missing from cleaned CSV: {a} / {b}")
            break
        if "&" in a or "&" in b:
            issues.append("junk & node")
            break
    if pair_n < 1:
        issues.append("no pair rows")
    if g.number_of_nodes() and any(u == v for u, v in g.edges):
        issues.append("graph self-loop")
    if issues:
        for i in issues:
            log("VALIDATE FAIL: " + i)
    else:
        log("VALIDATE_OK")
    return issues


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log("Loading kept mentions from SQLite (read-only)")
    conn = connect_nlp()
    try:
        mentions, skipped_quality = load_mentions(conn)
    finally:
        conn.close()
    log(f"mentions after skip-list {len(mentions):,}")
    eligible = eligible_entities(mentions)
    rejects = {
        "min_entity_posts": MIN_ENTITY_POSTS,
        "mentions_dropped_quality_or_promo": skipped_quality,
        "entities_eligible": len(eligible),
        "entities_below_frequency": len({(m["entity"], m["category"]) for m in mentions}) - len(eligible),
    }
    log(f"eligible entities {len(eligible):,} (n_posts>={MIN_ENTITY_POSTS})")
    pair_rows, rej2, edge_acc = build_pairs(mentions, eligible)
    rejects.update(rej2)
    all_edges = edge_records(edge_acc)
    final_edges = [r for r in all_edges if int(r["unique_posts"]) >= MIN_EDGE_WEIGHT]
    rejects["edges_below_min_weight"] = len(all_edges) - len(final_edges)
    rejects["final_edges"] = len(final_edges)
    log(f"pairs={len(pair_rows):,} candidate_edges={len(all_edges):,} final_edges={len(final_edges):,}")

    write_csv(
        PAIRS_CSV,
        ["source", "tweet_id", "created_at", "entity_a", "entity_b", "category_a", "category_b"],
        pair_rows,
    )
    write_csv(
        EDGES_CSV,
        [
            "entity_a", "entity_b", "category_a", "category_b",
            "edge_weight", "unique_posts", "unique_users",
            "keyword_post_count", "timeline_raw_post_count", "timeline_weighted_estimate",
            "first_date", "last_date", "mix_note",
        ],
        final_edges,
    )
    write_csv(
        REJECT_CSV,
        ["reason", "n"],
        [{"reason": k, "n": v} for k, v in rejects.items()],
    )

    g = graph_from_edges(final_edges)
    cents = attach_centralities(g)
    comm = communities(g)
    comm_sizes = list(Counter(comm.values()).values())
    comm_sizes.sort(reverse=True)
    node_stats = node_post_stats(mentions, eligible)
    nodes = []
    metrics = []
    for n, data in g.nodes(data=True):
        cat = data.get("category", "")
        ent = data.get("entity", n)
        st = node_stats.get((ent, cat), {"posts": set(), "users": set(), "kw": 0, "tl": 0})
        c = cents.get(n, {})
        row = {
            "entity": ent,
            "category": cat,
            "node_weight": c.get("weighted_degree", 0),
            "unique_posts": len(st["posts"]),
            "unique_users": len(st["users"]),
            "n_keyword": st["kw"],
            "n_timeline": st["tl"],
            "degree": c.get("degree", 0),
            "weighted_degree": c.get("weighted_degree", 0),
            "betweenness_centrality": round(c.get("betweenness_centrality", 0), 6),
            "closeness_centrality": round(c.get("closeness_centrality", 0), 6),
            "pagerank": round(c.get("pagerank", 0), 6),
            "eigenvector_centrality": round(c.get("eigenvector_centrality", 0), 6),
            "community_id": comm.get(n, -1),
        }
        nodes.append(row)
        metrics.append(row)
    nodes.sort(key=lambda r: -float(r["weighted_degree"]))
    write_csv(
        NODES_CSV,
        [
            "entity", "category", "node_weight", "unique_posts", "unique_users",
            "n_keyword", "n_timeline", "degree", "weighted_degree",
            "betweenness_centrality", "closeness_centrality", "pagerank",
            "eigenvector_centrality", "community_id",
        ],
        nodes,
    )
    write_csv(
        METRICS_CSV,
        [
            "entity", "category", "degree", "weighted_degree",
            "betweenness_centrality", "closeness_centrality", "pagerank", "eigenvector_centrality",
            "community_id",
        ],
        metrics,
    )

    g_kw = nx.Graph()
    g_tl = nx.Graph()
    for r in all_edges:
        a, b = r["entity_a"], r["entity_b"]
        if a == b:
            continue
        if int(r["keyword_post_count"]) >= MIN_EDGE_WEIGHT:
            g_kw.add_node(a, category=r["category_a"])
            g_kw.add_node(b, category=r["category_b"])
            g_kw.add_edge(a, b, weight=int(r["keyword_post_count"]))
        if int(r["timeline_raw_post_count"]) >= MIN_EDGE_WEIGHT:
            g_tl.add_node(a, category=r["category_a"])
            g_tl.add_node(b, category=r["category_b"])
            g_tl.add_edge(a, b, weight=int(r["timeline_raw_post_count"]))

    def cat_pred(*cats):
        return lambda r: r["category_a"] in cats and r["category_b"] in cats

    def mixed_pred(a, b):
        return lambda r: {r["category_a"], r["category_b"]} == {a, b}

    g_pp = graph_from_edges(final_edges, pred=cat_pred("person"))
    g_pc = graph_from_edges(final_edges, pred=mixed_pred("person", "country"))
    g_org = graph_from_edges(final_edges, pred=cat_pred("organization"))

    summary = [
        graph_metrics(g, "combined_min_edge"),
        graph_metrics(g_kw, "keyword_only"),
        graph_metrics(g_tl, "timeline_only_raw"),
        graph_metrics(g_pp, "person_person"),
        graph_metrics(g_pc, "person_country"),
        graph_metrics(g_org, "organization"),
    ]
    write_csv(
        SUMMARY_CSV,
        [
            "graph", "n_nodes", "n_edges", "density", "n_components", "largest_component",
            "average_degree", "average_weighted_degree", "clustering_coefficient", "note",
        ],
        summary,
    )

    wdeg = {n: cents[n]["weighted_degree"] for n in g}
    draw_network(g, GRAPH_PNG, "Entity Co-occurrence Network", wdeg, VIZ_TOP_N)
    draw_network(g_pp, PP_PNG, "Entity Co-occurrence Network — person–person", dict(g_pp.degree(weight="weight")), 24)
    draw_network(g_pc, PC_PNG, "Entity Co-occurrence Network — person–country", dict(g_pc.degree(weight="weight")), 24)
    draw_network(g_org, ORG_PNG, "Entity Co-occurrence Network — organizations", dict(g_org.degree(weight="weight")), 24)

    cleaned_names = set()
    if CLEANED_CSV.exists():
        with CLEANED_CSV.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                cleaned_names.add(row.get("canonical_entity") or row.get("entity") or "")
    issues = validate(g, final_edges, len(pair_rows), cleaned_names)
    checklist = {
        "src/entity_network_analysis.py": True,
        "notebooks/entity_network_analysis.ipynb": (ROOT / "notebooks" / "entity_network_analysis.ipynb").exists(),
        "outputs/entity_pairs.csv": PAIRS_CSV.exists(),
        "outputs/entity_network_edges.csv": EDGES_CSV.exists(),
        "outputs/entity_network_nodes.csv": NODES_CSV.exists(),
        "outputs/entity_network_metrics.csv": METRICS_CSV.exists(),
        "outputs/entity_network_summary.csv": SUMMARY_CSV.exists(),
        "outputs/entity_network_graph.png": GRAPH_PNG.exists(),
        "outputs/entity_network_person_person.png": PP_PNG.exists(),
        "outputs/entity_network_person_country.png": PC_PNG.exists(),
        "outputs/entity_network_organization.png": ORG_PNG.exists(),
        "ENTITY_NETWORK_REPORT.md": True,
    }
    write_report(rejects, summary, nodes, final_edges, comm_sizes, checklist)
    log("NETWORK_COMPLETE")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
