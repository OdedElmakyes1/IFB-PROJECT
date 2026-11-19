"""Copy graded deliverables into the official guideline folder tree.

Does not copy databases or outputs/topic_model.pkl.
Does not duplicate giant CSVs (Posts_sentiment, Posts_emotions, entities_*).
Does not modify IFB.db.

Usage (repo root):
    python src/postaudit_populate_guideline_folders.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# Files larger than this are pointed at, not copied.
MAX_COPY_BYTES = 25 * 1024 * 1024  # keep guideline CSVs; exclude 67 MB+ dumps


def copy_file(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return f"MISSING {src}"
    if src.stat().st_size > MAX_COPY_BYTES:
        return f"SKIP_LARGE {src.name} ({src.stat().st_size / 1_048_576:.1f} MB)"
    shutil.copy2(src, dest)
    return f"copied {src.name} -> {dest.relative_to(ROOT)}"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


EXCLUDED = """# Excluded from this folder (on purpose)

These files exist in the project but are **not** duplicated here:

| File | Why excluded | Where it lives |
|------|----------------|----------------|
| `IFB.db` (11.89 GB) | Source database, read-only input | project root |
| `data/analysis_corpus.db` (12.37 GB) | Frozen corpus | `data/` |
| `data/nlp_analysis_corpus.db` (1.30 GB) | NLP tables (`clean_text`, `topic_text`, `text_translated_en`, scores) | `data/` |
| `outputs/topic_model.pkl` (480 MB) | Final BERTopic model; reproducible with seed 2026 | `outputs/` |
| `outputs/Posts_sentiment.csv` (314 MB) | 742,942-row dump | `outputs/` |
| `outputs/Posts_emotions.csv` (423 MB) | 742,942-row dump | `outputs/` |
| `outputs/entities_extracted.csv` (193 MB) | Raw NER mentions | `outputs/` |
| `outputs/entities_cleaned.csv` (67 MB) | Cleaned entity table (len≥3) | `outputs/` |

