from pathlib import Path

from tailor.guards import SENTENCE_RE, check_cover_letter, check_resume, new_capitalized_terms, new_numbers

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
RESUME = (EXAMPLES / "sample_resume.txt").read_text()
JD = (Path(__file__).parent / "fixtures" / "acme_data_analyst.txt").read_text()


def test_unchanged_resume_with_log_passes():
    report = check_resume(RESUME + "\nCHANGE LOG\n- No changes", RESUME, JD, "")
    assert report.ok, report.problems


def test_missing_change_log_fails():
    assert not check_resume(RESUME, RESUME, JD, "").ok


def test_invented_metric_is_caught():
    edited = RESUME.replace("14 vehicle sales", "22 vehicle sales") + "\nCHANGE LOG\n- x"
    report = check_resume(edited, RESUME, JD, "")
    assert any("22" in p for p in report.problems)


def test_blocked_skill_is_caught_even_if_jd_mentions_it():
    edited = RESUME.replace("DealerSocket CRM", "DealerSocket & Salesforce CRM") + "\nCHANGE LOG\n- x"
    report = check_resume(edited, RESUME, JD, "")
    assert any("Salesforce" in p for p in report.problems)


def test_new_tool_mid_sentence_is_flagged_but_new_opening_verb_is_not():
    edited = RESUME.replace("Built a 3-step pipeline", "Engineered a 3-step Airbyte pipeline")
    terms = new_capitalized_terms(edited, RESUME, JD)
    assert "Airbyte" in terms
    assert "Engineered" not in terms


def test_em_dash_and_banned_word_are_caught():
    edited = RESUME.replace("Python, SQL, Tableau.", "Python, SQL, Tableau — a robust stack.") + "\nCHANGE LOG\n- x"
    problems = " ".join(check_resume(edited, RESUME, JD, "").problems)
    assert "em dash" in problems and "robust" in problems


def test_change_log_edit_missing_from_resume_is_caught():
    # Reproduces a real qwen2.5:7b output: the log describes an edit the resume never got.
    log = ('\nCHANGE LOG\n- Old: "exports 4 Tableau views"\n'
           '  New: "exports 4 dashboards using Tableau" | Why: JD asks for dashboards')
    report = check_resume(RESUME + log, RESUME, JD, "")
    assert any("change log lists edits" in p for p in report.problems)


def test_change_log_edit_that_was_applied_passes():
    edited = RESUME.replace("exports 4 Tableau views", "exports 4 Tableau dashboards")
    log = '\nCHANGE LOG\n- Old: "exports 4 Tableau views"\n  New: \u201cexports 4 Tableau dashboards\u201d | Why: JD wording'
    report = check_resume(edited + log, RESUME, JD, "")
    assert report.ok, report.problems


def test_numbers_keep_formatting_variants_equal():
    assert not new_numbers("$1,200 and 15%", "1200 dollars, 15 %")


GOOD_LETTER = (
    "Acme moved sales reporting into a shared Tableau workbook this year. That is the kind of work I want to do. "
    "In a retail project I found a -1.5% gross margin on US bike sales. "
    "I built a 3-step pipeline that fed 4 Tableau views. "
    "At Bayside Motors I cut follow-up time from 3 days to 1 day. "
    "I did it with a tracker the whole team used. "
    "I'd like to bring that habit to your sales reporting. "
    "Could we talk this week?"
)


def test_good_cover_letter_passes():
    report = check_cover_letter(GOOD_LETTER, RESUME, JD, "")
    assert report.ok, report.problems


def test_cover_letter_length_and_opening_rules():
    short = "I am writing to apply. I like data. Thanks."
    problems = " ".join(check_cover_letter(short, RESUME, JD, "").problems)
    assert "7 to 9" in problems and "I am writing" in problems


def test_banned_word_forms_and_placeholders_are_caught():
    # Both slipped through in a real qwen2.5:7b cover letter for the BILL posting.
    letter = GOOD_LETTER.replace("That is the kind of work I want to do.",
                                 "I would enjoy leveraging that at [Company Name].")
    problems = " ".join(check_cover_letter(letter, RESUME, JD, "").problems)
    assert "leverage" in problems and "[Company Name]" in problems


def test_stem_matching_does_not_flag_unrelated_words():
    from tailor.guards import banned_words_in
    assert banned_words_in("I fostered a dynamic team") == ["foster", "dynamic"]
    assert banned_words_in("Leverett Street") == []  # shares letters but not the stem "leverag"
    # Accepted trade-off: other forms of a banned word are flagged too, even literal ones.
    assert banned_words_in("a landscaping crew") == ["landscape"]

def test_decimal_does_not_split_a_sentence():
    assert len(SENTENCE_RE.findall("I found a -1.5% margin. Could we talk?")) == 2


# Audit 2026-10-21: gaps found by feeding the guards adversarial drafts


def _letter(*middle):
    opening = "Acme is rebuilding how dealers price inventory."
    closing = ["I work well with finance teams.", "I like hard problems.",
               "I would value a conversation.", "Thank you for your time."]
    return " ".join([opening, *middle, *closing])


def test_cover_letter_blocked_claim_is_caught():
    letter = _letter("I ran Salesforce reporting for a sales team.", "I keep dashboards simple.")
    report = check_cover_letter(letter, RESUME, JD, "")
    assert any("Salesforce" in p for p in report.problems), report.problems


def test_cover_letter_new_tool_is_caught():
    letter = _letter("I built pipelines in Airbyte every week.", "I keep dashboards simple.")
    report = check_cover_letter(letter, RESUME, JD, "")
    assert any("Airbyte" in p for p in report.problems), report.problems


def test_spelled_out_quantities_are_caught():
    letter = _letter("I doubled the team's reporting speed.", "Accuracy rose by fifty percent.")
    problems = " ".join(check_cover_letter(letter, RESUME, JD, "").problems)
    assert "doubled" in problems and "fifty percent" in problems
    edited = RESUME.replace("Built a 3-step pipeline", "Built a 3-step pipeline that tripled throughput")
    assert not check_resume(edited + "\nCHANGE LOG\n- x", RESUME, JD, "").ok


def test_new_name_matching_is_whole_word():
    source = "Built dashboards in JavaScript."
    assert "Java" in new_capitalized_terms("Built dashboards in Java too.", source)
    assert "JavaScript" not in new_capitalized_terms("Built dashboards in JavaScript.", source)
