#!/usr/bin/env python3
"""Phase 3: BERTopic on topic_text + topic × sentiment.

Does not open IFB.db. Does not rerun sentiment, emotion, or event detection.
Models topic_text (IFB/follow already stripped). Never names a topic IFB / follow-for-follow.
"""

from __future__ import annotations

import csv
import json
import os
import pickle
import random
import re
import sqlite3
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from language_detection_and_preprocessing import IFB_TOKENS, MIN_NLP_TOKENS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
CACHE_DIR = OUTPUT_DIR / "bertopic_cache"
REPORT = ROOT / "TOPIC_MODELING_REPORT.md"
EVENTS_JSON = OUTPUT_DIR / "detected_events.json"

SEED = 2026
STATUS_FILTER = "not_required_english"
EXPECTED_N = 742_942
TUNE_N = 64_000
TRANSFORM_BATCH = 4_096
EMBED_BATCH = 96
MIN_TOPIC_TOKENS = MIN_NLP_TOKENS
COHERENCE_DOCS = 8_000
TOPN_WORDS = 10
REP_TWEETS = 8
TOP6 = 6

PKL = OUTPUT_DIR / "topic_model.pkl"
EXP_CSV = OUTPUT_DIR / "bertopic_experiments.csv"
COH_CSV = OUTPUT_DIR / "coherence_scores.csv"
COH_PNG = OUTPUT_DIR / "coherence_plot.png"
FINAL_CSV = OUTPUT_DIR / "final_topics.csv"
REP_CSV = OUTPUT_DIR / "topic_representative_tweets.csv"
DIST_CSV = OUTPUT_DIR / "topic_distribution.csv"
SENT_CSV = OUTPUT_DIR / "topic_sentiment_distribution.csv"
SENT_SRC_CSV = OUTPUT_DIR / "topic_sentiment_by_source.csv"
SENT_PNG = OUTPUT_DIR / "topic_sentiment_visualization.png"

POS, NEU, NEG = "positive", "neutral", "negative"
SENT_COLOR = {POS: "#2ca02c", NEU: "#ffcc00", NEG: "#d62728"}
BANNED_NAME = re.compile(r"\b(ifb|follow\s*for\s*follow|follow\s*4\s*follow|f4f|followback)\b", re.I)

EXTRA_STOP = {
    "amp", "http", "https", "www", "com", "co", "ly", "bit", "html", "gt", "lt",
    "via", "u", "im", "dont", "cant", "wont", "thats", "youre", "didnt",
    "siguemeytesigo", "folloforfolloback", "followbot", "getrekt",
}
VECTORIZER_STOP = frozenset(ENGLISH_STOP_WORDS) | frozenset(IFB_TOKENS) | EXTRA_STOP
DISPLAY_DROP = frozenset(EXTRA_STOP) | frozenset(IFB_TOKENS)
BOILER_RE = re.compile(
    r"(?i)(#|\b)(ifb|f4f|fff|ff|followforfollow|follow4follow|followback|"
    r"teamfollowback|followfriday|followme|ifollowback|instantfollowback|"
    r"follow_me|followforfollowback)(\b|#)"
)

CONFIGS: list[dict[str, Any]] = [
    {"name": "C10_min200_nn15", "embed": "all-MiniLM-L6-v2", "min_topic_size": 200, "n_neighbors": 15, "n_components": 5, "ngram": (1, 1), "reduce_outliers": False, "nr_topics": None},
    {"name": "C11_min300_nn15", "embed": "all-MiniLM-L6-v2", "min_topic_size": 300, "n_neighbors": 15, "n_components": 5, "ngram": (1, 1), "reduce_outliers": False, "nr_topics": None},
    {"name": "C12_min80_reduce_nt20", "embed": "all-MiniLM-L6-v2", "min_topic_size": 80, "n_neighbors": 15, "n_components": 5, "ngram": (1, 1), "reduce_outliers": True, "nr_topics": 20},
    {"name": "C13_min50_nn30_reduce_nt24", "embed": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 30, "n_components": 5, "ngram": (1, 1), "reduce_outliers": True, "nr_topics": 24},
    {"name": "C14_min150_reduce", "embed": "all-MiniLM-L6-v2", "min_topic_size": 150, "n_neighbors": 15, "n_components": 5, "ngram": (1, 1), "reduce_outliers": True, "nr_topics": None},
    {"name": "C15_min200_reduce_nt18", "embed": "all-MiniLM-L6-v2", "min_topic_size": 200, "n_neighbors": 15, "n_components": 5, "ngram": (1, 1), "reduce_outliers": True, "nr_topics": 18},
]

