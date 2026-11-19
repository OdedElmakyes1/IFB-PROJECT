"""Write CSV-only verification notebooks and execute them in-process.

No database is opened. No sentiment / emotion / BERTopic / NER / network / bot
model is rerun. Images are embedded from shipped PNGs.

Usage (repo root):
    python src/postaudit_write_and_execute_notebooks.py
"""
from __future__ import annotations

import base64
import io
import traceback
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"

BOOTSTRAP = '''from pathlib import Path
import pandas as pd
from IPython.display import Image, display

def find_root() -> Path:
    start = Path.cwd().resolve()
    for p in [start, *start.parents]:
        if (p / "outputs").is_dir() and (p / "src").is_dir():
            return p
    raise FileNotFoundError(
        "Cannot find the project root (need outputs/ and src/). "
        "Open this notebook from the repo, from notebooks/, or from a guideline folder."
    )

ROOT = find_root()
OUT = ROOT / "outputs"
print("ROOT =", ROOT)
print("This notebook reads shipped CSVs and PNGs only.")
print("It does not open IFB.db, does not open any analysis database,")
print("and does not rerun sentiment, emotion, BERTopic, NER, network, or bot models.")
'''


def md(text: str):
    return new_markdown_cell(text)


def code(text: str):
    return new_code_cell(text)


def write_nb(name: str, cells: list) -> Path:
    nb = new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
    )
    path = NB_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)
    return path


def execute_notebook(path: Path) -> None:
    """Execute a notebook without a Jupyter kernel; embed stdout and PNGs."""
    nb = nbformat.read(path, as_version=4)
    ns: dict = {"__name__": "__main__"}
    # Provide a display() that records outputs on the current cell
    current_outputs: list = []

    class _Image:
        def __init__(self, filename=None, **kwargs):
            self.filename = filename

    def _display(obj, **kwargs):
        if isinstance(obj, _Image) or obj.__class__.__name__ == "Image":
            fn = getattr(obj, "filename", None)
            if fn and Path(fn).exists():
                raw = Path(fn).read_bytes()
                current_outputs.append(
                    new_output(
                        "display_data",
                        data={"image/png": base64.b64encode(raw).decode("ascii")},
                        metadata={"image/png": {"width": 900}},
                    )
                )
                print(f"[embedded figure] {Path(fn).name} ({len(raw):,} bytes)")
                return
        if hasattr(obj, "to_string"):
            text = obj.to_string()
            html = obj.to_html() if hasattr(obj, "to_html") else text
            current_outputs.append(
                new_output(
                    "execute_result",
                    data={"text/plain": text, "text/html": html},
                    metadata={},
                    execution_count=1,
                )
            )
            return
        print(obj)

    ns["display"] = _display
    # IPython.display is imported inside cells; patch after first import via sitecustomize-like hook
    import IPython.display as ipd

    ipd.Image = _Image
    ipd.display = _display

    count = 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        count += 1
        current_outputs = []
        buf = io.StringIO()
        err = io.StringIO()
        try:
            from contextlib import redirect_stderr, redirect_stdout

            with redirect_stdout(buf), redirect_stderr(err):
                exec(compile(cell.source, f"{path.name}:{count}", "exec"), ns)
            text = buf.getvalue()
            etext = err.getvalue()
            outs = []
            if text:
                outs.append(new_output("stream", name="stdout", text=text))
            if etext:
                outs.append(new_output("stream", name="stderr", text=etext))
            outs.extend(current_outputs)
            cell.outputs = outs
            cell.execution_count = count
        except Exception:
            tb = traceback.format_exc()
            cell.outputs = [new_output("stream", name="stderr", text=tb)]
            cell.execution_count = count
            nbformat.write(nb, path)
            raise RuntimeError(f"{path.name} cell {count} failed:\n{tb}") from None
    nbformat.write(nb, path)
    print(f"executed {path.name} ({count} code cells)")


