# T002 Slice 3 — AuthoringCaseContext constructor from canonical state (Issue #60)

**Sprint:** T002 Sprint 1
**Issue:** #60
**GitHub title (spec):** `Story: Generate one structured application package from a bounded case`
**T002.md scope (canonical):** Deterministic constructor that builds a fully-populated
`AuthoringCaseContext` from canonical JobPipe state — no agent call, no generation.

> **Drift note.** The GitHub #60 title describes the full generation story. T002.md
> §Sprint 1 scopes this slice to the constructor only. Generation requires an agent
> call, which is excluded by Option C for this sprint. The constructor is the necessary
> precondition; generation is deferred. Do not implement generation in this slice.

**Branch:** `codex/T002-authoring-mvp` (rebase on latest main before starting)
**Worker:** Codex (implementation)
**Planner:** Claude (this document)
**Risk label:** Green
**Date:** 2026-04-21
**Depends on:** ee555bf (Slice 1 — `AuthoringCaseContext`), f15b883 (Slice 2 — output contracts)

---

## One-sentence objective

Add `build_authoring_case_context()` to `jobpipe/authoring/builder.py` — a
deterministic, pure function that maps
`(job_ctx, decision_ctx, evidence_ctx, narrative_ctx, *, candidate_id, evaluation_id)`
to a fully-populated, frozen `AuthoringCaseContext`; no agent call, no
generation, no side effects.

## Why this slice is third

