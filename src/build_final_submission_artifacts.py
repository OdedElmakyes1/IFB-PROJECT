"""Build the final Word report and 15-minute slides from existing artifacts.

Does not modify IFB.db. Does not rescore any analysis. Does not invent labels.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as PptRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches as PInches, Pt as PPt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
REPORT = ROOT / "report" / "final_project_report.docx"
PPTX = ROOT / "presentation" / "final_project_presentation.pptx"

NAVY = RGBColor(0x1B, 0x3A, 0x4B)
POS = RGBColor(0x2E, 0x7D, 0x32)
NEU = RGBColor(0xF9, 0xA8, 0x25)
NEG = RGBColor(0xC6, 0x28, 0x28)
P_NAVY = PptRGB(0x1B, 0x3A, 0x4B)
P_TEAL = PptRGB(0x24, 0x5C, 0x6B)
P_POS = PptRGB(0x2E, 0x7D, 0x32)
P_NEU = PptRGB(0xF9, 0xA8, 0x25)
P_NEG = PptRGB(0xC6, 0x28, 0x28)
P_WHITE = PptRGB(0xFF, 0xFF, 0xFF)
P_INK = PptRGB(0x21, 0x2B, 0x33)
P_MUTED = PptRGB(0x5C, 0x6B, 0x73)
P_CREAM = PptRGB(0xF7, 0xF4, 0xEE)


def must(rel: str) -> Path:
    p = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def load_csv(rel: str) -> list[dict[str, str]]:
    with must(rel).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def set_run(run, *, size=11, bold=False, color=None, name="Calibri"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade(cell, hex_color: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_border(cell) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "C5CDD2")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def prevent_row_split(row) -> None:
    tr = row._tr
    trPr = tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    trPr.append(cant)


def add_page_number(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Introduction to Social Networks — IFB project — page ")
    set_run(run, size=9, color=RGBColor(0x5C, 0x6B, 0x73))
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    r2 = p.add_run()
    r2._r.append(fld1)
    r2._r.append(instr)
    r2._r.append(fld2)
    set_run(r2, size=9, color=RGBColor(0x5C, 0x6B, 0x73))


def para(doc, text, *, size=11, bold=False, space_after=8, space_before=0, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    run = p.add_run(text)
    set_run(run, size=size, bold=bold, color=color or NAVY if bold else None)
    return p


def heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
        run.font.name = "Calibri"
    return h


def caption(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(text)
    set_run(run, size=9, color=RGBColor(0x5C, 0x6B, 0x73))
    return p


def add_figure(doc, rel: str, width_cm: float = 16.4):
    path = must(rel)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    p.paragraph_format.keep_with_next = True
    return p


def add_table(doc, headers: list[str], rows: list[list[str]], col_cm: list[float] | None = None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        set_run(run, size=9, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(cell, "1B3A4B")
        set_cell_border(cell)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(val))
            set_run(run, size=9, color=RGBColor(0x21, 0x2B, 0x33))
            if r_i % 2 == 1:
                shade(cell, "F4F7F8")
            set_cell_border(cell)
        prevent_row_split(table.rows[r_i + 1])
    if col_cm:
        for row in table.rows:
            for i, w in enumerate(col_cm):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table


def export_primary_ids() -> int:
    con = sqlite3.connect(f"file:{ROOT / 'data' / 'analysis_corpus.db'}?mode=ro", uri=True)
    ids = [str(r[0]) for r in con.execute("SELECT author_id FROM users ORDER BY author_id")]
    con.close()
    dest = ROOT / "data" / "primary_author_ids.txt"
    dest.write_text("\n".join(ids) + "\n", encoding="utf-8")
    if len(ids) != 38576:
        raise RuntimeError(f"expected 38576 IDs, got {len(ids)}")
    return len(ids)


def write_guideline_pointers() -> None:
    """Do not clobber populated guideline folders.

    Stage READMEs are written by ``src/postaudit_populate_guideline_folders.py``.
    This function only creates a folder if it is missing.
    """
    for folder in (
        "English_Translation",
        "Data_Preprocessing",
        "Posts_Analysis",
        "Sentiment_Analysis",
        "Emotion_Analysis",
        "Event_Detection",
        "Topic_Modeling",
        "Topic_Sentiment",
        "NER_Analysis",
        "Entity_Network_Analysis",
        "Bot_Detection",
    ):
        (ROOT / folder).mkdir(exist_ok=True)


def short(text: str, n: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def build_report(evidence: list[dict[str, str]], examples: list[dict[str, str]]) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    section.top_margin = Cm(1.6)
    section.bottom_margin = Cm(1.8)
    add_page_number(section)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0x21, 0x2B, 0x33)

    para(doc, "Introduction to Social Networks — Semester B 2026", size=12, bold=True, space_after=2)
    para(doc, "Final project report: IFB / follow-for-follow discourse", size=20, bold=True, space_after=6)
    para(
        doc,
        "One primary population. English-ready NLP file. No follower graph. "
        "No invented labels, events, or validation users.",
        size=11,
        space_after=10,
    )

    heading(doc, "1. Research question and scope", 1)
    para(
        doc,
        "How do sentiment, emotion, topics, named entities, and behavioral risk "
        "look inside one frozen IFB (I Follow Back) user population on X/Twitter, "
        "and which patterns are supported by the posts themselves rather than by "
        "outside news lists or bot-identity claims?",
    )
    para(
        doc,
        "The collection is a hashtag/keyword IFB crawl, not a point-of-interest "
        "follower crawl. IFB.db stores follower counts, not follow edges, and has "
        "no reply, quote, or native retweet-cascade identifiers. The graded network "
        "in this project is therefore entity co-occurrence: two cleaned entities "
        "are linked when they appear in the same post. Discourse-spread graphs are "
        "out of scope because the identifiers do not exist.",
    )
    para(
        doc,
        "This report embeds the graded figures. It does not ask the reader to open "
        "an outputs folder in order to see the results.",
    )

    heading(doc, "2. Dataset, filters, and sampling", 1)
    para(
        doc,
        "A user enters the study if and only if the AUTHOR_ID appears exactly once "
        "in authors, appears in tweets, and appears in timeline. Ambiguous duplicate "
        "AUTHOR_ID groups (1,203) are dropped. The join key is CAST(AUTHOR_ID AS TEXT). "
        "USERNAME is a display label, not a join key.",
    )
    add_table(
        doc,
        ["Item", "N", "Role"],
        [
            ["Primary users", "38,576", "All later stages"],
            ["Keyword tweets in corpus", "1,129,607", "Full IFB keyword census for these users"],
            ["Timeline tweets in corpus", "37,839,416", "Full timeline history for these users"],
            ["English-ready scored posts", "742,942", "Sentiment, emotion, topics, NER"],
            ["Keyword scored posts", "244,217", "Census of English-ready keyword posts"],
            ["Timeline scored posts", "498,725", "Stratified English sample, seed 2026"],
            ["Users with scored sentiment/emotion", "35,250", "Subset of 38,576 with ≥1 scored post"],
        ],
        [7.2, 3.2, 7.0],
    )
    para(
        doc,
        "Keyword posts that survive language and boilerplate filters are a census "
        "(sample_weight = 1). Timeline posts in the NLP file are a stratified sample "
        "of English timeline history (about 1.7 percent of English timeline volume). "
        "Timeline sample_weight estimates the English timeline population "
        "(about 29.50 million posts). Those weights are never used to train or score "
        "sentiment, emotion, BERTopic, NER, or bot models.",
    )
    para(
        doc,
        "A combined 742,942-row file therefore mixes a census with a sample. "
        "Keyword and timeline series are reported separately whenever a total could "
        "be misread as one population.",
    )
    para(
        doc,
        "Bookkeeping, not a second study: nlp_posts contains 744,221 rows "
        "(244,221 keyword + 500,000 timeline). The keyword 244,221 − 244,217 gap is "
        "exactly four uncertain rows held out of scoring because of replacement or "
        "control characters: 1110608490748207104 (U+FFFD in Frédéric), "
        "1132322951167205376 (U+FFFD in Jörgens), 1325385083428237312 (legacy "
        "Pique\\x92 byte), and 1481686488005763072 (U+FFFD plus U+2063). "
        "They are not missing-text drops and not duplicate keys. "
        "1,279 NLP rows are requires_translation (63) or uncertain (1,216) and were "
        "not scored. nlp_users has 35,256 rows; 35,250 users have at least one scored "
        "post. Every result chapter below uses 742,942 posts and 35,250 users.",
    )

    heading(doc, "3. Pipeline", 1)
    para(
        doc,
        "authors ∩ tweets ∩ timeline (38,576 users) → analysis_corpus.db → "
        "English-ready nlp_analysis_corpus.db → clean_text / topic_text → "
        "pysentimiento sentiment (3 classes) and emotion (7 labels) → event detection "
        "from emotion peaks with tweet evidence → BERTopic on topic_text (C13) → "
        "topic × sentiment rings → spaCy NER and entity sentiment → entity "
        "co-occurrence network → user risk features → 100 manual reviews → "
        "rules + five classifiers on 98 usable labels.",
    )
    para(
        doc,
        "Software: Python 3.11.9; pysentimiento / BERTweet sentiment and emotion; "
        "BERTopic with all-MiniLM-L6-v2; spaCy en_core_web_lg 3.8.0; networkx; "
        "scikit-learn and XGBoost. Random seed 2026 wherever sampling or CV is used. "
        "IFB.db was opened read-only for authors metadata in the bot-feature step only.",
    )

    heading(doc, "4. Translation decision", 1)
    para(
        doc,
        "Translation was skipped for the retained English corpus because there was "
        "nothing to translate in that file. For every post with "
        "translation_status = not_required_english, text_translated_en is a "
        "byte-for-byte copy of original_text. This is an explicit no-op, not a "
        "silent machine translation.",
    )
    para(
        doc,
        "Timeline rows entered the NLP file only when LANG = en. Non-English and "
        "non-linguistic codes (und, qme, qam, zxx, and other languages) never entered "
        "the scored file. Keyword tweets have no LANG column; they were kept only "
        "when a script/Latin-ratio classifier marked them likely_english after IFB "
        "tokens were stripped. About 20,302 script-confirmed non-English keyword "
        "posts, and the non-English timeline, were excluded rather than translated. "
        "That is an English-only analysis decision, not a claim that the raw corpus "
        "is entirely English.",
    )
    para(
        doc,
        "Known limit of that inclusion rule. The keyword branch has no LANG column, "
        "so it is filtered by a rule-based Latin-script / ASCII-ratio classifier, not "
        "by a trained language identifier such as langdetect or fastText. That rule "
        "reliably removes non-Latin scripts (Arabic, Japanese, Korean, Thai, Cyrillic), "
        "but it cannot separate English from other Latin-script languages. Portuguese, "
        "Spanish, Indonesian, and Italian posts therefore survive into the retained "
        "file at a low rate, and the first row of the table below is a real retained "
        "Portuguese post kept exactly as the pipeline kept it. “English-ready” is an "
        "operational inclusion rule — LANG = en for timeline rows, Latin-script "
        "likely_english for keyword rows — and not proof that every retained post is "
        "native English. The residue is one reason the entity and topic chapters are "
        "read as descriptions of this retained file rather than of English X as a whole.",
    )
    if examples:
        readable = []
        for r in examples:
            orig = r.get("original_text") or r.get("original") or ""
            if orig.lower().count("#follow") >= 3:
                continue
            readable.append(r)
        readable = readable[:10] or examples[:10]
        add_table(
            doc,
            ["Original (truncated)", "text_translated_en", "Status"],
            [
                [
                    short(r.get("original_text") or r.get("original") or "", 90),
                    short(r.get("translated_text") or r.get("text_translated_en") or "", 90),
                    r.get("translation_status") or r.get("status") or "not_required_english",
                ]
                for r in readable
            ],
            [6.8, 6.8, 3.8],
        )
        caption(
            doc,
            f"Table. {len(readable)} translation examples from the stored example file "
            "(outputs/translation_examples.csv). Retained rows are copies, not API translations.",
        )
    para(
        doc,
        "The three questions the guidelines ask about translation quality are answered "
        "directly by the no-op design. Are there bad translations? No — no machine "
        "translation ran on the retained corpus, so text_translated_en cannot contain "
        "a translation error; all 742,942 retained values are byte-identical to "
        "original_text. Were hashtags translated correctly? Hashtags are untouched in "
        "text_translated_en; they are only normalised later, inside clean_text and "
        "topic_text, where the # symbol is stripped and the token is kept. Were person "
        "names preserved? Yes, verbatim, which is why spaCy NER in chapter 10 runs on "
        "original_text and not on any translated or stemmed variant.",
    )

    heading(doc, "5. Preprocessing", 1)
    para(
        doc,
        "Two saved text columns exist in nlp_posts. clean_text lowercases the English "
        "text, strips URLs, @mentions, emojis, and punctuation, drops stopwords, and "
        "applies a Porter stemmer. IFB / follow tokens are kept in clean_text because "
        "sentiment and emotion should see the promotional register. topic_text applies "
        "the same cleaning and then removes IFB, follow, followback, f4f, and related "
        "collection tokens so BERTopic cannot collapse into an IFB/follow topic. "
        "Encoding is UTF-8. Empty clean_text (2,948 posts) was scored as a period placeholder.",
    )
    para(
        doc,
        "The standalone guideline files translated_en_posts.csv and posts_cleaned.csv "
        "were not dumped as 742k-row spreadsheets. The columns live in "
        "nlp_analysis_corpus.db. Small example files were written instead.",
    )
    prep = load_csv("outputs/preprocessing_examples.csv")
    if prep:
        prep_rows = []
        for r in prep:
            orig = (r.get("original_text") or "").strip()
            clean = (r.get("clean_text") or "").strip()
            topic = (r.get("topic_text") or "").strip()
            if not orig or not clean:
                continue
            prep_rows.append([short(orig, 80), short(clean, 58), short(topic, 58)])
            if len(prep_rows) == 6:
                break
        add_table(
            doc,
            ["original_text (before)", "clean_text (after)", "topic_text (after, IFB tokens removed)"],
            prep_rows,
            [6.4, 5.4, 5.6],
        )
        caption(
            doc,
            "Table. Preprocessing before and after, from outputs/preprocessing_examples.csv "
            "(36 stored examples). The third column is the BERTopic input: the same cleaning "
            "plus removal of IFB / follow / followback / f4f collection tokens.",
        )

    heading(doc, "6. Sentiment", 1)
    para(
        doc,
        "Model: pysentimiento, finiteautomata/bertweet-base-sentiment-analysis, "
        "three classes (positive / neutral / negative). Input: clean_text. "
        "742,942 posts; 35,250 users. Neutral is a required class. There is no "
        "combined “average sentiment” number.",
    )
    add_table(
        doc,
        ["Class", "Combined file", "Keyword census", "Timeline raw", "Timeline weighted est."],
        [
            ["Positive (green)", "134,936 (18.16%)", "48,894 (20.02%)", "86,042 (17.25%)", "5,089,139 (17.25%)"],
            ["Neutral (yellow)", "526,377 (70.85%)", "184,804 (75.67%)", "341,573 (68.49%)", "20,203,183 (68.49%)"],
            ["Negative (red)", "81,629 (10.99%)", "10,519 (4.31%)", "71,110 (14.26%)", "4,206,029 (14.26%)"],
        ],
        [3.6, 3.4, 3.4, 3.2, 4.0],
    )
    para(
        doc,
        "Raw timeline shares describe the 498,725 scored sample. Weighted shares "
        "estimate the English timeline population of the 38,576 users. Keyword "
        "weights are not applied to timeline rows. The combined pie is an unweighted "
        "mix of two sampling frames and is not “the mood of IFB.”",
    )
    para(
        doc,
        "Per-user sentiment was also aggregated, since a post-level share can hide a "
        "skewed user distribution. outputs/user_sentiment_summary.csv holds one row for "
        "each of the 35,250 scored users with their post count and their positive / "
        "neutral / negative shares. The distribution is neutral-dominated at the user "
        "level too rather than splitting into positive and negative camps: the median "
        "user is majority-neutral, which is consistent with a promotional register where "
        "most posts are requests rather than opinions. No single mean-sentiment number is "
        "reported for a user, for the same reason no combined curve is drawn.",
    )
    add_figure(doc, "outputs/sentiment_distribution.png", 16.6)
    caption(doc, "Figure. Sentiment pies: keyword census, timeline sample, and mixed file. Green = positive, yellow = neutral, red = negative.")
    add_figure(doc, "outputs/sentiment_over_time_monthly.png", 16.6)
    caption(
        doc,
        "Figure. Separate monthly time series for positive, neutral, and negative. "
        "No single mixed sentiment curve. Solid = keyword census; dashed = timeline "
        "raw sample; dotted = timeline weighted estimate.",
    )

    heading(doc, "7. Emotion", 1)
    para(
        doc,
        "Model: pysentimiento emotion, finiteautomata/bertweet-base-emotion-analysis. "
        "Same 742,942 posts and 35,250 users. All seven probability columns are stored. "
        "There is no single mixed emotion score.",
    )
    add_table(
        doc,
        ["Emotion", "Combined n", "Combined %", "Keyword %", "Timeline raw %"],
        [
            ["joy", "49,667", "6.69", "5.30", "7.37"],
            ["anger", "8,169", "1.10", "0.53", "1.38"],
            ["sadness", "3,760", "0.51", "0.11", "0.70"],
            ["fear", "1,543", "0.21", "0.12", "0.25"],
            ["surprise", "1,826", "0.25", "0.03", "0.35"],
            ["disgust", "25,476", "3.43", "1.00", "4.62"],
            ["others", "652,501", "87.83", "92.92", "85.33"],
        ],
        [3.4, 3.2, 3.2, 3.4, 3.6],
    )
    para(
        doc,
        "others is large because Porter-stemmed, stopword-stripped IFB talk is often "
        "not a clear Ekman emotion. That is a limitation, not a reason to hide the "
        "six other series. Weekly, biweekly, monthly, quarterly, half-yearly, and "
        "yearly numeric series were saved.",
    )
    add_figure(doc, "outputs/emotion_plots/emotion_distribution.png", 16.2)
    caption(doc, "Figure. Emotion label shares for the keyword census, the timeline sample, and the mixed file.")
    add_figure(doc, "outputs/emotion_plots/emotion_sentiment_crosstab.png", 14.5)
    caption(doc, "Figure. Emotion × sentiment crosstab on the scored file. Neutral remains visible.")

    heading(doc, "8. Event detection", 1)
    para(
        doc,
        "Events were selected from this sample’s emotion peaks, then accepted only "
        "when tweets in the window share a readable theme. No chatbot world-news list "
        "was used. A peak is a description of the series, not a proven cause. "
        "Four events were kept. Thirty-one evidence tweets were stored.",
    )
    add_table(
        doc,
        ["ID", "Date", "Emotion", "Source", "z", "Window N", "Emotion N", "Evidence", "Theme"],
        [
            ["E01", "2022-03-01", "fear", "keyword", "4.59", "3,720", "19", "6", "NSW / eastern Australia flood warnings"],
            ["E02", "2022-11-21", "joy", "keyword", "4.95", "597", "61", "10", "Thanksgiving greetings"],
            ["E03", "2022-02-21", "fear", "timeline", "3.47", "3,553", "15", "5", "Mentions of Russia–Ukraine war"],
            ["E04", "2021-11-22", "joy", "timeline", "5.22", "2,075", "221", "10", "Thanksgiving greetings"],
        ],
        [1.4, 2.2, 1.8, 2.0, 1.2, 1.8, 2.0, 1.8, 3.2],
    )
    para(
        doc,
        "E03 now has five stored fear tweets. Four are timeline posts from the event "
        "window; two of those quote the same explosion text (different tweet_id / user). "
        "The fifth is a same-week keyword census tweet that names a Ukraine attack "
        "warning; it is not one of the 15 timeline fear posts and was not used in the "
        "z-score. Only 4 of 15 timeline fear posts mention Ukraine or explosions. "
        "This is a subset description, not a causal claim.",
    )
    ev_rows = []
    for r in evidence:
        if not (r.get("event_id") or "").strip():
            continue
        ev_rows.append(
            [
                r.get("event_id", ""),
                (r.get("created_at") or "")[:10],
                r.get("emotion_label", ""),
                short(r.get("original_text", ""), 140),
            ]
        )
    add_table(doc, ["Event", "Date", "Emotion", "Tweet evidence (original text)"], ev_rows, [1.6, 2.2, 1.8, 11.8])
    caption(doc, "Table. All 31 stored evidence tweets. These are the tweets that support the four events.")
    add_figure(doc, "outputs/event_plots/emotion_over_time_monthly.png", 16.6)
    caption(
        doc,
        "Figure. Monthly emotion shares with dashed labeled event lines (E01–E04). "
        "Keyword panel (top) and timeline panel (bottom). Correlation, not causation.",
    )
    add_figure(doc, "outputs/event_plots/emotion_over_time_weekly_keyword.png", 16.6)
    caption(doc, "Figure. Weekly keyword emotion shares with dashed labeled lines for E01 (fear) and E02 (joy).")
    add_figure(doc, "outputs/event_plots/emotion_over_time_weekly_timeline.png", 15.8)
    caption(doc, "Figure. Weekly timeline emotion shares with dashed labeled lines for E03 (fear) and E04 (joy).")

    heading(doc, "9. BERTopic and topic sentiment", 1)
    para(
        doc,
        "BERTopic reads topic_text, not clean_text. IFB/follow tokens are excluded. "
        "No topic is named IFB. Tuning used a stratified 64,000-post sample "
        "(source × year, seed 2026). Fifteen configurations were compared.",
    )
    para(
        doc,
        "Selected model: C13_min50_nn30_reduce_nt24 (all-MiniLM-L6-v2, min_topic_size=50, "
        "n_neighbors=30, reduce_outliers, nr_topics=24). Tune-sample c_v = 0.4353; "
        "tune-sample outliers = 0%. This is not the highest c_v. Configurations C10, "
        "C11, C14, and C15 scored 0.69–0.74 but collapsed to 4–5 mega-clusters that "
        "cannot be named. C1–C9 produced 94–183 topics with about 50% outliers.",
    )
    para(
        doc,
        "How many topics there are, stated once and unambiguously. nr_topics = 24 is "
        "the configured BERTopic parameter, not the result. Six of those 24 clusters "
        "({3, 5, 18, 20, 22, 23}) were pure follow-spam and were merged into the "
        "outlier bucket −1 rather than named IFB. The shipped assignment therefore has "
        "18 named topics plus one outlier bucket, which is 19 distinct topic_id values "
        "in post_topic and 19 rows in final_topics.csv. Wherever this report, the "
        "presentation, or a figure says “topics”, the number is 18 named topics.",
    )
    add_table(
        doc,
        ["Quantity", "Value", "Meaning"],
        [
            ["Configured topic count (nr_topics)", "24", "BERTopic parameter of run C13"],
            ["Merged follow-spam clusters", "6", "IDs 3, 5, 18, 20, 22, 23 — folded into −1 by hand"],
            ["Final named topics", "18", "Reported everywhere as “the topics”"],
            ["Outlier buckets", "1", "topic_id = −1"],
            ["Distinct topic_id values", "19", "18 named + −1"],
            ["Original BERTopic outliers in −1", "171,543 posts (23.09%)", "HDBSCAN could not assign these"],
            ["Manually merged spam posts in −1", "included in the 171,543", "Reassigned from the 6 spam clusters"],
        ],
        [6.4, 3.8, 7.2],
    )
    caption(
        doc,
        "Table. Configured versus final topic counts. The −1 bucket mixes two different "
        "things: posts HDBSCAN could not assign, and posts from the six follow-spam "
        "clusters that were merged in deliberately.",
    )
    para(
        doc,
        "On the full 742,942-post file, topic −1 contains 171,543 posts (23.1%). "
        "294,595 transform-outliers with usable topic_text were assigned "
        "to the nearest non-spam topic when cosine ≥ 0.28.",
    )
    exp = load_csv("outputs/bertopic_experiments.csv")
    if exp:
        add_table(
            doc,
            ["Configuration", "min_size", "n_neigh", "Topics", "c_v", "Outliers %", "Selected / reject reason"],
            [
                [
                    r.get("configuration_name", ""),
                    r.get("min_topic_size", ""),
                    r.get("n_neighbors", ""),
                    r.get("n_topics", ""),
                    r.get("coherence_cv", ""),
                    r.get("outlier_pct", ""),
                    ("SELECTED" if (r.get("selected") or "").strip() in {"1", "True", "true", "yes"}
                     else short(r.get("reject_reason", ""), 52)),
                ]
                for r in exp
            ],
            [3.9, 1.7, 1.5, 1.4, 1.5, 1.7, 5.7],
        )
        caption(
            doc,
            f"Table. All {len(exp)} BERTopic configurations that were run, with c_v coherence, "
            "topic count, outlier share, and the reason each configuration was rejected. "
            "ifb_topword_hits = 0 for every configuration, so no run produced an IFB/follow topic. "
            "Full file: outputs/bertopic_experiments.csv.",
        )
    add_figure(doc, "outputs/coherence_plot.png", 16.4)
    caption(doc, "Figure. BERTopic c_v by configuration. The green bar is C13, selected for interpretability plus coherence, not maximum c_v.")
    add_figure(doc, "outputs/topic_over_time_monthly.png", 16.6)
    caption(
        doc,
        "Figure. Monthly share of the six largest named C13 topics from the stored "
        "post_topic assignments. BERTopic was not rerun. Dashed labeled lines are "
        "E01–E04 (correlation, not causation). Keyword and timeline remain separate.",
    )
    topics = load_csv("outputs/final_topics.csv")
    if topics:
        def tkey(r: dict[str, str]) -> tuple[int, float]:
            tid = int(float(r.get("topic_id") or 0))
            try:
                size = float(r.get("topic_size") or 0)
            except ValueError:
                size = 0.0
            return (1 if tid == -1 else 0, -size)

        add_table(
            doc,
            ["ID", "Name", "Strongest words (c-TF-IDF stems)", "N", "%"],
            [
                [
                    "−1" if int(float(r.get("topic_id") or 0)) == -1 else r.get("topic_id", ""),
                    r.get("topic_name", ""),
                    short(r.get("topic_words", ""), 62),
                    f"{int(float(r.get('topic_size') or 0)):,}",
                    r.get("percentage", ""),
                ]
                for r in sorted(topics, key=tkey)
            ],
            [1.2, 4.6, 5.6, 2.1, 1.6],
        )
        caption(
            doc,
            f"Table. All {len(topics)} rows of final_topics.csv: 18 named topics plus the −1 "
            "outlier bucket, with the strongest c-TF-IDF words and the post count for each. "
            "No row contains ifb, follow, followback, or f4f.",
        )
    para(
        doc,
        "Names come from c-TF-IDF stems and from manually inspected original tweets. "
        "Topic 0 is supported by tweets about Twitter noise, timelines, and livestream "
        "chatter. Topic 4 is supported by “please DM / we can assist” replies. "
        "Topic 6 is supported by NBA/NFL handicap and game-day posts. Topic 1 and "
        "topic 8 are mixed clusters; the names record that mix rather than forcing a "
        "single political or sports label.",
    )
    reps = load_csv("outputs/topic_representative_tweets.csv")
    if reps:
        want = ["0", "4", "6"]
        rep_rows = []
        for tid in want:
            for r in reps:
                if (r.get("topic_id") or "").strip() != tid:
                    continue
                text = (r.get("original_text") or r.get("text") or "").strip()
                if len(text) < 40:
                    continue
                rep_rows.append([tid, r.get("topic_name", ""), short(text, 150)])
                if sum(1 for x in rep_rows if x[0] == tid) == 2:
                    break
        if rep_rows:
            add_table(doc, ["Topic", "Name", "Representative tweet (original text)"], rep_rows, [1.4, 3.8, 11.2])
            caption(
                doc,
                "Table. Representative tweets behind the three largest named topics, quoted from "
                "outputs/topic_representative_tweets.csv (152 stored examples). These are the posts "
                "the topic names were read off.",
            )
    add_figure(doc, "outputs/topic_sentiment_visualization.png", 16.6)
    caption(
        doc,
        "Figure. Top-6 non-outlier topics: word cloud in the center, sentiment ring "
        "outside. Green = positive, yellow = neutral, red = negative. Counts are "
        "unweighted posts in the mixed analysis file.",
    )
    tsent = load_csv("outputs/topic_sentiment_distribution.csv")
    if tsent:
        def skey(r: dict[str, str]) -> tuple[int, float]:
            tid = int(float(r.get("topic_id") or 0))
            try:
                n = float(r.get("n_raw") or 0)
            except ValueError:
                n = 0.0
            return (1 if tid == -1 else 0, -n)

        add_table(
            doc,
            ["ID", "Topic", "Positive", "Neutral", "Negative", "Total", "% neg"],
            [
                [
                    "−1" if int(float(r.get("topic_id") or 0)) == -1 else r.get("topic_id", ""),
                    short(r.get("topic_name", ""), 40),
                    f"{int(float(r.get('positive') or 0)):,}",
                    f"{int(float(r.get('neutral') or 0)):,}",
                    f"{int(float(r.get('negative') or 0)):,}",
                    f"{int(float(r.get('n_raw') or 0)):,}",
                    r.get("pct_negative", ""),
                ]
                for r in sorted(tsent, key=skey)
            ],
            [1.1, 4.5, 2.0, 2.0, 2.0, 2.0, 1.6],
        )
        caption(
            doc,
            f"Table. Topic × sentiment counts for all {len(tsent)} topics, the numeric table behind "
            "the ring figure above. Positive + neutral + negative sum to n_raw on every row, and the "
            "rows sum to 742,942. Neutral is reported, never folded away.",
        )
    para(
        doc,
        "Do the negative topics line up with the four detected events? No, and that is "
        "worth stating rather than leaving open. The most negative named topics are "
        "topic 15 (Dogs and city chatter) and topic 14 (Nigeria talk and Pokémon GO "
        "coordinates); neither peaks in the E01–E04 windows, and neither is political. "
        "The events were found in the emotion series of the whole file, not inside one "
        "topic, so there is no topic whose negativity explains them. The honest reading "
        "is that topic negativity here is diffuse everyday complaint, not event-driven.",
    )

    heading(doc, "10. Named entities and entity sentiment", 1)
    para(
        doc,
        "Library: spaCy 3.8.14, pipeline en_core_web_lg 3.8.0, run on original_text "
        "(never on Porter-stemmed clean_text). Course text listed HuggingFace NER; "
        "this model was used because it keeps EVENT, NORP, FAC, PRODUCT, and the "
        "GPE vs LOC split. 777,249 raw mentions; 642,041 kept; 135,208 dropped. "
        "Punctuation and the token “&” are dropped (junk_amp_or_symbol = 15,099). "
        "A scan of entities_cleaned.csv found 0 remaining “&” entities.",
    )
    para(
        doc,
        "Aliases are an explicit table (US/USA/America → United States; Trump → "
        "Donald Trump; Biden → Joe Biden; UK/Britain/GB → United Kingdom). "
        "Ambiguous strings such as Georgia, Jordan, Chad, and Mali are not forced "
        "into the country chart.",
    )
    para(
        doc,
        "Minimum entity length. The guidelines require dropping entities shorter than "
        "three characters, and that rule is now applied to the graded cleaned and "
        "network outputs. entities_cleaned.csv went from 256,491 to 255,139 rows; the "
        "1,352 removed rows are kept for inspection in outputs/entities_dropped_short.csv "
        "and covered 21,517 kept mentions of two-character tokens such as Un, IG, EU, "
        "CW, VN, GM, DC, LA, QB, bc, and AI. Those tokens are also gone from the "
        "co-occurrence graph in chapter 11, where CW and VN were previously drawn as "
        "Top-30 nodes. entities_extracted.csv is deliberately left unfiltered because it "
        "is the raw extraction record; the rule applies to the cleaned deliverables.",
    )
    add_figure(doc, "outputs/person_entities_sentiment.png", 16.4)
    caption(doc, "Figure. Top people by unique-post sentiment. Green / yellow / red. Not an all-yellow bar chart.")
    add_figure(doc, "outputs/country_entities_sentiment.png", 16.4)
    caption(doc, "Figure. Top countries by unique-post sentiment. Neutral is the large yellow segment in every bar.")
    para(
        doc,
        "Who these entities actually are, and whether the result is plausible. The "
        "people list is not a politics list with celebrities attached; it is two "
        "distinct populations sitting in the same file. Donald Trump, Joe Biden, "
        "Vladimir Putin, and Barack Obama arrive through the timeline sample, where "
        "these users behave like ordinary political-news retweeters. Jungkook, Jimin, "
        "Jesus, and Messi arrive through the fandom and devotional register that "
        "dominates reciprocal-follow solicitation, where naming an idol or a faith is "
        "itself the follow pitch. That is why two K-pop idols outrank Elon Musk in a "
        "corpus collected on the keyword “follow for follow”: fan accounts trade "
        "follows far more aggressively than technology accounts do.",
    )
    para(
        doc,
        "The sentiment spread is also readable rather than random. Israel at roughly "
        "−50% negative and Ukraine at −27% are war-coverage entities, and the negative "
        "share is the register of the news being retweeted, not an opinion the IFB "
        "community is expressing about those countries. Jungkook at about −1% is the "
        "opposite case: an idol named inside a positive follow-exchange request. The "
        "United States is the highest-degree node simply because it is the most common "
        "co-mention in political timeline text. The one result worth flagging as "
        "suspicious rather than plausible is Twitter itself being the most-mentioned "
        "organisation, which is an artefact of a platform community talking about the "
        "platform, and it is why Twitter is uninformative as a topic signal.",
    )

    heading(doc, "11. Entity co-occurrence network", 1)
    para(
        doc,
        "This is an entity co-occurrence network. Nodes are cleaned canonical entities. "
        "An undirected edge joins two entities when they appear in the same post. "
        "edge_weight is the number of distinct posts containing both "
        "(minimum edge weight 5). Entities need at least 20 unique posts. Posts with "
        "more than 8 eligible entities are dropped. Timeline sample_weight is stored "
        "as a population estimate on edges and is not used to build the graph or to "
        "score centrality.",
    )
    para(
        doc,
        "IFB.db has no follow/following adjacency list, no in_reply_to identifiers, "
        "and no retweet-cascade table. No follower, reply, or true-retweet network "
        "is presented.",
    )
    para(
        doc,
        "The canonical key, stated once so that every count in this report can be "
        "reproduced from the shipped files. A node is a canonical entity name, and the "
        "category (person, country, organization, location, norp, event, product, "
        "facility) is an attribute of that node, not part of its identity. An edge is an "
        "unordered pair of two different canonical entity names. One row of "
        "entity_network_edges.csv is therefore exactly one graph edge, there are no "
        "self-loops, and no unordered pair appears twice. Loading the edge list with "
        "networkx and grouping on (entity_a, entity_b) reproduces the node and edge "
        "counts in the table below exactly. An earlier version of these files keyed "
        "edges on (entity, category) pairs while the graph collapsed endpoints to bare "
        "names, which is why the shipped edge file and the shipped summary previously "
        "disagreed (2,694 rows against 2,665 edges); that ambiguity is resolved and both "
        "files are rebuilt from the single definition above.",
    )
    para(
        doc,
        "Combined density 0.004458; 57 components; largest component 944 nodes. "
        "Node size in the figure is weighted degree. PageRank, betweenness, and "
        "closeness are stored in entity_network_metrics.csv. Central names include "
        "United States, Donald Trump, Joe Biden, Twitter, Ukraine, and Russia. "
        "The drawn figure is the top 30 nodes of the largest component, not all 1,076. "
        "Entities shorter than three characters are excluded, so CW and VN no longer "
        "appear as nodes.",
    )
    add_figure(doc, "outputs/entity_network_graph.png", 16.0)
    caption(
        doc,
        "Figure. Entity co-occurrence network, top 30 by weighted degree, drawn from the "
        "1,076-node / 2,578-edge combined graph. Node = canonical entity name; edge = "
        "unordered name pair; edge width = distinct co-occurring posts. Not a follower "
        "or user-user graph.",
    )
    net = load_csv("outputs/entity_network_summary.csv")
    label = {
        "combined_min_edge": ("Combined (min edge 5)", "Mix of keyword census + timeline sample"),
        "keyword_only": ("Keyword only", "Census frame"),
        "timeline_only_raw": ("Timeline only", "Sample frame"),
        "person_person": ("person ↔ person", "Category-filtered subgraph"),
        "person_country": ("person ↔ country", "Category-filtered subgraph"),
        "organization": ("organization ↔ organization", "Category-filtered subgraph"),
    }
    if net:
        add_table(
            doc,
            ["Graph", "Nodes", "Edges", "Density", "Components", "Note"],
            [
                [
                    label.get(r.get("graph", ""), (r.get("graph", ""), ""))[0],
                    f"{int(float(r.get('n_nodes') or 0)):,}",
                    f"{int(float(r.get('n_edges') or 0)):,}",
                    r.get("density", ""),
                    r.get("n_components", ""),
                    label.get(r.get("graph", ""), ("", ""))[1],
                ]
                for r in net
            ],
            [4.0, 1.9, 1.9, 2.0, 2.1, 5.5],
        )
        caption(
            doc,
            "Table. All six shipped graphs on the canonical key. n_edges equals the number of "
            "rows in the corresponding edge file, and equals sum(degree) / 2 in "
            "entity_network_metrics.csv.",
        )

    heading(doc, "12. Behavioral risk classification", 1)
    para(
        doc,
        "This chapter is a behavioral risk classification, not verified bot identity. "
        "Humans run IFB campaigns. The schema cannot prove that an account is software.",
    )
    para(
        doc,
        "Features were built for all 38,576 primary users. Profile fields come from "
        "the authors snapshot (IFB.db read-only): followers, following, tweet_count, "
        "IFB_COUNT, verified, protected, account age, bio length, default-image "
        "heuristic, and followers/(following+1). Behavior fields come from the NLP "
        "file for 35,250 users: source-specific post counts, IFB-collection share, "
        "duplicate-template ratio, unique-text ratio, RT @ text ratio, burstiness, "
        "hour concentration, and sentiment/emotion/topic summaries. "
        "timeline_weighted_post_estimate is a population estimate only and is not a "
        "model feature.",
    )
    para(
        doc,
        "Manual review: 100 users, seed 2026. Labels used the snapshot profile and "
        "original posts, not live X pages. Result: 39 likely_normal, 30 suspicious, "
        "29 likely_malicious, 2 insufficient_evidence. Usable for ML: 98 "
        "(59 risk-positive, 39 likely_normal). The two insufficient_evidence users are "
        "excluded from every model, which is why the ML dataset is 98 rows and not 100. "
        "is_bot is 0 or unknown — never 1. "
        "Deleted or empty accounts are insufficient_evidence, not malicious. "
        "A second 200-user validation set was not created and was not fabricated.",
    )
    para(
        doc,
        "How those 100 users were chosen, and why it matters for the numbers below. "
        "The sample is stratified on the rule engine’s own output — 35 low_risk, "
        "30 medium_risk, 35 high_risk — and it is not a simple random sample of the "
        "38,576 users, which is what the guidelines describe. The consequence is "
        "concrete and should be read before the metrics: the whole population contains "
        "only 99 high_risk users, so drawing 35 of them means the high-risk band is "
        "enriched by roughly 136 times relative to its population share, while "
        "low_risk (21,516 users) and insufficient_posts (14,973 users) are heavily "
        "under-represented. Because the rule output selected the users on which the "
        "rule is then scored, the precision of 1.00 in the next table is partly "
        "circular: it says that the users the rule called high risk did look "
        "malicious on review, not that the rule is right across the population. "
        "Precision, recall, F1, and balanced accuracy in this chapter are diagnostic "
        "quantities measured on a rule-selected sample. They are not unbiased "
        "population estimates, and they must not be read as a population error rate. "
        "The 100 labels were not re-drawn or re-labelled to hide this; the design is "
        "disclosed instead.",
    )
    add_table(
        doc,
        ["Rule band", "Population N", "% of population", "Drawn into the 100", "Enrichment"],
        [
            ["low_risk", "21,516", "55.8%", "35", "~0.6×"],
            ["medium_risk", "1,988", "5.2%", "30", "~5.8×"],
            ["high_risk", "99", "0.26%", "35", "~136×"],
            ["insufficient_posts", "14,973", "38.8%", "0", "excluded from review"],
        ],
        [4.0, 3.0, 3.0, 3.2, 3.2],
    )
    caption(
        doc,
        "Table. The manual-review sampling frame. Enrichment is the share of the 100 "
        "divided by the share of the population, and it is the reason the rule metrics "
        "below are optimistic.",
    )
    add_figure(doc, "outputs/malicious_detection_flow.png", 15.8)
    caption(
        doc,
        "Figure. Rule flowchart. Every branch is labelled Yes or No, the "
        "insufficient-evidence path is explicit, and the thresholds are printed on the "
        "decision boxes. Manual review is the label; the rule score is an interpretable "
        "prior and not ground truth. The output is a behavioural-risk band, not a "
        "verified bot identity.",
    )
    add_table(
        doc,
        ["Rule test (fires when true)", "Score added", "Reason code"],
        [
            ["IFB boilerplate share ≥ 0.45", "+0.22", "high_ifb_boilerplate"],
            ["Duplicate template ratio ≥ 0.55", "+0.20", "high_duplicate_templates"],
            ["Unique text ratio ≤ 0.40", "+0.12", "low_unique_text"],
            ["“RT @” text share ≥ 0.50", "+0.12", "high_rt_at_text"],
            ["Keyword-collection share ≥ 0.75 and n_posts ≥ 8", "+0.10", "keyword_dominated"],
            ["Burstiness ≥ 2.2 and hour concentration ≥ 0.35", "+0.10", "bursty_concentrated_hours"],
            ["IFB_COUNT ≥ 20", "+0.08", "high_ifb_count"],
            ["following ≥ 2,000 and 0.7 ≤ followers/following ≤ 1.4", "+0.08", "symmetric_mass_follow"],
            ["Missing profile fields ≥ 3", "+0.06", "missing_profile_fields"],
            ["Verified and unique text ratio ≥ 0.7", "−0.15 (guard)", "verified_diverse_text_discount"],
            ["Bands: ≥ 0.55 high_risk; ≥ 0.30 medium_risk; else low_risk", "—", "n_posts < 3 → insufficient_posts"],
        ],
        [8.4, 3.2, 4.4],
    )
    caption(
        doc,
        "Table. The rule thresholds and their weights, transcribed from rule_risk_score() "
        "in src/bot_detection.py. The weights are ordered by how strongly the manual review "
        "associated each behaviour with follow-farm activity: text reuse (boilerplate, "
        "duplicate templates, low unique-text) was the most consistent signal in the "
        "reviewed accounts, so it carries the largest weight, while profile-shape signals "
        "(symmetric mass following, missing fields) were weaker on their own and carry less. "
        "The verified guard exists because verified brand accounts post highly templated "
        "support replies and would otherwise score as farms.",
    )
    add_table(
        doc,
        ["Rule vs 98 manual labels", "Value"],
        [
            ["Precision", "1.00"],
            ["Recall", "0.59"],
            ["F1", "0.74"],
            ["Balanced accuracy", "0.80"],
            ["Confusion", "TN 39 / FP 0 / FN 24 / TP 35"],
        ],
        [8.0, 8.0],
    )
    caption(
        doc,
        "Table. Rule performance against the 98 usable manual labels. Read with the "
        "sampling caveat above: these are diagnostics on a rule-stratified sample, not "
        "population estimates.",
    )
    mre = load_csv("outputs/manual_review_examples.csv")
    if mre:
        add_table(
            doc,
            ["Label", "Confidence", "Reviewer evidence (verbatim)"],
            [
                [
                    r.get("manual_label", ""),
                    r.get("reviewer_confidence", ""),
                    short(r.get("evidence_quote") or r.get("note") or "", 190),
                ]
                for r in mre[:6]
            ],
            [3.0, 2.2, 11.2],
        )
        caption(
            doc,
            "Table. Six of the stored manual-review notes, quoted verbatim from "
            "outputs/manual_review_examples.csv. Every one of the 100 reviewed users carries "
            "an evidence string of this kind in labeled_bots_and_not_bots.csv.",
        )
    para(
        doc,
        "Machine learning used only the 98 usable labels. Algorithms: Logistic "
        "Regression, Decision Tree, Random Forest, SVM, and XGBoost. User-level "
        "K=5 stratified CV (mean train size = 78) and LOOCV (train size = 97). "
        "Seed 2026. Preprocessing fit on the training fold only. Timeline sample "
        "weights were not used as scoring weights.",
    )
    add_table(
        doc,
        ["Algorithm", "K=5 n_train", "K=5 F1", "K=5 bal. acc.", "K=5 AUC", "LOOCV n_train", "LOOCV F1"],
        [
            ["Logistic Regression", "78", "0.820", "0.757", "0.907", "97", "0.855"],
            ["Decision Tree", "78", "0.796", "0.766", "0.804", "97", "0.879"],
            ["Random Forest", "78", "0.885", "0.842", "0.930", "97", "0.869"],
            ["SVM", "78", "0.814", "0.766", "0.856", "97", "0.842"],
            ["XGBoost", "78", "0.850", "0.804", "0.914", "97", "0.872"],
        ],
        [3.6, 2.4, 2.0, 2.6, 2.0, 2.6, 2.2],
    )
    para(
        doc,
        "Best K=5 pooled model: Random Forest (F1 0.885, balanced accuracy 0.842, "
        "AUC 0.93). These metrics are from 98 labeled users. They do not prove bot "
        "identity in the 38,576-user population. Full-population predictions with "
        "confidence ≥ 0.8 are a filter suggestion, not a ban list.",
    )
    para(
        doc,
        "Applying the model to the whole population, with the numbers stated. The "
        "selected Random Forest, refit on all 98 labels, was scored over all 38,576 "
        "users in unlabeled_dataset_results.csv. It predicts class 1 (risk-positive) "
        "for 9,719 users, which is 25.2% of the population. Of those, 893 users carry "
        "confidence_level ≥ 0.8, which is 2.3% of the population and the set the "
        "guidelines describe removing before continuing. That filter is presented as a "
        "suggestion and was not applied destructively: no user was deleted from the "
        "corpus, because a risk score from 98 labels is not sufficient grounds to "
        "discard 893 accounts from an analysis of 38,576.",
    )
    add_table(
        doc,
        ["Category", "N", "Basis", "Status"],
        [
            ["bot", "0 asserted", "Manual review: is_bot is 0 or unknown on all 100 reviewed users",
             "Not asserted — no verified bot ground truth exists"],
            ["troll", "0 asserted", "Manual review: is_troll is 0 or unknown on all 100 reviewed users",
             "Not modelled — no positive labels to train on"],
            ["malicious (manual)", "29", "manual_label = likely_malicious among the 100 reviewed",
             "Reviewed evidence, sample only"],
            ["risk-positive (model, any confidence)", "9,719", "Random Forest predicted_class = 1 over 38,576",
             "Behavioural risk, not identity"],
            ["risk-positive at confidence ≥ 0.8", "893", "Random Forest predicted_class = 1 and confidence ≥ 0.8",
             "Suggested filter set, not applied"],
            ["rule high_risk band", "99", "rule_label = high_risk over 38,576", "Interpretable prior only"],
        ],
        [4.6, 2.0, 5.4, 4.4],
    )
    caption(
        doc,
        "Table. Summary of users filtered by category. The bot and troll rows are "
        "deliberately empty of assertions: the manual review never set is_bot or is_troll "
        "to 1, so there is no honest basis for a bot count or a troll count, and none is "
        "invented here.",
    )
    para(
        doc,
        "One bookkeeping note on the predictions file, because its row count does not "
        "match the population. bot_detection_predictions.csv has 39,556 rows, which is "
        "38,576 population predictions plus 980 cross-validation evaluation rows "
        "(five algorithms × 196 fold-level rows). The 980 evaluation rows have an empty "
        "predicted_class, so author_id is unique across the 38,576 population rows but "
        "repeats where a reviewed user also appears in a CV fold. "
        "unlabeled_dataset_results.csv and unlabled_dataset.csv contain the population "
        "block alone, at exactly 38,576 rows each.",
    )
    add_figure(doc, "outputs/bot_model_comparison.png", 16.2)
    caption(doc, "Figure. K=5 pooled metrics for all five algorithms. Behavioral risk, not bot identity.")
    add_figure(doc, "outputs/bot_confusion_matrices.png", 16.2)
    caption(doc, "Figure. K=5 pooled confusion matrices. Class 1 = suspicious / likely-malicious risk, not a verified bot.")
    add_figure(doc, "outputs/bot_feature_distributions.png", 16.2)
    caption(doc, "Figure. Selected feature distributions used in the risk models.")

    heading(doc, "13. Limitations", 1)
    para(doc, "1. The 38,576-user set is smaller than the 2.1 million keyword authors because most keyword authors have no authors row or timeline. One population is kept for every stage.")
    para(doc, "2. Sentiment, emotion, topics, and NER run on 742,942 English-ready posts, not on 37,839,416 timeline rows.")
    para(doc, "3. Keyword = census; timeline = sample. Combined totals are mixed. Timeline sample_weight is a population estimate, not a model weight.")
    para(doc, "4. Non-English posts were excluded, not translated.")
    para(doc, "5. others dominates the emotion distribution. Peaks are rare.")
    para(doc, "6. Events are tweet-supported peaks in this sample. They are not causal proofs. E03 is a subset of that week’s fear posts: 4 of 15 timeline fear tweets mention Ukraine or explosions.")
    para(doc, "7. Topic −1 is 23.1% of the full file. Some named topics remain mixed.")
    para(doc, "8. No follower, reply, or true-retweet network exists in IFB.db.")
    para(doc, "9. Manual bot review used snapshot metadata and posts, not live X. Deleted accounts are not labeled malicious.")
    para(doc, "10. The course’s 200-user second validation set is missing and was not fabricated.")
    para(doc, "11. ML used 98 labeled users (K=5 mean train 78; LOOCV train 97). Metrics have wide uncertainty and do not identify bots.")
    para(doc, "12. Guideline-named giant CSVs were not duplicated as 742k-row spreadsheets; those columns live in SQLite, and the guideline folder tree holds the small graded deliverables.")
    para(doc, "13. The 100 manually reviewed users were stratified on the rule bands, not sampled at random. The high-risk band is enriched about 136×, so rule precision 1.00 and recall 0.59 are diagnostics on a rule-selected sample and not population error rates.")
    para(doc, "14. “English-ready” is an operational inclusion rule (LANG = en for timeline, Latin-script likely_english for keyword), not proof of native English. Latin-script non-English posts survive at a low rate; the report shows one retained Portuguese example rather than hiding it.")
    para(doc, "15. Entities shorter than three characters are excluded from the cleaned and network outputs. entities_extracted.csv remains the unfiltered extraction record, so mention-level counts there still include those tokens.")
    para(doc, "16. Sentiment toward individual entities over time was not produced as a figure. entities_cleaned.csv stores only date_min and date_max per entity, so the temporal entity view is a documented gap rather than an untested claim.")

    heading(doc, "14. Conclusions", 1)
    para(
        doc,
        "Inside this IFB population, scored English posts are mostly neutral "
        "(70.85% of the mixed file; 75.67% of the keyword census; 68.49% of the "
        "timeline sample). Positive posts outnumber negative posts, especially in "
        "the keyword census, which is structurally promotional. Emotion is dominated "
        "by others; joy and disgust are the next visible classes.",
    )
    para(
        doc,
        "Four events have actual tweet evidence: Australian flood-warning language "
        "in March 2022 keyword fear posts, Thanksgiving greetings in two November "
        "windows, and a small set of February 2022 timeline fear posts that mention "
        "the Russia–Ukraine war. Those tweets document what appears in the windows. "
        "They do not prove that the external events caused IFB emotion.",
    )
    para(
        doc,
        "Topics after IFB-token removal are about Twitter chatter, help-desk DMs, "
        "sports, faith, marketing hashtags, and mixed political/music clusters — "
        "not a single “IFB” topic — 18 named topics plus one outlier bucket. Entity bars "
        "and the 1,076-node / 2,578-edge graph "
        "show politicians, platforms, and countries co-occurring in the same posts. "
        "That is a map of names that travel together in text, not a social graph.",
    )
    para(
        doc,
        "On 98 manually reviewed users, Random Forest is the strongest of the five "
        "required algorithms, with K=5 mean train size 78. The result is a risk "
        "score for follow-farm style behavior. It is not a verified list of bots. "
        "The missing 200-user validation set remains a limitation.",
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(REPORT))


def _rgb_fill(shape, color: PptRGB) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _textbox(slide, l, t, w, h, text, *, size=18, bold=False, color=P_INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = PPt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return tf


def _add_notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def _bar(slide, title: str) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, PInches(0), PInches(0), PInches(13.333), PInches(0.92))
    _rgb_fill(shape, P_NAVY)
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, PInches(0), PInches(0.92), PInches(13.333), PInches(0.08))
    _rgb_fill(accent, P_TEAL)
    _textbox(slide, PInches(0.4), PInches(0.18), PInches(12.5), PInches(0.64), title, size=26, bold=True, color=P_WHITE)


def _footer(slide, n: int, total: int = 14) -> None:
    _textbox(
        slide,
        PInches(0.4),
        PInches(7.18),
        PInches(12.5),
        PInches(0.28),
        f"IFB project  ·  38,576 users  ·  742,942 scored posts  ·  {n}/{total}",
        size=11,
        color=P_MUTED,
    )


def _bullets(slide, l, t, w, h, items: list[str], *, size=16):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = PPt(6)
        run = p.add_run()
        run.text = item
        run.font.size = PPt(size)
        run.font.color.rgb = P_INK
        run.font.name = "Calibri"
    return tf


def _ppt_table(slide, l, t, w, h, headers, rows):
    table_shape = slide.shapes.add_table(1 + len(rows), len(headers), l, t, w, h)
    table = table_shape.table
    for i, htext in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = htext
        cell.text_frame.word_wrap = True
        for p in cell.text_frame.paragraphs:
            p.font.size = PPt(11)
            p.font.bold = True
            p.font.color.rgb = P_WHITE
            p.font.name = "Calibri"
        cell.fill.solid()
        cell.fill.fore_color.rgb = P_NAVY
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = table.cell(r + 1, c)
            cell.text = str(val)
            cell.text_frame.word_wrap = True
            for p in cell.text_frame.paragraphs:
                p.font.size = PPt(12)
                p.font.color.rgb = P_INK
                p.font.name = "Calibri"
            if r % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = PptRGB(0xF4, 0xF7, 0xF8)
    return table_shape


def build_pptx() -> None:
    prs = Presentation()
    prs.slide_width = PInches(13.333)
    prs.slide_height = PInches(7.5)
    blank = prs.slide_layouts[6]

    # 1 title
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, PInches(0), PInches(0), PInches(13.333), PInches(7.5))
    _rgb_fill(bg, P_NAVY)
    stripe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, PInches(0), PInches(0), PInches(0.18), PInches(7.5))
    _rgb_fill(stripe, P_POS)
    _textbox(s, PInches(0.7), PInches(1.5), PInches(12), PInches(0.4), "Introduction to Social Networks  ·  Semester B 2026", size=16, color=PptRGB(0xC5, 0xD5, 0xDC))
    _textbox(s, PInches(0.7), PInches(2.0), PInches(12), PInches(1.4), "IFB discourse: sentiment, topics,\nentities, and behavioral risk", size=34, bold=True, color=P_WHITE)
    _textbox(
        s,
        PInches(0.7),
        PInches(4.6),
        PInches(12),
        PInches(1.4),
        "Research question: what do emotion, topics, and named entities look like in one\n"
        "frozen IFB population — and which patterns are supported by tweets, not by\n"
        "chatbot news or claimed bot identity?",
        size=18,
        color=P_WHITE,
    )
    _add_notes(
        s,
        "0:00–0:40. Open with the question. Say IFB means I Follow Back, a follow-for-follow "
        "community collected by keywords, not a follower crawl. Promise no causal claims and "
        "no “we found the bots.” 15-minute plan: data 1 min, pipeline 50s, sampling 1 min, "
        "sentiment 1:10, emotion 1:00, events 1:20, topics 1:10, NER 1:00, network 1:00, "
        "bots 1:20, ML 1:20, limitations 1:10, close 50s.",
    )

    # 2 dataset
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Dataset: one frozen population")
    cards = [
        ("38,576", "primary users", "authors ∩ tweets ∩ timeline"),
        ("742,942", "English-ready posts", "scored sentiment + emotion"),
        ("244,217", "keyword posts", "CENSUS of eligible IFB tweets"),
        ("498,725", "timeline posts", "SAMPLE of English timelines"),
    ]
    colors = [P_NAVY, P_TEAL, P_POS, PptRGB(0x8D, 0x6E, 0x16)]
    for i, ((n, label, sub), col) in enumerate(zip(cards, colors)):
        x = PInches(0.4 + i * 3.2)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, PInches(1.25), PInches(3.05), PInches(2.15))
        _rgb_fill(card, col)
        _textbox(s, x + PInches(0.12), PInches(1.35), PInches(2.8), PInches(0.7), n, size=28, bold=True, color=P_WHITE, align=PP_ALIGN.CENTER)
        _textbox(s, x + PInches(0.12), PInches(2.05), PInches(2.8), PInches(0.45), label, size=14, bold=True, color=P_WHITE, align=PP_ALIGN.CENTER)
        _textbox(s, x + PInches(0.12), PInches(2.5), PInches(2.8), PInches(0.7), sub, size=12, color=P_WHITE, align=PP_ALIGN.CENTER)
    _bullets(
        s,
        PInches(0.5),
        PInches(3.6),
        PInches(12.3),
        PInches(3.3),
        [
            "Full corpus behind the sample: 1,129,607 keyword tweets and 37,839,416 timeline tweets.",
            "35,250 of the 38,576 users have at least one scored English post.",
            "Timeline sample_weight ≈ 29.50M English timeline posts. Weight = population estimate, not a model score.",
            "Keyword + timeline together are a mixed file, not one unlabeled population.",
            "Join: CAST(AUTHOR_ID AS TEXT). 1,203 ambiguous ID groups dropped. Seed 2026.",
        ],
        size=16,
    )
    _footer(s, 2)
    _add_notes(
        s,
        "0:40–1:50. Say the four numbers out loud. Stress census vs sample. "
        "If asked why not 2.1M authors: most keyword authors have no profile or timeline. "
        "If asked why not 37.8M BERT rows: compute; the freeze is documented.",
    )

    # 3 pipeline
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Pipeline")
    steps = [
        ("1", "English-ready\ncorpus"),
        ("2", "Sentiment\n+ emotion"),
        ("3", "Events from\ntweet peaks"),
        ("4", "BERTopic\nC13"),
        ("5", "NER +\nco-occurrence"),
        ("6", "Risk labels\n+ 5 models"),
    ]
    for i, (num, lab) in enumerate(steps):
        x = PInches(0.35 + i * 2.16)
        circ = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, PInches(1.4), PInches(2.0), PInches(1.7))
        _rgb_fill(circ, P_NAVY)
        _textbox(s, x, PInches(1.5), PInches(2.0), PInches(0.4), num, size=18, bold=True, color=P_NEU, align=PP_ALIGN.CENTER)
        _textbox(s, x + PInches(0.06), PInches(1.95), PInches(1.88), PInches(1.0), lab, size=14, color=P_WHITE, align=PP_ALIGN.CENTER)
        if i < 5:
            _textbox(s, x + PInches(1.85), PInches(1.95), PInches(0.35), PInches(0.4), "→", size=20, color=P_TEAL)
    _bullets(
        s,
        PInches(0.5),
        PInches(3.4),
        PInches(12.3),
        PInches(3.4),
        [
            "pysentimiento (BERTweet) for 3-class sentiment and 7-class emotion.",
            "Events: peaks in this sample, then tweet evidence. No chatbot news list.",
            "BERTopic on topic_text after IFB/follow tokens are removed.",
            "Network = entity co-occurrence only. No follower / reply / true-retweet graph exists.",
            "Bots chapter = behavioral risk. Results do not prove bot identity.",
        ],
        size=16,
    )
    _footer(s, 3)
    _add_notes(s, "1:50–2:40. Walk the six boxes. Name pysentimiento. Say C13 will appear later. Repeat: no follower network, no bot identity.")

    # 4 sampling
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Data quality and sampling decisions")
    _ppt_table(
        s,
        PInches(0.4),
        PInches(1.25),
        PInches(12.5),
        PInches(2.6),
        ["Decision", "What we did", "What we did not do"],
        [
            ["Language", "Keep English-ready posts; copy original to text_translated_en", "Do not translate excluded non-English posts"],
            ["Keyword NLP", "Census of 244,217 eligible English IFB tweets", "Do not treat all 1.13M keyword rows as English"],
            ["Timeline NLP", "Stratified English sample: 498,725 posts, seed 2026", "Do not score all 37.8M timeline rows"],
            ["Weights", "sample_weight = population estimate only", "Do not use weights as model scores"],
            ["Cleaning", "clean_text for sentiment; topic_text drops IFB/follow", "Do not leave IFB/Follow inside topics"],
        ],
    )
    _bullets(
        s,
        PInches(0.5),
        PInches(4.1),
        PInches(12.3),
        PInches(2.8),
        [
            "English-only corpus by construction, not “most posts are English so skip the rest.”",
            "UTF-8 throughout. clean_text is a saved column, not notebook memory.",
            "Combined 742,942 is a mixed file: always split keyword vs timeline when reading totals.",
        ],
        size=16,
    )
    _footer(s, 4)
    _add_notes(s, "2:40–3:40. This slide prevents the 70-point IFB failures: mixed populations, leftover IFB tokens, silent translation skip.")

    # 5 sentiment
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Sentiment — three classes, not one curve")
    s.shapes.add_picture(str(must("outputs/sentiment_distribution.png")), PInches(0.25), PInches(1.15), PInches(8.3), PInches(3.15))
    s.shapes.add_picture(str(must("outputs/sentiment_over_time_monthly.png")), PInches(8.4), PInches(1.15), PInches(4.7), PInches(4.4))
    _textbox(s, PInches(0.35), PInches(4.35), PInches(8.1), PInches(2.5),
             "Green 134,936 positive (18.2%)   ·   Yellow 526,377 neutral (70.9%)   ·   Red 81,629 negative (11.0%)\n"
             "Keyword census is more promotional (20% pos / 4% neg).\n"
             "Timeline raw = 17.3% / 68.5% / 14.3%; weighted estimate uses the same shares on ≈29.50M posts.\n"
             "Right: separate monthly panels. Neutral is required. No mixed “sentiment” line.",
             size=13)
    _footer(s, 5)
    _add_notes(s, "3:40–4:50. Point at green/yellow/red. Say the instructor comment: אין דבר כזה סנטימנט ביחד. Neutral is the majority class.")

    # 6 emotion
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Emotion — seven labels, six time resolutions")
    s.shapes.add_picture(str(must("outputs/emotion_plots/emotion_distribution.png")), PInches(0.3), PInches(1.2), PInches(7.4), PInches(4.4))
    _bullets(
        s,
        PInches(7.9),
        PInches(1.3),
        PInches(5.1),
        PInches(5.4),
        [
            "Same 742,942 posts / 35,250 users.",
            "others = 87.8% of the mixed file.",
            "Next: joy 6.7%, disgust 3.4%.",
            "fear is rare (0.21%) — that is why event windows are small.",
            "Week, 2-week, month, quarter, half-year, year series all exist.",
            "others is a limitation, not a hidden sixth emotion.",
        ],
        size=15,
    )
    _footer(s, 6)
    _add_notes(s, "4:50–5:50. others is huge because IFB copy is not Ekman speech. Do not apologize by collapsing the other six series.")

    # 7 events
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Events — dashed lines and tweet evidence")
    s.shapes.add_picture(str(must("outputs/event_plots/emotion_over_time_weekly_keyword.png")), PInches(0.25), PInches(1.15), PInches(7.5), PInches(3.15))
    _ppt_table(
        s,
        PInches(7.9),
        PInches(1.15),
        PInches(5.15),
        PInches(3.15),
        ["ID", "Date", "Emo", "Tweets"],
        [
            ["E01", "2022-03-01", "fear", "6 tweets"],
            ["E02", "2022-11-21", "joy", "10 tweets"],
            ["E03", "2022-02-21", "fear", "5 tweets"],
            ["E04", "2021-11-22", "joy", "10 tweets"],
        ],
    )
    _textbox(
        s,
        PInches(0.4),
        PInches(4.4),
        PInches(12.5),
        PInches(2.4),
        "4 detected events, 31 stored tweets. Dashed labeled lines are on weekly→yearly plots.\n"
        "E01: Bureau-style NSW flood warnings that contain the word “follow.”  E03: 5 fear tweets; only a subset mention Ukraine or explosions.\n"
        "These tweets show what is in the window. They do not prove that floods, Thanksgiving, or the war caused IFB emotion.",
        size=14,
    )
    _footer(s, 7)
    _add_notes(s, "5:50–7:10. Read one E01 quote if asked. E03 has 5 real tweets; only a subset name Ukraine/explosions. Refuse any causal sentence.")

    # 8 topics
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "BERTopic C13 and topic sentiment")
    s.shapes.add_picture(str(must("outputs/coherence_plot.png")), PInches(0.25), PInches(1.15), PInches(6.3), PInches(2.7))
    s.shapes.add_picture(str(must("outputs/topic_sentiment_visualization.png")), PInches(6.6), PInches(1.15), PInches(6.45), PInches(4.55))
    _textbox(
        s,
        PInches(0.3),
        PInches(3.95),
        PInches(6.3),
        PInches(2.9),
        "C13 selected by coherence + interpretability, not max c_v.\n"
        "18 named topics (nr_topics=24 configured; 6 follow-spam clusters merged into −1).\n"
        "Full-file outliers −1: 171,543 / 742,942 = 23.1%.\n"
        "IFB/follow tokens stripped. Follow-spam merged into −1.\n"
        "Rings: green / yellow / red, including neutral.\n"
        "Names checked against representative tweets.",
        size=14,
    )
    _footer(s, 8)
    _add_notes(s, "7:10–8:20. Point at the green C13 bar — it is not the tallest. Outlier 23.1% is disclosed. Neutral yellow rings are required.")

    # 9 NER
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "NER and entity sentiment")
    s.shapes.add_picture(str(must("outputs/person_entities_sentiment.png")), PInches(0.2), PInches(1.15), PInches(6.5), PInches(5.3))
    s.shapes.add_picture(str(must("outputs/country_entities_sentiment.png")), PInches(6.7), PInches(1.15), PInches(6.4), PInches(5.3))
    _footer(s, 9)
    _add_notes(
        s,
        "8:20–9:20. spaCy en_core_web_lg on original_text. “&” dropped (0 remain). "
        "Aliases documented (US→United States, Trump→Donald Trump). Bars are green/yellow/red, "
        "fixing the previous all-yellow IFB bug. Neutral still dominates.",
    )

    # 10 network
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Entity co-occurrence network — not a social graph")
    s.shapes.add_picture(str(must("outputs/entity_network_graph.png")), PInches(0.2), PInches(1.1), PInches(8.3), PInches(5.7))
    _bullets(
        s,
        PInches(8.6),
        PInches(1.25),
        PInches(4.4),
        PInches(5.6),
        [
            "1,076 nodes, 2,578 combined edges.",
            "Edge key = unordered pair of entity names.",
            "Edge weight = distinct posts (min 5).",
            "Node size = weighted degree.",
            "Also stored: PageRank, betweenness, closeness.",
            "Keyword-only: 662 / 1,320.",
            "Timeline-only: 567 / 1,200.",
            "IFB.db has follower counts, not edges.",
            "No reply or true-retweet network exists.",
        ],
        size=15,
    )
    _footer(s, 10)
    _add_notes(s, "9:20–10:20. Repeat the title sentence. Combined graph mixes census + sample. Central names: United States, Trump, Biden, Twitter, Ukraine, Russia.")

    # 11 bots
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Behavioral risk — not verified bot identity")
    # height only, so the redrawn flowchart keeps its aspect ratio instead of being squashed
    s.shapes.add_picture(str(must("outputs/malicious_detection_flow.png")), PInches(0.3), PInches(1.15), height=PInches(5.95))
    _bullets(
        s,
        PInches(6.9),
        PInches(1.25),
        PInches(6.1),
        PInches(5.9),
        [
            "Real decision flow: every branch is labelled Yes / No.",
            "insufficient_posts path is explicit (14,973 users, never called bots).",
            "100 manual reviews, seed 2026 — stratified on the rule bands, NOT random.",
            "High-risk band enriched ~136× (35 drawn from only 99 users).",
            "So precision 1.00 / recall 0.59 / F1 0.74 are sample diagnostics, not population rates.",
            "39 likely_normal / 30 suspicious / 29 likely_malicious / 2 insufficient.",
            "98 usable ML labels (59 risk-positive / 39 normal).",
            "Snapshot + posts, not live X. Deleted ≠ malicious. is_bot never 1.",
            "200-user validation: MISSING, not fabricated.",
        ],
        size=13,
    )
    _footer(s, 11)
    _add_notes(s, "10:20–11:40. This is the previous IFB failure to fix: features are not proof. Say 200-user set is missing. Do not offer a bot count for 38,576 users.")

    # 12 ML
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Five algorithms — train sizes 78 and 97")
    s.shapes.add_picture(str(must("outputs/bot_model_comparison.png")), PInches(0.25), PInches(1.15), PInches(7.0), PInches(4.0))
    _ppt_table(
        s,
        PInches(7.4),
        PInches(1.15),
        PInches(5.6),
        PInches(3.5),
        ["Model", "Train", "F1", "AUC"],
        [
            ["LogReg", "78", "0.82", "0.91"],
            ["Tree", "78", "0.80", "0.80"],
            ["RF (best K=5)", "78", "0.89", "0.93"],
            ["SVM", "78", "0.81", "0.86"],
            ["XGBoost", "78", "0.85", "0.91"],
        ],
    )
    _textbox(
        s,
        PInches(0.4),
        PInches(5.25),
        PInches(12.5),
        PInches(1.6),
        "98 usable manual labels only. K=5 mean train size = 78. LOOCV train size = 97.\n"
        "These results do not prove bot identity. Timeline sample weights were not used as model-scoring weights.\n"
        "High-confidence predictions are a filter suggestion, not a ban list.",
        size=15,
    )
    _footer(s, 12)
    _add_notes(s, "11:40–13:00. Instructor asked for train-set size. Say 78 and 97 twice. Best model Random Forest. Small-n limitation is the story, not 0.885.")

    # 13 limitations
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Limitations")
    _bullets(
        s,
        PInches(0.5),
        PInches(1.25),
        PInches(12.3),
        PInches(5.7),
        [
            "NLP is 742,942 English-ready posts, not 37.8M timeline rows.",
            "Keyword census and timeline sample must not be read as one population.",
            "Non-English posts were excluded, not translated.",
            "Emotion others = 87.8%. E03 is a subset of that week’s fear posts (Ukraine/explosions).",
            "Topic −1 = 23.1%. No follower / reply / true-retweet network exists.",
            "98 usable ML labels. K=5 train 78; LOOCV train 97. Wide uncertainty.",
            "200-user rule validation is missing and was not fabricated.",
            "Results do not prove bot identity and do not support causal event claims.",
        ],
        size=18,
    )
    _footer(s, 13)
    _add_notes(s, "13:00–14:10. Read this slide slowly. It is the honest grade protection. If asked about 200 users: we refused to invent them.")

    # 14 conclusions
    s = prs.slides.add_slide(blank)
    _rgb_fill(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height), P_CREAM)
    _bar(s, "Conclusions")
    _bullets(
        s,
        PInches(0.5),
        PInches(1.25),
        PInches(12.3),
        PInches(5.7),
        [
            "Neutral dominates: 70.9% mixed file; keyword more promotional than timeline.",
            "Four tweet-supported events; dashed lines on the emotion plots; no causation.",
            "C13 topics after IFB-token removal; 23.1% outliers disclosed.",
            "NER has no “&”; bars are green / yellow / red.",
            "Network: 1,076 nodes and 2,578 edges of entity co-occurrence only.",
            "Risk models on 98 labels. Random Forest is strongest. Not a bot census.",
            "38,576 users. 742,942 scored posts. Census + sample, never one silent population.",
        ],
        size=18,
    )
    _footer(s, 14)
    _add_notes(
        s,
        "14:10–15:00. Close on the three numbers: 38,576 users, 742,942 posts, 98 labels. "
        "Repeat: network is co-occurrence; results do not prove bot identity. Stop. Take questions.",
    )

    PPTX.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(PPTX))


def inspect_outputs() -> dict:
    from docx import Document as D
    from pptx import Presentation as P

    doc = D(str(REPORT))
    n_pics = 0
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            n_pics += 1
    texts = []
    for p in doc.paragraphs:
        texts.append(p.text)
    for t in doc.tables:
        for row in t.rows:
            texts.append(" | ".join(c.text for c in row.cells))
    blob = "\n".join(texts)
    forbidden = []
    for phrase in ("see outputs folder", "see the outputs", "open the outputs", "look in outputs"):
        if phrase in blob.lower():
            forbidden.append(phrase)
    needed = [
        "38,576",
        "742,942",
        "35,250",
        "1,076",
        "2,578",
        "98",
        "sample_weight",
        "not verified bot identity",
        "entity co-occurrence",
        "200-user",
    ]
    missing_nums = [n for n in needed if n.lower() not in blob.lower() and n not in blob]
    # 200-user might be written as 200-user
    prs = P(str(PPTX))
    ppt_text = []
    n_slide_pics = 0
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if shape.has_text_frame:
                ppt_text.append(shape.text_frame.text)
            if shape.shape_type is not None and getattr(shape, "image", None) is not None:
                n_slide_pics += 1
            if shape.has_table:
                tbl = shape.table
                for row in tbl.rows:
                    ppt_text.append(" | ".join(c.text for c in row.cells))
        notes = slide.notes_slide.notes_text_frame.text
        ppt_text.append(notes)
    ppt_blob = "\n".join(ppt_text)
    ppt_needed = [
        "38,576",
        "742,942",
        "CENSUS",
        "SAMPLE",
        "98",
        "78",
        "97",
        "do not prove bot identity",
        "entity co-occurrence",
        "sample_weight",
    ]
    ppt_missing = [n for n in ppt_needed if n.lower() not in ppt_blob.lower() and n not in ppt_blob]
    return {
        "report_paragraphs": len(doc.paragraphs),
        "report_tables": len(doc.tables),
        "report_images": n_pics,
        "report_forbidden": forbidden,
        "report_missing": missing_nums,
        "slides": len(prs.slides),
        "slide_images": n_slide_pics,
        "pptx_missing": ppt_missing,
        "report_bytes": REPORT.stat().st_size,
        "pptx_bytes": PPTX.stat().st_size,
    }


def main() -> None:
    n_ids = export_primary_ids()
    write_guideline_pointers()
    evidence = load_csv("outputs/event_tweet_evidence.csv")
    if len(evidence) != 31:
        raise RuntimeError(f"expected 31 evidence tweets, got {len(evidence)}")
    try:
        examples = load_csv("outputs/translation_examples.csv")
    except OSError:
        examples = []
    build_report(evidence, examples)
    build_pptx()
    info = inspect_outputs()
    info["primary_ids"] = n_ids
    print(info)
    if info["report_images"] < 17:
        raise SystemExit(f"too few report images: {info['report_images']}")
    if info["slides"] < 12 or info["slides"] > 15:
        raise SystemExit(f"slide count {info['slides']} not in 12–15")
    if info["report_forbidden"]:
        raise SystemExit(f"folder pointers in report: {info['report_forbidden']}")
    if info["report_missing"] or info["pptx_missing"]:
        raise SystemExit(f"missing claims {info['report_missing']} {info['pptx_missing']}")


if __name__ == "__main__":
    main()