def translator():
    return [
        md(
            "# 2.1 Translation audit — English NLP corpus\n\n"
            "Course: Introduction to Social Networks (CS, 2026 Semester B).\n\n"
            "**This notebook does not call a translation API and does not open any database.** "
            "It verifies the shipped translation examples and documents the English-ready inclusion rule.\n\n"
            "- Full decision: `TRANSLATION_DECISION.md`\n"
            "- The 742,942 scored rows live in `data/nlp_analysis_corpus.db` "
            "(`text_translated_en` is a byte-for-byte copy of `original_text`). "
            "That database is **excluded from the submission package**.\n"
            "- Do not open or modify `IFB.db`."
        ),
        code(BOOTSTRAP),
        md(
            "## Decision\n\n"
            "Timeline posts entered the NLP file only when Twitter `LANG = en`. "
            "Keyword tweets have no `LANG` column; they were kept only when a "
            "**rule-based Latin-script / ASCII-ratio classifier** marked them `likely_english` "
            "after IFB tokens were stripped.\n\n"
            "**English-ready is an operational inclusion rule, not proof that every retained "
            "post is native English.** Portuguese, Spanish, Indonesian, and Italian posts "
            "can survive because they are Latin-script. The Portuguese example below is a "
            "real retained post, kept on purpose."
        ),
        code(
            """ex = pd.read_csv(OUT / "translation_examples.csv", encoding="utf-8-sig")
print("rows", len(ex))
print("columns", list(ex.columns))
display(ex)
# The Portuguese row is a real retained post, not a translation error.
pt = ex[ex.apply(lambda r: "dormir" in str(r.get("original_text", "")).lower(), axis=1)]
print("portuguese_rows_in_examples", len(pt))
if len(pt):
    print(pt.iloc[0].get("original_text") or pt.iloc[0].get("original"))
    print("status", pt.iloc[0].get("translation_status") or pt.iloc[0].get("status"))
"""
        ),
        md(
            "## Guideline questions\n\n"
            "1. Bad translations? **No.** No machine translation ran. "
            "`text_translated_en` is a copy of `original_text` for all 742,942 scored posts.\n"
            "2. Hashtags translated correctly? Hashtags are **untouched** in `text_translated_en`.\n"
            "3. Person names preserved? **Yes, verbatim.** NER later runs on `original_text`."
        ),
        code(
            """four = OUT / "keyword_unscored_four_rows.csv"
if four.exists():
    gap = pd.read_csv(four, encoding="utf-8-sig")
    print("keyword retained 244,221 minus scored 244,217 = 4 held-out rows")
    display(gap)
else:
    print("keyword_unscored_four_rows.csv not present; gap is documented in TRANSLATION_DECISION.md")
print("DONE translation verification")
"""
        ),
    ]


def preprocessing():
    return [
        md(
            "# 2.2 Text preprocessing\n\n"
            "Guideline notebook `text_preprocessing.ipynb`.\n\n"
            "This notebook **does not rerun** the cleaner. It loads "
            "`outputs/preprocessing_examples.csv` (36 stored before/after rows).\n\n"
            "Two saved columns exist in SQLite `nlp_posts` (database excluded from submission):\n"
            "- `clean_text` — lowercase; strip URLs, @mentions, emojis, punctuation; drop stopwords; Porter stem. "
            "**Keeps** IFB / follow tokens for sentiment.\n"
            "- `topic_text` — same cleaning, then **removes** IFB / follow / followback / f4f so BERTopic cannot collapse."
        ),
        code(BOOTSTRAP),
        code(
            """ex = pd.read_csv(OUT / "preprocessing_examples.csv", encoding="utf-8-sig")
print("rows", len(ex))
print("columns", list(ex.columns))
cols = [c for c in ["original_text", "clean_text", "topic_text"] if c in ex.columns]
display(ex[cols].head(12))
# IFB tokens should remain in clean_text examples that contained them, and be gone from topic_text.
ifb = ex[ex.apply(lambda r: "follow" in str(r.get("original_text", "")).lower(), axis=1)].head(5)
print("examples_containing_follow", len(ifb))
display(ifb[cols] if len(ifb) else ex[cols].head(3))
print("DONE preprocessing verification")
"""
        ),
    ]


