"""Deterministic checks that run on every model output.

The model writes. Python decides whether the writing is allowed out. A small local
model will happily invent a metric or a tool, so these checks are the safety net,
not the prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?(?:%|[kKmMbB]\b|x\b)?")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+")
CAPITALIZED_RE = re.compile(r"\b[A-Z][A-Za-z0-9+#.&-]*[A-Za-z0-9+#]\b")
# Change log entries look like:  New: "the edited bullet"  (straight or curly quotes)
LOGGED_NEW_RE = re.compile(r'New:\s*["\u201c](.+?)["\u201d]', re.S)


def _load_list(name: str) -> list[str]:
    path = CONFIG_DIR / name
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


@dataclass
class GuardReport:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_feedback(self) -> str:
        return "\n".join(f"- {p}" for p in self.problems)


def _normalize_number(token: str) -> str:
    # "$1,200", "1200" and "1,200" are the same fact; formatting changes aren't fabrication.
    return token.replace(",", "").replace(" ", "").replace("$", "").lower()


def numbers_in(text: str) -> set[str]:
    return {_normalize_number(m.group()) for m in NUMBER_RE.finditer(text)}


def new_numbers(output: str, *sources: str) -> set[str]:
    """Numbers in the output that appear in none of the source texts."""
    allowed: set[str] = set()
    for src in sources:
        allowed |= numbers_in(src)
    return numbers_in(output) - allowed


def new_capitalized_terms(output: str, *sources: str) -> set[str]:
    """Capitalized terms (tools, companies, titles) the model introduced on its own."""
    source_text = " ".join(sources).lower()
    ignore = {w.lower() for w in _load_list("ignore_terms.txt")}
    found = set()
    for m in CAPITALIZED_RE.finditer(output):
        term = m.group()
        if term.lower() in ignore or term.lower() in source_text:
            continue
        # Verbs that open a bullet or sentence are capitalized by grammar, not because they're names.
        before = output[: m.start()].rstrip(" \t")
        if not before or before[-1] in "\n.:;-*•|" or before.endswith(("- ", "• ")):
            continue
        found.add(term)
    return found


def banned_words_in(text: str) -> list[str]:
    lowered = text.lower()
    return [w for w in _load_list("banned_words.txt") if re.search(rf"\b{re.escape(w.lower())}\b", lowered)]


def blocked_claims_in(output: str, resume: str) -> list[str]:
    """Skills you have said you can't defend, added when the resume doesn't already list them."""
    hits = []
    for claim in _load_list("blocked_claims.txt"):
        pattern = rf"\b{re.escape(claim.lower())}\b"
        if re.search(pattern, output.lower()) and not re.search(pattern, resume.lower()):
            hits.append(claim)
    return hits


def check_style(text: str, report: GuardReport) -> None:
    if "—" in text:
        report.problems.append("Remove em dashes. Use a comma, period or restructure.")
    if "```" in text:
        report.problems.append("Plain text only. No code fences.")
    banned = banned_words_in(text)
    if banned:
        report.problems.append(f"Banned words used: {', '.join(banned)}.")


def _squash(text: str) -> str:
    return " ".join(text.split()).lower()


def unapplied_log_edits(resume_part: str, change_log: str) -> list[str]:
    """Edits the change log claims that don't appear in the resume text.

    Found in a real run: a 7B model logged an edit ("...4 dashboards using Tableau") and then
    returned the original bullet unchanged, so the log described a resume that didn't exist.
    """
    body = _squash(resume_part)
    return [new for new in LOGGED_NEW_RE.findall(change_log) if _squash(new) not in body]


def check_resume(output: str, resume: str, jd: str, buzzwords: str) -> GuardReport:
    report = GuardReport()
    resume_part, _, change_log = output.partition("CHANGE LOG")
    if not change_log.strip():
        report.problems.append("Missing a 'CHANGE LOG' section after the resume.")

    invented = new_numbers(resume_part, resume)
    if invented:
        report.problems.append(
            f"Numbers not in the original resume: {', '.join(sorted(invented))}. Never add or change metrics."
        )
    blocked = blocked_claims_in(resume_part, resume)
    if blocked:
        report.problems.append(f"Added skills you can't defend: {', '.join(blocked)}. Remove them.")
    new_terms = new_capitalized_terms(resume_part, resume, jd, buzzwords)
    if new_terms:
        report.problems.append(
            f"New names or tools not in the resume or job description: {', '.join(sorted(new_terms))}."
        )
    missing_edits = unapplied_log_edits(resume_part, change_log)
    if missing_edits:
        report.problems.append(
            "The change log lists edits that aren't in the resume: "
            + "; ".join(f'"{m[:80]}"' for m in missing_edits)
            + ". Apply each edit to the resume text, or drop it from the log."
        )
    check_style(resume_part, report)
    return report


def check_cover_letter(output: str, resume: str, jd: str, notes: str) -> GuardReport:
    report = GuardReport()
    body = output.strip()
    sentences = SENTENCE_RE.findall(body)
    if not 7 <= len(sentences) <= 9:
        report.problems.append(f"Cover letter has {len(sentences)} sentences. It must have 7 to 9.")
    if re.match(r"\s*(dear[^\n]*\n+)?\s*i am writing", body, re.I):
        report.problems.append("Don't open with 'I am writing...'. Open with the company's work.")
    if "!" in body:
        report.problems.append("No exclamation points.")
    invented = new_numbers(body, resume, jd, notes)
    if invented:
        report.problems.append(f"Numbers not found in your resume, the JD or your notes: {', '.join(sorted(invented))}.")
    check_style(body, report)
    return report
