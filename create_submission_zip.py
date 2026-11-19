"""Build IFB-project-submission.zip for the project partner.

Does not modify IFB.db, does not delete the project folder, and does not
rerun any analysis model. Only packaging files are written:

- SOURCE_DATABASE_NOTE.md
- ZIP_CONTENTS.md
- IFB-project-submission.zip
- optional 7-Zip split volumes if the ZIP exceeds 1.5 GB
"""
from __future__ import annotations

import csv
import io
import os
import stat
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZIP_NAME = "IFB-project-submission.zip"
ZIP_PATH = ROOT / ZIP_NAME
CONTENTS_PATH = ROOT / "ZIP_CONTENTS.md"
NOTE_PATH = ROOT / "SOURCE_DATABASE_NOTE.md"
SPLIT_BYTES = 1_500_000_000  # ~1.5 GB

GUIDELINE_FOLDERS = [
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
]

ROOT_MARKDOWN = [
    "SOURCE_DATABASE_NOTE.md",
    "HOW_TO_RUN.md",
    "requirements.txt",
    "SUBMISSION_EXCLUSIONS.md",
    "INSTRUCTOR_REQUIREMENTS.md",
    "PROJECT_COMPLIANCE_CHECKLIST.md",
    "PROJECT_RISKS_AND_LIMITATIONS.md",
    "CORPUS_MANIFEST.md",
    "DATASET_DECISION.md",
    "TRANSLATION_DECISION.md",
    "TOPIC_MODELING_REPORT.md",
    "BOT_DETECTION_REPORT.md",
    "ENTITY_NETWORK_REPORT.md",
    "NER_ENTITY_ANALYSIS_REPORT.md",
    "EVENT_DETECTION_REPORT.md",
    "SENTIMENT_ANALYSIS_REPORT.md",
    "EMOTION_ANALYSIS_REPORT.md",
    "LANGUAGE_AND_PREPROCESSING_REPORT.md",
    "FINAL_COMPLIANCE_AUDIT_FINAL.md",
    "FINAL_HIGH_PRIORITY_FIXES.md",
    "FINAL_SUBMISSION_CHECKLIST.md",
    "FINAL_REPRODUCIBILITY_CHECKLIST.md",
    "FINAL_READ_ONLY_AUDIT.md",
    "FINAL_MISSING_ITEMS.md",
    "NLP_SAMPLING_PLAN.md",
    "MANUAL_BOT_REVIEW_GUIDE.md",
    "DATABASE_INSPECTION_REPORT.md",
    "project_structure.md",
]

ROOT_FILES = [
    "detected_events.docx",
    "malicious_detection_flow.pptx",
    "create_submission_zip.py",
]

REQUIRED_EXIST = [
    "src",
    "notebooks",
    "outputs",
    "data/primary_author_ids.txt",
    *GUIDELINE_FOLDERS,
    "report/final_project_report.docx",
    "presentation/final_project_presentation.pptx",
    "detected_events.docx",
    "malicious_detection_flow.pptx",
    "FINAL_COMPLIANCE_AUDIT_FINAL.md",
    "FINAL_SUBMISSION_CHECKLIST.md",
    "requirements.txt",
    "HOW_TO_RUN.md",
    "SOURCE_DATABASE_NOTE.md",
]

SKIP_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".cursor",
    "scratch",
    "models",
}
SKIP_FILE_NAMES = {
    "IFB.db",
    "topic_model.pkl",
    "Untitled0.ipynb",
    "FINAL_COMPLIANCE_AUDIT.md",
    ZIP_NAME,
}
SKIP_SUFFIXES = {".db", ".pyc", ".pyo", ".pyd", ".log", ".wal", ".shm"}
SKIP_PREFIXES = (".env",)
SECRET_HINTS = ("credential", "secret", "password", ".pem", "id_rsa")


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_source_note() -> None:
    if NOTE_PATH.exists():
        return
    NOTE_PATH.write_text(
        "# Source database note\n\n"
        "`IFB.db` is the original source database supplied by the project partner.\n",
        encoding="utf-8",
    )