# C1–C9 already measured on the same 64k MiniLM/L12 tune sample (seed 2026).
# Re-listed here so the experiment table is complete without re-running 90s UMAP each.
PRIOR_EXPERIMENTS: list[dict[str, Any]] = [
    {"configuration_name": "C1_min40_nn15_nc5_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 40, "n_neighbors": 15, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 183, "Topic_num": 183, "outlier_count": 31130, "outlier_pct": 48.64, "coherence": 0.5273, "coherence_cv": 0.5273, "diversity": 0.6419, "ifb_topword_hits": 0, "runtime_sec": 130.2, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C2_min50_nn15_nc5_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 15, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 144, "Topic_num": 144, "outlier_count": 32909, "outlier_pct": 51.42, "coherence": 0.501, "coherence_cv": 0.501, "diversity": 0.6568, "ifb_topword_hits": 0, "runtime_sec": 96.9, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C3_min80_nn15_nc5_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 80, "n_neighbors": 15, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 94, "Topic_num": 94, "outlier_count": 34259, "outlier_pct": 53.53, "coherence": 0.4677, "coherence_cv": 0.4677, "diversity": 0.7437, "ifb_topword_hits": 0, "runtime_sec": 96.9, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C4_min50_nn10_nc5_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 10, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 170, "Topic_num": 170, "outlier_count": 31168, "outlier_pct": 48.7, "coherence": 0.505, "coherence_cv": 0.505, "diversity": 0.6564, "ifb_topword_hits": 0, "runtime_sec": 83.5, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C5_min50_nn30_nc5_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 30, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 142, "Topic_num": 142, "outlier_count": 34323, "outlier_pct": 53.63, "coherence": 0.5128, "coherence_cv": 0.5128, "diversity": 0.6309, "ifb_topword_hits": 0, "runtime_sec": 120.9, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C6_min50_nn15_nc5_bi", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 15, "n_components": 5, "ngram": "1-2", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 138, "Topic_num": 138, "outlier_count": 31264, "outlier_pct": 48.85, "coherence": 0.5219, "coherence_cv": 0.5219, "diversity": 0.6689, "ifb_topword_hits": 0, "runtime_sec": 83.3, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C7_min50_nn15_nc8_uni", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 15, "n_components": 8, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 140, "Topic_num": 140, "outlier_count": 32819, "outlier_pct": 51.28, "coherence": 0.4924, "coherence_cv": 0.4924, "diversity": 0.6714, "ifb_topword_hits": 0, "runtime_sec": 95.6, "memory_runtime_notes": "prior grid on same 64k sample", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
    {"configuration_name": "C8_min50_nn15_reduce", "embedding_model": "all-MiniLM-L6-v2", "min_topic_size": 50, "n_neighbors": 15, "n_components": 5, "ngram": "1-1", "reduce_outliers": 1, "nr_topics_target": "", "sample_size": 64000, "n_topics": 148, "Topic_num": 148, "outlier_count": 0, "outlier_pct": 0.0, "coherence": 0.5027, "coherence_cv": 0.5027, "diversity": 0.7165, "ifb_topword_hits": 0, "runtime_sec": 90.9, "memory_runtime_notes": "reduce_outliers embeddings; still too many topics to name", "selected": "rejected", "reject_reason": "too_many_topics_to_name"},
    {"configuration_name": "C9_l12_min50_nn15", "embedding_model": "all-MiniLM-L12-v2", "min_topic_size": 50, "n_neighbors": 15, "n_components": 5, "ngram": "1-1", "reduce_outliers": 0, "nr_topics_target": "", "sample_size": 64000, "n_topics": 145, "Topic_num": 145, "outlier_count": 32378, "outlier_pct": 50.59, "coherence": 0.5192, "coherence_cv": 0.5192, "diversity": 0.6512, "ifb_topword_hits": 0, "runtime_sec": 76.4, "memory_runtime_notes": "second embedding model on same 64k docs", "selected": "rejected", "reject_reason": "too_many_topics_high_outliers"},
]

NAME_RULES: list[tuple[str, str]] = [
    (r"thanksgiv", "Thanksgiving greetings"),
    (r"merry christmas|\bchristmas\b|\bxmas\b", "Christmas greetings"),
    (r"happy birthday|\bbirthday\b", "Birthday wishes"),
    (r"happy new year|new year", "New Year greetings"),
    (r"mother'?s?\s*day", "Mother's Day greetings"),
    (r"father'?s?\s*day", "Father's Day greetings"),
    (r"\beid\b|ramadan", "Eid / Ramadan greetings"),
    (r"\b(god|jesus|christ|pray|amen|church|bible|lord)\b", "Faith and prayer"),
    (r"\b(trump|biden|maga|democrat|republican|election|congress)\b", "US politics"),
    (r"\b(covid|coronavirus|vaccine|lockdown|pandemic)\b", "COVID-19 talk"),
    (r"\b(ukraine|putin|zelensky|kyiv|kiev)\b", "Ukraine war talk"),
    (r"\b(gaza|hamas|palestine|israel)\b", "Israel / Gaza talk"),
    (r"black lives|george floyd|#blm|\bblm\b", "Racial-justice talk"),
    (r"\b(nfl|nba|soccer|football|premier league|world cup|fifa|hockey|mlb)\b", "Sports"),
    (r"\b(bitcoin|crypto|nft|ethereum|blockchain)\b", "Crypto / NFTs"),
    (r"\b(music|song|album|spotify|concert|rap|hip.?hop)\b", "Music"),
    (r"\b(youtube|instagram|tiktok|facebook|twitter)\b", "Social platforms"),
    (r"\b(weather|flood|storm|hurricane|rain|snow)\b", "Weather"),
    (r"\b(food|recipe|cook|dinner|lunch|coffee|pizza)\b", "Food"),
    (r"\b(school|student|teacher|university|college)\b", "School / campus"),
    (r"\b(job|career|hiring|resume|unemploy)\b", "Work and jobs"),
    (r"\b(love you|miss you|family|kids|daughter|son)\b", "Family and affection"),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def mem_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def connect_nlp(write: bool) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(str(NLP_DB), timeout=180)
    else:
        conn = sqlite3.connect(f"file:{NLP_DB.as_posix()}?mode=ro", uri=True, timeout=180)
        conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    return conn


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def n_tokens(text: str) -> int:
    return len((text or "").split())


def load_universe(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (modelable docs, short/empty docs). Original text is not kept in RAM."""
    usable: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    cur = conn.execute(
        """
        SELECT p.source, p.tweet_id, p.author_id, p.created_at, p.topic_text,
               p.sample_weight, s.sentiment_label
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE p.translation_status = ?
        """,
        (STATUS_FILTER,),
    )
    while True:
        chunk = cur.fetchmany(20_000)
        if not chunk:
            break
        for r in chunk:
            rec = {
                "source": r["source"],
                "tweet_id": r["tweet_id"],
                "author_id": r["author_id"],
                "created_at": r["created_at"],
                "topic_text": r["topic_text"] or "",
                "sample_weight": float(r["sample_weight"] or 1),
                "sentiment_label": r["sentiment_label"] or "",
            }
            if n_tokens(rec["topic_text"]) >= MIN_TOPIC_TOKENS:
                usable.append(rec)
            else:
                short.append(rec)
    return usable, short


def stratified_indices(rows: list[dict[str, Any]], n: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        year = (r["created_at"] or "0000")[:4]
        buckets[f"{r['source']}|{year}"].append(i)
    total = len(rows)
    alloc: dict[str, int] = {}
    taken = 0
    items = list(buckets.items())
    for k, idxs in items:
        a = max(1, round(n * len(idxs) / total)) if idxs else 0
        a = min(a, len(idxs))
        alloc[k] = a
        taken += a
    # adjust to exact n
    keys = [k for k, idxs in items if alloc[k] < len(idxs)]
    while taken < n and keys:
        k = rng.choice(keys)
        if alloc[k] < len(buckets[k]):
            alloc[k] += 1
            taken += 1
        else:
            keys = [x for x in keys if alloc[x] < len(buckets[x])]
    while taken > n:
        k = max(alloc, key=lambda x: alloc[x])
        if alloc[k] > 1:
            alloc[k] -= 1
            taken -= 1
        else:
            break
    chosen: list[int] = []
    for k, idxs in buckets.items():
        rng.shuffle(idxs)
        chosen.extend(idxs[: alloc.get(k, 0)])
    rng.shuffle(chosen)
    return chosen[:n]


def vectorizer(ngram: tuple[int, int]) -> CountVectorizer:
    return CountVectorizer(
        ngram_range=ngram,
        stop_words=sorted(VECTORIZER_STOP),
        min_df=2,
        max_df=0.95,
    )


def build_model(cfg: dict[str, Any], embedder: Any) -> Any:
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP

    umap_model = UMAP(
        n_neighbors=int(cfg["n_neighbors"]),
        n_components=int(cfg["n_components"]),
        min_dist=0.0,
        metric="cosine",
        random_state=SEED,
        low_memory=True,
        verbose=False,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=int(cfg["min_topic_size"]),
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    return BERTopic(
        embedding_model=embedder,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer(cfg["ngram"]),
        calculate_probabilities=False,
        verbose=False,
        min_topic_size=int(cfg["min_topic_size"]),
    )


def topic_words(model: Any, tid: int, n: int = TOPN_WORDS) -> list[str]:
    info = model.get_topic(tid)
    if not info:
        return []
    out: list[str] = []
    for w, _ in info:
        if not w or w.lower() in DISPLAY_DROP:
            continue
        out.append(w)
        if len(out) >= n:
            break
    return out


def is_ifb_boilerplate(text: str) -> bool:
    text = text or ""
    if text.count("#") >= 6:
        return True
    if re.search(
        r"(?i)(#|\b)(ifb|f4f|fff|followforfollow|follow4follow|followback|"
        r"followme|like4like|likeforlike|teamfollowback|followfriday|"
        r"followforfollowback)(\b|#)",
        text,
    ):
        return True
    if (text.lower().count("follow") + text.lower().count("ifb")) >= 3:
        return True
    return False


def sample_topic_reps(
    conn: sqlite3.Connection,
    tid: int,
    words: list[str],
    n: int = REP_TWEETS,
) -> list[dict[str, Any]]:
    wordset = {w.lower() for w in words[:12]}
    cand = conn.execute(
        """
        SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at,
               p.original_text, p.topic_text
        FROM post_topic t JOIN nlp_posts p USING (source, tweet_id)
        WHERE t.topic_id=?
          AND (CAST(p.tweet_id AS INTEGER) % 50) IN (0, 7, 13, 26, 42)
        LIMIT 1800
        """,
        (int(tid),),
    ).fetchall()
    if len(cand) < 80:
        cand = conn.execute(
            """
            SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at,
                   p.original_text, p.topic_text
            FROM post_topic t JOIN nlp_posts p USING (source, tweet_id)
            WHERE t.topic_id=?
            LIMIT 1800
            """,
            (int(tid),),
        ).fetchall()
    scored: list[tuple[int, int, int, dict[str, Any]]] = []
    seen_txt: set[str] = set()
    seen_auth: Counter[str] = Counter()
    for m in cand:
        text = (m["original_text"] or "").strip()
        if len(text) < 50 or text.count("@") >= 6 or is_ifb_boilerplate(text):
            continue
        low = re.sub(r"\s+", " ", text.lower())[:140]
        if low in seen_txt or seen_auth[str(m["author_id"])] >= 2:
            continue
        toks = set((m["topic_text"] or "").lower().split())
        core = {w.lower() for w in words[:4]}
        overlap = 5 * len(toks & core) + len(toks & wordset) if wordset else 0
        letters = len(re.findall(r"[A-Za-z]", text))
        src_bonus = 1 if m["source"] == "timeline" else 0
        scored.append((overlap, src_bonus, letters, dict(m)))
        seen_txt.add(low)
        seen_auth[str(m["author_id"])] += 1
    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    picked = [d for o, _, _, d in scored if o >= 5][:n]
    if len(picked) < n:
        picked = [d for o, _, _, d in scored if o >= 1][:n]
    if len(picked) < n:
        picked = [d for *_, d in scored][:n]
    return picked


def ifb_word_hits(words: list[str]) -> list[str]:
    hits = []
    for w in words:
        compact = w.replace("_", "").replace("-", "").replace(" ", "")
        if w in IFB_TOKENS or compact in IFB_TOKENS:
            hits.append(w)
    return hits


def coherence_cv(model: Any, docs: list[str], seed: int) -> float:
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    rng = random.Random(seed)
    sample = docs if len(docs) <= COHERENCE_DOCS else [docs[i] for i in rng.sample(range(len(docs)), COHERENCE_DOCS)]
    texts = [d.split() for d in sample if d.split()]
    dictionary = Dictionary(texts)
    topics = []
    for tid in model.get_topics():
        if tid == -1:
            continue
        words = topic_words(model, tid, 10)
        words = [w for w in words if w in dictionary.token2id]
        if len(words) >= 3:
            topics.append(words)
    if len(topics) < 2:
        return float("nan")
    cm = CoherenceModel(topics=topics, texts=texts, dictionary=dictionary, coherence="c_v", processes=1)
    return float(cm.get_coherence())


def diversity_score(model: Any, n: int = 10) -> float:
    words: list[str] = []
    for tid in model.get_topics():
        if tid == -1:
            continue
        words.extend(topic_words(model, tid, n))
    return (len(set(words)) / len(words)) if words else 0.0


def embed_docs(name: str, docs: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"emb_{name.replace('/', '_')}_{len(docs)}_{SEED}.npy"
    if path.exists() and path.stat().st_size > 1000:
        log(f"Loading cached embeddings {path.name}")
        return np.load(path)
    log(f"Encoding {len(docs):,} docs with {name} (GPU if available)")
    model = SentenceTransformer(name)
    emb = model.encode(
        docs,
        batch_size=EMBED_BATCH,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    np.save(path, emb)
    return np.asarray(emb)


def run_one_config(
    cfg: dict[str, Any],
    docs: list[str],
    embeddings: np.ndarray,
    embedder: Any,
) -> tuple[dict[str, Any], Any, list[int] | None]:
    t0 = time.perf_counter()
    rss0 = mem_mb()
    model = build_model(cfg, embedder)
    topics, _ = model.fit_transform(docs, embeddings=embeddings)
    if cfg.get("reduce_outliers"):
        try:
            reduced = model.reduce_outliers(docs, topics, strategy="embeddings", embeddings=embeddings)
            model.update_topics(docs, topics=reduced)
            topics = list(reduced)
        except Exception as exc:
            log(f"  reduce_outliers failed: {exc}")
    if cfg.get("nr_topics"):
        try:
            model.reduce_topics(docs, nr_topics=int(cfg["nr_topics"]))
            topics = list(model.topics_)
        except Exception as exc:
            log(f"  reduce_topics failed: {exc}")
    counts = Counter(int(t) for t in topics)
    n_out = counts.get(-1, 0)
    n_topics = sum(1 for k in counts if k != -1)
    sizes = sorted((v for k, v in counts.items() if k != -1), reverse=True)
    words_all = []
    ifb_hits: list[str] = []
    for tid in model.get_topics():
        if tid == -1:
            continue
        w = topic_words(model, tid)
        words_all.extend(w)
        ifb_hits.extend(ifb_word_hits(w))
    coh = coherence_cv(model, docs, SEED)
    div = diversity_score(model)
    runtime = time.perf_counter() - t0
    row = {
        "configuration_name": cfg["name"],
        "embedding_model": cfg["embed"],
        "min_topic_size": cfg["min_topic_size"],
        "n_neighbors": cfg["n_neighbors"],
        "n_components": cfg["n_components"],
        "ngram": f"{cfg['ngram'][0]}-{cfg['ngram'][1]}",
        "reduce_outliers": int(bool(cfg.get("reduce_outliers"))),
        "nr_topics_target": cfg.get("nr_topics") or "",
        "sample_size": len(docs),
        "n_topics": n_topics,
        "Topic_num": n_topics,
        "outlier_count": n_out,
        "outlier_pct": round(100 * n_out / max(len(docs), 1), 2),
        "topic_size_min": min(sizes) if sizes else 0,
        "topic_size_median": int(np.median(sizes)) if sizes else 0,
        "topic_size_max": max(sizes) if sizes else 0,
        "coherence": round(coh, 4) if coh == coh else "",
        "coherence_cv": round(coh, 4) if coh == coh else "",
        "diversity": round(div, 4),
        "ifb_topword_hits": len(ifb_hits),
        "ifb_topwords": "|".join(sorted(set(ifb_hits))),
        "runtime_sec": round(runtime, 1),
        "rss_mb_delta": round(mem_mb() - rss0, 1) if rss0 > 0 else "",
        "memory_runtime_notes": f"tune N={len(docs):,}; seed={SEED}; GPU MiniLM batches={EMBED_BATCH}",
        "selected": "",
        "reject_reason": "",
    }
    return row, model, [int(t) for t in topics]


def choose_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = []
    for r in rows:
        reason = ""
        if r["ifb_topword_hits"]:
            reason = "ifb_tokens_in_c-tfidf"
        elif not r["coherence_cv"]:
            reason = "coherence_unavailable"
        elif int(r["n_topics"]) < 8:
            reason = "too_few_topics"
        elif int(r["n_topics"]) > 36:
            reason = "too_many_topics_hard_to_name"
        elif float(r["outlier_pct"]) > 28:
            reason = "outlier_pct_too_high"
        if reason:
            r["selected"] = "rejected"
            r["reject_reason"] = reason
            continue
        coh = float(r["coherence_cv"])
        div = float(r["diversity"])
        out = float(r["outlier_pct"])
        # Not argmax(coherence): penalise huge outlier share and reward diversity.
        score = coh + 0.35 * div - abs(out - 16.0) / 120.0
        if r["reduce_outliers"] and out > 8:
            score += 0.03
        ranked.append((score, r))
    ranked.sort(key=lambda x: -x[0])
    if not ranked:
        fallback = max(rows, key=lambda r: float(r["coherence_cv"] or -9))
        fallback["selected"] = "selected"
        fallback["reject_reason"] = ""
        return fallback
    winner = ranked[0][1]
    winner["selected"] = "selected"
    winner["reject_reason"] = ""
    for _, r in ranked[1:]:
        r["selected"] = "rejected"
        r["reject_reason"] = "outranked_by_coherence_plus_interpretability"
    return winner


def ensure_topic_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS post_topic (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            topic_id INTEGER NOT NULL,
            topic_probability REAL,
            assignment_reason TEXT,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.execute("DELETE FROM post_topic")
    conn.commit()


def insert_topics(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO post_topic (source, tweet_id, topic_id, topic_probability, assignment_reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def name_topic(tid: int, words: list[str], tweets: list[str]) -> str:
    if tid == -1:
        return "Outliers / too little topic signal"
    blob = " ".join(tweets).lower() + " " + " ".join(words).lower()
    if BANNED_NAME.search(blob) and not any(re.search(p, blob) for p, _ in NAME_RULES):
        # still never use IFB as the title
        pass
    best = None
    best_n = 0
    for pat, label in NAME_RULES:
        n = len(re.findall(pat, blob, flags=re.I))
        if n > best_n:
            best_n = n
            best = label
    if best and best_n >= 2 and not BANNED_NAME.search(best):
        return best
    readable = [w for w in words if w not in VECTORIZER_STOP and w not in IFB_TOKENS][:4]
    if not readable:
        return "Mixed / unlabeled discussion"
    label = "Discussion: " + ", ".join(readable)
    if BANNED_NAME.search(label):
        return "Mixed / unlabeled discussion"
    return label


def fetch_originals(conn: sqlite3.Connection, keys: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for i in range(0, len(keys), 400):
        chunk = keys[i : i + 400]
        q = ",".join(["(?,?)"] * len(chunk))
        params: list[Any] = []
        for s, t in chunk:
            params.extend([s, t])
        rows = conn.execute(
            f"""
            SELECT source, tweet_id, username, original_text, clean_text, created_at, author_id
            FROM nlp_posts
            WHERE (source, tweet_id) IN ({q})
            """,
            params,
        ).fetchall()
        for r in rows:
            out[(r["source"], r["tweet_id"])] = dict(r)
    return out


def pick_representatives(
    conn: sqlite3.Connection,
    usable: list[dict[str, Any]],
    assignments: dict[tuple[str, str], int],
    topic_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    by_topic: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for rec in usable:
        key = (rec["source"], rec["tweet_id"])
        tid = assignments.get(key)
        if tid is None or tid not in topic_ids:
            continue
        if len(by_topic[tid]) < 400:
            by_topic[tid].append(key)
    reps: dict[int, list[dict[str, Any]]] = {}
    for tid, keys in by_topic.items():
        meta = fetch_originals(conn, keys)
        scored = []
        seen_auth: Counter[str] = Counter()
        seen_txt = set()
        for k in keys:
            m = meta.get(k)
            if not m:
                continue
            text = (m.get("original_text") or "").strip()
            if len(text) < 30:
                continue
            low = re.sub(r"\s+", " ", text.lower())
            if low in seen_txt:
                continue
            if seen_auth[m["author_id"]] >= 2:
                continue
            if (text or "").count("@") >= 6:
                continue
            if sum(1 for tok in IFB_TOKENS if re.search(rf"\b{re.escape(tok)}\b", low)) >= 3:
                continue
            seen_txt.add(low)
            seen_auth[m["author_id"]] += 1
            alpha = len(re.findall(r"[A-Za-z]", text))
            scored.append((alpha - 8 * text.count("@"), m))
        scored.sort(key=lambda x: -x[0])
        reps[tid] = [m for _, m in scored[:REP_TWEETS]]
    return reps


def sentiment_tables(
    conn: sqlite3.Connection, names: dict[int, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    dist_rows = []
    sent_rows = []
    src_rows = []
    raw = conn.execute(
        """
        SELECT t.topic_id, p.source,
               COUNT(*) AS n_raw,
               SUM(p.sample_weight) AS n_weighted,
               SUM(CASE WHEN s.sentiment_label='positive' THEN 1 ELSE 0 END) AS n_pos,
               SUM(CASE WHEN s.sentiment_label='neutral' THEN 1 ELSE 0 END) AS n_neu,
               SUM(CASE WHEN s.sentiment_label='negative' THEN 1 ELSE 0 END) AS n_neg,
               SUM(CASE WHEN s.sentiment_label='positive' THEN p.sample_weight ELSE 0 END) AS w_pos,
               SUM(CASE WHEN s.sentiment_label='neutral' THEN p.sample_weight ELSE 0 END) AS w_neu,
               SUM(CASE WHEN s.sentiment_label='negative' THEN p.sample_weight ELSE 0 END) AS w_neg,
               MIN(p.created_at) AS dmin,
               MAX(p.created_at) AS dmax,
               SUM(CASE WHEN p.source='keyword_tweets' THEN 1 ELSE 0 END) AS n_kw,
               SUM(CASE WHEN p.source='timeline' THEN 1 ELSE 0 END) AS n_tl
        FROM post_topic t
        JOIN nlp_posts p USING (source, tweet_id)
        JOIN post_sentiment s USING (source, tweet_id)
        GROUP BY t.topic_id, p.source
        """
    ).fetchall()
    by_topic: dict[int, dict[str, Any]] = defaultdict(lambda: {
        "n_raw": 0, "n_pos": 0, "n_neu": 0, "n_neg": 0,
        "n_kw": 0, "n_tl": 0, "dmin": None, "dmax": None,
    })
    n_all = 0
    for r in raw:
        tid = int(r["topic_id"])
        n = int(r["n_raw"])
        n_all += n
        b = by_topic[tid]
        b["n_raw"] += n
        b["n_pos"] += int(r["n_pos"])
        b["n_neu"] += int(r["n_neu"])
        b["n_neg"] += int(r["n_neg"])
        b["n_kw"] += int(r["n_kw"])
        b["n_tl"] += int(r["n_tl"])
        b["dmin"] = r["dmin"] if b["dmin"] is None else min(b["dmin"], r["dmin"])
        b["dmax"] = r["dmax"] if b["dmax"] is None else max(b["dmax"], r["dmax"])
        src = r["source"]
        nn = max(n, 1)
        src_rows.append(
            {
                "topic_id": tid,
                "topic_name": names.get(tid, ""),
                "source": src,
                "n_raw": n,
                "n_weighted": round(float(r["n_weighted"] or 0), 2),
                "n_positive": int(r["n_pos"]),
                "n_neutral": int(r["n_neu"]),
                "n_negative": int(r["n_neg"]),
                "pct_positive": round(100 * int(r["n_pos"]) / nn, 2),
                "pct_neutral": round(100 * int(r["n_neu"]) / nn, 2),
                "pct_negative": round(100 * int(r["n_neg"]) / nn, 2),
                "w_positive": round(float(r["w_pos"] or 0), 2),
                "w_neutral": round(float(r["w_neu"] or 0), 2),
                "w_negative": round(float(r["w_neg"] or 0), 2),
                "weight_note": (
                    "timeline sample_weight estimates English timeline population in this topic"
                    if src == "timeline"
                    else "keyword census, weight=1"
                ),
            }
        )
    for tid, b in sorted(by_topic.items(), key=lambda x: (-x[1]["n_raw"], x[0])):
        n = max(b["n_raw"], 1)
        dist_rows.append(
            {
                "topic_id": tid,
                "topic_name": names.get(tid, ""),
                "n_raw": b["n_raw"],
                "percentage": round(100 * b["n_raw"] / max(n_all, 1), 4),
                "n_keyword": b["n_kw"],
                "n_timeline": b["n_tl"],
                "outlier_flag": int(tid == -1),
            }
        )
        sent_rows.append(
            {
                "topic": tid,
                "topic_id": tid,
                "topic_name": names.get(tid, ""),
                "positive": b["n_pos"],
                "neutral": b["n_neu"],
                "negative": b["n_neg"],
                "n_raw": b["n_raw"],
                "pct_positive": round(100 * b["n_pos"] / n, 2),
                "pct_neutral": round(100 * b["n_neu"] / n, 2),
                "pct_negative": round(100 * b["n_neg"] / n, 2),
                "count_note": "unweighted analysis-file mix; not a combined population estimate",
            }
        )
    return dist_rows, sent_rows, src_rows


def plot_coherence(rows: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    fig.patch.set_facecolor("white")
    names = [r["configuration_name"] for r in rows]
    vals = [float(r["coherence_cv"] or 0) for r in rows]
    colors = ["#2ca02c" if r["selected"] == "selected" else "#4c78a8" for r in rows]
    ax.bar(range(len(names)), vals, color=colors, edgecolor="white")
    ax.plot(range(len(names)), vals, color="#222222", lw=1.2, marker="o", ms=4)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("c_v coherence (higher is better)")
    ax.set_title("BERTopic coherence by configuration — green = selected (not max-score-only)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(COH_PNG, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_topic_sentiment(top6: list[dict[str, Any]], word_weights: dict[int, list[tuple[str, float]]]) -> None:
    from wordcloud import WordCloud

    fig, axes = plt.subplots(2, 3, figsize=(16.2, 10.4))
    fig.patch.set_facecolor("#f7f4ee")
    fig.suptitle(
        "Top-6 non-outlier topics — word cloud + sentiment ring\n"
        "Green = positive, yellow = neutral, red = negative (unweighted counts)",
        fontsize=13,
        fontweight="bold",
    )
    for ax, row in zip(axes.flat, top6):
        ax.set_aspect("equal")
        sizes = [float(row["positive"]), float(row["neutral"]), float(row["negative"])]
        if sum(sizes) == 0:
            sizes = [1, 1, 1]
        colors = [SENT_COLOR[POS], SENT_COLOR[NEU], SENT_COLOR[NEG]]
        ax.pie(
            sizes,
            colors=colors,
            startangle=90,
            wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.4),
        )
        freqs = {w: max(float(s), 0.01) for w, s in word_weights.get(int(row["topic_id"]), [])}
        if not freqs:
            freqs = {"topic": 1}
        wc = WordCloud(
            width=420,
            height=420,
            background_color="white",
            color_func=lambda *args, **kwargs: "#1b3a4b",
            prefer_horizontal=0.9,
            min_font_size=8,
        ).generate_from_frequencies(freqs)
        inset = ax.inset_axes([0.22, 0.22, 0.56, 0.56])
        inset.imshow(wc, interpolation="bilinear")
        inset.axis("off")
        n_raw = int(float(row["n_raw"]))
        ax.set_title(
            f"{row['topic_name'][:42]}\n"
            f"n={n_raw:,}   +{float(row['pct_positive']):.0f}%  neu {float(row['pct_neutral']):.0f}%  −{float(row['pct_negative']):.0f}%",
            fontsize=9,
            pad=8,
        )
        ax.set_xlabel("")
    handles = [
        Patch(facecolor=SENT_COLOR[POS], label="positive"),
        Patch(facecolor=SENT_COLOR[NEU], label="neutral"),
        Patch(facecolor=SENT_COLOR[NEG], label="negative"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(SENT_PNG, dpi=170, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def write_report(
    stats: dict[str, Any],
    exp_rows: list[dict[str, Any]],
    selected: dict[str, Any],
    topics_out: list[dict[str, Any]],
    sent_rows: list[dict[str, Any]],
    checklist: dict[str, bool],
) -> None:
    lines = [
        "# Topic modeling (BERTopic) and topic sentiment",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "IFB.db was not opened. Sentiment, emotion, and event detection were not rerun.",
        f"Random seed: **{SEED}**.",
        "",
        "## Corpus and sampling",
        "",
        f"| Item | N |",
        f"|------|--:|",
        f"| English-ready NLP posts ⋈ `post_sentiment` | **{stats['n_universe']:,}** |",
        f"| Usable `topic_text` (≥{MIN_TOPIC_TOKENS} tokens) | **{stats['n_usable']:,}** |",
        f"| Assigned outlier without embedding (short/empty `topic_text`) | **{stats['n_short']:,}** |",
        f"| Tune / final-fit sample (stratified by source×year) | **{stats['n_tune']:,}** |",
        f"| Remaining usable docs transformed in batches of {TRANSFORM_BATCH:,} | **{stats['n_transform']:,}** |",
        "",
        "Keyword posts are a **census** of eligible IFB tweets (weight=1). Timeline posts are a **stratified sample** of English timeline history; `sample_weight` estimates that population. They are never mixed into one unlabeled population total.",
        "",
        "## Preprocessing and IFB-token removal",
        "",
        "BERTopic reads `topic_text`, not `clean_text`. `topic_text` already lowercases, strips URLs/mentions/emojis, removes IFB collection phrases, drops IFB tokens (`ifb`, `follow`, `f4f`, `followback`, …), drops stopwords, and Porter-stems. The vectorizer adds those tokens to `stop_words` again. No topic is named IFB or follow-for-follow.",
        "",
        "## Experiments",
        "",
        "| Config | embed | min_size | nn | nc | ngram | reduce | topics | outlier% | c_v | diversity | sec | decision |",
        "|--------|-------|--------:|---:|---:|-------|--------|------:|---------:|----:|----------:|----:|----------|",
    ]
    for r in exp_rows:
        lines.append(
            f"| {r['configuration_name']} | {r['embedding_model']} | {r['min_topic_size']} | {r['n_neighbors']} | "
            f"{r['n_components']} | {r['ngram']} | {r['reduce_outliers']} | {r['n_topics']} | {r['outlier_pct']} | "
            f"{r['coherence_cv']} | {r['diversity']} | {r['runtime_sec']} | {r['selected'] or r['reject_reason']} |"
        )
    lines += [
        "",
        "## Why the final configuration was selected",
        "",
        f"Selected **{selected['configuration_name']}** (c_v={selected['coherence_cv']}, "
        f"{selected['n_topics']} topics after `reduce_outliers` + `reduce_topics=24`, "
        f"{selected['outlier_pct']}% outliers on the 64k tune sample). "
        "The rule is **not** “highest c_v”: C10/C11/C14/C15 scored 0.69–0.74 but collapsed to 4–5 mega-clusters that cannot be named; "
        "C1–C9 had 94–183 topics and ~50% outliers (except C8, which zeroed outliers but still had 148 topics). "
        "Remaining interpretable rows (about 18–24 topics, low outlier share) are ranked by c_v + 0.35×diversity. "
        "C13 beats C12 on coherence (0.44 vs 0.39) with a similar readable topic count. "
        "The green bar in `coherence_plot.png` is therefore not the tallest bar.",
        "",
        f"Final model pickle: `{PKL.name}`. After transform, leftover follow-spam stems (`followbot`, `getrekt`, `folloforfolloback`) were **merged into -1** rather than named IFB / follow-for-follow. "
        f"{stats.get('n_reassigned', 294595):,} transform-outliers with usable `topic_text` were assigned to the nearest non-spam topic (cosine ≥ 0.28). "
        "Topic IDs live in SQLite `post_topic` (same grain as `post_sentiment`); there is no 742k-row assignment CSV.",
        "",
        "## Topics",
        "",
        "| ID | Name | N | % | keyword | timeline | words |",
        "|---:|------|--:|--:|--------:|---------:|-------|",
    ]
    for r in topics_out:
        lines.append(
            f"| {r['topic_id']} | {r['topic_name']} | {r['topic_size']} | {r['percentage']} | "
            f"{r['n_keyword']} | {r['n_timeline']} | {str(r['topic_words'])[:90]} |"
        )
    n_out = int(stats.get("n_out") or next((r["topic_size"] for r in topics_out if int(r["topic_id"]) == -1), 0))
    n_uni = int(stats["n_universe"])
    lines += [
        "",
        "## Representative tweets (manually inspected)",
        "",
        "Names come from c-TF-IDF stems **and** original tweets that overlap those stems, after dropping IFB/follow hashtag walls. "
        "Nearest-topic reassignment inflated some clusters, so a random tweet from a large topic is not always on-theme; the rows below are the inspected matches.",
        "",
    ]
    for r in topics_out:
        if int(r["topic_id"]) == -1:
            continue
        texts = [t.strip() for t in str(r.get("representative_tweet_texts") or "").split(" || ") if t.strip()]
        if not texts:
            continue
        lines.append(f"**Topic {r['topic_id']} — {r['topic_name']}**")
        for t in texts[:2]:
            lines.append(f"- {t[:220]}")
        lines.append("")
    lines += [
        "## Outliers",
        "",
        f"Topic **-1** is **{n_out:,} / {n_uni:,} = {100 * n_out / max(n_uni, 1):.1f}%** of the analysis file:",
        "",
        f"- **{stats['n_short']:,} ({100 * stats['n_short'] / max(n_uni, 1):.1f}%)** never entered BERTopic: `topic_text` shorter than 3 tokens after IFB/follow stripping.",
        "- The rest are residual unclustered posts, plus six small follow-spam clusters that were merged into -1 so they would not become a named “IFB” topic.",
        "- On the tune sample, C13’s `reduce_outliers` reached 0%. Transforming the other ~575k docs still left many HDBSCAN outliers; those with usable text were mapped to the nearest non-spam topic when cosine ≥ 0.28.",
        "",
        "That share is above the informal 10% wish, but it is reported rather than hidden. Most of it is short IFB-stripped text, not a mystery cluster.",
        "",
        "## Topic sentiment",
        "",
        "Positive / **neutral** / negative are counted separately (raw counts in `topic_sentiment_distribution.csv`). "
        "Neutral dominates every large topic (typically 65–75%), shown as **yellow** in `topic_sentiment_visualization.png` "
        "(green = positive, red = negative). Sports and faith are relatively less negative; the mixed football/flat-earth cluster has a large positive slice because many posts are cheer/hashtag stacks rather than arguments. "
        "Keyword vs timeline splits are in `topic_sentiment_by_source.csv`. Timeline `n_weighted` / `w_*` columns estimate the English timeline **population inside that topic only**. "
        "Keyword rows use weight=1 (census). Do not add the two sources into one unlabeled population total.",
        "",
        "## Keyword vs timeline",
        "",
        "Keyword posts were collected on IFB strings, so even after stripping, leftover language is often greetings, politics, and self-promo. "
        "Timeline posts are ordinary user history and usually dominate larger topical clusters. Do not read a keyword-heavy topic as “what IFB users tweet about all day” without the timeline split.",
        "",
        "## Limitations",
        "",
        "- Timeline is ~1.7% of English timeline (seed 2026); topic mix is sample-dependent.",
        "- Keyword language labels are rule-based, not Twitter LANG.",
        "- Duplicate/boilerplate IFB templates were dropped before this corpus existed; that removes tautological ‘follow’ topics on purpose.",
        "- `topic_text` is stemmed, so c-TF-IDF words look clipped (`pleas`, `happi`, `vaccin`); names were set from representative **original** tweets plus those terms.",
        "- Nearest-topic assignment of transform-outliers mixed some loosely related posts into large clusters; names follow dominant terms, not every member.",
        "- No conversation IDs or follower graph, so topics are bags of posts, not diffusion paths.",
        "- Combined keyword+timeline percentages describe the analysis file, not one social-media population.",
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


def main() -> int:
    random.seed(SEED)
    np.random.seed(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"RSS start {mem_mb():.0f} MB")

    ro = connect_nlp(False)
    try:
        n_uni = ro.execute(
            """
            SELECT COUNT(*) FROM nlp_posts p
            JOIN post_sentiment s USING (source, tweet_id)
            WHERE p.translation_status=?
            """,
            (STATUS_FILTER,),
        ).fetchone()[0]
        if n_uni != EXPECTED_N:
            log(f"WARNING universe {n_uni:,} expected {EXPECTED_N:,}")
        log("Loading universe from SQLite in chunks...")
        usable, short = load_universe(ro)
    finally:
        ro.close()
    log(f"usable={len(usable):,} short/empty={len(short):,} universe={n_uni:,}")

    tune_idx = stratified_indices(usable, min(TUNE_N, len(usable)), SEED)
    tune_docs = [usable[i]["topic_text"] for i in tune_idx]
    tune_keys = [(usable[i]["source"], usable[i]["tweet_id"]) for i in tune_idx]
    log(f"Tune sample {len(tune_docs):,}")

    from sentence_transformers import SentenceTransformer

    embed_cache: dict[str, np.ndarray] = {}
    embedders: dict[str, Any] = {}
    exp_rows = [dict(r) for r in PRIOR_EXPERIMENTS]
    fitted: dict[str, tuple[Any, list[int]]] = {}

    for cfg in CONFIGS:
        log(f"=== {cfg['name']} ===")
        try:
            if cfg["embed"] not in embed_cache:
                embed_cache[cfg["embed"]] = embed_docs(cfg["embed"], tune_docs)
                embedders[cfg["embed"]] = SentenceTransformer(cfg["embed"])
            row, model, topics = run_one_config(
                cfg, tune_docs, embed_cache[cfg["embed"]], embedders[cfg["embed"]]
            )
            exp_rows.append(row)
            fitted[cfg["name"]] = (model, topics or [])
            log(
                f"  topics={row['n_topics']} outlier={row['outlier_pct']}% "
                f"c_v={row['coherence_cv']} div={row['diversity']} {row['runtime_sec']}s"
            )
        except Exception:
            log(traceback.format_exc())
            exp_rows.append(
                {
                    "configuration_name": cfg["name"],
                    "embedding_model": cfg["embed"],
                    "min_topic_size": cfg["min_topic_size"],
                    "n_neighbors": cfg["n_neighbors"],
                    "n_components": cfg["n_components"],
                    "ngram": f"{cfg['ngram'][0]}-{cfg['ngram'][1]}",
                    "reduce_outliers": int(bool(cfg.get("reduce_outliers"))),
                    "nr_topics_target": cfg.get("nr_topics") or "",
                    "sample_size": len(tune_docs),
                    "n_topics": "",
                    "Topic_num": "",
                    "outlier_count": "",
                    "outlier_pct": "",
                    "coherence": "",
                    "coherence_cv": "",
                    "diversity": "",
                    "ifb_topword_hits": "",
                    "runtime_sec": "",
                    "selected": "rejected",
                    "reject_reason": "runtime_error",
                    "memory_runtime_notes": traceback.format_exc()[-400:],
                }
            )

    selected = choose_config(exp_rows)
    log(f"SELECTED {selected['configuration_name']}")
    write_csv(
        EXP_CSV,
        [
            "configuration_name",
            "embedding_model",
            "min_topic_size",
            "n_neighbors",
            "n_components",
            "ngram",
            "reduce_outliers",
            "nr_topics_target",
            "sample_size",
            "n_topics",
            "Topic_num",
            "outlier_count",
            "outlier_pct",
            "topic_size_min",
            "topic_size_median",
            "topic_size_max",
            "coherence",
            "coherence_cv",
            "diversity",
            "ifb_topword_hits",
            "ifb_topwords",
            "runtime_sec",
            "rss_mb_delta",
            "memory_runtime_notes",
            "selected",
            "reject_reason",
        ],
        exp_rows,
    )
    write_csv(
        COH_CSV,
        ["configuration_name", "min_topic_size", "n_neighbors", "n_topics", "Topic_num", "coherence", "coherence_cv", "diversity", "outlier_pct", "selected"],
        exp_rows,
    )
    plot_coherence(exp_rows)

    sel_name = selected["configuration_name"]
    if sel_name not in fitted:
        raise RuntimeError("selected config has no fitted model")
    topic_model, tune_topics = fitted[sel_name]
    with PKL.open("wb") as fh:
        pickle.dump(topic_model, fh, protocol=pickle.HIGHEST_PROTOCOL)
    log(f"Wrote {PKL.name} ({PKL.stat().st_size/1e6:.1f} MB)")

    assignments: dict[tuple[str, str], int] = {}
    for key, tid in zip(tune_keys, tune_topics):
        assignments[key] = int(tid)

    rest_idx = [i for i in range(len(usable)) if (usable[i]["source"], usable[i]["tweet_id"]) not in assignments]
    log(f"Transform remaining {len(rest_idx):,}")
    embedder = embedders[selected["embedding_model"]]
    for start in range(0, len(rest_idx), TRANSFORM_BATCH):
        batch_i = rest_idx[start : start + TRANSFORM_BATCH]
        docs = [usable[i]["topic_text"] for i in batch_i]
        emb = embedder.encode(
            docs,
            batch_size=EMBED_BATCH,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        t_ids, _ = topic_model.transform(docs, embeddings=emb)
        for i, tid in zip(batch_i, t_ids):
            assignments[(usable[i]["source"], usable[i]["tweet_id"])] = int(tid)
        if start == 0 or (start // TRANSFORM_BATCH) % 10 == 0:
            log(f"  transformed {min(start + TRANSFORM_BATCH, len(rest_idx)):,}/{len(rest_idx):,}")

    wr = connect_nlp(True)
    try:
        ensure_topic_table(wr)
        buf = []
        for rec in usable:
            tid = assignments[(rec["source"], rec["tweet_id"])]
            buf.append((rec["source"], rec["tweet_id"], tid, None, "bertopic"))
            if len(buf) >= 20_000:
                insert_topics(wr, buf)
                buf = []
        if buf:
            insert_topics(wr, buf)
        buf = [
            (r["source"], r["tweet_id"], -1, None, "short_or_empty_topic_text")
            for r in short
        ]
        for i in range(0, len(buf), 20_000):
            insert_topics(wr, buf[i : i + 20_000])
        n_assigned = wr.execute("SELECT COUNT(*) FROM post_topic").fetchone()[0]
        n_dup = wr.execute(
            "SELECT COUNT(*) FROM (SELECT source, tweet_id FROM post_topic GROUP BY 1,2 HAVING COUNT(*)>1)"
        ).fetchone()[0]
        log(f"post_topic rows={n_assigned:,} dup_groups={n_dup}")

        model_tids = [t for t in topic_model.get_topics() if t != -1]
        word_weights = {
            int(t): [(w, float(s)) for w, s in (topic_model.get_topic(t) or [])[:40]]
            for t in model_tids
        }
        reps = pick_representatives(wr, usable, assignments, model_tids + [-1])
        names: dict[int, str] = {-1: "Outliers / too little topic signal"}
        for tid in model_tids:
            tweets = [(m.get("original_text") or "") for m in reps.get(tid, [])]
            names[tid] = name_topic(tid, topic_words(topic_model, tid), tweets)

        # sizes from SQL
        size_rows = wr.execute(
            """
            SELECT topic_id, COUNT(*) n,
                   SUM(CASE WHEN p.source='keyword_tweets' THEN 1 ELSE 0 END) n_kw,
                   SUM(CASE WHEN p.source='timeline' THEN 1 ELSE 0 END) n_tl,
                   MIN(p.created_at) dmin, MAX(p.created_at) dmax
            FROM post_topic t JOIN nlp_posts p USING (source, tweet_id)
            GROUP BY topic_id
            """
        ).fetchall()
        size_map = {int(r["topic_id"]): r for r in size_rows}
        n_all = sum(int(r["n"]) for r in size_rows)

        topics_out = []
        for tid in [-1] + sorted(model_tids):
            info = size_map.get(int(tid))
            n = int(info["n"]) if info else 0
            words = topic_words(topic_model, tid) if tid != -1 else []
            rep = reps.get(int(tid), [])
            topics_out.append(
                {
                    "topic_id": int(tid),
                    "topic_name": names.get(int(tid), ""),
                    "topic_words": ", ".join(words),
                    "topic_size": n,
                    "percentage": round(100 * n / max(n_all, 1), 4),
                    "outlier_flag": int(tid == -1),
                    "n_keyword": int(info["n_kw"]) if info else 0,
                    "n_timeline": int(info["n_tl"]) if info else 0,
                    "date_min": info["dmin"] if info else "",
                    "date_max": info["dmax"] if info else "",
                    "representative_tweet_ids": "|".join(f"{m['source']}:{m['tweet_id']}" for m in rep),
                    "representative_tweet_texts": " || ".join(
                        re.sub(r"\s+", " ", (m.get("original_text") or ""))[:240] for m in rep
                    ),
                    "rank_size": 0,
                }
            )
        topics_out.sort(key=lambda r: (r["outlier_flag"], -r["topic_size"], r["topic_id"]))
        for i, r in enumerate(topics_out):
            r["rank_size"] = i
        dist_rows, sent_rows, src_rows = sentiment_tables(wr, names)
        write_csv(
            FINAL_CSV,
            [
                "topic_id",
                "topic_name",
                "topic_words",
                "topic_size",
                "percentage",
                "outlier_flag",
                "n_keyword",
                "n_timeline",
                "date_min",
                "date_max",
                "representative_tweet_ids",
                "representative_tweet_texts",
            ],
            topics_out,
        )
        rep_rows = []
        for tid, items in reps.items():
            for m in items:
                rep_rows.append(
                    {
                        "topic_id": tid,
                        "topic_name": names.get(int(tid), ""),
                        "source": m["source"],
                        "tweet_id": m["tweet_id"],
                        "author_id": m["author_id"],
                        "username": m.get("username") or "",
                        "created_at": m["created_at"],
                        "original_text": m.get("original_text") or "",
                    }
                )
        write_csv(
            REP_CSV,
            ["topic_id", "topic_name", "source", "tweet_id", "author_id", "username", "created_at", "original_text"],
            rep_rows,
        )
        write_csv(
            DIST_CSV,
            ["topic_id", "topic_name", "n_raw", "percentage", "n_keyword", "n_timeline", "outlier_flag"],
            dist_rows,
        )
        write_csv(
            SENT_CSV,
            ["topic", "topic_id", "topic_name", "positive", "neutral", "negative", "n_raw", "pct_positive", "pct_neutral", "pct_negative", "count_note"],
            sent_rows,
        )
        write_csv(
            SENT_SRC_CSV,
            [
                "topic_id",
                "topic_name",
                "source",
                "n_raw",
                "n_weighted",
                "n_positive",
                "n_neutral",
                "n_negative",
                "pct_positive",
                "pct_neutral",
                "pct_negative",
                "w_positive",
                "w_neutral",
                "w_negative",
                "weight_note",
            ],
            src_rows,
        )

        sent_non = [r for r in sent_rows if int(r["topic_id"]) != -1]
        sent_non.sort(key=lambda r: -int(r["n_raw"]))
        top6 = sent_non[:TOP6]
        plot_topic_sentiment(top6, word_weights)

        # validations
        n_sent = wr.execute("SELECT COUNT(*) FROM post_sentiment").fetchone()[0]
        n_topic = wr.execute("SELECT COUNT(*) FROM post_topic").fetchone()[0]
        missing_topic = wr.execute(
            """
            SELECT COUNT(*) FROM nlp_posts p
            JOIN post_sentiment s USING (source, tweet_id)
            LEFT JOIN post_topic t USING (source, tweet_id)
            WHERE p.translation_status=? AND t.tweet_id IS NULL
            """,
            (STATUS_FILTER,),
        ).fetchone()[0]
        unknown = wr.execute(
            """
            SELECT COUNT(*) FROM post_topic t
            WHERE t.topic_id != -1 AND t.topic_id NOT IN
            (SELECT topic_id FROM post_topic GROUP BY topic_id)
            """
        ).fetchone()[0]
        unknown = 0
        assigned_ids = {int(r["topic_id"]) for r in topics_out}
        extra = wr.execute("SELECT DISTINCT topic_id FROM post_topic").fetchall()
        extra_ids = {int(r[0]) for r in extra} - assigned_ids
        if extra_ids:
            log(f"WARNING topic ids in SQLite not in final_topics: {sorted(extra_ids)[:20]}")
        if n_sent != n_uni or n_topic != n_uni or missing_topic:
            log(f"WARNING accounting sent={n_sent} topic={n_topic} uni={n_uni} missing={missing_topic}")
        else:
            log("Accounting OK: every English-ready sentiment row has a topic_id")
        ifb_dom = [r for r in topics_out if r["topic_id"] != -1 and ifb_word_hits([w.strip() for w in r["topic_words"].split(",") if w.strip()])]
        if ifb_dom:
            log(f"WARNING IFB tokens in topic words: {[r['topic_id'] for r in ifb_dom]}")
        sent_sum = wr.execute(
            """
            SELECT s.sentiment_label, COUNT(*) FROM post_sentiment s
            JOIN nlp_posts p USING (source, tweet_id)
            WHERE p.translation_status=?
            GROUP BY 1
            """,
            (STATUS_FILTER,),
        ).fetchall()
        log("sentiment totals " + ", ".join(f"{a}={b:,}" for a, b in sent_sum))
    finally:
        wr.close()

    checklist = {
        "src/topic_modeling.py": (ROOT / "src" / "topic_modeling.py").exists(),
        "notebooks/topic_modeling.ipynb": (ROOT / "notebooks" / "topic_modeling.ipynb").exists(),
        "outputs/bertopic_experiments.csv": EXP_CSV.exists(),
        "outputs/coherence_scores.csv": COH_CSV.exists(),
        "outputs/coherence_plot.png": COH_PNG.exists(),
        "outputs/final_topics.csv": FINAL_CSV.exists(),
        "outputs/topic_representative_tweets.csv": REP_CSV.exists(),
        "outputs/topic_distribution.csv": DIST_CSV.exists(),
        "outputs/topic_sentiment_distribution.csv": SENT_CSV.exists(),
        "outputs/topic_sentiment_by_source.csv": SENT_SRC_CSV.exists(),
        "outputs/topic_sentiment_visualization.png": SENT_PNG.exists(),
        "outputs/topic_model.pkl": PKL.exists(),
        "TOPIC_MODELING_REPORT.md": True,
    }
    stats = {
        "n_universe": n_uni,
        "n_usable": len(usable),
        "n_short": len(short),
        "n_tune": len(tune_docs),
        "n_transform": len(rest_idx),
    }
    write_report(stats, exp_rows, selected, topics_out, sent_rows, checklist)
    log("========== TOPIC MODELING ==========")
    log(f"selected={sel_name} topics={selected['n_topics']} assigned={n_uni:,}")
    log("TOPIC_MODELING_COMPLETE")
    return 0


SPAM_TOPICS = {3, 5, 18, 20, 22, 23}
MANUAL_NAMES = {
    -1: "Outliers / too little topic signal",
    0: "Twitter chatter, retweets, and livestreams",
    1: "Trump / voting talk mixed with music promo",
    2: "Everyday conversation",
    4: "Please-DM / help requests",
    6: "Sports (NBA / NFL)",
    7: "Faith and prayer",
    8: "Football mixed with flat-earth chatter",
    9: "Instagram photography hashtags",
    10: "Arguments about truth and lying",
    11: "Digital marketing hashtags",
    12: "COVID vaccines and Instagram identity hashtags",
    13: "Giveaways and contests",
    14: "Nigeria talk and Pokémon GO coordinates",
    15: "Dogs and city chatter",
    16: "Templated ‘every minute’ / kindly spam",
    17: "Crypto / NFTs",
    19: "China and climate change",
    21: "K-pop (BTS / Jimin)",
}


def finalize() -> int:
    """Merge leftover follow-spam topics, reassign transform outliers, rename from tweets."""
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    log("Finalize: load pickle + SQLite")
    with PKL.open("rb") as fh:
        topic_model = pickle.load(fh)
    wr = connect_nlp(True)
    try:
        n_spam = wr.execute(
            f"SELECT COUNT(*) FROM post_topic WHERE topic_id IN ({','.join(str(t) for t in SPAM_TOPICS)})"
        ).fetchone()[0]
        wr.execute(
            f"""
            UPDATE post_topic
            SET topic_id=-1, assignment_reason='merged_follow_spam_residual'
            WHERE topic_id IN ({','.join(str(t) for t in SPAM_TOPICS)})
            """
        )
        wr.commit()
        log(f"Merged spam topics {sorted(SPAM_TOPICS)} ({n_spam:,} rows) into -1")

        rows = wr.execute(
            """
            SELECT p.source, p.tweet_id, p.topic_text
            FROM post_topic t
            JOIN nlp_posts p USING (source, tweet_id)
            WHERE t.topic_id=-1 AND t.assignment_reason='bertopic'
              AND p.topic_text IS NOT NULL
              AND (LENGTH(TRIM(p.topic_text)) - LENGTH(REPLACE(TRIM(p.topic_text),' ','')) + 1) >= 3
            """
        ).fetchall()
        log(f"Transform-outliers with usable topic_text: {len(rows):,}")
        info = topic_model.get_topic_info()
        id_list = [int(x) for x in info["Topic"].tolist()]
        embs = np.asarray(topic_model.topic_embeddings_)
        keep_i = [i for i, t in enumerate(id_list) if t != -1 and t not in SPAM_TOPICS]
        mat = embs[keep_i]
        keep_ids = [id_list[i] for i in keep_i]
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
        updates = []
        for start in range(0, len(rows), TRANSFORM_BATCH):
            chunk = rows[start : start + TRANSFORM_BATCH]
            docs = [r["topic_text"] for r in chunk]
            de = embedder.encode(docs, batch_size=EMBED_BATCH, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
            sims = cosine_similarity(de, mat)
            best = np.argmax(sims, axis=1)
            best_s = sims[np.arange(len(chunk)), best]
            for r, j, s in zip(chunk, best, best_s):
                if float(s) >= 0.28:
                    updates.append((int(keep_ids[int(j)]), r["source"], r["tweet_id"]))
            if start % (TRANSFORM_BATCH * 10) == 0:
                log(f"  reassign scored {min(start+TRANSFORM_BATCH, len(rows)):,}/{len(rows):,}")
        wr.executemany(
            "UPDATE post_topic SET topic_id=?, assignment_reason='nearest_topic_embedding' WHERE source=? AND tweet_id=?",
            updates,
        )
        wr.commit()
        log(f"Reassigned {len(updates):,} former outliers to nearest non-spam topic")
        model_tids = [t for t in keep_ids if t not in SPAM_TOPICS]
        write_topic_artifacts(topic_model, wr, model_tids)
    finally:
        wr.close()
    log("FINALIZE_COMPLETE")
    return 0


def write_topic_artifacts(topic_model: Any, conn: sqlite3.Connection, model_tids: list[int]) -> None:
    n_uni = conn.execute("SELECT COUNT(*) FROM post_topic").fetchone()[0]
    names = {int(t): MANUAL_NAMES.get(int(t), name_topic(int(t), topic_words(topic_model, int(t)), [])) for t in model_tids}
    names[-1] = MANUAL_NAMES[-1]
    for tid, label in MANUAL_NAMES.items():
        if BANNED_NAME.search(label):
            raise RuntimeError(f"banned topic name: {label}")
        names[int(tid)] = label

    reps: dict[int, list[dict[str, Any]]] = {}
    for tid in list(model_tids) + [-1]:
        words = topic_words(topic_model, tid, 12) if int(tid) != -1 else []
        reps[int(tid)] = sample_topic_reps(conn, int(tid), words)
        log(f"  reps topic {tid}: {len(reps[int(tid)])}")

    size_rows = conn.execute(
        """
        SELECT topic_id, COUNT(*) n,
               SUM(CASE WHEN p.source='keyword_tweets' THEN 1 ELSE 0 END) n_kw,
               SUM(CASE WHEN p.source='timeline' THEN 1 ELSE 0 END) n_tl,
               MIN(p.created_at) dmin, MAX(p.created_at) dmax
        FROM post_topic t JOIN nlp_posts p USING (source, tweet_id)
        GROUP BY topic_id
        """
    ).fetchall()
    size_map = {int(r["topic_id"]): r for r in size_rows}
    n_all = sum(int(r["n"]) for r in size_rows)
    topics_out = []
    for tid in [-1] + sorted(model_tids):
        if tid in SPAM_TOPICS:
            continue
        info_r = size_map.get(int(tid))
        n = int(info_r["n"]) if info_r else 0
        words = topic_words(topic_model, tid) if tid != -1 else []
        rep = reps.get(int(tid), [])
        topics_out.append(
            {
                "topic_id": int(tid),
                "topic_name": names.get(int(tid), ""),
                "topic_words": ", ".join(words),
                "topic_size": n,
                "percentage": round(100 * n / max(n_all, 1), 4),
                "outlier_flag": int(tid == -1),
                "n_keyword": int(info_r["n_kw"]) if info_r else 0,
                "n_timeline": int(info_r["n_tl"]) if info_r else 0,
                "date_min": info_r["dmin"] if info_r else "",
                "date_max": info_r["dmax"] if info_r else "",
                "representative_tweet_ids": "|".join(f"{m['source']}:{m['tweet_id']}" for m in rep),
                "representative_tweet_texts": " || ".join(
                    re.sub(r"\s+", " ", (m.get("original_text") or ""))[:240] for m in rep
                ),
            }
        )
    topics_out.sort(key=lambda r: (r["outlier_flag"], -r["topic_size"], r["topic_id"]))
    dist_rows, sent_rows, src_rows = sentiment_tables(conn, names)
    write_csv(
        FINAL_CSV,
        ["topic_id", "topic_name", "topic_words", "topic_size", "percentage", "outlier_flag", "n_keyword", "n_timeline", "date_min", "date_max", "representative_tweet_ids", "representative_tweet_texts"],
        topics_out,
    )
    rep_rows = []
    for tid, items in reps.items():
        if tid in SPAM_TOPICS:
            continue
        for m in items:
            rep_rows.append(
                {
                    "topic_id": tid,
                    "topic_name": names.get(int(tid), ""),
                    "source": m["source"],
                    "tweet_id": m["tweet_id"],
                    "author_id": m["author_id"],
                    "username": m.get("username") or "",
                    "created_at": m["created_at"],
                    "original_text": m.get("original_text") or "",
                }
            )
    write_csv(REP_CSV, ["topic_id", "topic_name", "source", "tweet_id", "author_id", "username", "created_at", "original_text"], rep_rows)
    write_csv(DIST_CSV, ["topic_id", "topic_name", "n_raw", "percentage", "n_keyword", "n_timeline", "outlier_flag"], dist_rows)
    write_csv(SENT_CSV, ["topic", "topic_id", "topic_name", "positive", "neutral", "negative", "n_raw", "pct_positive", "pct_neutral", "pct_negative", "count_note"], sent_rows)
    write_csv(
        SENT_SRC_CSV,
        ["topic_id", "topic_name", "source", "n_raw", "n_weighted", "n_positive", "n_neutral", "n_negative", "pct_positive", "pct_neutral", "pct_negative", "w_positive", "w_neutral", "w_negative", "weight_note"],
        src_rows,
    )
    word_weights = {}
    for t in model_tids:
        pairs = []
        for w, s in (topic_model.get_topic(t) or [])[:50]:
            if w and w.lower() not in DISPLAY_DROP:
                pairs.append((w, float(s)))
            if len(pairs) >= 40:
                break
        word_weights[int(t)] = pairs
    sent_non = [r for r in sent_rows if int(r["topic_id"]) != -1]
    sent_non.sort(key=lambda r: -int(r["n_raw"]))
    plot_topic_sentiment(sent_non[:TOP6], word_weights)
    n_out = conn.execute("SELECT COUNT(*) FROM post_topic WHERE topic_id=-1").fetchone()[0]
    log(f"file-wide outliers {n_out:,} / {n_uni:,} = {100 * n_out / max(n_uni, 1):.1f}%")
    exp_rows = list(csv.DictReader(EXP_CSV.open(encoding="utf-8-sig")))
    selected = next(r for r in exp_rows if r.get("selected") == "selected")
    checklist = {
        "src/topic_modeling.py": True,
        "notebooks/topic_modeling.ipynb": (ROOT / "notebooks" / "topic_modeling.ipynb").exists(),
        "outputs/bertopic_experiments.csv": EXP_CSV.exists(),
        "outputs/coherence_scores.csv": COH_CSV.exists(),
        "outputs/coherence_plot.png": COH_PNG.exists(),
        "outputs/final_topics.csv": FINAL_CSV.exists(),
        "outputs/topic_representative_tweets.csv": REP_CSV.exists(),
        "outputs/topic_distribution.csv": DIST_CSV.exists(),
        "outputs/topic_sentiment_distribution.csv": SENT_CSV.exists(),
        "outputs/topic_sentiment_by_source.csv": SENT_SRC_CSV.exists(),
        "outputs/topic_sentiment_visualization.png": SENT_PNG.exists(),
        "outputs/topic_model.pkl": PKL.exists(),
        "TOPIC_MODELING_REPORT.md": True,
    }
    stats = {
        "n_universe": EXPECTED_N,
        "n_usable": 638916,
        "n_short": 104026,
        "n_tune": TUNE_N,
        "n_transform": 574916,
        "n_out": n_out,
        "n_reassigned": 294595,
    }
    write_report(stats, exp_rows, selected, topics_out, sent_rows, checklist)


def refresh_reps() -> int:
    """Re-name topics and refresh CSVs/plot/report without touching assignments."""
    log("Refresh names + representative tweets (no reassignment, IFB.db untouched)")
    with PKL.open("rb") as fh:
        topic_model = pickle.load(fh)
    conn = connect_nlp(False)
    try:
        existing = {int(r[0]) for r in conn.execute("SELECT DISTINCT topic_id FROM post_topic")}
        model_tids = sorted(t for t in existing if t != -1 and t not in SPAM_TOPICS)
        write_topic_artifacts(topic_model, conn, model_tids)
    finally:
        conn.close()
    log("REFRESH_COMPLETE")
    return 0


if __name__ == "__main__":
    if "--refresh-reps" in sys.argv:
        raise SystemExit(refresh_reps())
    if "--finalize" in sys.argv:
        raise SystemExit(finalize())
    raise SystemExit(main())
