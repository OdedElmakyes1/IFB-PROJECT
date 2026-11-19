#!/usr/bin/env python3
"""Phase 4: NER + entity sentiment on original_text.

Does not open IFB.db. Does not rerun sentiment, emotion, events, or BERTopic.
Writes mention tables into data/nlp_analysis_corpus.db only.
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("USE_TF", "0")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
NLP_DB = ROOT / "data" / "nlp_analysis_corpus.db"
OUTPUT_DIR = ROOT / "outputs"
REPORT = ROOT / "NER_ENTITY_ANALYSIS_REPORT.md"
FINAL_TOPICS = OUTPUT_DIR / "final_topics.csv"

EXTRACTED_CSV = OUTPUT_DIR / "entities_extracted.csv"
CLEANED_CSV = OUTPUT_DIR / "entities_cleaned.csv"
SENT_CSV = OUTPUT_DIR / "entity_sentiment_distribution.csv"
SENT_SRC_CSV = OUTPUT_DIR / "entity_sentiment_by_source.csv"
ALIAS_CSV = OUTPUT_DIR / "entity_alias_mapping.csv"
PERSON_PNG = OUTPUT_DIR / "person_entities_sentiment.png"
COUNTRY_PNG = OUTPUT_DIR / "country_entities_sentiment.png"

SEED = 2026
STATUS_FILTER = "not_required_english"
EXPECTED_N = 742_942
SPACY_MODEL = "en_core_web_lg"
KEEP_LABELS = ("PERSON", "GPE", "LOC", "ORG", "EVENT", "NORP", "FAC", "PRODUCT")
FETCH_CHUNK = 1_024
PIPE_BATCH = 128
COMMIT_EVERY = 2_048
REP_TWEETS = 4
PERSON_MIN_POSTS = 50
COUNTRY_MIN_POSTS = 25
TOP_N = 10
CHART_SKIP_PERSON = frozenset(
    {
        "drop", "joe", "taylor", "johnson", "dm", "retweet", "steph", "otis",
        "follow wayne's", "se l'offerta vi è piaciuta", "yo", "hi", "jack",
        "jung kook",
    }
)

POS, NEU, NEG = "positive", "neutral", "negative"
SENT_COLOR = {POS: "#2ca02c", NEU: "#ffcc00", NEG: "#d62728"}

URL_RE = re.compile(r"https?://|www\.|\w+\.(com|net|org|io|co|ly)\b", re.I)
USER_RE = re.compile(r"^@\w{1,32}$")
HASHTAG_RE = re.compile(r"^#")
ONLY_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)
ONLY_NUM_RE = re.compile(r"^[\d\s.,:%+-]+$")
MULTI_SPACE = re.compile(r"\s+")
APOS_RE = re.compile(r"[’`´]")

JUNK_EXACT = frozenset(
    {
        "&", "+", "-", "|", "/", "\\", "*", "#", "@", "amp", "gt", "lt", "nbsp",
        "rt", "http", "https", "www", "com", "org", "net", "html", "php",
        "the", "a", "an", "this", "that", "today", "tomorrow", "yesterday",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "ifb", "follow", "followback", "f4f", "fff", "ff", "teamfollowback",
        "like", "comment", "share", "subscribe", "click", "link",
        "god", "lord", "sir", "bro", "dude", "girl", "man", "woman", "people",
        "someone", "anyone", "everyone", "nobody", "thing", "stuff",
        "one", "two", "first", "last", "new", "old", "good", "great",
    }
)
JUNK_PERSON = frozenset({"god", "lord", "jesus christ's", "mom", "dad", "bro", "sis"})

# 2-letter codes mapped only when the surface form is a short uppercase code.
ISO2_COUNTRY = {
    "us": "United States", "usa": "United States", "uk": "United Kingdom",
    "gb": "United Kingdom", "ae": "United Arab Emirates", "ng": "Nigeria",
    "za": "South Africa", "cn": "China", "in": "India", "pk": "Pakistan",
    "bd": "Bangladesh", "id": "Indonesia", "ph": "Philippines", "vn": "Vietnam",
    "jp": "Japan", "kr": "South Korea", "kp": "North Korea", "au": "Australia",
    "nz": "New Zealand", "ca": "Canada", "mx": "Mexico", "br": "Brazil",
    "ar": "Argentina", "cl": "Chile", "co": "Colombia", "pe": "Peru",
    "fr": "France", "de": "Germany", "es": "Spain", "it": "Italy",
    "pt": "Portugal", "nl": "Netherlands", "be": "Belgium", "ch": "Switzerland",
    "at": "Austria", "se": "Sweden", "no": "Norway", "dk": "Denmark",
    "fi": "Finland", "ie": "Ireland", "pl": "Poland", "ua": "Ukraine",
    "ru": "Russia", "tr": "Turkey", "il": "Israel", "eg": "Egypt",
    "sa": "Saudi Arabia", "qa": "Qatar", "kw": "Kuwait", "iq": "Iraq",
    "ir": "Iran", "sy": "Syria", "lb": "Lebanon", "jo": "Jordan",
    "ke": "Kenya", "gh": "Ghana", "tz": "Tanzania", "ug": "Uganda",
    "et": "Ethiopia", "ma": "Morocco", "dz": "Algeria", "tn": "Tunisia",
    "gr": "Greece", "cz": "Czechia", "hu": "Hungary", "ro": "Romania",
    "sg": "Singapore", "my": "Malaysia", "th": "Thailand", "hk": "Hong Kong",
    "tw": "Taiwan", "af": "Afghanistan", "np": "Nepal", "lk": "Sri Lanka",
}

COUNTRY_ALIASES: dict[str, str] = {
    "united states": "United States",
    "united states of america": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "u.s.a": "United States",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "u.k.": "United Kingdom",
    "uk": "United Kingdom",
    "england": "England",
    "scotland": "Scotland",
    "wales": "Wales",
    "northern ireland": "Northern Ireland",
    "nigeria": "Nigeria",
    "nigerian": "Nigeria",
    "ghana": "Ghana",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "canada": "Canada",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "argentina": "Argentina",
    "china": "China",
    "people's republic of china": "China",
    "prc": "China",
    "india": "India",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "indonesia": "Indonesia",
    "philippines": "Philippines",
    "japan": "Japan",
    "south korea": "South Korea",
    "republic of korea": "South Korea",
    "north korea": "North Korea",
    "dprk": "North Korea",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "france": "France",
    "germany": "Germany",
    "spain": "Spain",
    "italy": "Italy",
    "portugal": "Portugal",
    "netherlands": "Netherlands",
    "holland": "Netherlands",
    "belgium": "Belgium",
    "switzerland": "Switzerland",
    "sweden": "Sweden",
    "norway": "Norway",
    "denmark": "Denmark",
    "finland": "Finland",
    "ireland": "Ireland",
    "republic of ireland": "Ireland",
    "poland": "Poland",
    "ukraine": "Ukraine",
    "russia": "Russia",
    "russian federation": "Russia",
    "turkey": "Turkey",
    "turkiye": "Turkey",
    "türkiye": "Turkey",
    "israel": "Israel",
    "palestine": "Palestine",
    "egypt": "Egypt",
    "saudi arabia": "Saudi Arabia",
    "ksa": "Saudi Arabia",
    "united arab emirates": "United Arab Emirates",
    "uae": "United Arab Emirates",
    "qatar": "Qatar",
    "kuwait": "Kuwait",
    "iraq": "Iraq",
    "iran": "Iran",
    "syria": "Syria",
    "lebanon": "Lebanon",
    "morocco": "Morocco",
    "algeria": "Algeria",
    "tunisia": "Tunisia",
    "ethiopia": "Ethiopia",
    "uganda": "Uganda",
    "tanzania": "Tanzania",
    "afghanistan": "Afghanistan",
    "vietnam": "Vietnam",
    "thailand": "Thailand",
    "malaysia": "Malaysia",
    "singapore": "Singapore",
    "hong kong": "Hong Kong",
    "taiwan": "Taiwan",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    "greece": "Greece",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "hungary": "Hungary",
    "romania": "Romania",
    "austria": "Austria",
    "sri lanka": "Sri Lanka",
    "nepal": "Nepal",
}
# Do not auto-promote these GPE strings to the country chart.
AMBIGUOUS_COUNTRY = frozenset(
    {
        "georgia", "jordan", "guinea", "chad", "mali", "niger", "jersey",
        "macedonia", "congo", "sudan", "samoa", "monaco", "andorra",
    }
)

PERSON_ALIASES: dict[str, tuple[str, str, float]] = {
    # canonical, reason, confidence
    "donald trump": ("Donald Trump", "standard name + title variants", 0.99),
    "donald j trump": ("Donald Trump", "middle initial", 0.99),
    "donald j. trump": ("Donald Trump", "middle initial", 0.99),
    "president trump": ("Donald Trump", "office title + surname", 0.98),
    "trump": ("Donald Trump", "dominant referent in 2007–2023 English Twitter", 0.90),
    "joe biden": ("Joe Biden", "standard name + title variants", 0.99),
    "joseph biden": ("Joe Biden", "full given name", 0.98),
    "president biden": ("Joe Biden", "office title + surname", 0.98),
    "biden": ("Joe Biden", "distinctive surname in this period", 0.92),
    "barack obama": ("Barack Obama", "standard name + title variants", 0.99),
    "president obama": ("Barack Obama", "office title + surname", 0.98),
    "obama": ("Barack Obama", "distinctive surname", 0.93),
    "hillary clinton": ("Hillary Clinton", "standard name", 0.99),
    "hillary": ("Hillary Clinton", "given name in US-politics tweets", 0.85),
    "kamala harris": ("Kamala Harris", "standard name", 0.99),
    "kamala": ("Kamala Harris", "distinctive given name", 0.90),
    "elon musk": ("Elon Musk", "standard name", 0.99),
    "elon": ("Elon Musk", "distinctive given name", 0.88),
    "vladimir putin": ("Vladimir Putin", "standard name", 0.99),
    "putin": ("Vladimir Putin", "distinctive surname", 0.93),
    "volodymyr zelensky": ("Volodymyr Zelenskyy", "transliteration", 0.97),
    "volodymyr zelenskyy": ("Volodymyr Zelenskyy", "standard name", 0.99),
    "zelensky": ("Volodymyr Zelenskyy", "transliteration", 0.95),
    "zelenskyy": ("Volodymyr Zelenskyy", "transliteration", 0.97),
    "zelenskiy": ("Volodymyr Zelenskyy", "transliteration", 0.95),
    "benjamin netanyahu": ("Benjamin Netanyahu", "standard name", 0.99),
    "netanyahu": ("Benjamin Netanyahu", "distinctive surname", 0.95),
    "bibi": ("Benjamin Netanyahu", "common nickname, politics context", 0.80),
    "kanye west": ("Kanye West", "standard name", 0.99),
    "ye": ("Kanye West", "adopted name; only exact token", 0.70),
    "taylor swift": ("Taylor Swift", "standard name", 0.99),
    "jungkook": ("Jungkook", "BTS stage name", 0.95),
    "jung kook": ("Jungkook", "spaced stage name", 0.95),
    "jeon jungkook": ("Jungkook", "full name", 0.97),
    "jimin": ("Jimin", "BTS stage name; not merged with other Jimins outside exact token", 0.80),
    "park jimin": ("Jimin", "full name", 0.95),
    "kim jong un": ("Kim Jong Un", "standard name", 0.99),
    "kim jong-un": ("Kim Jong Un", "hyphen variant", 0.99),
}

ORG_ALIASES: dict[str, tuple[str, str, float]] = {
    "twitter": ("Twitter", "platform name", 0.99),
    "twitter.com": ("Twitter", "domain", 0.95),
    "instagram": ("Instagram", "platform name", 0.99),
    "insta": ("Instagram", "abbreviation", 0.85),
    "youtube": ("YouTube", "platform name", 0.99),
    "yt": ("YouTube", "abbreviation; only as ORG", 0.70),
    "facebook": ("Facebook", "platform name", 0.99),
    "fb": ("Facebook", "abbreviation", 0.80),
    "nba": ("NBA", "league acronym", 0.95),
    "nfl": ("NFL", "league acronym", 0.95),
    "cnn": ("CNN", "outlet acronym", 0.95),
    "fox news": ("Fox News", "outlet", 0.97),
    "new york times": ("New York Times", "outlet", 0.97),
    "nytimes": ("New York Times", "handle/domain style", 0.90),
    "bbc": ("BBC", "outlet acronym", 0.95),
    "opensea": ("OpenSea", "NFT marketplace", 0.93),
}

EVENT_ALIASES: dict[str, tuple[str, str, float]] = {
    "covid": ("COVID-19", "short form", 0.95),
    "covid-19": ("COVID-19", "standard name", 0.99),
    "covid19": ("COVID-19", "compact form", 0.97),
    "coronavirus": ("COVID-19", "common alias in 2020–2023 tweets", 0.90),
    "covid 19": ("COVID-19", "spaced form", 0.97),
    "world cup": ("World Cup", "sporting event", 0.90),
    "fifa world cup": ("World Cup", "official prefix", 0.95),
}

LABEL_TO_CAT = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "EVENT": "event",
    "NORP": "norp",
    "FAC": "facility",
    "PRODUCT": "product",
}


def log(msg: str) -> None:
    print(msg, flush=True)


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
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def load_topic_names() -> dict[int, str]:
    names: dict[int, str] = {-1: "Outliers / too little topic signal"}
    if FINAL_TOPICS.exists():
        with FINAL_TOPICS.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                names[int(row["topic_id"])] = row["topic_name"]
    return names


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def normalize_surface(text: str) -> str:
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKC", text)
    text = APOS_RE.sub("'", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = HASHTAG_RE.sub("", text.strip())
    text = text.strip(" \t\r\n\"'`.,:;!?()[]{}<>“”‘’#*|~")
    text = MULTI_SPACE.sub(" ", text).strip()
    return text


def is_mostly_emoji_or_symbol(text: str) -> bool:
    if not text:
        return True
    letters = sum(ch.isalpha() for ch in text)
    return letters == 0


def junk_reason(surface: str, raw: str, label: str) -> str | None:
    s = surface.strip()
    if not s:
        return "empty"
    if s in {"&", "+", "|"} or s.lower() in JUNK_EXACT:
        return "junk_token"
    if len(s) == 1:
        return "one_character"
    if ONLY_NUM_RE.match(s):
        return "numeric_only"
    if ONLY_PUNCT_RE.match(s) or is_mostly_emoji_or_symbol(s):
        return "punct_or_symbol"
    if URL_RE.search(s) or URL_RE.search(raw or ""):
        return "url_like"
    if USER_RE.match(raw.strip() if raw else "") or (s.startswith("@") and " " not in s):
        return "username_like"
    if label == "PERSON" and s.lower() in JUNK_PERSON:
        return "generic_person"
    if len(s) < 2:
        return "too_short"
    return None


def lookup_alias(norm_l: str, label: str) -> tuple[str, str, str, float] | None:
    if label == "PERSON" and norm_l in PERSON_ALIASES:
        canon, reason, conf = PERSON_ALIASES[norm_l]
        return canon, "person", reason, conf
    if label == "ORG" and norm_l in ORG_ALIASES:
        canon, reason, conf = ORG_ALIASES[norm_l]
        return canon, "organization", reason, conf
    if label in {"EVENT", "PRODUCT", "ORG"} and norm_l in EVENT_ALIASES:
        canon, reason, conf = EVENT_ALIASES[norm_l]
        return canon, "event", reason, conf
    return None


def country_canonical(norm_l: str, raw: str, label: str) -> tuple[str, str, float] | None:
    if label not in {"GPE", "LOC"}:
        return None
    if norm_l in AMBIGUOUS_COUNTRY:
        return None
    if norm_l in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[norm_l], "country alias / English name", 0.95
    raw_stripped = (raw or "").strip().lstrip("#")
    if len(raw_stripped) == 2 and raw_stripped.isalpha() and raw_stripped.isupper():
        mapped = ISO2_COUNTRY.get(raw_stripped.lower())
        if mapped and raw_stripped.lower() not in AMBIGUOUS_COUNTRY:
            return mapped, "uppercase ISO-3166 alpha-2", 0.88
    if len(norm_l) == 3 and norm_l.isalpha():
        iso3 = {
            "usa": "United States", "gbr": "United Kingdom", "nga": "Nigeria",
            "chn": "China", "ind": "India", "can": "Canada", "aus": "Australia",
            "deu": "Germany", "fra": "France", "isr": "Israel", "are": "United Arab Emirates",
            "rus": "Russia", "ukr": "Ukraine", "tur": "Turkey", "jpn": "Japan",
            "kor": "South Korea", "bra": "Brazil", "mex": "Mexico", "egy": "Egypt",
            "sau": "Saudi Arabia", "zaf": "South Africa", "gha": "Ghana", "ken": "Kenya",
        }
        if norm_l in iso3:
            return iso3[norm_l], "ISO-3166 alpha-3", 0.90
    return None


def classify_entity(raw: str, label: str) -> dict[str, Any]:
    surface = normalize_surface(raw)
    reason = junk_reason(surface, raw, label)
    if reason:
        return {
            "entity_text_normalized": surface,
            "canonical_entity": surface,
            "normalized_category": LABEL_TO_CAT.get(label, "other"),
            "keep_flag": 0,
            "drop_reason": reason,
            "alias_reason": "",
            "alias_confidence": "",
        }
    norm_l = surface.lower()
    cat = LABEL_TO_CAT.get(label, "other")
    canonical = surface
    alias_reason = "identity (no merge)"
    conf = 1.0

    aliased = lookup_alias(norm_l, label)
    if aliased:
        canonical, cat, alias_reason, conf = aliased
    else:
        country = country_canonical(norm_l, raw, label)
        if country:
            canonical, alias_reason, conf = country
            cat = "country"
        elif label == "PERSON":
            canonical = surface.title() if surface.islower() or surface.isupper() else surface
            cat = "person"
        elif label == "ORG":
            cat = "organization"
        elif label in {"GPE", "LOC"}:
            cat = "location"
            canonical = surface.title() if surface.islower() else surface
        elif label == "EVENT":
            cat = "event"
        elif label == "NORP":
            cat = "norp"
        elif label == "FAC":
            cat = "facility"
        elif label == "PRODUCT":
            cat = "product"

    return {
        "entity_text_normalized": surface,
        "canonical_entity": canonical,
        "normalized_category": cat,
        "keep_flag": 1,
        "drop_reason": "",
        "alias_reason": alias_reason,
        "alias_confidence": conf,
    }


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ner_post_done (
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            n_ents INTEGER NOT NULL,
            PRIMARY KEY (source, tweet_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_mention (
            mention_id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            author_id TEXT,
            username TEXT,
            created_at TEXT,
            entity_text TEXT NOT NULL,
            entity_text_normalized TEXT NOT NULL,
            entity_label TEXT NOT NULL,
            normalized_category TEXT NOT NULL,
            character_start INTEGER NOT NULL,
            character_end INTEGER NOT NULL,
            topic_id INTEGER,
            topic_name TEXT,
            sentiment_label TEXT,
            sentiment_positive REAL,
            sentiment_neutral REAL,
            sentiment_negative REAL,
            sample_weight REAL,
            keep_flag INTEGER NOT NULL DEFAULT 1,
            drop_reason TEXT,
            canonical_entity TEXT,
            alias_reason TEXT,
            alias_confidence REAL,
            UNIQUE (source, tweet_id, character_start, character_end)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_keep ON entity_mention(keep_flag, normalized_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_canon ON entity_mention(canonical_entity, normalized_category)")
    conn.commit()


def extract(conn: sqlite3.Connection, topic_names: dict[int, str]) -> dict[str, Any]:
    import spacy

    n_done = conn.execute("SELECT COUNT(*) FROM ner_post_done").fetchone()[0]
    log(f"NER model {SPACY_MODEL}; already done {n_done:,} / {EXPECTED_N:,}")
    nlp = spacy.load(SPACY_MODEL, disable=["tagger", "parser", "lemmatizer", "attribute_ruler", "senter"])
    meta = {"name": nlp.meta.get("name"), "version": nlp.meta.get("version"), "spacy": spacy.__version__, "pipes": list(nlp.pipe_names)}
    log(f"Loaded {meta}")

    sql = """
        SELECT p.source, p.tweet_id, p.author_id, p.username, p.created_at,
               p.original_text, p.sample_weight,
               s.sentiment_label, s.sentiment_positive, s.sentiment_neutral, s.sentiment_negative,
               t.topic_id
        FROM nlp_posts p
        JOIN post_sentiment s USING (source, tweet_id)
        JOIN post_topic t USING (source, tweet_id)
        WHERE p.translation_status=?
          AND NOT EXISTS (
              SELECT 1 FROM ner_post_done d
              WHERE d.source=p.source AND d.tweet_id=p.tweet_id
          )
    """
    cur = conn.execute(sql, (STATUS_FILTER,))
    t0 = time.perf_counter()
    processed = 0
    n_ents = 0
    insert_mentions = """
        INSERT OR IGNORE INTO entity_mention (
            source, tweet_id, author_id, username, created_at,
            entity_text, entity_text_normalized, entity_label, normalized_category,
            character_start, character_end, topic_id, topic_name,
            sentiment_label, sentiment_positive, sentiment_neutral, sentiment_negative,
            sample_weight, keep_flag, drop_reason, canonical_entity, alias_reason, alias_confidence
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    insert_done = "INSERT OR IGNORE INTO ner_post_done (source, tweet_id, n_ents) VALUES (?,?,?)"

    while True:
        rows = cur.fetchmany(FETCH_CHUNK)
        if not rows:
            break
        texts = [r["original_text"] or "" for r in rows]
        docs = nlp.pipe(texts, batch_size=PIPE_BATCH)
        mention_batch: list[tuple[Any, ...]] = []
        done_batch: list[tuple[Any, ...]] = []
        for rec, doc in zip(rows, docs):
            tid = int(rec["topic_id"])
            tname = topic_names.get(tid, f"topic_{tid}")
            kept_here = 0
            for ent in doc.ents:
                if ent.label_ not in KEEP_LABELS:
                    continue
                info = classify_entity(ent.text, ent.label_)
                mention_batch.append(
                    (
                        rec["source"],
                        rec["tweet_id"],
                        rec["author_id"],
                        rec["username"] or "",
                        rec["created_at"],
                        ent.text,
                        info["entity_text_normalized"],
                        ent.label_,
                        info["normalized_category"],
                        int(ent.start_char),
                        int(ent.end_char),
                        tid,
                        tname,
                        rec["sentiment_label"],
                        float(rec["sentiment_positive"]),
                        float(rec["sentiment_neutral"]),
                        float(rec["sentiment_negative"]),
                        float(rec["sample_weight"] or 1),
                        int(info["keep_flag"]),
                        info["drop_reason"],
                        info["canonical_entity"],
                        info["alias_reason"],
                        info["alias_confidence"] if info["alias_confidence"] != "" else None,
                    )
                )
                kept_here += 1
            done_batch.append((rec["source"], rec["tweet_id"], kept_here))
            n_ents += kept_here
        conn.executemany(insert_mentions, mention_batch)
        conn.executemany(insert_done, done_batch)
        processed += len(rows)
        if processed % COMMIT_EVERY < FETCH_CHUNK:
            conn.commit()
            elapsed = time.perf_counter() - t0
            rate = processed / max(elapsed, 1e-6)
            remain = (EXPECTED_N - n_done - processed) / max(rate, 1e-6)
            log(
                f"  NER {n_done + processed:,}/{EXPECTED_N:,} "
                f"({rate:.0f} tweets/s, ~{remain/60:.1f} min left, ents={n_ents:,})"
            )
    conn.commit()
    n_done2 = conn.execute("SELECT COUNT(*) FROM ner_post_done").fetchone()[0]
    n_mentions = conn.execute("SELECT COUNT(*) FROM entity_mention").fetchone()[0]
    n_keep = conn.execute("SELECT COUNT(*) FROM entity_mention WHERE keep_flag=1").fetchone()[0]
    log(f"Extract done posts={n_done2:,} mentions={n_mentions:,} kept={n_keep:,}")
    meta["n_posts"] = n_done2
    meta["n_mentions"] = n_mentions
    meta["n_keep"] = n_keep
    meta["runtime_sec"] = round(time.perf_counter() - t0, 1)
    return meta


def postprocess_mentions(conn: sqlite3.Connection) -> None:
    """Second-pass cleanup on stored mentions. Does not rerun spaCy."""
    log("Post-process: drop junk, remap platforms / Trump / COVID")
    conn.execute(
        """
        UPDATE entity_mention
        SET canonical_entity='Donald Trump',
            normalized_category='person',
            alias_reason='spaCy often tags the surname Trump as ORG',
            alias_confidence=0.88
        WHERE keep_flag=1
          AND lower(trim(entity_text_normalized)) IN (
              'trump','donald trump','donald j trump','donald j. trump','president trump'
          )
        """
    )
    conn.execute(
        """
        UPDATE entity_mention
        SET canonical_entity='COVID-19',
            normalized_category='event',
            alias_reason='COVID surface tagged as PERSON/PRODUCT/ORG',
            alias_confidence=0.93
        WHERE keep_flag=1
          AND lower(replace(replace(entity_text_normalized,' ',''),'-',''))
              IN ('covid','covid19','coronavirus')
        """
    )
    for raw, canon in (
        ("twitter", "Twitter"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("facebook", "Facebook"),
        ("twitch", "Twitch"),
    ):
        conn.execute(
            """
            UPDATE entity_mention
            SET canonical_entity=?,
                normalized_category='organization',
                alias_reason='platform name, not a person',
                alias_confidence=0.95
            WHERE keep_flag=1 AND lower(trim(entity_text_normalized))=?
            """,
            (canon, raw),
        )
    junk = (
        "retweet", "rt", "dm", "steph", "otis", "bako", "yo", "hi", "ok",
        "follow", "ifb", "f4f", "pogohub", "rt &", "amp", "drop",
        "follow wayne's", "se l'offerta vi è piaciuta",
    )
    q = ",".join("?" * len(junk))
    conn.execute(
        f"""
        UPDATE entity_mention
        SET keep_flag=0, drop_reason='junk_token'
        WHERE keep_flag=1 AND lower(trim(canonical_entity)) IN ({q})
        """,
        junk,
    )
    conn.execute(
        """
        UPDATE entity_mention
        SET keep_flag=0, drop_reason='junk_amp_or_symbol'
        WHERE keep_flag=1 AND (
            instr(canonical_entity, '&') > 0
            OR instr(entity_text_normalized, '&') > 0
            OR instr(canonical_entity, '👋') > 0
            OR instr(entity_text, '👋') > 0
        )
        """
    )
    conn.commit()
    n_junk = conn.execute("SELECT COUNT(*) FROM entity_mention WHERE drop_reason IN ('junk_token','junk_amp_or_symbol')").fetchone()[0]
    log(f"  junk rows now flagged={n_junk:,}")


def export_extracted(conn: sqlite3.Connection) -> int:
    fields = [
        "source", "tweet_id", "author_id", "username", "created_at",
        "entity_text", "entity_text_normalized", "entity_label", "normalized_category",
        "character_start", "character_end", "topic_id", "topic_name",
        "sentiment_label", "sentiment_positive", "sentiment_neutral", "sentiment_negative",
        "sample_weight", "keep_flag", "drop_reason", "canonical_entity",
    ]
    n = 0
    log(f"Writing {EXTRACTED_CSV.name}")
    EXTRACTED_CSV.parent.mkdir(parents=True, exist_ok=True)
    with EXTRACTED_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        cur = conn.execute(
            f"SELECT {', '.join(fields)} FROM entity_mention ORDER BY source, tweet_id, character_start"
        )
        while True:
            chunk = cur.fetchmany(20_000)
            if not chunk:
                break
            for r in chunk:
                w.writerow({k: r[k] for k in fields})
                n += 1
    log(f"  extracted rows={n:,}")
    return n


def alias_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT entity_text_normalized, canonical_entity, normalized_category,
               alias_reason, AVG(alias_confidence) conf, COUNT(*) n
        FROM entity_mention
        WHERE keep_flag=1 AND canonical_entity != entity_text_normalized
        GROUP BY 1,2,3,4
        ORDER BY n DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "original_entity": r["entity_text_normalized"],
                "normalized_entity": r["canonical_entity"],
                "normalized_category": r["normalized_category"],
                "reason": r["alias_reason"],
                "confidence": round(float(r["conf"] or 0), 3),
                "n_mentions": int(r["n"]),
            }
        )
    return out


