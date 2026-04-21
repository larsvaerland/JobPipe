# T002 Slice 2 — Output model contracts: GeneratedApplicationPackage and DocumentValidationResult (Issue #59)

**Sprint:** T002 Sprint 1
**Issue:** #59 `Task: Define GeneratedApplicationPackage and DocumentValidationResult as Pydantic models` (per `docs/execplans/T002.md` §Sprint 1; GitHub issue #59 title is stale as "Create frozen one-job authoring fixture" — execplan is canonical)
**Branch:** `codex/T002-authoring-mvp`
**Worker:** Codex (implementation)
**Planner:** Claude (this document)
**Risk label:** Green
**Date:** 2026-04-21
**Depends on:** Slice 1 (merge commit ee555bf) — `jobpipe/authoring/case_context.py` exists

---

## One-sentence objective

Define `GeneratedApplicationPackage` and `DocumentValidationResult` as Pydantic
v2 `BaseModel` subclasses in a new `jobpipe/authoring/output_models.py` —
contract only, no generation logic, no validation rules execution, no agent
call, no pipeline edit.

## Why this slice is second

`AuthoringCaseContext` (Slice 1) is the input contract. These two models are the
output contracts. Nothing in Slices 3–5 (#60, #61, #63) can be typed correctly
without them. Keeping this as a pure contract slice (no logic) keeps the diff
minimal and the review fast.

---

## Audit findings (planner-completed, do not re-audit)

### What exists

- `jobpipe/authoring/__init__.py` — exists (empty, from Slice 1 ee555bf).
- `jobpipe/authoring/case_context.py` — exists (Slice 1). Paired input contract.
- `jobpipe/model/schema.py` line 108 — `ApplicationPackOut(BaseModel)` is the
  **existing** agent output for the current `application_pack` stage. It is
  unrelated to `GeneratedApplicationPackage`. Do not conflate them.
  `ApplicationPackOut` lives in `model/schema.py` and is not touched in this
  slice.
- Pydantic v2 (`pydantic>=2.0.0`) is already in `pyproject.toml`. Import
  pattern confirmed from `schema.py`: `from pydantic import BaseModel, Field`.
  No `Config` inner class in use; pydantic v2 defaults apply.

### What is missing

- `jobpipe/authoring/output_models.py` — does not exist. This slice creates it.
- Tests for the two new models — do not exist. This slice creates them.

### Spec-canonical shapes

Exact field names and types are taken verbatim from
`specs/ai-document-authoring-mvp-workflow-2026-04-21.md` lines 70–87.
Do not alter field names, types, or defaults in this slice.

**GeneratedApplicationPackage** (spec lines 70–76):

```python
class GeneratedApplicationPackage(BaseModel):
    job_id: str
    cover_letter_draft: str
    tailored_cv_projection: dict
    evidence_refs: list[dict]
    gap_notes: list[str]
    validation: dict | None = None
```

**DocumentValidationResult** (spec lines 82–86):

```python
class DocumentValidationResult(BaseModel):
    passed: bool
    score: float
    failures: list[str]
    warnings: list[str]
```

### Design notes for Codex

- `validation: dict | None = None` on `GeneratedApplicationPackage` is typed
  as `dict` intentionally — it is a future slot for a serialised
  `DocumentValidationResult`. Do not change the type to
  `DocumentValidationResult | None` in this slice; that coupling belongs in
  the generator slice (#60), not here.
- `score` is `float`. Pydantic v2 will coerce an `int` input; tests should
  verify both inputs round-trip correctly.
- Both models use pydantic v2 defaults. No `model_config`, no `Config` class,
  no custom validators in this slice.
- Use `from __future__ import annotations` at the top of the file for
  consistency with `case_context.py` and to ensure `dict | None` syntax is
  safe on Python < 3.10.
- Serialisation: pydantic v2 uses `.model_dump()`, not `.dict()`. Tests
  should use `.model_dump()`.

---

## Files to create / edit

### Create: `jobpipe/authoring/output_models.py`

```python
from __future__ import annotations

from pydantic import BaseModel


class GeneratedApplicationPackage(BaseModel):
    """
    Structured output of one authoring generation pass for a single job.

    Produced by the authoring generator (Slice #60) and consumed by the
    validation step (#63) and document persistence layer (#74–#77).
    This is a derived artifact — not source of truth. Provenance lives in
    JobPipe case state.

    Fields
    ------
    job_id:
        Matches AuthoringCaseContext.job_id. Links the package back to the
        originating case.
    cover_letter_draft:
        Raw cover-letter text. Unrendered; passed to refinement or DOCX
        export in a later slice.
    tailored_cv_projection:
        Structured CV projection dict. Keyed by section; values are lists of
        evidence-backed bullet strings. Passed to Reactive Resume patch or
        ATS-safe render in a later slice.
    evidence_refs:
        List of dicts, each referencing an evidence unit used in generation.
        Minimum expected keys: evidence_unit_id, source_type, canonical_text.
    gap_notes:
        List of plain-text notes about gaps between the job requirements and
        the candidate evidence. Surfaced in the validation report.
    validation:
        Reserved slot for a serialised DocumentValidationResult dict.
        None until the validation step runs. Typed as dict | None for now;
        will be structurally constrained in the generator slice (#60).
    """

    job_id: str
    cover_letter_draft: str
    tailored_cv_projection: dict
    evidence_refs: list[dict]
    gap_notes: list[str]
    validation: dict | None = None


class DocumentValidationResult(BaseModel):
    """
    Deterministic quality gate result for one generated application package.

    Produced by the validation checklist (#63). All fields are required —
    there is no partial result. A missing validation run should be represented
    as an absent DocumentValidationResult, not a zero-scored one.

    Fields
    ------
    passed:
        True if the package cleared all required checks. False if any
        entry in failures is non-empty.
    score:
        Aggregate quality score in [0.0, 1.0]. Computation defined in #63.
        Stored as float; pydantic v2 coerces int inputs.
    failures:
        List of human-readable failure reasons. Non-empty implies
        passed == False.
    warnings:
        List of advisory notes that did not cause a failure. May be
        non-empty even when passed == True.
    """

    passed: bool
    score: float
    failures: list[str]
    warnings: list[str]
```

### Create: `tests/test_authoring_output_models.py`

Seven synchronous tests. No async. No anyio. No `pytest.mark.asyncio`.

```python
import subprocess

import pytest
from pydantic import ValidationError

from jobpipe.authoring.output_models import (
    DocumentValidationResult,
    GeneratedApplicationPackage,
)


# GeneratedApplicationPackage --------------------------------------------------

def test_generated_package_happy_path():
    pkg = GeneratedApplicationPackage(
        job_id="job-001",
        cover_letter_draft="Dear hiring manager...",
        tailored_cv_projection={"experience": ["Led platform migration"]},
        evidence_refs=[{"evidence_unit_id": "eu-1", "source_type": "work_highlight"}],
        gap_notes=["No direct fintech experience"],
    )
    assert pkg.job_id == "job-001"
    assert pkg.cover_letter_draft == "Dear hiring manager..."
    assert pkg.validation is None


def test_generated_package_validation_field_accepts_dict():
    pkg = GeneratedApplicationPackage(
        job_id="job-001",
        cover_letter_draft="x",
        tailored_cv_projection={},
        evidence_refs=[],
        gap_notes=[],
        validation={"passed": True, "score": 0.9, "failures": [], "warnings": []},
    )
    assert isinstance(pkg.validation, dict)
    assert pkg.validation["passed"] is True


def test_generated_package_missing_required_field_raises():
    with pytest.raises(ValidationError):
        GeneratedApplicationPackage(
            cover_letter_draft="x",
            tailored_cv_projection={},
            evidence_refs=[],
            gap_notes=[],
        )


def test_generated_package_model_dump_shape():
    pkg = GeneratedApplicationPackage(
        job_id="job-002",
        cover_letter_draft="y",
        tailored_cv_projection={"summary": ["Result-oriented"]},
        evidence_refs=[],
        gap_notes=["Gap 1"],
    )
    d = pkg.model_dump()
    assert set(d.keys()) == {
        "job_id",
        "cover_letter_draft",
        "tailored_cv_projection",
        "evidence_refs",
        "gap_notes",
        "validation",
    }
    assert d["validation"] is None


# DocumentValidationResult -----------------------------------------------------

def test_validation_result_happy_path():
    result = DocumentValidationResult(
        passed=True,
        score=0.85,
        failures=[],
        warnings=["Cover letter is brief"],
    )
    assert result.passed is True
    assert result.score == pytest.approx(0.85)
    assert result.failures == []
    assert len(result.warnings) == 1


def test_validation_result_score_coerces_int():
    result = DocumentValidationResult(
        passed=False,
        score=0,
        failures=["Missing evidence refs"],
        warnings=[],
    )
    assert isinstance(result.score, float)
    assert result.score == 0.0


# Cross-cutting ---------------------------------------------------------------

def test_no_crewai_import():
    result = subprocess.run(
        ["grep", "-r", "crewai", "jobpipe/", "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout == "", (
        f"crewai import found — violates Option C constraint:\n{result.stdout}"
    )
```

---

## Files explicitly out of scope

Stop and escalate to the coordinator if any of the following appears required:

- `jobpipe/stages/application_pack.py` — no changes
- `jobpipe/decision/models.py` — no changes; read-only reference
- `jobpipe/model/schema.py` — no changes; `ApplicationPackOut` is unrelated
- `jobpipe/core/` — no changes
- `jobpipe/authoring/case_context.py` — no changes; read-only reference
- `pyproject.toml` — no new dependencies; pydantic already in deps
- `configs/`, `specs/`, `docs/` — no changes beyond this execplan
- `AUDIT.md`, `AGENT_STATUS.md` — historical; do not update

---

## Acceptance criteria

1. `jobpipe/authoring/output_models.py` exists and exports
   `GeneratedApplicationPackage` and `DocumentValidationResult`.
2. Both classes are `pydantic.BaseModel` subclasses (not dataclasses, not
   TypedDict).
3. Field names and types match the spec
   (`specs/ai-document-authoring-mvp-workflow-2026-04-21.md` lines 70–87)
   exactly. No additions, removals, or renames.
4. `GeneratedApplicationPackage.validation` defaults to `None` when omitted.
5. `DocumentValidationResult.score` is typed as `float`; pydantic v2 coerces
   an `int` input without raising.
6. All seven tests in `tests/test_authoring_output_models.py` pass.
7. `test_no_crewai_import` passes — grep returns empty stdout.
8. `python compile_check.py` exits 0.
9. No new runtime dependency introduced beyond pydantic (already present).
10. `from jobpipe.authoring.output_models import GeneratedApplicationPackage, DocumentValidationResult`
    succeeds without error.

---

## Validation commands (run in order, report verbatim)

```bash
# 1. Targeted tests. Repo-canonical pytest invocation uses the workaround
#    established in toolchain_notes (Python 3.14 + anyio on Windows).
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp tests/test_authoring_output_models.py -v

# 2. Compile check
python compile_check.py

# 3. Importability smoke
python -c "from jobpipe.authoring.output_models import GeneratedApplicationPackage, DocumentValidationResult; print('ok')"

# 4. No-crewai grep (must return empty output — grep exits 1 on no match)
grep -r "crewai" jobpipe/ --include="*.py" && echo "FAIL: crewai found" || echo "ok: no crewai"
```

**Do NOT run `jobpipe run --dry-run`** — this slice does not touch the
pipeline runtime path.

---

## Risk label

**Green.** One new file (`output_models.py`) and one test file. Pure Pydantic
model definitions. No schema change, no pipeline surface, no auth, billing,
secret, deploy, model-cost, or OSS/Workbench boundary.

---

## Escalation gates

Stop and ask the coordinator before acting if:

- Any reason to edit `application_pack.py`, `decision/models.py`, `schema.py`,
  or any file in `jobpipe/core/`
- Any new runtime dependency beyond pydantic + stdlib
- Any proposal to add validators, computed fields, or custom `model_config`
  in this slice (that belongs in #63, not here)
- Any ambiguity about field typing that would affect the generator contract
  in Slice 3 (#60)
- Any OSS/Workbench boundary question
- Any agent-framework-specific coupling (autogen, langchain, or equivalent)

---

## Founder decision needed

None for this slice as scoped. The `validation: dict | None` typing decision
is spec-canonical; do not reopen it in this slice.

---

## Self-review pass (8-item checklist)

Verified against `docs/ai-playbook.md` §"Slice Brief Self-Review":

1. **Scope inside T002 / #59** — ✅ Two model definitions and their tests. No
   generation, no validation rules, no agent call, no pipeline edit.
2. **No crewai import anywhere** — ✅ `test_no_crewai_import` enforces it;
   grep assertion in validation commands; banned in Codex prompt.
3. **No #82–#89 scope** — ✅ Supabase, hosted shell, and agent framework work
   explicitly excluded.
4. **Escalation gates defined** — ✅ Six gates listed.
5. **Acceptance criteria testable and deterministic** — ✅ Ten criteria; all
   binary pass/fail.
6. **Validation commands with toolchain workaround** — ✅
   `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -p no:debugging -p no:cacheprovider`
   per `docs/current-state.json` toolchain_notes.
7. **Risk label assigned** — ✅ Green, with justification.
8. **No TODO placeholders in Codex prompt** — ✅ Verified below.

---

## Codex worker prompt (ready-to-paste)

```
You are the Codex implementer on worktree ../Jobpipe-codex-v2, branch
codex/T002-authoring-mvp. Implement T002 Slice 2 (Issue #59): define
GeneratedApplicationPackage and DocumentValidationResult as Pydantic v2
BaseModel subclasses in jobpipe/authoring/output_models.py. Coordinator
has APPROVED this slice as of 2026-04-21. Proceed.

IMPORTANT: commit and push your work before reporting. Slice 1 was
delivered uncommitted and required the coordinator to commit on your
behalf; do not repeat. After validation passes:
  git add jobpipe/authoring/output_models.py tests/test_authoring_output_models.py
  git commit -m "feat(authoring): add GeneratedApplicationPackage + DocumentValidationResult (T002 slice 2, #59)"
  git push origin codex/T002-authoring-mvp

Read first (in order):
  CLAUDE.md
  PRODUCT_VISION.md
  DEPENDENCY_POLICY.md
  docs/ai-playbook.md
  docs/current-state.json
  docs/execplans/T002.md
  docs/execplans/T002-slice-2.md  ← primary instruction source
  specs/ai-document-authoring-mvp-workflow-2026-04-21.md (lines 69-87)
  jobpipe/authoring/case_context.py (Slice 1 — paired input contract)
  jobpipe/model/schema.py (read-only — confirm pydantic import pattern)

Scope — create these files only:

  1. jobpipe/authoring/output_models.py
     Define two Pydantic v2 BaseModel subclasses with exactly these fields
     (names and types verbatim from spec lines 70-86 — do not alter):

     class GeneratedApplicationPackage(BaseModel):
         job_id: str
         cover_letter_draft: str
         tailored_cv_projection: dict
         evidence_refs: list[dict]
         gap_notes: list[str]
         validation: dict | None = None

     class DocumentValidationResult(BaseModel):
         passed: bool
         score: float
         failures: list[str]
         warnings: list[str]

     Requirements:
     - Add "from __future__ import annotations" at the top.
     - Import only: from pydantic import BaseModel (Field not needed here).
     - Add a class-level docstring to each model explaining field provenance
       (see docs/execplans/T002-slice-2.md §"Create: output_models.py" for
       the reference docstrings — copy them verbatim).
     - No model_config, no Config class, no custom validators, no computed
       fields. Contract only.
     - Do not import from crewai, crewai_tools, autogen, langchain, or any
       external agent framework.

  2. tests/test_authoring_output_models.py
     Seven synchronous tests (no async, no anyio, no pytest.mark.asyncio).
     Implement exactly these test functions (see slice brief for full
     bodies — copy verbatim):

     test_generated_package_happy_path
     test_generated_package_validation_field_accepts_dict
     test_generated_package_missing_required_field_raises
     test_generated_package_model_dump_shape
     test_validation_result_happy_path
     test_validation_result_score_coerces_int
     test_no_crewai_import

Out of scope — do not touch, stop and escalate if required:
  jobpipe/stages/application_pack.py
  jobpipe/decision/models.py
  jobpipe/model/schema.py
  jobpipe/authoring/case_context.py
  jobpipe/core/ (any file)
  configs/, specs/, docs/ (except reading for reference)
  pyproject.toml (no new dependencies — pydantic already present)
  AUDIT.md, AGENT_STATUS.md

Runtime dependencies:
  pydantic (already in pyproject.toml — do not add or upgrade).
  Tests: stdlib subprocess, pytest, pydantic.ValidationError only.
  No crewai. No anyio. No new packages.

Validation — run in order and paste verbatim output into your handoff:
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp tests/test_authoring_output_models.py -v
  python compile_check.py
  python -c "from jobpipe.authoring.output_models import GeneratedApplicationPackage, DocumentValidationResult; print('ok')"
  grep -r "crewai" jobpipe/ --include="*.py" && echo "FAIL: crewai found" || echo "ok: no crewai"

Do NOT run jobpipe run --dry-run. This slice does not touch the pipeline path.

Approval gates — stop and ask the coordinator before acting if:
  Any reason to edit application_pack.py, decision/models.py, schema.py,
    case_context.py, or any file in jobpipe/core/
  Any new runtime dependency beyond pydantic + stdlib
  Any proposal to add validators, computed fields, or model_config
  Any ambiguity about field typing affecting Slice 3 generator contract
  Any OSS/Workbench boundary question
  Any agent-framework-specific coupling

Report back with:
  Exact list of files created (paths and line counts)
  The commit SHA and pushed branch (codex/T002-authoring-mvp)
  Verbatim output of all four validation commands above
  One-line confirmation that no crewai import exists in jobpipe/
  One-line confirmation that no new runtime dependency was introduced
  Any escalation flags or unexpected findings
```

---

## Status

Approved — ready for Codex handoff on `codex/T002-authoring-mvp`. Tracked on
GitHub Project #6 linked to issue #59 (Status: Ready, Priority: P1,
Agent-ready). Planner approval stamped 2026-04-21. Coordinator independent
review stamped 2026-04-21. Escalation gates in the Codex worker prompt
remain in force during implementation.
