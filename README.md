# AI Resume Tailor

Tailors a resume and writes a cover letter for each job description, then fact-checks every draft in plain Python before you see it. If the model invents a metric, adds a tool you've never used or slips in a banned word, the draft goes back with the exact problem listed. After two failed retries you get the draft marked **FLAGGED** instead of a quiet pass.

Built with [CrewAI](https://docs.crewai.com). Runs free on a local model through Ollama. Switching to Claude is one line in `.env`.

## Why the fact checker isn't another agent

Small free models are good at rewording and bad at not making things up. A second agent reviewing the first one shares the same blind spots. So the checks that matter are deterministic:

| Check | What it catches |
|---|---|
| New numbers | Any figure in the draft that isn't in your original resume |
| Blocked claims | Skills on your "can't defend this" list (`config/blocked_claims.txt`) that the draft adds |
| New names | Tools or companies that appear mid-sentence and aren't in your resume or the job description |
| Style | Em dashes, code fences, banned words (`config/banned_words.txt`) |
| Cover letter shape | 7 to 9 sentences, no "I am writing to...", no exclamation points |

## How it works

```
Resume mode:   JD Analyst ──> Resume Editor ──> guards ──┬─ pass ──> output/<job>_resume.txt
                    ^                                     └─ fail ──> retry with feedback (max 2)
Cover mode:    Hook Finder ──> Letter Writer ──> guards ──> output/<job>_cover.txt
```

The analyst lists which job keywords your resume can honestly support. The editor uses only those, edits surgically and writes a change log.

## Setup

```bash
git clone https://github.com/jbattohokson/AI_Resume_Tailor && cd AI_Resume_Tailor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Free local model (one-time download, about 4.7 GB)
ollama pull qwen2.5:7b
```

## Use it

```bash
# One job, resume only
python -m tailor resume --resume examples/sample_resume.txt \
  --jd examples/jobs/brex_data_analyst_ii.txt --buzzwords "SQL, Python, data quality"

# One job, cover letter (notes file is optional but makes the opening specific)
python -m tailor cover --resume examples/sample_resume.txt \
  --jd examples/jobs/bill_risk_data_analyst.txt --notes examples/jobs/bill_risk_data_analyst_notes.txt

# Every .txt in a folder. A file named <job>_notes.txt is used as that job's notes.
python -m tailor batch --resume examples/sample_resume.txt --jobs-dir examples/jobs
```

Output goes to `output/`.

## Example inputs

- **Job descriptions are real.** `examples/jobs/` holds three public postings retrieved on 2026-10-20: Brex Data Analyst II, BILL Risk Data Analyst and BILL Business Development Representative. Each file links to the original and summarizes it in my own words rather than copying it, so check the link for the current version. Postings close, so a link may stop working.
- **The resume is fictional.** `examples/sample_resume.txt` is "Alex Rivera", a made-up candidate with an `example.com` email. No real person's resume is in this repo, and `.gitignore` keeps `my_resume*.txt` out of commits.
- The made-up "Acme" posting the tests use lives in `tests/fixtures/`, so test results don't change when real postings do.

## Switching models

Set `LLM_MODEL` in `.env`:

| Value | Cost | Notes |
|---|---|---|
| `ollama/qwen2.5:7b` | Free | Default. Follows formatting rules well for its size |
| `ollama/llama3.1:8b` | Free | Alternative local model |
| `anthropic/claude-sonnet-5-5` | Paid | Run `pip install "crewai[anthropic]"` and set `ANTHROPIC_API_KEY` |

The guards don't change when the model does, so a stronger model just fails them less often.

## Make it yours

- `config/protocol.md`: the editing rules every agent follows
- `config/blocked_claims.txt`: skills you won't claim unless your resume already lists them
- `config/banned_words.txt`: words that get a draft rejected

## Tests

```bash
pytest
```

The tests swap in a scripted fake model, so they run offline in under a second. They cover each guard, a clean first-try pass, a fabricated draft that gets caught and fixed on retry, and the flagged fallback after too many failures.

## Testing status (2026-10-20)

- `pytest`: 13 passed, run 3 times with identical results.
- Not tested here: live runs against Ollama or Claude on the new real postings. The tests use a scripted fake model, so they prove the guards and retry logic, not draft quality.

## Limits

- The new-names check skips words at the start of a line or sentence, so a made-up tool used as a bullet's first word gets past it. Blocked claims and number checks still apply.
- The cover letter can only be as specific as your notes file. The agents don't browse the web.
- Local 7B models are slower and make more first-draft mistakes than Claude. Expect more retries.

## License

MIT (see `LICENSE`).