def pick_reps(conn: sqlite3.Connection, canonical: str, category: str) -> list[dict[str, Any]]:
    cand = conn.execute(
        """
        SELECT e.source, e.tweet_id, e.author_id, e.username, e.created_at,
               e.entity_text, e.sentiment_label, p.original_text
        FROM entity_mention e
        JOIN nlp_posts p USING (source, tweet_id)
        WHERE e.keep_flag=1 AND e.canonical_entity=? AND e.normalized_category=?
        LIMIT 400
        """,
        (canonical, category),
    ).fetchall()
    picked: list[dict[str, Any]] = []
    seen_txt: set[str] = set()
    needle = canonical.lower()
    for r in cand:
        text = (r["original_text"] or "").strip()
        if len(text) < 40:
            continue
        low = text.lower()
        if needle not in low and (r["entity_text"] or "").lower() not in low:
            continue
        key = re.sub(r"\s+", " ", low)[:100]
        if key in seen_txt:
            continue
        seen_txt.add(key)
        picked.append(dict(r))
        if len(picked) >= REP_TWEETS:
            break
    return picked


def aggregate(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    log("Aggregating kept mentions")
    raw = conn.execute(
        """
        SELECT canonical_entity, normalized_category,
               source, tweet_id, author_id, created_at, sample_weight,
               sentiment_label, sentiment_positive, sentiment_neutral, sentiment_negative,
               entity_label, entity_text_normalized
        FROM entity_mention
        WHERE keep_flag=1
        """
    ).fetchall()
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    posts: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    users: dict[tuple[str, str], set[str]] = defaultdict(set)
    src_posts: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    src_sent: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    src_w: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {POS: 0.0, NEU: 0.0, NEG: 0.0, "n": 0.0})
    variants: dict[tuple[str, str], Counter] = defaultdict(Counter)
    labels: dict[tuple[str, str], Counter] = defaultdict(Counter)
    dates: dict[tuple[str, str], list[str]] = defaultdict(list)
    post_sent: dict[tuple[str, str, str, str], tuple[str, float, float, float, float]] = {}

    for r in raw:
        key = (r["canonical_entity"], r["normalized_category"])
        st = stats.setdefault(
            key,
            {"n_mentions": 0, "n_pos": 0, "n_neu": 0, "n_neg": 0, "sp": 0.0, "sn": 0.0, "sg": 0.0, "n_prob": 0},
        )
        st["n_mentions"] += 1
        variants[key][r["entity_text_normalized"]] += 1
        labels[key][r["entity_label"]] += 1
        post_key = (key[0], key[1], r["source"], r["tweet_id"])
        if post_key not in post_sent:
            post_sent[post_key] = (
                r["sentiment_label"],
                float(r["sentiment_positive"] or 0),
                float(r["sentiment_neutral"] or 0),
                float(r["sentiment_negative"] or 0),
                float(r["sample_weight"] or 1),
            )
            posts[key].add((r["source"], r["tweet_id"]))
            users[key].add(str(r["author_id"]))
            src_posts[(key[0], key[1], r["source"])].add((r["source"], r["tweet_id"]))
            lab = r["sentiment_label"]
            src_sent[(key[0], key[1], r["source"])][lab] += 1
            if r["created_at"]:
                dates[key].append(r["created_at"])
            if r["source"] == "timeline":
                w = float(r["sample_weight"] or 1)
                src_w[(key[0], key[1], r["source"])]["n"] += w
                if lab in src_w[(key[0], key[1], r["source"])]:
                    src_w[(key[0], key[1], r["source"])][lab] += w

    for (_ent, _cat, _src, _tid), (lab, ppos, pneu, pneg, _w) in post_sent.items():
        key = (_ent, _cat)
        st = stats[key]
        if lab == POS:
            st["n_pos"] += 1
        elif lab == NEU:
            st["n_neu"] += 1
        elif lab == NEG:
            st["n_neg"] += 1
        st["sp"] += ppos
        st["sn"] += pneu
        st["sg"] += pneg
        st["n_prob"] += 1

    cleaned: list[dict[str, Any]] = []
    sent_rows: list[dict[str, Any]] = []
    src_rows: list[dict[str, Any]] = []
    for key, st in stats.items():
        ent, cat = key
        n_post = len(posts[key])
        n = max(n_post, 1)
        n_kw = sum(1 for s, _ in posts[key] if s == "keyword_tweets")
        n_tl = n_post - n_kw
        dmin = min(dates[key]) if dates[key] else ""
        dmax = max(dates[key]) if dates[key] else ""
        mode_label = labels[key].most_common(1)[0][0] if labels[key] else ""
        var = ", ".join(f"{a} ({c})" for a, c in variants[key].most_common(8))
        row = {
            "canonical_entity": ent,
            "entity": ent,
            "entity_type": cat,
            "normalized_category": cat,
            "entity_label_mode": mode_label,
            "n_mentions": st["n_mentions"],
            "Count": n_post,
            "n_posts": n_post,
            "n_users": len(users[key]),
            "n_keyword": n_kw,
            "n_timeline": n_tl,
            "n_positive": st["n_pos"],
            "n_neutral": st["n_neu"],
            "n_negative": st["n_neg"],
            "positive": st["n_pos"],
            "neutral": st["n_neu"],
            "negative": st["n_neg"],
            "pct_positive": round(100 * st["n_pos"] / n, 2),
            "pct_neutral": round(100 * st["n_neu"] / n, 2),
            "pct_negative": round(100 * st["n_neg"] / n, 2),
            "avg_sentiment_positive": round(st["sp"] / max(st["n_prob"], 1), 4),
            "avg_sentiment_neutral": round(st["sn"] / max(st["n_prob"], 1), 4),
            "avg_sentiment_negative": round(st["sg"] / max(st["n_prob"], 1), 4),
            "date_min": dmin,
            "date_max": dmax,
            "singleton_flag": int(n_post == 1),
            "variants": var,
            "count_note": "sentiment counts are unique posts, not mention copies; unweighted analysis-file mix",
        }
        cleaned.append(row)
        sent_rows.append(row)
        for src in ("keyword_tweets", "timeline"):
            sp = src_posts.get((ent, cat, src), set())
            ss = src_sent.get((ent, cat, src), Counter())
            nn = max(len(sp), 1)
            ww = src_w.get((ent, cat, src), {POS: 0.0, NEU: 0.0, NEG: 0.0, "n": 0.0})
            src_rows.append(
                {
                    "canonical_entity": ent,
                    "normalized_category": cat,
                    "source": src,
                    "n_posts": len(sp),
                    "n_positive": int(ss.get(POS, 0)),
                    "n_neutral": int(ss.get(NEU, 0)),
                    "n_negative": int(ss.get(NEG, 0)),
                    "pct_positive": round(100 * ss.get(POS, 0) / nn, 2) if sp else 0,
                    "pct_neutral": round(100 * ss.get(NEU, 0) / nn, 2) if sp else 0,
                    "pct_negative": round(100 * ss.get(NEG, 0) / nn, 2) if sp else 0,
                    "n_weighted": round(float(ww["n"]), 2),
                    "w_positive": round(float(ww[POS]), 2),
                    "w_neutral": round(float(ww[NEU]), 2),
                    "w_negative": round(float(ww[NEG]), 2),
                    "weight_note": (
                        "timeline sample_weight estimates English timeline population mentioning this entity"
                        if src == "timeline"
                        else "keyword census, weight=1"
                    ),
                }
            )
    cleaned.sort(key=lambda r: (-int(r["n_posts"]), r["normalized_category"], r["canonical_entity"]))
    log(f"cleaned entities={len(cleaned):,}")
    return cleaned, sent_rows, src_rows