def is_skipped_dir(path: Path) -> bool:
    return path.name in SKIP_DIR_NAMES or path.name.startswith(".")


def is_skipped_file(path: Path) -> tuple[bool, str]:
    name = path.name
    if name in SKIP_FILE_NAMES:
        return True, f"explicit exclude: {name}"
    if name.endswith(".db") or path.suffix.lower() in SKIP_SUFFIXES:
        return True, "database or cache artifact"
    if name.startswith(SKIP_PREFIXES):
        return True, "environment / secret file"
    lower = name.lower()
    if any(h in lower for h in SECRET_HINTS):
        return True, "possible secret / credential"
    if name.startswith("IFB-project-submission.") and (
        name.endswith(".zip") or ".7z." in name or name.endswith(".7z")
    ):
        return True, "the submission archive itself"
    return False, ""


def collect_files() -> tuple[list[Path], list[tuple[str, str]]]:
    included: list[Path] = []
    excluded: list[tuple[str, str]] = []

    def add_tree(rel: str) -> None:
        base = ROOT / rel
        if not base.exists():
            if rel in {"ZIP_CONTENTS.md", "create_submission_zip.py"}:
                return
            raise FileNotFoundError(rel)
        if base.is_file():
            skip, why = is_skipped_file(base)
            if skip:
                excluded.append((rel.replace("\\", "/"), why))
                return
            included.append(base)
            return
        for dirpath, dirnames, filenames in os.walk(base):
            dpath = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not is_skipped_dir(dpath / d)]
            for fn in filenames:
                p = dpath / fn
                rel_p = p.relative_to(ROOT).as_posix()
                skip, why = is_skipped_file(p)
                if skip:
                    excluded.append((rel_p, why))
                    continue
                included.append(p)

    add_tree("src")
    add_tree("notebooks")
    add_tree("outputs")
    add_tree("report")
    add_tree("presentation")
    add_tree("data/primary_author_ids.txt")
    data_readme = ROOT / "data" / "README.md"
    if data_readme.exists():
        included.append(data_readme)
    for folder in GUIDELINE_FOLDERS:
        add_tree(folder)
    for name in ROOT_MARKDOWN + ROOT_FILES:
        add_tree(name)

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in included:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
    return unique, excluded


def verify_required() -> list[str]:
    missing = []
    for rel in REQUIRED_EXIST:
        if not (ROOT / rel).exists():
            missing.append(rel)
    return missing


