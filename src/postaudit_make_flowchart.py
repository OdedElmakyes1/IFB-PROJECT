"""Redraw the malicious / bot-risk rule flowchart.

The previous figure had overlapping boxes, no connector arrows and no Yes/No
branch labels, so it did not read as a flowchart at all. This script draws a
real top-to-bottom decision flow and rebuilds ``malicious_detection_flow.pptx``
around it.

Thresholds and weights are transcribed from ``rule_risk_score()`` in
``src/bot_detection.py``. Band counts are read from
``outputs/rule_based_bot_scores.csv`` and the manual-review counts from
``outputs/labeled_bots_and_not_bots.csv``, so nothing on the figure is invented.

No model is rerun.

Usage (from the repo root):
    python src/postaudit_make_flowchart.py
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PNG = OUT / "malicious_detection_flow.png"
PPTX = ROOT / "malicious_detection_flow.pptx"

MIN_POSTS_FOR_TEXT = 3
HIGH_CUT = 0.55
MED_CUT = 0.30

# (condition text, weight text, reason label) — transcribed from bot_detection.py
TESTS = [
    ("IFB boilerplate share  >= 0.45", "+0.22", "high_ifb_boilerplate"),
    ("Duplicate template ratio  >= 0.55", "+0.20", "high_duplicate_templates"),
    ("Unique text ratio  <= 0.40", "+0.12", "low_unique_text"),
    ("'RT @' text share  >= 0.50", "+0.12", "high_rt_at_text"),
    ("Keyword-collection share  >= 0.75  and  n_posts >= 8", "+0.10", "keyword_dominated"),
    ("Burstiness  >= 2.2   and   hour concentration  >= 0.35", "+0.10", "bursty_concentrated_hours"),
    ("IFB_COUNT  >= 20", "+0.08", "high_ifb_count"),
    ("following >= 2000  and  0.7 <= followers/following <= 1.4", "+0.08", "symmetric_mass_follow"),
    ("Missing profile fields  >= 3", "+0.06", "missing_profile_fields"),
]

INK = "#1f2933"
BLUE = "#2f5d8a"
GREY = "#7b8794"
GREEN = "#2f7a4f"
AMBER = "#b3761a"
RED = "#a32d2d"
SLATE = "#4a5568"


def read_counts() -> tuple[Counter, int, Counter]:
    bands: Counter = Counter()
    with io.open(OUT / "rule_based_bot_scores.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            bands[row.get("rule_label") or "?"] += 1
    total = sum(bands.values())
    manual: Counter = Counter()
    with io.open(OUT / "labeled_bots_and_not_bots.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            manual[row.get("manual_label") or "?"] += 1
    return bands, total, manual


def box(ax, cx, cy, w, h, text, *, fc="white", ec=INK, fs=10.5, bold=False, tc=None, style="round"):
    pad = 0.02
    if style == "round":
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle=f"round,pad={pad},rounding_size=1.1",
            linewidth=1.5, facecolor=fc, edgecolor=ec, zorder=3,
        )
    else:
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle=f"square,pad={pad}",
            linewidth=1.5, facecolor=fc, edgecolor=ec, zorder=3,
        )
    ax.add_patch(patch)
    ax.text(
        cx, cy, text, ha="center", va="center", fontsize=fs, zorder=4,
        color=tc or INK, fontweight="bold" if bold else "normal", linespacing=1.35,
    )
    return patch


def diamond(ax, cx, cy, w, h, text, *, fc="#eef4fa", ec=BLUE, fs=10.5):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=ec, linewidth=1.6, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, zorder=4, color=INK, linespacing=1.3)


def arrow(ax, xy_from, xy_to, *, label=None, color=SLATE, lw=1.6, label_dx=0.0, label_dy=0.0,
          fs=9.5, label_color=None, connectionstyle="arc3,rad=0"):
    ax.add_patch(
        FancyArrowPatch(
            xy_from, xy_to, arrowstyle="-|>", mutation_scale=15,
            linewidth=lw, color=color, zorder=2, shrinkA=0, shrinkB=0,
            connectionstyle=connectionstyle,
        )
    )
    if label:
        mx = (xy_from[0] + xy_to[0]) / 2 + label_dx
        my = (xy_from[1] + xy_to[1]) / 2 + label_dy
        ax.text(
            mx, my, label, ha="center", va="center", fontsize=fs,
            color=label_color or color, fontweight="bold", zorder=5,
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.95),
        )


def draw(bands: Counter, total: int) -> None:
    fig, ax = plt.subplots(figsize=(15.6, 15.0))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 132)
    ax.axis("off")

    n_insuf = bands.get("insufficient_posts", 0)
    n_low = bands.get("low_risk", 0)
    n_med = bands.get("medium_risk", 0)
    n_high = bands.get("high_risk", 0)

    ax.text(
        50, 130.6,
        "IFB behavioural-risk rule flow  —  not a verified bot-identity test",
        ha="center", va="center", fontsize=16, fontweight="bold", color=INK,
    )
    ax.text(
        50, 128.0,
        "Manual review is the label. The rule score is an interpretable prior, not ground truth.",
        ha="center", va="center", fontsize=10.5, color=SLATE, style="italic",
    )

    spine_x = 34.0
    rail_x = 75.0
    term_x = 86.0

    # --- entry -------------------------------------------------------------- #
    box(ax, 50, 124.0, 46, 5.0,
        f"START:  {total:,} users with a profile row in IFB.db",
        fc="#eef4fa", ec=BLUE, bold=True)
    arrow(ax, (50, 121.5), (50, 119.2))

    diamond(ax, 50, 115.6, 36, 7.2,
            f"Does the user have >= {MIN_POSTS_FOR_TEXT} usable\nEnglish NLP posts?")
    # No -> insufficient evidence terminal
    arrow(ax, (68, 115.6), (term_x - 13.5, 115.6), label="No", label_dy=1.8, color=RED, label_color=RED)
    box(ax, term_x, 115.6, 27, 8.4,
        f"insufficient_posts\nrule_score = 0.15  (fixed)\n{n_insuf:,} users\nNot scored, not called a bot",
        fc="#f3f4f6", ec=GREY, fs=9.8, bold=False)

    arrow(ax, (50, 112.0), (50, 109.0), label="Yes", label_dx=3.4, color=GREEN, label_color=GREEN)
    box(ax, 50, 106.8, 40, 4.4, "Initialise  rule_score = 0.00", fc="white", ec=INK, fs=10.5)

    # --- the nine additive behavioural tests -------------------------------- #
    arrow(ax, (50, 104.6), (spine_x, 102.0), connectionstyle="arc3,rad=0.0")
    top = 99.5
    step = 6.6
    h = 4.9
    w = 52.0
    for i, (cond, weight, reason) in enumerate(TESTS):
        cy = top - i * step
        diamond(ax, spine_x, cy, w, h, cond, fc="#f7fafc", ec=BLUE, fs=9.8)
        # Yes -> weight bubble on the rail
        arrow(ax, (spine_x + w / 2, cy), (rail_x - 9.0, cy),
              label="Yes", label_dy=1.4, color=GREEN, label_color=GREEN, fs=9)
        box(ax, rail_x, cy, 17.0, 4.0, f"rule_score  {weight}\n{reason}",
            fc="#eaf5ee", ec=GREEN, fs=8.6)
        # No -> straight down to the next test
        if i < len(TESTS) - 1:
            arrow(ax, (spine_x, cy - h / 2), (spine_x, cy - step + h / 2),
                  label="No  (+0.00)", label_dx=-9.6, color=GREY, label_color=GREY, fs=8.6)

    last_y = top - (len(TESTS) - 1) * step
    guard_y = 38.5
    score_y = 30.0

    # rail collects downward into the score node
    arrow(ax, (rail_x, last_y - 2.0), (rail_x, score_y), color=GREEN, lw=1.4)
    arrow(ax, (rail_x, score_y), (58.6, score_y), color=GREEN, lw=1.4)

    # --- verified discount --------------------------------------------------- #
    arrow(ax, (spine_x, last_y - h / 2), (spine_x, guard_y + 2.6), label="No  (+0.00)",
          label_dx=-9.6, color=GREY, label_color=GREY, fs=8.6)
    box(ax, spine_x, guard_y, 52.0, 5.0,
        "Guard:  verified account  AND  unique text ratio >= 0.7\n"
        "->  rule_score = max(0, rule_score - 0.15)",
        fc="#fff8e6", ec=AMBER, fs=9.6)
    arrow(ax, (spine_x, guard_y - 2.6), (spine_x, score_y))
    arrow(ax, (spine_x, score_y), (41.4, score_y))

    box(ax, 50, score_y, 16.4, 4.6, "rule_score\n0.00 – 1.00", fc="#eef4fa", ec=BLUE, bold=True, fs=9.8)

    # --- banding ------------------------------------------------------------- #
    arrow(ax, (50, score_y - 2.3), (50, 24.9))
    diamond(ax, 50, 21.5, 34, 6.6, f"rule_score  >=  {HIGH_CUT}?")
    arrow(ax, (67, 21.5), (term_x - 13.5, 21.5), label="Yes", label_dy=1.7, color=RED, label_color=RED)
    box(ax, term_x, 21.5, 27, 5.8, f"high_risk\n{n_high:,} users",
        fc="#fbeaea", ec=RED, bold=True, fs=10.4)

    arrow(ax, (50, 18.2), (50, 14.9), label="No", label_dx=-3.4, color=GREY, label_color=GREY)
    diamond(ax, 50, 11.5, 34, 6.6, f"rule_score  >=  {MED_CUT}?")
    arrow(ax, (67, 11.5), (term_x - 13.5, 11.5), label="Yes", label_dy=1.7, color=AMBER, label_color=AMBER)
    box(ax, term_x, 11.5, 27, 5.8, f"medium_risk\n{n_med:,} users",
        fc="#fff4e0", ec=AMBER, bold=True, fs=10.4)

    arrow(ax, (50, 8.2), (50, 5.6), label="No", label_dx=-3.4, color=GREY, label_color=GREY)
    box(ax, 50, 3.2, 30, 4.6, f"low_risk   {n_low:,} users", fc="#eaf5ee", ec=GREEN, bold=True, fs=10.4)

    # --- side note (top-left gutter, clear of every shape) ------------------- #
    ax.text(
        1.0, 124.5,
        "Reading the chart\n"
        "•  Every test is independent\n"
        "    and additive.\n"
        "•  Yes adds its weight.\n"
        "•  No adds nothing and control\n"
        "    passes to the next test.\n"
        "•  Weights are transcribed from\n"
        "    rule_risk_score() in\n"
        "    src/bot_detection.py, seed 2026.",
        ha="left", va="top", fontsize=9.0, color=SLATE, linespacing=1.5,
    )
    fig.text(
        0.5, 0.012,
        "This flow produces a behavioural-risk band, NOT a verified bot identity. "
        "No platform suspension list or verified-bot ground truth exists for this corpus, "
        "so is_bot is never asserted as 1.\n"
        "Deleted or empty accounts are insufficient_evidence, never malicious. "
        "The 100 manually reviewed users were stratified by these rule bands, "
        "so rule precision/recall are not unbiased population estimates.",
        ha="center", va="bottom", fontsize=9.4, color=INK, linespacing=1.5,
    )

    fig.savefig(PNG, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {PNG.name}")


def build_pptx(bands: Counter, total: int, manual: Counter) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Emu, Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def title(slide, text, sub=None):
        tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.35), Inches(12.2), Inches(0.9))
        p = tb.text_frame.paragraphs[0]
        p.text = text
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0x1F, 0x29, 0x33)
        if sub:
            tb2 = slide.shapes.add_textbox(Inches(0.55), Inches(1.18), Inches(12.2), Inches(0.5))
            q = tb2.text_frame.paragraphs[0]
            q.text = sub
            q.font.size = Pt(13)
            q.font.italic = True
            q.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)

    def bullets(slide, lines, top=1.85, size=14, width=12.2):
        tb = slide.shapes.add_textbox(Inches(0.55), Inches(top), Inches(width), Inches(5.2))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size = Pt(size)
            p.font.color.rgb = RGBColor(0x1F, 0x29, 0x33)
            p.space_after = Pt(8)

    # slide 1 — framing
    s = prs.slides.add_slide(blank)
    title(s, "Malicious / bot-risk detection flow",
          "Behavioural risk classification — not verified bot identification")
    bullets(s, [
        f"Population: {total:,} unambiguous users with a profile row in IFB.db.",
        "45 features: profile metadata (followers/following, account age, bio, verified, "
        "default image, IFB_COUNT) plus NLP behaviour (boilerplate share, duplicate templates, "
        "unique-text ratio, 'RT @' share, burstiness, hour/day concentration).",
        "The rule score is an interpretable prior built from those features. "
        "It is not ground truth and it is not used as an ML label.",
        f"Manual review of 100 users is the label source: "
        + ", ".join(f"{k} = {v}" for k, v in sorted(manual.items())) + ".",
        "98 of the 100 reviews are usable as ML labels (2 are insufficient_evidence).",
        "The required 200-user post-hoc validation set does not exist and was NOT fabricated: "
        "the corpus ends 2023-12 and live X profiles cannot be aligned in 2026.",
    ])

    # slide 2 — the flowchart
    s = prs.slides.add_slide(blank)
    title(s, "Rule flow: from raw profile to risk band",
          "Every branch is labelled Yes / No. Weights are additive and transcribed from src/bot_detection.py.")
    pic_top = Inches(1.62)
    avail_h = prs.slide_height - pic_top - Inches(0.30)
    pic = s.shapes.add_picture(str(PNG), Inches(0), pic_top, height=avail_h)
    pic.left = Emu(int((prs.slide_width - pic.width) / 2))

    # slide 3 — limits
    s = prs.slides.add_slide(blank)
    title(s, "Why this is not a bot-identity system")
    bullets(s, [
        "No verified bot ground truth exists for this corpus — no platform suspension list, "
        "no verified-bot dataset, no third-party labels.",
        "is_bot is therefore never asserted as 1 in the manual review. "
        "The 100 reviewed users are labelled on observable behaviour only.",
        "Deleted or empty accounts are insufficient_evidence, never malicious. "
        "An account disappearing between 2023 and 2026 is not evidence of automation.",
        "The 100 reviewed users were sampled stratified by rule band "
        f"(low {bands.get('low_risk', 0):,} / medium {bands.get('medium_risk', 0):,} / "
        f"high {bands.get('high_risk', 0):,}), not by simple random sampling. "
        "The high-risk band was heavily enriched, so rule precision and recall measured on "
        "these users are optimistic and are not population estimates.",
        "Live profile inspection was impossible: the corpus ends 2023-12.",
        "Model output is reported as risk_positive, never as 'bot'.",
    ], size=13.5)

    prs.save(str(PPTX))
    print(f"Wrote {PPTX.name} ({len(prs.slides._sldIdLst)} slides)")


def main() -> int:
    bands, total, manual = read_counts()
    print("rule bands:", dict(bands), "total:", total)
    print("manual labels:", dict(manual))
    draw(bands, total)
    build_pptx(bands, total, manual)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