def sentiment():
    return [
        md(
            "# 2.3 Sentiment analysis\n\n"
            "pysentimiento / `finiteautomata/bertweet-base-sentiment-analysis` on `clean_text`.\n"
            "**742,942** scored posts, **35,250** users. Neutral is required. "
            "No combined “average sentiment” curve.\n\n"
            "This notebook reads shipped CSVs and PNGs only. "
            "The 314 MB `outputs/Posts_sentiment.csv` is intentionally **not** loaded here. "
            "Scoring is **not** rerun. `IFB.db` is not opened."
        ),
        code(BOOTSTRAP),
        code(
            """dist = pd.read_csv(OUT / "sentiment_distribution.csv", encoding="utf-8-sig")
print("sentiment_distribution rows", len(dist))
display(dist)
users = pd.read_csv(OUT / "user_sentiment_summary.csv", encoding="utf-8-sig")
print("scored users", len(users))
assert len(users) == 35250
display(users.sort_values("n_posts", ascending=False).head(8))
display(Image(filename=str(OUT / "sentiment_distribution.png")))
display(Image(filename=str(OUT / "sentiment_over_time_monthly.png")))
print("DONE sentiment verification")
"""
        ),
    ]


def emotion():
    return [
        md(
            "# 2.4 Emotion analysis\n\n"
            "pysentimiento / `finiteautomata/bertweet-base-emotion-analysis`. "
            "Seven labels including **others**. Same 742,942 posts / 35,250 users.\n\n"
            "This notebook reads shipped CSVs and PNGs only. "
            "The 423 MB `outputs/Posts_emotions.csv` is **not** loaded. Scoring is **not** rerun."
        ),
        code(BOOTSTRAP),
        code(
            """dist = pd.read_csv(OUT / "emotion_distribution.csv", encoding="utf-8-sig")
display(dist)
cross = pd.read_csv(OUT / "emotion_sentiment_crosstab.csv", encoding="utf-8-sig")
print("crosstab rows", len(cross))
display(cross.head(14))
display(Image(filename=str(OUT / "emotion_plots" / "emotion_distribution.png")))
display(Image(filename=str(OUT / "emotion_plots" / "emotion_sentiment_crosstab.png")))
print("DONE emotion verification")
"""
        ),
    ]


def events():
    return [
        md(
            "# 2.5 Event detection\n\n"
            "Four tweet-supported emotion peaks. **31** evidence tweets. "
            "E03 has **exactly 5** evidence tweets; the keyword tweet is contextual "
            "and was **not** used in the timeline z-score.\n\n"
            "No causation is claimed. This notebook does not rerun event detection."
        ),
        code(BOOTSTRAP),
        code(
            """events = pd.read_csv(OUT / "detected_events.csv", encoding="utf-8-sig")
evid = pd.read_csv(OUT / "event_tweet_evidence.csv", encoding="utf-8-sig")
print("events", len(events), "evidence tweets", len(evid))
assert len(events) == 4
assert len(evid) == 31
display(events)
print(evid.groupby("event_id").size())
e03 = evid[evid["event_id"].astype(str).str.upper() == "E03"]
print("E03 evidence", len(e03))
display(e03[["event_id", "source"] + [c for c in e03.columns if "note" in c.lower() or c == "original_text"][:3]])
display(Image(filename=str(OUT / "event_plots" / "emotion_over_time_monthly.png")))
print("DONE event verification")
"""
        ),
    ]


def topics():
    return [
        md(
            "# 3. BERTopic\n\n"
            "Reads `topic_text` (IFB / follow already stripped). "
            "**nr_topics = 24** is the configured BERTopic parameter, not the result.\n\n"
            "- Configured topic count: **24** (C13 `nr_topics`)\n"
            "- Six follow-spam clusters `{3, 5, 18, 20, 22, 23}` were merged into **−1**\n"
            "- **Final named topics: 18** plus one outlier bucket (−1) = 19 rows in `final_topics.csv`\n"
            "- Original HDBSCAN outliers and the six merged spam clusters share the −1 bucket\n\n"
            "`outputs/topic_model.pkl` (480 MB) is **excluded from the submission package**. "
            "BERTopic is **not** refit here."
        ),
        code(BOOTSTRAP),
        code(
            """exp = pd.read_csv(OUT / "bertopic_experiments.csv", encoding="utf-8-sig")
topics = pd.read_csv(OUT / "final_topics.csv", encoding="utf-8-sig")
print("configurations", len(exp))
assert len(exp) == 15
display(exp)
named = topics[topics["topic_id"].astype(float) >= 0]
print("final_topics rows", len(topics), "named", len(named), "outlier_rows", len(topics) - len(named))
assert len(named) == 18
assert len(topics) == 19
display(topics[["topic_id", "topic_name", "topic_size", "percentage"] +
               [c for c in ["topic_words"] if c in topics.columns]])
if "ifb_topword_hits" in exp.columns:
    print("ifb_topword_hits sum", exp["ifb_topword_hits"].astype(float).sum())
display(Image(filename=str(OUT / "coherence_plot.png")))
display(Image(filename=str(OUT / "topic_over_time_monthly.png")))
print("DONE topic verification")
"""
        ),
    ]