def attach_reps(conn: sqlite3.Connection, cleaned: list[dict[str, Any]]) -> None:
    n_done = 0
    for row in cleaned:
        if int(row["n_posts"]) < 25:
            row["representative_tweet_ids"] = ""
            row["representative_texts"] = ""
            continue
        reps = pick_reps(conn, row["canonical_entity"], row["normalized_category"])
        row["representative_tweet_ids"] = "|".join(f"{m['source']}:{m['tweet_id']}" for m in reps)
        row["representative_texts"] = " || ".join(
            re.sub(r"\s+", " ", (m.get("original_text") or ""))[:220] for m in reps
        )
        n_done += 1
        if n_done % 75 == 0:
            log(f"  reps attached for {n_done} entities")


def person_chart_ok(name: str) -> bool:
    low = (name or "").lower().strip()
    if low in CHART_SKIP_PERSON:
        return False
    if "offerta" in low or low.startswith("follow "):
        return False
    return True


def plot_stacked(rows: list[dict[str, Any]], title: str, path: Path, xlabel: str) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 6.4))
    fig.patch.set_facecolor("white")
    names = [re.sub(r"[^\w\s.\-']+", "", r["canonical_entity"]).strip() or r["canonical_entity"] for r in rows][::-1]
    pos = [int(r["n_positive"]) for r in rows][::-1]
    neu = [int(r["n_neutral"]) for r in rows][::-1]
    neg = [int(r["n_negative"]) for r in rows][::-1]
    y = range(len(names))
    ax.barh(y, pos, color=SENT_COLOR[POS], edgecolor="white", label="positive")
    ax.barh(y, neu, left=pos, color=SENT_COLOR[NEU], edgecolor="white", label="neutral")
    left2 = [a + b for a, b in zip(pos, neu)]
    ax.barh(y, neg, left=left2, color=SENT_COLOR[NEG], edgecolor="white", label="negative")
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="x", alpha=0.25)
    for i, r in enumerate(rows[::-1]):
        n = max(int(r["n_posts"]), 1)
        ax.text(
            n + max(n * 0.01, 0.5),
            i,
            f"n={int(r['n_posts']):,}  +{float(r['pct_positive']):.0f}%  neu {float(r['pct_neutral']):.0f}%  −{float(r['pct_negative']):.0f}%",
            va="center",
            fontsize=8,
            color="#333333",
        )
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log(f"Wrote {path.name}")


