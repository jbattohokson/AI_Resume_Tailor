"""Command line entry point.

    python -m tailor resume --resume my_resume.txt --jd jobs/acme.txt --buzzwords "SQL, dbt"
    python -m tailor cover  --resume my_resume.txt --jd jobs/acme.txt --notes jobs/acme_notes.txt
    python -m tailor batch  --resume my_resume.txt --jobs-dir jobs/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from tailor.crew import TailorResult, tailor_resume, write_cover_letter
from tailor.llm import MissingProviderError


def _read(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        sys.exit(f"File not found: {p}")
    return p.read_text(encoding="utf-8")


def _save(result: TailorResult, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.text + "\n", encoding="utf-8")
    status = "passed" if result.report.ok else "FLAGGED, review before using"
    print(f"{out}  ({status}, {result.attempts} attempt(s))")
    if not result.report.ok:
        print(result.report.as_feedback())


def _batch(args: argparse.Namespace, resume: str) -> None:
    jobs = sorted(Path(args.jobs_dir).glob("*.txt"))
    jobs = [j for j in jobs if not j.stem.endswith("_notes")]
    if not jobs:
        sys.exit(f"No .txt job descriptions in {args.jobs_dir}")
    for jd_path in jobs:
        jd = jd_path.read_text(encoding="utf-8")
        _save(tailor_resume(resume, jd, args.buzzwords), Path(args.out) / f"{jd_path.stem}_resume.txt")
        notes_path = jd_path.with_name(f"{jd_path.stem}_notes.txt")
        notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        _save(write_cover_letter(resume, jd, notes), Path(args.out) / f"{jd_path.stem}_cover.txt")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="tailor", description="Fact-checked resume and cover letter tailoring.")
    parser.add_argument("mode", choices=["resume", "cover", "batch"])
    parser.add_argument("--resume", required=True, help="Your baseline resume as a .txt file")
    parser.add_argument("--jd", help="Job description .txt (resume and cover modes)")
    parser.add_argument("--buzzwords", default="", help="Comma-separated keywords to work in")
    parser.add_argument("--notes", help="Company notes .txt for the cover letter hook")
    parser.add_argument("--jobs-dir", help="Folder of job description .txt files (batch mode)")
    parser.add_argument("--out", default="output", help="Output folder")
    args = parser.parse_args()

    resume = _read(args.resume)
    try:
        if args.mode == "batch":
            if not args.jobs_dir:
                sys.exit("batch mode needs --jobs-dir")
            _batch(args, resume)
            return
        jd = _read(args.jd)
        if not jd:
            sys.exit("--jd is required for resume and cover modes")
        name = Path(args.jd).stem
        if args.mode == "resume":
            _save(tailor_resume(resume, jd, args.buzzwords), Path(args.out) / f"{name}_resume.txt")
        else:
            _save(write_cover_letter(resume, jd, _read(args.notes)), Path(args.out) / f"{name}_cover.txt")
    except MissingProviderError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
