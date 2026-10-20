"""Two crews: resume tailoring (Mode A) and cover letters (Mode B).

Each run goes model -> guards -> retry with the guard's feedback. After MAX_RETRIES
failed attempts the last draft comes back flagged instead of silently passing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from crewai import Agent, BaseLLM, Crew, Process, Task

from tailor.guards import GuardReport, check_cover_letter, check_resume
from tailor.llm import get_llm

PROTOCOL = (Path(__file__).resolve().parent.parent / "config" / "protocol.md").read_text(encoding="utf-8")
MAX_RETRIES = int(os.getenv("TAILOR_MAX_RETRIES", "2"))


@dataclass
class TailorResult:
    text: str
    report: GuardReport
    attempts: int


def _agent(role: str, goal: str, backstory: str, llm: BaseLLM) -> Agent:
    return Agent(role=role, goal=goal, backstory=f"{backstory}\n\n{PROTOCOL}", llm=llm,
                 allow_delegation=False, verbose=os.getenv("CREW_VERBOSE") == "1")


def _feedback_block(feedback: str) -> str:
    if not feedback:
        return ""
    return ("\n\nYour previous draft was rejected by the fact checker. Fix every item below "
            f"and change nothing else:\n{feedback}")


def build_resume_crew(llm: BaseLLM, feedback: str = "") -> Crew:
    analyst = _agent(
        "Job Description Analyst",
        "Find which job description terms the existing resume can honestly support",
        "You compare job descriptions to resumes line by line. You never suggest a term the "
        "resume can't back up.", llm)
    editor = _agent(
        "Resume Editor",
        "Make small, accurate edits that add supported keywords without changing any facts",
        "You edit resumes surgically. You'd rather leave a keyword out than stretch the truth.", llm)

    match = Task(
        description=(
            "Job description:\n{jd}\n\nTarget keywords:\n{buzzwords}\n\nResume:\n{resume}\n\n"
            "List each keyword the resume genuinely supports, the exact resume line it fits, and "
            "the keywords it can't support."),
        expected_output="Two lists: supported keywords with the matching resume line, and unsupported keywords.",
        agent=analyst)
    edit = Task(
        description=(
            "Using only the supported keywords from the analysis, edit this resume:\n{resume}\n\n"
            "Output the full updated resume in plain text. Then a line that says exactly CHANGE LOG, "
            "followed by one bullet per changed line showing the old line, the new line and why."
            + _feedback_block(feedback)),
        expected_output="The full plain-text resume, then CHANGE LOG with one bullet per change.",
        agent=editor, context=[match])
    return Crew(agents=[analyst, editor], tasks=[match, edit], process=Process.sequential, verbose=False)


def build_cover_letter_crew(llm: BaseLLM, feedback: str = "") -> Crew:
    hook = _agent(
        "Company Hook Finder",
        "Pick one specific, real initiative from the company notes to open the letter",
        "You only use facts that are in the notes or job description. If the notes are thin, "
        "you say so and pick the most concrete detail available.", llm)
    writer = _agent(
        "Cover Letter Writer",
        "Write a 7 to 9 sentence cover letter that sounds like a person, not a template",
        "You write short, specific letters built on one or two real projects from the resume.", llm)

    pick = Task(
        description=("Company notes:\n{notes}\n\nJob description:\n{jd}\n\n"
                     "Name the single most specific initiative or problem to open with and quote the "
                     "line it comes from."),
        expected_output="One opening hook and its source line.", agent=hook)
    write = Task(
        description=(
            "Resume:\n{resume}\n\nWrite the cover letter. Open with the hook, never with 'I am writing'. "
            "Use one or two resume projects with their real numbers (situation, action, result). Close "
            "with a short request for a conversation. Exactly 7 to 9 sentences total. Plain text, "
            "no exclamation points." + _feedback_block(feedback)),
        expected_output="A 7 to 9 sentence plain-text cover letter.", agent=writer, context=[pick])
    return Crew(agents=[hook, writer], tasks=[pick, write], process=Process.sequential, verbose=False)


def _run(build, check, inputs: dict, llm: BaseLLM) -> TailorResult:
    feedback, text, report = "", "", GuardReport(["Model never ran."])
    for attempt in range(1, MAX_RETRIES + 2):
        text = str(build(llm, feedback).kickoff(inputs=inputs).raw).strip()
        report = check(text)
        if report.ok:
            return TailorResult(text, report, attempt)
        feedback = report.as_feedback()
    return TailorResult(text, report, MAX_RETRIES + 1)


def tailor_resume(resume: str, jd: str, buzzwords: str = "", stub: BaseLLM | None = None) -> TailorResult:
    llm = get_llm(stub)
    inputs = {"resume": resume, "jd": jd, "buzzwords": buzzwords or "(none given)"}
    return _run(build_resume_crew, lambda out: check_resume(out, resume, jd, buzzwords), inputs, llm)


def write_cover_letter(resume: str, jd: str, notes: str = "", stub: BaseLLM | None = None) -> TailorResult:
    llm = get_llm(stub)
    inputs = {"resume": resume, "jd": jd, "notes": notes or "(no notes given; use the job description)"}
    return _run(build_cover_letter_crew, lambda out: check_cover_letter(out, resume, jd, notes), inputs, llm)