def write_report(
    meta: dict[str, Any],
    cleaned: list[dict[str, Any]],
    drop_counts: dict[str, int],
    n_raw: int,
    n_keep: int,
    n_posts: int,
    checklist: dict[str, bool],
    aliases: list[dict[str, Any]],
) -> None:
    people = [
        r
        for r in cleaned
        if r["normalized_category"] == "person"
        and int(r["n_posts"]) >= PERSON_MIN_POSTS
        and person_chart_ok(r["canonical_entity"])
    ]
    countries = [r for r in cleaned if r["normalized_category"] == "country" and int(r["n_posts"]) >= COUNTRY_MIN_POSTS]
    people = sorted(people, key=lambda r: -int(r["n_posts"]))[:TOP_N]
    countries = sorted(countries, key=lambda r: -int(r["n_posts"]))[:TOP_N]
    cat_counts = Counter(r["normalized_category"] for r in cleaned)
    lines = [
        "# Named entity recognition and entity sentiment",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "IFB.db was not opened. Sentiment, emotion, event detection, and BERTopic were not rerun.",
        f"Random seed: **{SEED}** (not used for the NER model; extraction is deterministic given spaCy).",
        "",
        "## NER model",
        "",
        f"Library: **spaCy {meta.get('spacy', '')}**. Pipeline: **`{SPACY_MODEL}` {meta.get('version', '')}** (OntoNotes 5 labels).",
        "Course text lists HuggingFace / BERTweet / LLM. BERTweet is the sentiment model already used; public HuggingFace CoNLL-03 NER only has PER/ORG/LOC/MISC and would drop EVENT, NORP, FAC, PRODUCT, and the GPE vs LOC split. `en_core_web_lg` is the best installed spaCy-compatible English model with those labels. GPU was available but this CNN model runs on CPU (`tok2vec` + `ner` only).",
        "Input column: **`original_text`**, never Porter-stemmed `clean_text` / `topic_text`.",
        "",
        "## Volume",
        "",
        f"| Item | N |",
        f"|------|--:|",
        f"| English-ready posts ⋈ `post_sentiment` ⋈ `post_topic` | **{n_posts:,}** |",
        f"| Raw entity occurrences (target labels) | **{n_raw:,}** |",
        f"| Kept after cleaning | **{n_keep:,}** |",
        f"| Dropped | **{n_raw - n_keep:,}** |",
        f"| Distinct cleaned (canonical, category) pairs | **{len(cleaned):,}** |",
        f"| Extract runtime (this process) | {meta.get('runtime_sec', '')} sec |",
        "",
        "Keyword posts are a census (weight=1). Timeline `sample_weight` is used only for timeline population estimates inside an entity, never as a model-scoring weight.",
        "",
        "## Filtering rules",
        "",
        "Kept spaCy labels: PERSON, GPE, LOC, ORG, EVENT, NORP, FAC, PRODUCT. Dates, money, percents, and cardinals were not extracted.",
        "Dropped: empty; one-character; numeric-only; punctuation/emoji/symbol-only including **`&`**; URL-like; `@username`; IFB/follow tokens; generic PERSON shells (god, lord, bro, …). Hashtag `#` is stripped before matching. Unicode NFKC, HTML unescape, apostrophe folding.",
        "Course guideline “drop length <3” is **not** applied blindly: it would delete `US` / `UK`. Length-2 strings are kept only as uppercase ISO-2 country codes or after alias tables. Frequency=1 entities stay in the CSVs (`singleton_flag=1`) so “all entities” files are complete; they are excluded from the bar charts.",
        "",
        "Drop reasons:",
        "",
    ]
    for k, v in sorted(drop_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{k}`: {v:,}")
    lines += [
        "",
        "## Alias merging",
        "",
        "Merges are explicit tables, not string-similarity. Different people/countries are not collapsed because names look alike (no `Jordan`→country, no `Musk` alone→Elon, no `Georgia`→the country). Examples:",
        "",
        "| original | canonical | reason | confidence |",
        "|----------|-----------|--------|----------:|",
    ]
    for r in aliases[:18]:
        lines.append(f"| {r['original_entity']} | {r['normalized_entity']} | {r['reason']} | {r['confidence']} |")
    lines += [
        "",
        "Full table: `outputs/entity_alias_mapping.csv`.",
        "",
        "## Person vs country",
        "",
        "PERSON stays person even if the string is also a place name. GPE/LOC become **country** only after an allowlist of English names / ISO codes. Cities and regions stay **location**. Ambiguous GPE strings (Georgia, Jordan, Chad, Mali, Niger, Guinea) are **not** forced into the country chart.",
        "",
        f"Cleaned category counts: {', '.join(f'{k}={v:,}' for k, v in cat_counts.most_common())}.",
        "",
        "## Sentiment methodology",
        "",
        "Each mention inherits `sentiment_label` and the three probabilities from `post_sentiment` for that `(source, tweet_id)`. We do not rescore text. Unique-post counts are used for positive / **neutral** / negative so a tweet that repeats a name does not triple its vote. Mention totals are stored separately. Average probabilities are means over unique posts. Green / yellow / red match the rest of the project.",
        "",
        f"Person chart: top {TOP_N} PERSON entities with **≥ {PERSON_MIN_POSTS} unique posts** (unweighted analysis-file mix), sorted by unique posts.",
        f"Country chart: top {TOP_N} canonical countries with **≥ {COUNTRY_MIN_POSTS} unique posts**, same colors, same sort.",
        "",
        "### Top people (unique posts)",
        "",
        "| Entity | posts | +% | neu% | −% |",
        "|--------|-----:|---:|-----:|---:|",
    ]
    for r in people:
        lines.append(
            f"| {r['canonical_entity']} | {r['n_posts']} | {r['pct_positive']} | {r['pct_neutral']} | {r['pct_negative']} |"
        )
        texts = [t for t in str(r.get("representative_texts") or "").split(" || ") if t.strip()]
        for t in texts[:1]:
            lines.append(f"|  |  |  |  | _{t[:160]}_ |")
    lines += [
        "",
        "### Top countries (unique posts)",
        "",
        "| Entity | posts | +% | neu% | −% |",
        "|--------|-----:|---:|-----:|---:|",
    ]
    for r in countries:
        lines.append(
            f"| {r['canonical_entity']} | {r['n_posts']} | {r['pct_positive']} | {r['pct_neutral']} | {r['pct_negative']} |"
        )
    lines += [
        "",
        "## Keyword vs timeline",
        "",
        "`entity_sentiment_by_source.csv` splits every cleaned entity. Timeline `n_weighted` / `w_*` estimate the English timeline population mentioning that entity. Keyword rows are a census. Do not add the two frames into one unlabeled population.",
        "",
        "## Interpretation",
        "",
        "This is an IFB (follow-back) community sample, not a news wire. Platforms (Twitter, Instagram, YouTube), sports leagues, and a few politicians are expected. High-count people should be checked against representative tweets in `entities_cleaned.csv`. Neutral still dominates because the parent sentiment distribution is ~71% neutral; bars are not “all yellow” — green and red slices are drawn whenever those posts exist.",
        "",
        "## Limitations",
        "",
        "- Timeline is a ~1.7% English sample (seed 2026); entity mix is sample-dependent.",
        "- Keyword language labels are rule-based, not Twitter LANG.",
        "- spaCy news-trained NER misfires on hashtags, handle fragments, and promo copy. Cleaning removes the worst junk; it cannot fix every wrong PERSON.",
        "- `Trump`→Donald Trump is a documented high-confidence alias; a handful of other Trumps could be absorbed.",
        "- Georgia/Jordan-style GPE strings were left out of the country chart rather than guessed.",
        "- Combined keyword+timeline percentages describe the analysis file, not one social-media population.",
        "- Entity co-occurrence network is **not** in this phase.",
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


def validate(conn: sqlite3.Connection, cleaned: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    n_posts = conn.execute("SELECT COUNT(*) FROM ner_post_done").fetchone()[0]
    if n_posts != EXPECTED_N:
        issues.append(f"ner_post_done {n_posts} != {EXPECTED_N}")
    dup = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT source, tweet_id, character_start, character_end
            FROM entity_mention GROUP BY 1,2,3,4 HAVING COUNT(*)>1
        )
        """
    ).fetchone()[0]
    if dup:
        issues.append(f"duplicate mention keys {dup}")
    amp = conn.execute(
        """
        SELECT COUNT(*) FROM entity_mention
        WHERE keep_flag=1 AND (
            entity_text_normalized IN ('&','amp')
            OR canonical_entity IN ('&','amp')
            OR instr(canonical_entity, '&') > 0
        )
        """
    ).fetchone()[0]
    if amp:
        issues.append(f"kept &/amp {amp}")
    mismatch = conn.execute(
        """
        SELECT COUNT(*) FROM entity_mention e
        JOIN post_sentiment s USING (source, tweet_id)
        WHERE e.sentiment_label != s.sentiment_label
        """
    ).fetchone()[0]
    if mismatch:
        issues.append(f"sentiment_label mismatch vs post_sentiment {mismatch}")
    by = {(r["canonical_entity"], r["normalized_category"]): r for r in cleaned}
    agg = conn.execute(
        """
        SELECT canonical_entity, normalized_category, COUNT(*) n
        FROM entity_mention WHERE keep_flag=1
        GROUP BY 1,2
        """
    ).fetchall()
    for r in agg:
        key = (r["canonical_entity"], r["normalized_category"])
        if key not in by:
            issues.append(f"missing cleaned row {key}")
            break
        if int(by[key]["n_mentions"]) != int(r["n"]):
            issues.append(f"mention total mismatch {key}")
            break
    sent_tot = conn.execute(
        "SELECT sentiment_label, COUNT(*) FROM post_sentiment GROUP BY 1"
    ).fetchall()
    expected = {"positive": 134936, "neutral": 526377, "negative": 81629}
    got = {r[0]: r[1] for r in sent_tot}
    if got != expected:
        issues.append(f"post_sentiment moved {got}")
    src_ent = dict(conn.execute("SELECT source, COUNT(*) FROM entity_mention WHERE keep_flag=1 GROUP BY 1").fetchall())
    if "keyword_tweets" not in src_ent or "timeline" not in src_ent:
        issues.append(f"missing source split {src_ent}")
    if issues:
        for i in issues:
            log("VALIDATE FAIL: " + i)
    else:
        log("VALIDATE_OK")
    return issues


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    skip_extract = "--aggregate-only" in sys.argv
    topic_names = load_topic_names()
    wr = connect_nlp(True)
    try:
        ensure_tables(wr)
        meta: dict[str, Any] = {"spacy": "", "version": "", "name": SPACY_MODEL}
        if skip_extract:
            import spacy

            meta = {"spacy": spacy.__version__, "version": "3.8.0", "name": SPACY_MODEL, "runtime_sec": 0}
            log("Skipping extract (--aggregate-only)")
        else:
            meta = extract(wr, topic_names)
        postprocess_mentions(wr)
        n_posts = wr.execute("SELECT COUNT(*) FROM ner_post_done").fetchone()[0]
        n_raw = wr.execute("SELECT COUNT(*) FROM entity_mention").fetchone()[0]
        n_keep = wr.execute("SELECT COUNT(*) FROM entity_mention WHERE keep_flag=1").fetchone()[0]
        drop_counts = {
            str(r["drop_reason"] or "kept"): int(r["n"])
            for r in wr.execute(
                "SELECT COALESCE(drop_reason,'kept') drop_reason, COUNT(*) n FROM entity_mention GROUP BY 1"
            )
        }
        if not skip_extract or not EXTRACTED_CSV.exists() or "--reexport" in sys.argv:
            export_extracted(wr)
        else:
            log("Keeping existing entities_extracted.csv (use --reexport to rewrite)")
        aliases = alias_rows(wr)
        write_csv(
            ALIAS_CSV,
            ["original_entity", "normalized_entity", "normalized_category", "reason", "confidence", "n_mentions"],
            aliases,
        )
        cleaned, sent_rows, src_rows = aggregate(wr)
        attach_reps(wr, cleaned)
        # copy reps onto sent_rows
        rep_map = {(r["canonical_entity"], r["normalized_category"]): r for r in cleaned}
        for r in sent_rows:
            src = rep_map.get((r["canonical_entity"], r["normalized_category"]), {})
            r["representative_tweet_ids"] = src.get("representative_tweet_ids", "")
            r["representative_texts"] = src.get("representative_texts", "")
        write_csv(
            CLEANED_CSV,
            [
                "canonical_entity", "entity", "entity_type", "normalized_category", "entity_label_mode",
                "n_mentions", "Count", "n_posts", "n_users", "n_keyword", "n_timeline",
                "n_positive", "n_neutral", "n_negative", "positive", "neutral", "negative",
                "pct_positive", "pct_neutral", "pct_negative",
                "avg_sentiment_positive", "avg_sentiment_neutral", "avg_sentiment_negative",
                "date_min", "date_max", "singleton_flag", "variants",
                "representative_tweet_ids", "representative_texts", "count_note",
            ],
            cleaned,
        )
        write_csv(
            SENT_CSV,
            [
                "canonical_entity", "normalized_category", "entity_label_mode",
                "n_mentions", "n_posts", "n_users",
                "positive", "neutral", "negative", "n_positive", "n_neutral", "n_negative",
                "pct_positive", "pct_neutral", "pct_negative",
                "avg_sentiment_positive", "avg_sentiment_neutral", "avg_sentiment_negative",
                "n_keyword", "n_timeline", "date_min", "date_max", "singleton_flag",
                "representative_tweet_ids", "representative_texts", "count_note",
            ],
            sent_rows,
        )
        write_csv(
            SENT_SRC_CSV,
            [
                "canonical_entity", "normalized_category", "source", "n_posts",
                "n_positive", "n_neutral", "n_negative",
                "pct_positive", "pct_neutral", "pct_negative",
                "n_weighted", "w_positive", "w_neutral", "w_negative", "weight_note",
            ],
            src_rows,
        )
        people = [
            r
            for r in cleaned
            if r["normalized_category"] == "person"
            and int(r["n_posts"]) >= PERSON_MIN_POSTS
            and person_chart_ok(r["canonical_entity"])
        ]
        countries = [r for r in cleaned if r["normalized_category"] == "country" and int(r["n_posts"]) >= COUNTRY_MIN_POSTS]
        people = sorted(people, key=lambda r: -int(r["n_posts"]))[:TOP_N]
        countries = sorted(countries, key=lambda r: -int(r["n_posts"]))[:TOP_N]
        plot_stacked(
            people,
            f"Top {len(people)} people — unique-post sentiment (min {PERSON_MIN_POSTS} posts)\nGreen = positive, yellow = neutral, red = negative",
            PERSON_PNG,
            "Unique posts (unweighted analysis-file mix)",
        )
        plot_stacked(
            countries,
            f"Top {len(countries)} countries — unique-post sentiment (min {COUNTRY_MIN_POSTS} posts)\nCanonical names; green / yellow / red",
            COUNTRY_PNG,
            "Unique posts (unweighted analysis-file mix)",
        )
        issues = validate(wr, cleaned)
        checklist = {
            "src/ner_entity_analysis.py": True,
            "notebooks/ner_entity_analysis.ipynb": (ROOT / "notebooks" / "ner_entity_analysis.ipynb").exists(),
            "outputs/entities_extracted.csv": EXTRACTED_CSV.exists(),
            "outputs/entities_cleaned.csv": CLEANED_CSV.exists(),
            "outputs/entity_sentiment_distribution.csv": SENT_CSV.exists(),
            "outputs/entity_sentiment_by_source.csv": SENT_SRC_CSV.exists(),
            "outputs/entity_alias_mapping.csv": ALIAS_CSV.exists(),
            "outputs/person_entities_sentiment.png": PERSON_PNG.exists(),
            "outputs/country_entities_sentiment.png": COUNTRY_PNG.exists(),
            "NER_ENTITY_ANALYSIS_REPORT.md": True,
        }
        write_report(meta, cleaned, drop_counts, n_raw, n_keep, n_posts, checklist, aliases)
        if issues:
            return 1
    finally:
        wr.close()
    log("NER_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