def _csv(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def verify_canonical() -> dict[str, tuple[object, object, bool]]:
    ids = [ln for ln in (ROOT / "data" / "primary_author_ids.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    topics = _csv("outputs/final_topics.csv")
    named = [r for r in topics if float(r["topic_id"]) >= 0]
    summary = _csv("outputs/entity_network_summary.csv")
    comb = next(r for r in summary if r["graph"] == "combined_min_edge")
    edges = _csv("outputs/entity_network_edges.csv")
    events = _csv("outputs/detected_events.csv")
    evid = _csv("outputs/event_tweet_evidence.csv")
    lab = _csv("outputs/labeled_bots_and_not_bots.csv")
    usable = [r for r in lab if r.get("manual_label") != "insufficient_evidence"]
    exp = _csv("outputs/bot_detection_experiments.csv")
    k5 = [r for r in exp if "kfold_k5_mean" in (r.get("training_type") or "")]
    loo = [r for r in exp if "loocv" in (r.get("training_type") or "")]
    users = _csv("outputs/user_sentiment_summary.csv")
    dist = _csv("outputs/sentiment_distribution.csv")
    scored = sum(
        int(float(r["n_raw"]))
        for r in dist
        if r.get("corpus") == "combined_unweighted"
    )
    results = {
        "users": (38576, len(ids), len(ids) == 38576),
        "scored_posts": (742942, scored, scored == 742942),
        "scored_users": (35250, len(users), len(users) == 35250),
        "events": (4, len(events), len(events) == 4),
        "network_nodes": (1076, int(float(comb["n_nodes"])), int(float(comb["n_nodes"])) == 1076),
        "network_edges": (2578, int(float(comb["n_edges"])), int(float(comb["n_edges"])) == 2578),
        "edge_file_rows": (2578, len(edges), len(edges) == 2578),
        "named_topics": (18, len(named), len(named) == 18),
        "manual_reviews": (100, len(lab), len(lab) == 100),
        "usable_ml_labels": (98, len(usable), len(usable) == 98),
        "k5_train": (78, int(float(k5[0]["n_train"])) if k5 else None, bool(k5) and int(float(k5[0]["n_train"])) == 78),
        "loocv_train": (97, int(float(loo[0]["n_train"])) if loo else None, bool(loo) and int(float(loo[0]["n_train"])) == 97),
        "e03_evidence": (5, sum(1 for r in evid if r.get("event_id") == "E03"), sum(1 for r in evid if r.get("event_id") == "E03") == 5),
    }
    return results


def ifb_mtime() -> str:
    p = ROOT / "IFB.db"
    if not p.exists():
        return "IFB.db not present in this working copy"
    ts = datetime.fromtimestamp(p.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def write_zip(files: list[Path]) -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        for p in files:
            arc = p.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(filename=arc)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            st = p.stat()
            info.date_time = datetime.fromtimestamp(st.st_mtime).timetuple()[:6]
            info.external_attr = (st.st_mode & 0o777) << 16
            # UTF-8 filename flag
            info.flag_bits |= 0x800
            with p.open("rb") as fh:
                zf.writestr(info, fh.read())


def inspect_zip() -> dict:
    names: list[str] = []
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        names = zf.namelist()
    db_hits = [n for n in names if n.lower().endswith(".db") or n.endswith("/IFB.db") or n == "IFB.db" or n.endswith("IFB.db")]
    stale = [n for n in names if n == "FINAL_COMPLIANCE_AUDIT.md" or n.endswith("/FINAL_COMPLIANCE_AUDIT.md")]
    scratch = [n for n in names if n.startswith("scratch/") or n.endswith("Untitled0.ipynb")]
    pkl = [n for n in names if n.endswith("topic_model.pkl")]
    return {
        "n_members": len(names),
        "db_hits": db_hits,
        "stale": stale,
        "scratch": scratch,
        "pkl": pkl,
        "names": names,
    }


def maybe_split(zip_size: int) -> list[Path]:
    if zip_size <= SPLIT_BYTES:
        return []
    parts: list[Path] = []
    # Prefer 7-Zip if present; otherwise write numbered 1.5 GB slices of the ZIP.
    seven = Path(r"C:\Program Files\7-Zip\7z.exe")
    if seven.exists():
        import subprocess

        prefix = ROOT / "IFB-project-submission.7z"
        for old in ROOT.glob("IFB-project-submission.7z.*"):
            old.unlink()
        subprocess.check_call(
            [str(seven), "a", f"-v{SPLIT_BYTES}b", "-mx=1", str(prefix), str(ZIP_PATH.name)],
            cwd=str(ROOT),
        )
        parts = sorted(ROOT.glob("IFB-project-submission.7z.*"))
        return parts

    idx = 1
    with ZIP_PATH.open("rb") as fh:
        while True:
            chunk = fh.read(SPLIT_BYTES)
            if not chunk:
                break
            dest = ROOT / f"IFB-project-submission.7z.{idx:03d}"
            dest.write_bytes(chunk)
            parts.append(dest)
            idx += 1
    return parts


def write_contents(
    files: list[Path],
    excluded: list[tuple[str, str]],
    canon: dict[str, tuple[object, object, bool]],
    zip_info: dict,
    zip_size: int,
    uncompressed: int,
    parts: list[Path],
    missing: list[str],
) -> None:
    top = sorted({(p.relative_to(ROOT).parts[0]) for p in files})
    required_listed = [
        "src/",
        "notebooks/",
        "outputs/  (except topic_model.pkl)",
        "data/primary_author_ids.txt",
        "data/README.md",
        *[f"{g}/" for g in GUIDELINE_FOLDERS],
        "report/final_project_report.docx",
        "presentation/final_project_presentation.pptx",
        "detected_events.docx",
        "malicious_detection_flow.pptx",
        "SOURCE_DATABASE_NOTE.md",
        "HOW_TO_RUN.md",
        "requirements.txt",
        "FINAL_COMPLIANCE_AUDIT_FINAL.md",
        "FINAL_SUBMISSION_CHECKLIST.md",
        "create_submission_zip.py",
        "ZIP_CONTENTS.md",
    ]
    lines = [
        "# ZIP contents — IFB-project-submission",
        "",
        f"Built: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Archive: `{ZIP_NAME}`",
        "",
        "## Totals",
        "",
        f"- Included files: **{len(files)}**",
        f"- ZIP members: **{zip_info['n_members']}**",
        f"- Uncompressed size: **{uncompressed / 1_000_000:.1f} MB** ({uncompressed:,} bytes)",
        f"- ZIP size: **{zip_size / 1_000_000:.1f} MB** ({zip_size:,} bytes)",
        f"- Split volumes: **{'yes — ' + ', '.join(p.name for p in parts) if parts else 'no'}**",
        "",
        "## Included top-level folders / files",
        "",
    ]
    for t in top:
        p = ROOT / t
        kind = "folder" if p.is_dir() else "file"
        lines.append(f"- `{t}` ({kind})")
    lines += [
        "",
        "## Required files (checklist)",
        "",
    ]
    for rel in required_listed:
        clean = rel.split()[0].rstrip("/")
        exists = any(
            p.relative_to(ROOT).as_posix() == clean
            or p.relative_to(ROOT).as_posix().startswith(clean.rstrip("/") + "/")
            or (clean.endswith("/") is False and p.name == Path(clean).name and clean in p.relative_to(ROOT).as_posix())
            for p in files
        )
        # simpler existence in the zip member list
        exists = any(
            n == clean or n.startswith(clean.rstrip("/") + "/") or n.endswith("/" + Path(clean).name)
            for n in zip_info["names"]
        ) or (ROOT / clean).exists() and any(
            p.relative_to(ROOT).as_posix() == clean or p.relative_to(ROOT).as_posix().startswith(clean + "/")
            for p in files
        )
        lines.append(f"- `{rel}` — {'included' if exists else 'MISSING'}")
    lines += [
        "",
        "## Excluded files and why",
        "",
        "| Path | Reason |",
        "|------|--------|",
        "| `IFB.db` | Original partner source database; opened read-only; not modified; partner already has it |",
        "| `data/*.db` | Large intermediate SQLite artifacts |",
        "| `outputs/topic_model.pkl` | 480 MB derived BERTopic model |",
        "| `scratch/` and `Untitled0.ipynb` | Colab leftover; write-capable IFB.db path |",
        "| `FINAL_COMPLIANCE_AUDIT.md` | Stale audit; superseded by `FINAL_COMPLIANCE_AUDIT_FINAL.md` |",
        "| `__pycache__/`, `.venv/`, `node_modules/`, `.git/`, `.cursor/` | Caches / environments / editor state |",
        "| `*.log`, secrets, credentials | Not part of the graded submission |",
    ]
    extra = [(p, w) for p, w in excluded if not p.endswith(".db") and "topic_model.pkl" not in p]
    # keep the list short: only notable extras
    notable = [e for e in excluded if e[0].endswith(".db") or "topic_model.pkl" in e[0] or "FINAL_COMPLIANCE" in e[0] or "Untitled" in e[0]]
    for p, w in notable:
        lines.append(f"| `{p}` | {w} |")
    lines += [
        "",
        "## Canonical-number validation",
        "",
        "| Claim | Expected | Observed | Pass |",
        "|-------|---------:|---------:|:----:|",
    ]
    for key, (exp, obs, ok) in canon.items():
        lines.append(f"| {key} | {exp} | {obs} | {'yes' if ok else 'NO'} |")
    lines += [
        "",
        "## Archive validation",
        "",
        f"- Required-path missing before ZIP: {missing or 'none'}",
        f"- Database files inside ZIP: {zip_info['db_hits'] or 'none'}",
        f"- Stale `FINAL_COMPLIANCE_AUDIT.md` inside ZIP: {zip_info['stale'] or 'none'}",
        f"- `scratch/` or `Untitled0.ipynb` inside ZIP: {zip_info['scratch'] or 'none'}",
        f"- `topic_model.pkl` inside ZIP: {zip_info['pkl'] or 'none'}",
        f"- `IFB.db` last write time (unchanged): {ifb_mtime()}",
        "",
        "## Split-volume instructions",
        "",
    ]
    if parts:
        lines += [
            "The single ZIP was larger than ~1.5 GB, so 7-Zip-compatible split volumes were also written:",
            "",
        ]
        for p in parts:
            lines.append(f"- `{p.name}` ({p.stat().st_size:,} bytes)")
        lines += [
            "",
            "Download **every** part into the **same folder**. Extract starting from `.001`",
            "(open `IFB-project-submission.7z.001` in 7-Zip, or run `7z x IFB-project-submission.7z.001`).",
            "All parts are required; a missing part will fail extraction.",
        ]
    else:
        lines += [
            "No split volumes were created. The single file `IFB-project-submission.zip` is within a convenient transfer size.",
        ]
    lines += [
        "",
        "## How this ZIP was built",
        "",
        "```",
        "python create_submission_zip.py",
        "```",
        "",
        "No analysis model was rerun. `IFB.db` was not opened for writing.",
        "",
    ]
    CONTENTS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ensure_source_note()
    missing = verify_required()
    if missing:
        print("MISSING required paths:", missing)
        return 1
    canon = verify_canonical()
    failed = [k for k, v in canon.items() if not v[2]]
    print("canonical checks:")
    for k, (e, o, ok) in canon.items():
        print(f"  {k}: expected {e} observed {o} {'OK' if ok else 'FAIL'}")
    if failed:
        print("canonical FAIL", failed)
        return 1

    files, excluded = collect_files()
    uncompressed = sum(p.stat().st_size for p in files)
    names_preview = [p.relative_to(ROOT).as_posix() for p in files] + ["ZIP_CONTENTS.md"]
    write_contents(files, excluded, canon, {
        "n_members": len(files) + 1,
        "db_hits": [],
        "stale": [],
        "scratch": [],
        "pkl": [],
        "names": names_preview,
    }, 0, uncompressed, [], missing)
    if CONTENTS_PATH.resolve() not in {p.resolve() for p in files}:
        files.append(CONTENTS_PATH)

    print(f"packing {len(files)} files, uncompressed {uncompressed/1e6:.1f} MB")
    write_zip(files)
    zip_size = ZIP_PATH.stat().st_size
    print(f"wrote {ZIP_PATH.name} ({zip_size/1e6:.1f} MB)")

    zip_info = inspect_zip()
    if zip_info["db_hits"] or zip_info["stale"] or zip_info["scratch"] or zip_info["pkl"]:
        print("ZIP validation failed", {k: zip_info[k] for k in ("db_hits", "stale", "scratch", "pkl")})
        return 1

    parts = maybe_split(zip_size)
    write_contents(files, excluded, canon, zip_info, zip_size, uncompressed, parts, missing)

    print("IFB.db mtime", ifb_mtime())
    print("excluded dbs from walk:", [e[0] for e in excluded if e[0].endswith(".db")])
    print("ZIP_PATH", ZIP_PATH)
    print("ZIP_SIZE_BYTES", zip_size)
    print("SPLIT", [p.name for p in parts] or "none")
    print("N_FILES", len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