The graded notebooks in this tree verify the shipped **small** CSVs and PNGs.
They do not require the excluded files to open and show results.
"""


def main() -> int:
    logs: list[str] = []

    # --- English_Translation ---
    d = ROOT / "English_Translation"
    logs.append(copy_file(ROOT / "notebooks" / "translator.ipynb", d / "translator.ipynb"))
    logs.append(copy_file(OUT / "translation_examples.csv", d / "translation_examples.csv"))
    logs.append(copy_file(ROOT / "TRANSLATION_DECISION.md", d / "TRANSLATION_DECISION.md"))
    write(
        d / "README.md",
        "# English_Translation\n\n"
        "Required guideline files in this folder:\n\n"
        "- `translator.ipynb` — executed verification notebook (CSV-only)\n"
        "- `translation_examples.csv` — 12 original / text_translated_en pairs\n\n"
        "`translated_en_posts.csv` was **not** dumped as a 742,942-row spreadsheet. "
        "The column `text_translated_en` lives in `data/nlp_analysis_corpus.db` table `nlp_posts` "
        "and is a byte-for-byte copy of `original_text` for every scored post. "
        "That database is excluded from the upload (1.30 GB).\n\n"
        + EXCLUDED,
    )

    # --- Data_Preprocessing ---
    d = ROOT / "Data_Preprocessing"
    logs.append(copy_file(ROOT / "notebooks" / "text_preprocessing.ipynb", d / "text_preprocessing.ipynb"))
    logs.append(copy_file(OUT / "preprocessing_examples.csv", d / "preprocessing_examples.csv"))
    logs.append(copy_file(ROOT / "LANGUAGE_AND_PREPROCESSING_REPORT.md", d / "LANGUAGE_AND_PREPROCESSING_REPORT.md"))
    write(
        d / "README.md",
        "# Data_Preprocessing\n\n"
        "Required guideline files in this folder:\n\n"
        "- `text_preprocessing.ipynb` — executed before/after notebook\n"
        "- `preprocessing_examples.csv` — 36 stored examples\n\n"
        "`posts_cleaned.csv` was **not** dumped as a 742k-row spreadsheet. "
        "`clean_text` and `topic_text` are columns in `nlp_posts` "
        "(`data/nlp_analysis_corpus.db`, excluded). "
        "`topic_text` is the BERTopic input: IFB / follow / followback / f4f are stripped there "
        "and kept in `clean_text` for sentiment.\n\n"
        + EXCLUDED,
    )

    # --- Posts_Analysis (missing folder from the PDF tree) ---
    d = ROOT / "Posts_Analysis"
    logs.append(copy_file(ROOT / "notebooks" / "sentiment_analysis.ipynb", d / "sentiment_analysis.ipynb"))
    logs.append(copy_file(ROOT / "notebooks" / "emotion_analysis.ipynb", d / "emotion_analysis.ipynb"))
    logs.append(copy_file(ROOT / "notebooks" / "event_detection.ipynb", d / "events_analysis.ipynb"))
    logs.append(copy_file(ROOT / "detected_events.docx", d / "detected_events.docx"))
    write(
        d / "README.md",
        "# Posts_Analysis\n\n"
        "Guideline folder for the scored-post stage. Real files here:\n\n"
        "- `sentiment_analysis.ipynb`\n"
        "- `emotion_analysis.ipynb`\n"
        "- `events_analysis.ipynb` (guideline name; source is `notebooks/event_detection.ipynb`)\n"
        "- `detected_events.docx`\n\n"
        "`posts.csv` is **not** a 38,969,023-row dump. Posts live in SQLite:\n"
        "- full freeze: `data/analysis_corpus.db` table `posts`\n"
        "- English-ready scored file: `data/nlp_analysis_corpus.db` view/tables `nlp_posts` / `post_sentiment` / `post_emotion`\n\n"
        "The matching stage folders `Sentiment_Analysis/`, `Emotion_Analysis/`, and "
        "`Event_Detection/` hold the same notebooks plus the small figures.\n\n"
        "Giant per-post CSVs stay in `outputs/` and are not copied here:\n"
        "- `outputs/Posts_sentiment.csv` (314 MB, 742,942 rows)\n"
        "- `outputs/Posts_emotions.csv` (423 MB, 742,942 rows)\n\n"
        + EXCLUDED,
    )

    # --- Sentiment_Analysis ---
    d = ROOT / "Sentiment_Analysis"
    logs.append(copy_file(ROOT / "notebooks" / "sentiment_analysis.ipynb", d / "sentiment_analysis.ipynb"))
    logs.append(copy_file(OUT / "sentiment_distribution.csv", d / "sentiment_distribution.csv"))
    logs.append(copy_file(OUT / "sentiment_distribution.png", d / "sentiment_distribution.png"))
    logs.append(copy_file(OUT / "sentiment_over_time_monthly.png", d / "sentiment_over_time_monthly.png"))
    logs.append(copy_file(ROOT / "SENTIMENT_ANALYSIS_REPORT.md", d / "SENTIMENT_ANALYSIS_REPORT.md"))
    write(
        d / "README.md",
        "# Sentiment_Analysis\n\n"
        "- `sentiment_analysis.ipynb` (executed)\n"
        "- `sentiment_distribution.csv` / `.png`\n"
        "- `sentiment_over_time_monthly.png` — three separate panels, no combined curve\n\n"
        "`Posts_sentiment.csv` (314 MB, 742,942 rows) stays in `outputs/` and is not duplicated here.\n\n"
        + EXCLUDED,
    )

    # --- Emotion_Analysis ---
    d = ROOT / "Emotion_Analysis"
    logs.append(copy_file(ROOT / "notebooks" / "emotion_analysis.ipynb", d / "emotion_analysis.ipynb"))
    logs.append(copy_file(OUT / "emotion_distribution.csv", d / "emotion_distribution.csv"))
    emo_png = OUT / "emotion_plots" / "emotion_distribution.png"
    logs.append(copy_file(emo_png, d / "emotion_distribution.png"))
    logs.append(copy_file(OUT / "emotion_plots" / "emotion_sentiment_crosstab.png", d / "emotion_sentiment_crosstab.png"))
    logs.append(copy_file(ROOT / "EMOTION_ANALYSIS_REPORT.md", d / "EMOTION_ANALYSIS_REPORT.md"))
    write(
        d / "README.md",
        "# Emotion_Analysis\n\n"
        "- `emotion_analysis.ipynb` (executed)\n"
        "- distribution + crosstab figures\n\n"
        "All six time resolutions with dashed event lines live in `outputs/event_plots/` "
        "and `outputs/emotion_plots/`. `Posts_emotions.csv` (423 MB) stays in `outputs/`.\n\n"
        + EXCLUDED,
    )

    # --- Event_Detection ---
    d = ROOT / "Event_Detection"
    logs.append(copy_file(ROOT / "notebooks" / "event_detection.ipynb", d / "events_analysis.ipynb"))
    logs.append(copy_file(ROOT / "detected_events.docx", d / "detected_events.docx"))
    logs.append(copy_file(OUT / "detected_events.csv", d / "detected_events.csv"))
    logs.append(copy_file(OUT / "event_tweet_evidence.csv", d / "event_tweet_evidence.csv"))
    logs.append(copy_file(OUT / "event_plots" / "emotion_over_time_monthly.png", d / "emotion_over_time_monthly.png"))
    logs.append(copy_file(ROOT / "EVENT_DETECTION_REPORT.md", d / "EVENT_DETECTION_REPORT.md"))
    write(
        d / "README.md",
        "# Event_Detection\n\n"
        "- `events_analysis.ipynb` (guideline name)\n"
        "- `detected_events.docx` — 4 events, 31 evidence tweets, E03 = 5 tweets\n"
        "- `detected_events.csv`, `event_tweet_evidence.csv`\n\n"
        "Dashed labeled event lines: `outputs/event_plots/`.\n\n"
        + EXCLUDED,
    )

    # --- Topic_Modeling ---
    d = ROOT / "Topic_Modeling"
    logs.append(copy_file(ROOT / "notebooks" / "topic_modeling.ipynb", d / "topic_modeling.ipynb"))
    logs.append(copy_file(OUT / "final_topics.csv", d / "final_topics.csv"))
    logs.append(copy_file(OUT / "bertopic_experiments.csv", d / "bertopic_experiments.csv"))
    logs.append(copy_file(OUT / "coherence_scores.csv", d / "coherence_scores.csv"))
    logs.append(copy_file(OUT / "coherence_plot.png", d / "coherence_plot.png"))
    logs.append(copy_file(OUT / "topic_over_time_monthly.png", d / "topic_over_time_monthly.png"))
    logs.append(copy_file(ROOT / "TOPIC_MODELING_REPORT.md", d / "TOPIC_MODELING_REPORT.md"))
    write(
        d / "README.md",
        "# Topic_Modeling\n\n"
        "- `topic_modeling.ipynb` (executed)\n"
        "- `final_topics.csv` — **18 named topics + −1** (19 rows)\n"
        "- `bertopic_experiments.csv` — all 15 configurations\n"
        "- `coherence_plot.png`\n\n"
        "`nr_topics = 24` is the C13 **parameter**. Six follow-spam clusters "
        "(3, 5, 18, 20, 22, 23) were merged into −1. The reported topic count is **18 named topics**.\n\n"
        "`outputs/topic_model.pkl` (480 MB) is excluded from this folder and from the upload. "
        "It can be rebuilt with seed 2026; BERTopic is not refit for submission.\n\n"
        + EXCLUDED,
    )

    # --- Topic_Sentiment ---
    d = ROOT / "Topic_Sentiment"
    logs.append(copy_file(ROOT / "notebooks" / "topic_sentiment_analysis.ipynb", d / "topic_sentiment_analysis.ipynb"))
    logs.append(copy_file(OUT / "topic_sentiment_distribution.csv", d / "topic_sentiment_distribution.csv"))
    logs.append(copy_file(OUT / "topic_sentiment_visualization.png", d / "topic_sentiment_visualization.png"))
    write(
        d / "README.md",
        "# Topic_Sentiment\n\n"
        "- `topic_sentiment_analysis.ipynb` (executed)\n"
        "- `topic_sentiment_distribution.csv` — 19 rows; class columns sum to 742,942\n"
        "- `topic_sentiment_visualization.png` — word cloud + green/yellow/red ring\n\n"
        + EXCLUDED,
    )

    # --- NER_Analysis ---
    d = ROOT / "NER_Analysis"
    logs.append(copy_file(ROOT / "notebooks" / "ner_entity_analysis.ipynb", d / "entity_extraction.ipynb"))
    logs.append(copy_file(OUT / "person_entities_sentiment.png", d / "person_entities_sentiment.png"))
    logs.append(copy_file(OUT / "country_entities_sentiment.png", d / "country_entities_sentiment.png"))
    logs.append(copy_file(OUT / "entities_dropped_short.csv", d / "entities_dropped_short.csv"))
    logs.append(copy_file(ROOT / "NER_ENTITY_ANALYSIS_REPORT.md", d / "NER_ENTITY_ANALYSIS_REPORT.md"))
    write(
        d / "README.md",
        "# NER_Analysis\n\n"
        "- `entity_extraction.ipynb` (guideline name; source `notebooks/ner_entity_analysis.ipynb`)\n"
        "- `person_entities_sentiment.png`, `country_entities_sentiment.png`\n"
        "- `entities_dropped_short.csv` — 1,352 rows removed by the len<3 rule (`CW`, `VN`, `EU`, …)\n\n"
        "`entities_extracted.csv` (193 MB) and `entities_cleaned.csv` (67 MB) stay in `outputs/` "
        "and are not duplicated here. The cleaned table has **zero** entities shorter than 3 characters "
        "and **zero** `&` entities. NER was not rerun for this packaging pass.\n\n"
        + EXCLUDED,
    )

    # --- Entity_Network_Analysis ---
    d = ROOT / "Entity_Network_Analysis"
    logs.append(copy_file(ROOT / "notebooks" / "entity_network_analysis.ipynb", d / "entity_network_analysis.ipynb"))
    logs.append(copy_file(OUT / "entity_network_edges.csv", d / "entity_network_edges.csv"))
    logs.append(copy_file(OUT / "entity_network_metrics.csv", d / "entity_network_metrics.csv"))
    logs.append(copy_file(OUT / "entity_network_summary.csv", d / "entity_network_summary.csv"))
    logs.append(copy_file(OUT / "entity_network_graph.png", d / "entity_network_graph.png"))
    logs.append(copy_file(OUT / "entity_pairs.csv", d / "entity_pairs.csv"))
    logs.append(copy_file(ROOT / "ENTITY_NETWORK_REPORT.md", d / "ENTITY_NETWORK_REPORT.md"))
    write(
        d / "README.md",
        "# Entity_Network_Analysis\n\n"
        "This is an **entity co-occurrence** network, not a follower or social graph.\n\n"
        "Canonical key:\n"
        "- node = canonical entity name (category is an attribute)\n"
        "- edge = unordered pair of two different names\n"
        "- one row of `entity_network_edges.csv` = one graph edge\n\n"
        "Combined graph after the len≥3 filter: **1,076 nodes / 2,578 edges**. "
        "No self-loops, no duplicate undirected edges, no `CW` / `VN` / `&`.\n\n"
        "The earlier 1,126 / 2,665 (and 2,694 category-typed rows) disagreement is resolved: "
        "those files mixed `(entity, category)` identity with a name-only graph. "
        "Both files are now generated from the single definition above.\n\n"
        + EXCLUDED,
    )

    # --- Bot_Detection ---
    d = ROOT / "Bot_Detection"
    logs.append(copy_file(ROOT / "notebooks" / "bot_detection.ipynb", d / "bot_detection.ipynb"))
    logs.append(copy_file(ROOT / "malicious_detection_flow.pptx", d / "malicious_detection_flow.pptx"))
    logs.append(copy_file(OUT / "malicious_detection_flow.png", d / "malicious_detection_flow.png"))
    logs.append(copy_file(OUT / "labeled_bots_and_not_bots.csv", d / "labeled_bots_and_not_bots.csv"))
    logs.append(copy_file(OUT / "bot_detection_experiments.csv", d / "bot_detection_experiments.csv"))
    logs.append(copy_file(OUT / "bot_detection_predictions.csv", d / "bot_detection_predictions.csv"))
    logs.append(copy_file(OUT / "unlabeled_dataset_results.csv", d / "unlabeled_dataset_results.csv"))
    logs.append(copy_file(OUT / "unlabled_dataset.csv", d / "unlabled_dataset.csv"))
    logs.append(copy_file(ROOT / "BOT_DETECTION_REPORT.md", d / "BOT_DETECTION_REPORT.md"))
    write(
        d / "README.md",
        "# Bot_Detection\n\n"
        "Behavioral risk classification — **not verified bot identity**.\n\n"
        "- `bot_detection.ipynb` (executed)\n"
        "- `malicious_detection_flow.pptx` / `.png` — real flowchart with Yes/No arrows\n"
        "- `labeled_bots_and_not_bots.csv` — 100 reviews, 98 usable ML labels\n"
        "- `bot_detection_experiments.csv` — 5 algorithms × K=5 + LOOCV; train sizes 78 / 97\n"
        "- `bot_detection_predictions.csv` — 39,556 rows = 38,576 population + 980 CV rows\n"
        "- `unlabeled_dataset_results.csv`, `unlabled_dataset.csv` (guideline spelling) — 38,576 each\n\n"
        "The 100 users were **stratified on the rule bands**, not sampled at random. "
        "High-risk (99 users) was enriched ~136×, so precision 1.00 is a sample diagnostic, "
        "not a population rate. The 200-user validation set is **missing and was not fabricated**.\n\n"
        + EXCLUDED,
    )

    # scratch for Colab leftover
    scratch = ROOT / "scratch"
    scratch.mkdir(exist_ok=True)
    untitled = ROOT / "Untitled0.ipynb"
    if untitled.exists():
        dest = scratch / "Untitled0.ipynb"
        if not dest.exists():
            shutil.copy2(untitled, dest)
        untitled.unlink()
        logs.append("moved Untitled0.ipynb -> scratch/Untitled0.ipynb")
        write(
            scratch / "README.md",
            "# scratch\n\n"
            "`Untitled0.ipynb` is leftover Colab code hard-coded to "
            "`/content/drive/MyDrive/IFB/IFB.db`. It is **not** part of the submission. "
            "Do not run it. It is the only notebook that ever opened `IFB.db` with write capability.\n",
        )

    write(ROOT / "SUBMISSION_EXCLUSIONS.md", EXCLUDED)
    print("\n".join(logs))
    print("guideline folders populated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
