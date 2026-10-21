"""End-to-end crew runs against a scripted model: wiring, retries and the flagged fallback."""
from tailor.crew import max_retries, tailor_resume, write_cover_letter
from tests.test_guards import GOOD_LETTER, JD, RESUME

ANALYSIS = "Supported: SQL, Tableau. Unsupported: dbt, Salesforce."
CLEAN = RESUME.replace("Python, SQL, Tableau.", "Python, SQL & Tableau dashboards.") + "\nCHANGE LOG\n- Added 'dashboards' to summary"
FABRICATED = RESUME.replace("DealerSocket CRM", "Salesforce CRM") + "\nCHANGE LOG\n- Swapped CRM"


def test_clean_edit_passes_first_try(scripted):
    result = tailor_resume(RESUME, JD, "SQL, Tableau", stub=scripted(ANALYSIS, CLEAN))
    assert result.report.ok and result.attempts == 1


def test_fabrication_triggers_retry_with_feedback(scripted):
    llm = scripted(ANALYSIS, FABRICATED, ANALYSIS, CLEAN)
    result = tailor_resume(RESUME, JD, "SQL, Tableau", stub=llm)
    assert result.report.ok and result.attempts == 2
    # The second editor prompt must carry the fact checker's complaint.
    assert "Salesforce" in str(llm.prompts[-1])


def test_gives_up_and_flags_after_max_retries(scripted):
    replies = [ANALYSIS, FABRICATED] * (max_retries() + 1)
    result = tailor_resume(RESUME, JD, "", stub=scripted(*replies))
    assert not result.report.ok and result.attempts == max_retries() + 1


def test_cover_letter_crew(scripted):
    result = write_cover_letter(RESUME, JD, "", stub=scripted("Hook: shared Tableau workbook", GOOD_LETTER))
    assert result.report.ok, result.report.problems