def topic_sentiment():
    return [
        md(
            "# 3.2 Topic sentiment\n\n"
            "Guideline notebook `topic_sentiment_analysis.ipynb`.\n\n"
            "Join of topic assignments with 3-class sentiment. "
            "Positive + neutral + negative sum to 742,942. Neutral is required. "
            "The ring figure is green / yellow / red. BERTopic is **not** refit."
        ),
        code(BOOTSTRAP),
        code(
            """dist = pd.read_csv(OUT / "topic_sentiment_distribution.csv", encoding="utf-8-sig")
print("rows", len(dist))
for col in ("positive", "neutral", "negative"):
    dist[col] = pd.to_numeric(dist[col], errors="coerce")
total = int(dist[["positive", "neutral", "negative"]].sum().sum())
print("class sum", total)
assert total == 742942
display(dist)
display(Image(filename=str(OUT / "topic_sentiment_visualization.png")))
print("DONE topic-sentiment verification")
"""
        ),
    ]


def ner():
    return [
        md(
            "# 4. NER and entity sentiment\n\n"
            "spaCy `en_core_web_lg` was already run on `original_text`. "
            "This notebook does **not** rerun NER.\n\n"
            "Guideline rule: entities shorter than **3 characters** are excluded from the "
            "graded cleaned table. `CW` and `VN` are therefore gone from the cleaned outputs. "
            "`entities_extracted.csv` (193 MB) remains the unfiltered extraction record and "
            "is excluded from the submission package."
        ),
        code(BOOTSTRAP),
        code(
            """cleaned = pd.read_csv(OUT / "entities_cleaned.csv", encoding="utf-8-sig")
name_col = "canonical_entity" if "canonical_entity" in cleaned.columns else "entity"
short = cleaned[cleaned[name_col].astype(str).str.len() < 3]
print("entities_cleaned", len(cleaned), "short_rows", len(short))
assert len(short) == 0
dropped = OUT / "entities_dropped_short.csv"
if dropped.exists():
    d = pd.read_csv(dropped, encoding="utf-8-sig")
    print("dropped_short_rows", len(d))
amp = cleaned[cleaned[name_col].astype(str).str.strip() == "&"]
print("ampersand_rows", len(amp))
assert len(amp) == 0
display(cleaned.head(8))
display(Image(filename=str(OUT / "person_entities_sentiment.png")))
display(Image(filename=str(OUT / "country_entities_sentiment.png")))
print("DONE NER verification")
"""
        ),
    ]