`AuthoringCaseContext` (Slice 1) and the output contracts (Slice 2) exist as
types. Nothing in Slices 4–5 (#61, #63) can be exercised without a working
constructor that produces a real, populated context from real pipeline state.
This is the bridge from abstract contract to concrete, testable data.

---

## Field-source correction note

**Inherited drift from Slice 1.** The docstring on `AuthoringCaseContext` in
`jobpipe/authoring/case_context.py` (merged ee555bf) states:

> `candidate_id: Candidate identifier, from JobContext.meta["candidate_id"].`
> `evaluation_id: Optional evaluation run identifier, from JobContext.meta.get("evaluation_id").`

Both source attributions are wrong. `JobContext.meta` is typed as `RunMeta`,
which has `{run_id, pipeline_name, created_at}` — no `candidate_id` and no
`evaluation_id` fields.

**Correct sources (verified from `jobpipe/stages/application_pack.py`):**

- `candidate_id` — `default_candidate_id()` from `jobpipe.core.candidate_data`.
  The pipeline stores this as the module-level `_DEFAULT_CANDIDATE_ID` and
  passes it explicitly everywhere. It does not come from `meta`.
- `evaluation_id` — pipeline convention `f"{ctx.meta.run_id}:{ctx.job_id}"`
  (line 255 of `application_pack.py`), constructed on-the-fly at persistence
  time. Not stored on `JobContext`; the caller assembles it as needed.

**Resolution for this slice.** The builder accepts both as explicit keyword-only
parameters. The caller decides what to pass. The builder stays pure and ignorant
of where the values originate. **This builder signature is the canonical
source-of-truth going forward for how these two fields reach `AuthoringCaseContext`.**

**Do not re-open Slice 1.** The docstring on `case_context.py` remains incorrect
until a dedicated docstring-only follow-up issue is filed separately. Do not
touch `case_context.py` in this slice.

---

## Spec source — verbatim governing lines

From `specs/ai-document-authoring-mvp-workflow-2026-04-21.md`:

**Lines 39–47 — MVP flow:**

```
actionable job
  -> AuthoringCaseContext
  -> structured application package
  -> validation report
  -> draft CV / cover letter
  -> user + AI refinement
  -> final document refs
  -> JobPipe case state
```

**Lines 54–65 — AuthoringCaseContext field definitions:**

```python
@dataclass(frozen=True)
class AuthoringCaseContext:
    candidate_id: str
    job_id: str
    evaluation_id: str | None
    job_summary: dict
    decision_brief: dict
    selected_evidence: list[dict]
    narrative_brief: dict | None
    artifact_plan: dict | None
```

**Lines 67–68 — design constraint:**

> "The first implementation should build a narrow case context instead of
> letting the generator reach through raw artifacts."

---

## Canonical input objects

| Argument | Type | Location | Notes |
|---|---|---|---|
| `job_ctx` | `JobContext` | `jobpipe/model/schema.py` | Pydantic model; pipeline stage outputs |
| `decision_ctx` | `DecisionContext` | `jobpipe/decision/models.py` | Produced by `build_decision_context()` |
| `evidence_ctx` | `CandidateEvidenceContext` | `jobpipe/decision/models.py` | Produced by `build_candidate_evidence_context()` |
| `narrative_ctx` | `CandidateNarrativeContext \| None` | `jobpipe/decision/models.py` | `None` when narrative stage skipped |
| `candidate_id` (kwarg) | `str` | Caller-supplied | Pipeline uses `default_candidate_id()` |
| `evaluation_id` (kwarg) | `str \| None` | Caller-supplied | Pipeline uses `f"{ctx.meta.run_id}:{ctx.job_id}"`; default `None` |

### Field-by-field mapping

| `AuthoringCaseContext` field | Source expression | Notes |
|---|---|---|
| `candidate_id` | `candidate_id` kwarg | Required; no default |
| `job_id` | `job_ctx.job_id` | Direct attribute |
| `evaluation_id` | `evaluation_id` kwarg | Defaults to `None` |
| `job_summary` | Dict assembled — see below | |
| `decision_brief` | Dict assembled — see below | |
| `selected_evidence` | `[eu.model_dump() for eu in evidence_ctx.selected_evidence_units]` | Pydantic v2 |
| `narrative_brief` | Dict or `None` — see below | `None` when `narrative_ctx is None` |
| `artifact_plan` | `None` | Reserved; always None in MVP |

### `job_summary` keys (snake_case output; source keys are mixed-case)

```python
{
    "title":           job_ctx.job.get("title", ""),
    "employer_name":   job_ctx.job.get("employer_name", ""),
    "sector":          job_ctx.job.get("sector", ""),
    "application_due": job_ctx.job.get("applicationDue"),   # camelCase in source
    "source_url":      job_ctx.job.get("sourceurl", ""),    # lowercase compound in source
    "role_summary":    job_ctx.parsed.role_summary,
}
```

### `decision_brief` keys

```python
{
    "final_decision":         _enum_val(job_ctx.moderator.final_decision),
    "recommendation_reason":  job_ctx.moderator.recommendation_reason,
    "cv_focus":               job_ctx.moderator.cv_focus,
    "act_now":                _enum_val(dt.act_now),
    "can_do_score":           dt.can_do.score,
    "can_get_score":          dt.can_get.score,
    "should_want_score":      dt.should_want.score,
    "can_explain_score":      dt.can_explain.score,
}
```

Note: `FinalDecision` and `DecisionAction` are both `Literal[str]` aliases at
runtime — calling `_enum_val()` on them is a no-op. The helper is defensive
against either being promoted to a real enum later; keep it.

### `narrative_brief` keys (only when `narrative_ctx is not None`)

```python
{
    "core_identity":        narrative_ctx.narrative_profile.core_identity,
    "future_direction":     narrative_ctx.narrative_profile.future_direction,
    "motivation_themes":    narrative_ctx.narrative_profile.motivation_themes,
    "pivot_thesis":         narrative_ctx.narrative_profile.pivot_thesis,
    "direction_fit_score":  narrative_ctx.job_narrative_assessment.direction_fit_score,
    "motivation_fit_score": narrative_ctx.job_narrative_assessment.motivation_fit_score,
    "story_strength_score": narrative_ctx.job_narrative_assessment.story_strength_score,
    "motivation_brief":     narrative_ctx.job_narrative_assessment.motivation_brief,
}
```

### Precondition guards

Raise `ValueError` (not return partial) if:

- `job_ctx.moderator is None` — moderation stage did not run
- `job_ctx.parsed is None` — parse stage did not run

Both error messages must include `job_ctx.job_id`. `JobContext.moderator` and
`.parsed` are `Optional` in `schema.py` (verified), so the guards are reachable.

---

## Files to create / edit

### Create: `jobpipe/authoring/builder.py`

```python
from __future__ import annotations

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.decision.models import (
    CandidateEvidenceContext,
    CandidateNarrativeContext,
    DecisionContext,
)
from jobpipe.model.schema import JobContext


def _enum_val(v: object) -> str:
    """Return v.value if v is an enum member, else str(v)."""
    return v.value if hasattr(v, "value") else str(v)


def build_authoring_case_context(
    job_ctx: JobContext,
    decision_ctx: DecisionContext,
    evidence_ctx: CandidateEvidenceContext,
    narrative_ctx: CandidateNarrativeContext | None,
    *,
    candidate_id: str,
    evaluation_id: str | None = None,
) -> AuthoringCaseContext:
    """
    Deterministic constructor for AuthoringCaseContext.

    Maps already-computed pipeline outputs into the immutable authoring
    contract. No side effects, no agent calls. Call after all required
    pipeline stages (parse, moderate, evidence, decision) have produced
    their outputs.

    Parameters
    ----------
    job_ctx:
        Full pipeline context for the job being authored.
    decision_ctx:
        Decision context produced by build_decision_context().
    evidence_ctx:
        Evidence context produced by build_candidate_evidence_context().
    narrative_ctx:
        Narrative context produced by build_candidate_narrative_context(),
        or None if the narrative stage was skipped.
    candidate_id:
        Caller-supplied candidate identifier. In the pipeline this is
        default_candidate_id() from jobpipe.core.candidate_data. The
        builder does not resolve it to keep the function pure.
    evaluation_id:
        Caller-supplied evaluation identifier, or None. Pipeline
        convention is f"{ctx.meta.run_id}:{ctx.job_id}" but the builder
        accepts whatever the caller provides, including None for MVP
        or test use.

    Raises
    ------
    ValueError
        If job_ctx.moderator is None (moderation stage absent) or
        job_ctx.parsed is None (parse stage absent).
    """
    if job_ctx.moderator is None:
        raise ValueError(
            f"[job_id={job_ctx.job_id}] moderator output is required to build "
            "AuthoringCaseContext but is absent. Ensure the moderation stage "
            "has completed before calling this constructor."
        )
    if job_ctx.parsed is None:
        raise ValueError(
            f"[job_id={job_ctx.job_id}] parsed job output is required to build "
            "AuthoringCaseContext but is absent. Ensure the parse stage "
            "has completed before calling this constructor."
        )

    job_summary = {
        "title":           job_ctx.job.get("title", ""),
        "employer_name":   job_ctx.job.get("employer_name", ""),
        "sector":          job_ctx.job.get("sector", ""),
        "application_due": job_ctx.job.get("applicationDue"),
        "source_url":      job_ctx.job.get("sourceurl", ""),
        "role_summary":    job_ctx.parsed.role_summary,
    }

    dt = decision_ctx.decision_table
    decision_brief = {
        "final_decision":         _enum_val(job_ctx.moderator.final_decision),
        "recommendation_reason":  job_ctx.moderator.recommendation_reason,
        "cv_focus":               job_ctx.moderator.cv_focus,
        "act_now":                _enum_val(dt.act_now),
        "can_do_score":           dt.can_do.score,
        "can_get_score":          dt.can_get.score,
        "should_want_score":      dt.should_want.score,
        "can_explain_score":      dt.can_explain.score,
    }

    selected_evidence = [
        eu.model_dump() for eu in evidence_ctx.selected_evidence_units
    ]

    narrative_brief: dict | None = None
    if narrative_ctx is not None:
        np_ = narrative_ctx.narrative_profile
        na = narrative_ctx.job_narrative_assessment
        narrative_brief = {
            "core_identity":        np_.core_identity,
            "future_direction":     np_.future_direction,
            "motivation_themes":    np_.motivation_themes,
            "pivot_thesis":         np_.pivot_thesis,
            "direction_fit_score":  na.direction_fit_score,
            "motivation_fit_score": na.motivation_fit_score,
            "story_strength_score": na.story_strength_score,
            "motivation_brief":     na.motivation_brief,
        }

    return AuthoringCaseContext(
        candidate_id=candidate_id,
        job_id=job_ctx.job_id,
        evaluation_id=evaluation_id,
        job_summary=job_summary,
        decision_brief=decision_brief,
        selected_evidence=selected_evidence,
        narrative_brief=narrative_brief,
        artifact_plan=None,
    )
```

### Create: `tests/test_authoring_builder.py`

Ten synchronous tests. No async. No anyio. No `pytest.mark.asyncio`.

Construction notes: build minimal but valid pydantic objects for `JobContext`,
`DecisionContext`, etc. using their constructors or `model_construct`. Do not
mock pipeline builder functions. Pass `candidate_id` and `evaluation_id` as
explicit keyword arguments; do not access `job_ctx.meta` for them.

Required tests:

```
test_happy_path_with_narrative
  candidate_id="cand-1", evaluation_id="run-abc:job-001"
  Assert: candidate_id, job_id, evaluation_id, job_summary, decision_brief,
          selected_evidence, narrative_brief (dict), artifact_plan (None)

test_happy_path_narrative_none
  narrative_ctx=None, candidate_id="cand-1", evaluation_id omitted
  Assert: narrative_brief is None, evaluation_id is None

test_job_summary_key_set
  Assert set(result.job_summary.keys()) == exact six-key set

test_decision_brief_key_set
  Assert set(result.decision_brief.keys()) == exact eight-key set

test_decision_brief_act_now_is_string
  Assert isinstance(result.decision_brief["act_now"], str)

test_missing_moderator_raises_value_error
  job_ctx.moderator = None
  Assert ValueError raised; job_ctx.job_id in str(exc_info.value)

test_missing_parsed_raises_value_error
  job_ctx.parsed = None
  Assert ValueError raised; job_ctx.job_id in str(exc_info.value)

test_evaluation_id_default_is_none
  Omit evaluation_id kwarg
  Assert result.evaluation_id is None

test_candidate_id_required
  Omit candidate_id kwarg
  Assert TypeError raised

test_determinism
  Call twice with identical inputs
  Assert results equal (dataclass __eq__)

test_no_crewai_import
  subprocess.run(["grep", "-r", "crewai", "jobpipe/", "--include=*.py"])
  Assert returncode == 1 and stdout == ""
```

That's **eleven** test functions — the list above includes `test_determinism`
(kept from original brief, corrected count from earlier "ten"). Target eleven
synchronous tests.

---

## Files explicitly out of scope

Stop and escalate if any of these appears necessary:

- `jobpipe/authoring/case_context.py` — no changes (docstring drift tracked separately)
- `jobpipe/authoring/output_models.py` — no changes
- `jobpipe/stages/application_pack.py` — no changes; read for reference only
- `jobpipe/decision/` any file — no changes; read for types only
- `jobpipe/model/schema.py` — no changes; read for `JobContext` shape only
- `jobpipe/core/` any file — no changes
- `pyproject.toml` — no new dependencies
- `configs/`, `specs/`, `docs/` — no changes
- `AUDIT.md`, `AGENT_STATUS.md` — historical; do not update

---

## Acceptance criteria (binary, testable)

1. `from jobpipe.authoring.builder import build_authoring_case_context` imports without error.
2. `build_authoring_case_context(job_ctx, decision_ctx, evidence_ctx, narrative_ctx, candidate_id="x")` returns an `AuthoringCaseContext` instance when preconditions are met.
3. `candidate_id` is a required keyword-only argument; omitting raises `TypeError`.
4. `evaluation_id` is an optional keyword-only argument defaulting to `None`.
5. `result.job_summary` contains exactly: `title`, `employer_name`, `sector`, `application_due`, `source_url`, `role_summary`.
6. `result.decision_brief` contains exactly: `final_decision`, `recommendation_reason`, `cv_focus`, `act_now`, `can_do_score`, `can_get_score`, `should_want_score`, `can_explain_score`; `act_now` value is a `str`.
7. `result.narrative_brief` is a dict when `narrative_ctx` is supplied; `None` when `narrative_ctx=None`.
8. `result.artifact_plan` is always `None`.
9. `job_ctx.moderator is None` → `ValueError` containing the job_id string.
10. `job_ctx.parsed is None` → `ValueError` containing the job_id string.
11. All eleven tests in `tests/test_authoring_builder.py` pass; `test_no_crewai_import` confirms empty grep output.

---

## Validation commands (run in order, report verbatim)

```bash
# 1. Targeted tests with plugin-autoload suppression
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_authoring_builder.py \
  -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp

# 2. Compile check
python compile_check.py

# 3. Importability smoke
python -c "from jobpipe.authoring.builder import build_authoring_case_context; print('ok')"

# 4. No-crewai grep (empty output required)
grep -r "crewai" jobpipe/ --include="*.py" && echo "FAIL: crewai found" || echo "ok: no crewai"
```

Do NOT run `jobpipe run --dry-run` — this slice does not touch the pipeline path.

---

## Risk label

**Green.** One new pure-function module (`builder.py`) and one test file. No
schema change, no pipeline edit, no agent call, no auth/billing/secret/deploy/
model-cost surface. OSS lane only.

## Escalation gates

Stop and ask the coordinator before acting if:

- Any reason to edit files outside `jobpipe/authoring/builder.py` and `tests/test_authoring_builder.py`
- `JobContext.moderator` or `JobContext.parsed` turn out to be non-optional in `schema.py`
- `CandidateEvidenceSelection` is a dataclass rather than a pydantic model (use `dataclasses.asdict()` and escalate to confirm)
- Any new runtime dependency required
- Any async code path needed
- Any OSS/Workbench boundary question

## Founder decision needed

None. The `candidate_id`-as-kwarg design is recorded in §"Field-source correction note" as canonical source-of-truth going forward.

---

## Codex worker prompt (ready-to-paste)

```
You are the Codex implementer on worktree ../Jobpipe-codex-v2, branch
codex/T002-authoring-mvp. Implement T002 Slice 3 (Issue #60): add
build_authoring_case_context() to jobpipe/authoring/builder.py — a
deterministic pure function mapping canonical pipeline outputs to a
fully-populated AuthoringCaseContext. Coordinator APPROVED 2026-04-21.
Proceed.

Step 0 — before any edits:
  git fetch origin
  git rebase origin/main
  Confirm clean rebase, then begin.

Read first (in order):
  CLAUDE.md
  PRODUCT_VISION.md
  DEPENDENCY_POLICY.md
  docs/ai-playbook.md
  docs/current-state.json
  docs/execplans/T002.md
  docs/execplans/T002-slice-3.md          ← primary instruction source
  specs/ai-document-authoring-mvp-workflow-2026-04-21.md (lines 39-87)
  jobpipe/authoring/case_context.py       (Slice 1 contract — import only,
                                           do not edit; note: docstring on
                                           candidate_id/evaluation_id source
                                           is incorrect — see slice-3.md
                                           §Field-source correction note)
  jobpipe/authoring/output_models.py      (Slice 2 contracts — read only)
  jobpipe/model/schema.py                 (JobContext — read only)
  jobpipe/decision/models.py              (DecisionContext, EvidenceContext,
                                           NarrativeContext — read only)
  jobpipe/stages/application_pack.py      (read only — confirm
                                           _DEFAULT_CANDIDATE_ID pattern and
                                           evaluation_id convention)

Scope — create these two files only:

  1. jobpipe/authoring/builder.py
     Implement exactly as specified in T002-slice-3.md §"Create: builder.py".

     Critical requirements:
     - Signature:
         def build_authoring_case_context(
             job_ctx: JobContext,
             decision_ctx: DecisionContext,
             evidence_ctx: CandidateEvidenceContext,
             narrative_ctx: CandidateNarrativeContext | None,
             *,
             candidate_id: str,
             evaluation_id: str | None = None,
         ) -> AuthoringCaseContext:
     - candidate_id and evaluation_id are keyword-only (after *).
     - Do NOT read from job_ctx.meta for candidate_id or evaluation_id.
       JobContext.meta is RunMeta = {run_id, pipeline_name, created_at}.
     - Include _enum_val() helper. Apply to BOTH final_decision AND act_now.
     - job_summary mapping:
         "applicationDue" -> "application_due"
         "sourceurl"      -> "source_url"
     - Guard: raise ValueError if job_ctx.moderator is None; include job_id.
     - Guard: raise ValueError if job_ctx.parsed is None; include job_id.
     - selected_evidence: [eu.model_dump() for eu in evidence_ctx.selected_evidence_units]
       (If CandidateEvidenceSelection turns out to be a dataclass, use
        dataclasses.asdict() and escalate before committing.)
     - narrative_brief: None when narrative_ctx is None.
     - artifact_plan: always None.
     - No crewai. No autogen. No langchain. No anyio. No new imports.

  2. tests/test_authoring_builder.py
     Eleven synchronous tests as specified in T002-slice-3.md.
     Use real constructed inputs. Pass candidate_id and evaluation_id as
     explicit kwargs. Do NOT access job_ctx.meta for these values.

     Tests:
       test_happy_path_with_narrative
       test_happy_path_narrative_none
       test_job_summary_key_set
       test_decision_brief_key_set
       test_decision_brief_act_now_is_string
       test_missing_moderator_raises_value_error
       test_missing_parsed_raises_value_error
       test_evaluation_id_default_is_none
       test_candidate_id_required
       test_determinism
       test_no_crewai_import

Out of scope — do not touch, escalate if required:
  jobpipe/authoring/case_context.py  (docstring drift tracked separately)
  jobpipe/authoring/output_models.py
  jobpipe/stages/application_pack.py
  jobpipe/decision/ (any file)
  jobpipe/model/schema.py
  jobpipe/core/ (any file)
  configs/, specs/, docs/ (reading only)
  pyproject.toml
  AUDIT.md, AGENT_STATUS.md

Runtime dependencies: stdlib + existing jobpipe imports only. No new packages.

Validation — run in order and paste verbatim output:
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_authoring_builder.py \
    -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp
  python compile_check.py
  python -c "from jobpipe.authoring.builder import build_authoring_case_context; print('ok')"
  grep -r "crewai" jobpipe/ --include="*.py" && echo "FAIL: crewai found" || echo "ok: no crewai"

Do NOT run jobpipe run --dry-run.

After validation:
  git add jobpipe/authoring/builder.py tests/test_authoring_builder.py
  git commit -m "feat(authoring): add build_authoring_case_context constructor

  Pure function mapping (JobContext, DecisionContext, CandidateEvidenceContext,
  optionally CandidateNarrativeContext) + keyword-only candidate_id/evaluation_id
  to a fully-populated frozen AuthoringCaseContext. candidate_id is caller-supplied
  (not from meta); evaluation_id defaults to None. Eleven synchronous tests.
  No agent call, no generation, no pipeline edit. T002 Sprint 1 Slice 3 #60.

  Correction: candidate_id and evaluation_id are kwarg not meta fields —
  see docs/execplans/T002-slice-3.md field-source correction note."
  git push origin codex/T002-authoring-mvp

Report back:
  Files created (paths, line counts)
  Verbatim output of all four validation commands
  Rebase on main confirmed clean
  Whether CandidateEvidenceSelection used .model_dump() (expected) or .asdict()
  One-line: no crewai import in jobpipe/
  One-line: no new runtime dependency introduced
  Any escalation flags
```

---

## Self-review (8-item)

1. **Scope inside T002 / #60** — ✅ Constructor only. GitHub title drift documented. Inherited Slice 1 docstring drift documented in §Field-source correction note; Slice 1 is not re-opened.
2. **No crewai import** — ✅ `test_no_crewai_import` enforces it; grep in validation commands; banned explicitly in Codex prompt.
3. **No #82–#89 scope** — ✅ Supabase, hosted shell, agent frameworks excluded in file scope and escalation gates.
4. **Escalation gates defined** — ✅ Five gates including `CandidateEvidenceSelection` serialization contingency.
5. **Acceptance criteria binary and testable** — ✅ Eleven criteria; each maps to a test or command assertion.
6. **Validation commands with `PYTEST_DISABLE_PLUGIN_AUTOLOAD`** — ✅ Full command with env var, `-p no:debugging`, `-p no:cacheprovider`, `--basetemp .pytest-tmp`.
7. **Risk label with justification** — ✅ Green; one pure-function module + one test file.
8. **No TODO placeholders in Codex prompt** — ✅ Verified.

---

## Status

**APPROVED** (coordinator Opus review 2026-04-21) — ready for Codex handoff on
`codex/T002-authoring-mvp`. Planner approval stamped 2026-04-21. Escalation
gates in Codex prompt remain in force during implementation.
