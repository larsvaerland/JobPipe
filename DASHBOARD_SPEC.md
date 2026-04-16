# JobPipe Dashboard — Design Spec

## Data source

Primary: `jobpipe.sqlite` — two tables:

### `job_evaluations` table (one row per unique job, latest state for a candidate)
Key columns:
- `job_id` (TEXT, PK) — unique job identifier
- `title` (TEXT) — job title
- `employer` (TEXT) — company name
- `work_city`, `work_county`, `work_postalCode` (TEXT) — location
- `applicationDue` (TEXT) — deadline (ISO date or empty)
- `source_url`, `application_url` (TEXT) — links to job ad
- `triage_decision` (TEXT) — SKIP | REVIEW | APPLY_CANDIDATE
- `triage_confidence` (REAL, 0–1)
- `triage_explanation` (TEXT) — why triage decided what it did
- `triage_signals` (TEXT) — comma-separated signal tags (e.g. "geo_postal_skip", "safety:target_title")
- `fit_score` (INTEGER, 0–100) — profile match score (NULL if triage SKIP'd)
- `pivot_score` (INTEGER, 0–100) — career pivot potential score
- `final_decision` (TEXT) — **APPLY_STRONGLY | APPLY | REVIEW_HIGH | REVIEW_LOW | SKIP**
- `final_confidence` (REAL, 0–1)
- `recommendation_reason` (TEXT) — moderator's reasoning
- `cv_focus` (TEXT) — what to emphasize in CV
- `run_id` (TEXT) — which pipeline run produced this result
- `run_seen_at` (TEXT) — timestamp of the run
- `updated_at` (TEXT) — last update timestamp
- `description_snip` (TEXT) — first ~500 chars of job description
- `raw_index_json`, `raw_match_json`, `raw_pivot_json`, `raw_moderator_json` (TEXT) — full JSON from each stage

### `job_run_events` table (one row per run × job)
Same core fields as `job_evaluations` but tracks every run, useful for history/trends.

### Current distribution (as of 2026-04-13)
- Total unique jobs: 7,898
- Total events (runs): 8,242
- Actionable (non-SKIP): 65
- Note: thresholds raised 2026-04-13 (apply_fit 62->67, apply_strong 75->78, review_min 25->30). export_dashboard.py re-applies current thresholds at export time so historical jobs are always re-classified against the latest config.

---

## Pipeline stages (the funnel)

Jobs flow through these stages in order:

1. **Geo filter** (pre-AI, zero-cost) — hard-blocks by Norwegian postal code. Signal: `geo_postal_skip`
2. **Hard-no title filter** (pre-AI, regex) — blocks retail/sales/clinical titles. Signal: `hard_no_title`
3. **Triage** (LLM, gpt-4.1-nano) — AI first-pass. Output: SKIP / REVIEW / APPLY_CANDIDATE
4. **Safety overrides** (post-triage regex) — can force REVIEW on SKIPs if target-title/strong-positive/weak-positive signals are present. Signals: `safety:target_title`, `safety:very_strong`, `safety:weak`
5. **Reverse triage** (LLM, gpt-4.1-mini) — reconsiders low-confidence SKIPs. Only runs when triage=SKIP and confidence < threshold and NOT geo-skip
6. **Parse** (LLM) — extracts structured requirements from job ad
7. **Profile match** (LLM) — scores fit 0–100 against candidate profile
8. **Pivot** (LLM) — scores career-pivot potential 0–100
9. **Moderate** (deterministic, no LLM) — combines fit + pivot into final decision using thresholds

### Final decision thresholds (from pipeline.v1.yaml)
- fit < 25 → SKIP (hard floor, regardless of pivot)
- fit >= 75 AND strong signals → APPLY_STRONGLY
- fit >= 62 → APPLY
- fit >= 55 → REVIEW_HIGH
- fit >= 25 → REVIEW_LOW

---

## Dashboard sections (recommended)

### 1. Action list (TOP PRIORITY — this is what Lars opens the dashboard for)
Table of jobs where `final_decision` IN (APPLY_STRONGLY, APPLY, REVIEW_HIGH), sorted by fit_score DESC.

Columns: title, employer, fit_score, pivot_score, final_decision, applicationDue, application_url (as clickable link), cv_focus, recommendation_reason

Color-code rows: APPLY_STRONGLY=green, APPLY=blue, REVIEW_HIGH=amber

Show count badge: "14 APPLY_STRONGLY, 11 APPLY, 0 REVIEW_HIGH"

Clicking a row should expand to show: triage_explanation, match overlaps/gaps (from raw_match_json), pivot reasoning (from raw_pivot_json), full recommendation_reason

### 2. Pipeline funnel
Visual showing job counts at each stage:
- Total jobs in → Geo-passed → Hard-no passed → Triage passed → Final non-SKIP

Show as horizontal bar chart or Sankey diagram. Key metric: **triage pass rate** (% of jobs that survive triage). Target: 5–15%.

To compute this from `job_evaluations`:
- Geo-blocked: WHERE triage_signals LIKE '%geo_postal_skip%' OR triage_signals LIKE '%geo_skip%'
- Hard-no blocked: WHERE triage_signals LIKE '%hard_no_title%'
- AI-SKIP: WHERE triage_decision = 'SKIP' AND above conditions not met
- Passed triage: WHERE triage_decision != 'SKIP'

### 3. SKIP breakdown (donut/pie)
Why jobs were filtered:
- Geo-blocked (postal code outside allowed area)
- Hard-no title (regex matched retail/sales/clinical)
- AI-decided SKIP (LLM said not relevant)
- Safety-overridden then SKIP'd at moderator (passed triage via safety but fit_score too low)

### 4. Score distribution
Histogram or scatter plot of `fit_score` vs `pivot_score` for all jobs that passed triage. Color by final_decision. This shows whether the scoring is well-calibrated or if everything clusters in one zone.

### 5. Run history (timeline)
Line chart of runs over time (from `job_run_events`, grouped by `run_id` → `seen_at`):
- Jobs processed per run
- Pass rate per run
- Number of APPLY+ decisions per run

Shows the effect of tuning changes over time.

### 6. Top employers
Bar chart of employers that appear most often in APPLY+ decisions. Helps Lars see which organizations consistently match his profile.

### 7. Expiring soon
Filtered view of action-list items where `applicationDue` is within the next 7 days. Urgent banner.

---

## Technical notes

### Generating the data export
Add a step to the pipeline's RunAll.cmd:

```powershell
python -m jobpipe.cli.sync_ledger --out .\out_runs --db C:\path\to\jobpipe.sqlite
python -m jobpipe.cli.export_dashboard --db C:\path\to\jobpipe.sqlite
```

### Triage signals parsing
The `triage_signals` column is a JSON array stored as text. Parse it to categorize SKIPs:
- Contains "geo_postal_skip" or "geo_skip" → geo-blocked
- Contains "hard_no_title" → hard-no title
- Contains "safety:" prefix → was overridden by safety system
- Otherwise → AI-decided

### Raw JSON columns
`raw_match_json` contains the full ProfileMatchOut (overlaps, gaps, hard_blockers). Parse and display in the expanded row view for each job.
`raw_pivot_json` contains PivotOut (pivot_type, why_it_matters, potential_risk).
`raw_moderator_json` contains ModeratorOut (recommendation_reason, cv_focus, feedback_flags).