def network():
    return [
        md(
            "# 4.2 Entity co-occurrence network\n\n"
            "**Not a follower / user-user graph.** `IFB.db` has no follow, reply, or retweet-cascade edges.\n\n"
            "Canonical key (one definition, used everywhere):\n"
            "- **Node** = canonical entity name (category is a node attribute)\n"
            "- **Edge** = unordered pair of two *different* names\n"
            "- **edge_weight** = distinct posts containing both names (min 5)\n\n"
            "Entities shorter than 3 characters are excluded. "
            "One row of `entity_network_edges.csv` = one graph edge. "
            "Combined graph: **1,076 nodes / 2,578 edges**. NER is **not** rerun."
        ),
        code(BOOTSTRAP),
        code(
            """edges = pd.read_csv(OUT / "entity_network_edges.csv", encoding="utf-8-sig")
nodes = pd.read_csv(OUT / "entity_network_nodes.csv", encoding="utf-8-sig")
summary = pd.read_csv(OUT / "entity_network_summary.csv", encoding="utf-8-sig")
metrics = pd.read_csv(OUT / "entity_network_metrics.csv", encoding="utf-8-sig")
display(summary)
print("edge rows", len(edges), "node rows", len(nodes))
comb = summary[summary["graph"] == "combined_min_edge"].iloc[0]
assert int(float(comb["n_edges"])) == len(edges)
assert int(float(comb["n_nodes"])) == len(nodes)
assert int((edges["entity_a"] == edges["entity_b"]).sum()) == 0
keys = [tuple(sorted([a, b])) for a, b in zip(edges["entity_a"], edges["entity_b"])]
assert len(keys) == len(set(keys))
assert ((edges["entity_a"].str.len() >= 3) & (edges["entity_b"].str.len() >= 3)).all()
assert not set(nodes["entity"]).intersection({"CW", "VN", "&"})
deg_sum = pd.to_numeric(metrics["degree"], errors="coerce").sum()
print("sum(degree)/2", deg_sum / 2)
assert int(deg_sum / 2) == len(edges)
display(edges.head(8))
display(Image(filename=str(OUT / "entity_network_graph.png")))
print("DONE network verification")
"""
        ),
    ]


def bots():
    return [
        md(
            "# 5. Behavioral risk classification — not verified bot identity\n\n"
            "100 manual reviews, seed 2026, **stratified on the rule engine’s own bands** "
            "(35 low / 30 medium / 35 high) — **not** a simple random sample.\n\n"
            "The high-risk band has only 99 users in the whole population, so drawing 35 of them "
            "enriches that band by ~136×. Precision / recall on these 98 usable labels are "
            "**sample diagnostics, not population estimates**.\n\n"
            "ML uses **98** usable labels (2 `insufficient_evidence` excluded). "
            "K=5 mean train size **78**; LOOCV train size **97**.\n\n"
            "The required **200-user validation set is missing and was not fabricated**."
        ),
        code(BOOTSTRAP),
        code(
            """lab = pd.read_csv(OUT / "labeled_bots_and_not_bots.csv", encoding="utf-8-sig")
exp = pd.read_csv(OUT / "bot_detection_experiments.csv", encoding="utf-8-sig")
print("manual reviews", len(lab))
assert len(lab) == 100
print(lab["manual_label"].value_counts(dropna=False).to_string())
print("is_bot value counts")
print(lab["is_bot"].value_counts(dropna=False).to_string())
usable = lab[lab["manual_label"] != "insufficient_evidence"]
print("usable ML labels", len(usable))
assert len(usable) == 98
k5 = exp[exp["training_type"].astype(str).str.contains("kfold_k5_mean", na=False)]
loo = exp[exp["training_type"].astype(str).str.contains("loocv", na=False)]
if len(k5):
    print("K=5 mean n_train", k5["n_train"].astype(float).mean())
if len(loo):
    print("LOOCV n_train", loo["n_train"].astype(float).iloc[0])
display(exp[["algorithm", "training_type", "n_train", "precision", "recall", "F1"]].head(16)
        if set(["algorithm", "training_type"]).issubset(exp.columns) else exp.head(16))
display(Image(filename=str(OUT / "malicious_detection_flow.png")))
display(Image(filename=str(OUT / "bot_model_comparison.png")))
print("DONE bot verification")
"""
        ),
    ]


NOTEBOOKS = {
    "translator.ipynb": translator,
    "text_preprocessing.ipynb": preprocessing,
    "sentiment_analysis.ipynb": sentiment,
    "emotion_analysis.ipynb": emotion,
    "event_detection.ipynb": events,
    "topic_modeling.ipynb": topics,
    "topic_sentiment_analysis.ipynb": topic_sentiment,
    "ner_entity_analysis.ipynb": ner,
    "entity_network_analysis.ipynb": network,
    "bot_detection.ipynb": bots,
}


def main() -> int:
    written = []
    for name, factory in NOTEBOOKS.items():
        path = write_nb(name, factory())
        execute_notebook(path)
        written.append(name)
    print("wrote+executed", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
