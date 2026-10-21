# Sample outputs (real, unedited)

Five runs of `python -m tailor` with `LLM_MODEL=ollama/qwen2.5:7b` on 2026-10-20, on a 2-vCPU cloud machine with no GPU. The job descriptions are the three real postings in `examples/jobs/`. The resume is the fictional `examples/sample_resume.txt`.

Nothing here was edited. The point is to show what a free 7B model actually does with these guards around it, including the mistakes.

| File | Result | Time | What happened |
|---|---|---|---|
| `brex_data_analyst_ii_resume.txt` | Passed, 1 attempt | 4m21s | One real edit: "exports 4 Tableau views" became "exports 4 dashboards", matching the posting. Everything else unchanged. |
| `bill_risk_data_analyst_resume.txt` | Passed, 1 attempt | 3m13s | Swapped the order of two project bullets and reworded one ("Found a -1.5% gross margin..." became "Analyzed... to find a -1.5% gross margin"). Its change log is wrong: it says a bullet was "added" when it was reordered, and it doesn't mention the rewording. |
| `bill_business_development_rep_resume.txt` | Passed, 1 attempt | 4m07s | No edits. It correctly didn't add Salesforce or ZoomInfo, which the posting asks for but the resume doesn't list (both are on `config/blocked_claims.txt`). Its change log wrongly says the bullets already contain "prospecting" and "KPIs". |
| `brex_data_analyst_ii_cover.txt` | **FLAGGED** after 3 attempts | 6m17s | 11 sentences (limit 7 to 9) and an invented "50%" improvement. The resume says follow-up went from 3 days to 1 day, which is a 67% cut, so the number was both made up and wrong. |
| `bill_risk_data_analyst_cover.txt` | **FLAGGED** after 3 attempts | 5m40s | 11 sentences. It also used "leveraging" and left "[Company Name]" placeholders, which the guards at the time missed. Both checks were added after this run; re-checked now, it fails on all three. |

## What these runs changed in the code

- **Change log vs. resume.** An earlier Brex run logged an edit that never made it into the resume, and passed. A guard now checks each logged `New: "..."` text against the resume body. That original output is kept in `docs/found_in_testing/`.
- **Banned-word variants.** "leverage" now also catches "leveraging".
- **Placeholders.** Bracketed text like `[Company Name]` is rejected.

## What the guards still don't catch

- A change log written in a different format (the model doesn't always use `Old:` / `New:`), or one that describes edits inaccurately without claiming text that's missing.
- Generic openings other than "I am writing..." (both letters opened "I am excited to apply"), and letters that never name the company.

Both cover letters failed, which is the intended behavior: a flagged draft is saved for a human to fix instead of being passed off as finished. A stronger model (Claude, via `LLM_MODEL` in `.env`) would fail the guards less often; the guards stay the same.
