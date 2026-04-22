# T002 Slice 5 — Deterministic validation rules on AuthoringCaseContext (Issue #63)

**Sprint:** T002 Sprint 1
**Issue:** #63 `Task: Implement deterministic document validation checklist`
**Branch:** `codex/T002-authoring-mvp`
**Worker:** Codex (implementation)
**Planner:** Claude Sonnet (this document)
**Risk label:** Green
**Date:** 2026-04-21

---

## 1. Scope + non-goals

### In scope

One new file:

```
jobpipe/authoring/validation.py
```

Exposes a single public function:

```python
def validate_authoring_context(ctx: AuthoringCaseContext) -> DocumentValidationResult: ...
```

Five deterministic rule functions (offline, no LLM, no network, no randomness,
no time dependence):

| Rule ID | Failure mode | Severity |
|---|---|---|
| `missing_decision_context` | `decision_brief` dict is empty or missing required keys | error |
| `empty_evidence_units` | `selected_evidence` list is empty | error |
| `narrative_empty` | `narrative_brief` is not None but has no content in any expected key | warning |
| `resume_job_mismatch` | evidence unit `evidence_unit_id` strings referenced in `narrative_brief` have no counterpart in `selected_evidence`; or `candidate_id` is blank | error |
| `required_field_absent` | any mandatory `AuthoringCaseContext` field (`candidate_id`, `job_id`, `decision_brief`, `selected_evidence`, `job_summary`) is falsy | error |

**Schema constraint (non-negotiable):** `DocumentValidationResult` has exactly four
fields: `passed: bool`, `score: float`, `failures: list[str]`, `warnings: list[str]`.
There is no per-finding `rule_id`, `path`, or `severity` field. Rule findings are
encoded as prefixed strings in `failures` / `warnings`:

```
"[missing_decision_context] decision_brief is missing required key: 'final_decision'"
"[narrative_empty] narrative_brief has no content in any expected key"
```

This encoding preserves traceability without requiring a schema change (which is
out of scope). The `passed` field is `True` iff `failures` is empty. The `score`
field is computed as `1.0 - (len(failures) * 0.2 + len(warnings) * 0.05)`, clamped
to `[0.0, 1.0]`.

One new test file:

```
tests/test_authoring_validation.py
```

### Non-goals

- Do **not** modify `AuthoringCaseContext` (Slice 1 / `jobpipe/authoring/case_context.py`)
- Do **not** modify `DocumentValidationResult` or `GeneratedApplicationPackage`
  (Slice 2 / `jobpipe/authoring/output_models.py`)
- Do **not** call any LLM, agent, or network resource
- Do **not** add a `--validate` CLI flag in this slice (deferred to Slice 6 — see
  §7 Risks + open questions)
- Do **not** add new external dependencies
- Do **not** touch `jobpipe/stages/`, `jobpipe/decision/`, or `jobpipe/model/`

---

## 2. Success criteria

- [ ] `jobpipe/authoring/validation.py` exists and is importable as
  `from jobpipe.authoring.validation import validate_authoring_context`
- [ ] `validate_authoring_context` accepts any `AuthoringCaseContext` and returns
  a `DocumentValidationResult`
- [ ] All five rules fire correctly on adversarial inputs (one failing test per rule)
- [ ] Golden-path test: a well-formed `AuthoringCaseContext` (all fields populated)
  produces `passed=True`, `failures=[]`, `warnings=[]`
- [ ] `narrative_empty` fires as a **warning** (not an error) — `passed` stays
  `True` when only `warnings` are present
- [ ] `score` is correctly computed and clamped to `[0.0, 1.0]`
- [ ] `test_no_crewai_import` passes — grep returns empty stdout and exit 1
- [ ] `python compile_check.py` exits 0
- [ ] No import of `crewai`, `langchain`, `openai`, or any external agent framework
  anywhere in `jobpipe/authoring/validation.py` or its test file

---

## 3. Signatures Verified Against origin/main @ ffbfc4d

> **Verification method:** Files were read directly from the mounted planner
> worktree at `C:\Users\larsv\Jobpipe-claude-v2` (branch `claude/T002-authoring-mvp`,
> which is at or ahead of ffbfc4d per coordinator confirmation). All symbols
> below were read from actual source files, not inferred.

| Symbol | Source file | Line | Signature / declaration |
|---|---|---|---|
| `AuthoringCaseContext` | `jobpipe/authoring/case_context.py` | 7 | `@dataclass(frozen=True) class AuthoringCaseContext:` |
| `AuthoringCaseContext.candidate_id` | `jobpipe/authoring/case_context.py` | 37 | `candidate_id: str` |
| `AuthoringCaseContext.job_id` | `jobpipe/authoring/case_context.py` | 38 | `job_id: str` |
| `AuthoringCaseContext.evaluation_id` | `jobpipe/authoring/case_context.py` | 39 | `evaluation_id: str \| None` |
| `AuthoringCaseContext.job_summary` | `jobpipe/authoring/case_context.py` | 40 | `job_summary: dict` |
| `AuthoringCaseContext.decision_brief` | `jobpipe/authoring/case_context.py` | 41 | `decision_brief: dict` |
| `AuthoringCaseContext.selected_evidence` | `jobpipe/authoring/case_context.py` | 42 | `selected_evidence: list[dict]` |
| `AuthoringCaseContext.narrative_brief` | `jobpipe/authoring/case_context.py` | 43 | `narrative_brief: dict \| None` |
| `AuthoringCaseContext.artifact_plan` | `jobpipe/authoring/case_context.py` | 44 | `artifact_plan: dict \| None` |
| `DocumentValidationResult` | `jobpipe/authoring/output_models.py` | 26 | `class DocumentValidationResult(BaseModel):` |
| `DocumentValidationResult.passed` | `jobpipe/authoring/output_models.py` | 37 | `passed: bool` |
| `DocumentValidationResult.score` | `jobpipe/authoring/output_models.py` | 38 | `score: float` |
| `DocumentValidationResult.failures` | `jobpipe/authoring/output_models.py` | 39 | `failures: list[str]` |
| `DocumentValidationResult.warnings` | `jobpipe/authoring/output_models.py` | 40 | `warnings: list[str]` |
| `build_authoring_case_context` | `jobpipe/authoring/builder.py` | 17 | `def build_authoring_case_context(job_ctx: JobContext, decision_ctx: DecisionContext, evidence_ctx: CandidateEvidenceContext, narrative_ctx: CandidateNarrativeContext \| None, *, candidate_id: str, evaluation_id: str \| None = None) -> AuthoringCaseContext:` |
| `DecisionContext` | `jobpipe/decision/models.py` | 324 | `class DecisionContext(BaseModel):` |
| `DecisionContext.decision_table` | `jobpipe/decision/models.py` | 327 | `decision_table: JobDecisionTable` |
| `CandidateEvidenceContext` | `jobpipe/decision/models.py` | 192 | `class CandidateEvidenceContext(BaseModel):` |
| `CandidateEvidenceContext.selected_evidence_units` | `jobpipe/decision/models.py` | 194 | `selected_evidence_units: list[CandidateEvidenceSelection] = Field(default_factory=list)` |
| `CandidateEvidenceSelection` | `jobpipe/decision/models.py` | 178 | `class CandidateEvidenceSelection(BaseModel):` |
| `CandidateEvidenceSelection.evidence_unit_id` | `jobpipe/decision/models.py` | 179 | `evidence_unit_id: str` |
| `CandidateNarrativeContext` | `jobpipe/decision/models.py` | 248 | `class CandidateNarrativeContext(BaseModel):` |
| `CandidateNarrativeContext.narrative_profile` | `jobpipe/decision/models.py` | 249 | `narrative_profile: CandidateNarrativeProfile` |
| `CandidateNarrativeContext.job_narrative_assessment` | `jobpipe/decision/models.py` | 252 | `job_narrative_assessment: JobNarrativeAssessment` |
| `DocumentValidationResult.model_dump` | pydantic v2 BaseModel | — | `def model_dump(self, *, mode='python', ...) -> dict[str, Any]` (inherited) |
| `GeneratedApplicationPackage` | `jobpipe/authoring/output_models.py` | 6 | `class GeneratedApplicationPackage(BaseModel):` (not used by validator — listed for completeness) |

**decision_brief expected keys** (verified from `jobpipe/authoring/builder.py` lines 83–92):
`final_decision`, `recommendation_reason`, `cv_focus`, `act_now`, `can_do_score`,
`can_get_score`, `should_want_score`, `can_explain_score`

**narrative_brief expected keys** (verified from `jobpipe/authoring/builder.py` lines 100–108):
`core_identity`, `future_direction`, `motivation_themes`, `pivot_thesis`,
`direction_fit_score`, `motivation_fit_score`, `story_strength_score`, `motivation_brief`

**job_summary expected keys** (verified from `jobpipe/authoring/builder.py` lines 73–80):
`title`, `employer_name`, `sector`, `application_due`, `source_url`, `role_summary`

---

## 4. Module template

```python
# jobpipe/authoring/validation.py
"""Deterministic validation rules for AuthoringCaseContext.

All rules are pure, offline, and deterministic: no LLM calls, no network
access, no randomness, no time dependence.

Findings are encoded as prefixed strings in DocumentValidationResult.failures
(errors) and .warnings (warnings/info). The DocumentValidationResult schema is
not modified.

Scoring: score = clamp(1.0 - (errors * 0.2 + warnings * 0.05), 0.0, 1.0)
"""
from __future__ import annotations

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import DocumentValidationResult

# Required keys per field — verified against builder.py
_DECISION_BRIEF_REQUIRED_KEYS: frozenset[str] = frozenset({
    "final_decision",
    "recommendation_reason",
    "cv_focus",
    "act_now",
    "can_do_score",
    "can_get_score",
    "should_want_score",
    "can_explain_score",
})

_JOB_SUMMARY_REQUIRED_KEYS: frozenset[str] = frozenset({
    "title",
    "employer_name",
    "sector",
    "application_due",
    "source_url",
    "role_summary",
})

_NARRATIVE_BRIEF_EXPECTED_KEYS: frozenset[str] = frozenset({
    "core_identity",
    "future_direction",
    "motivation_themes",
    "pivot_thesis",
    "direction_fit_score",
    "motivation_fit_score",
    "story_strength_score",
    "motivation_brief",
})


# ---------------------------------------------------------------------------
# Rule functions — each returns (failures: list[str], warnings: list[str])
# ---------------------------------------------------------------------------


def _rule_required_field_absent(ctx: AuthoringCaseContext) -> tuple[list[str], list[str]]:
    """required_field_absent: mandatory top-level fields must be non-empty."""
    failures: list[str] = []
    if not ctx.candidate_id or not ctx.candidate_id.strip():
        failures.append("[required_field_absent] candidate_id is absent or blank")
    if not ctx.job_id or not ctx.job_id.strip():
        failures.append("[required_field_absent] job_id is absent or blank")
    if not ctx.job_summary:
        failures.append("[required_field_absent] job_summary is empty")
    if not ctx.decision_brief:
        failures.append("[required_field_absent] decision_brief is empty")
    if ctx.selected_evidence is None:
        failures.append("[required_field_absent] selected_evidence is None")
    return failures, []


def _rule_missing_decision_context(ctx: AuthoringCaseContext) -> tuple[list[str], list[str]]:
    """missing_decision_context: decision_brief must contain all required keys."""
    failures: list[str] = []
    if not ctx.decision_brief:
        # already caught by required_field_absent; skip to avoid duplicate
        return [], []
    for key in sorted(_DECISION_BRIEF_REQUIRED_KEYS):
        if key not in ctx.decision_brief:
            failures.append(
                f"[missing_decision_context] decision_brief is missing required key: {key!r}"
            )
    return failures, []


def _rule_empty_evidence_units(ctx: AuthoringCaseContext) -> tuple[list[str], list[str]]:
    """empty_evidence_units: selected_evidence must contain at least one entry."""
    if not ctx.selected_evidence:
        return (
            ["[empty_evidence_units] selected_evidence is empty — no evidence units selected for this job"],
            [],
        )
    return [], []


def _rule_narrative_empty(ctx: AuthoringCaseContext) -> tuple[list[str], list[str]]:
    """narrative_empty: if narrative_brief is provided, it must have content.

    Severity: warning (not error) — narrative context is optional for the MVP.
    """
    if ctx.narrative_brief is None:
        return [], []
    # Check whether any expected key has a non-empty value
    has_content = any(
        ctx.narrative_brief.get(k)
        for k in _NARRATIVE_BRIEF_EXPECTED_KEYS
    )
    if not has_content:
        return [], [
            "[narrative_empty] narrative_brief is present but has no content "
            "in any expected key"
        ]
    return [], []


def _rule_resume_job_mismatch(ctx: AuthoringCaseContext) -> tuple[list[str], list[str]]:
    """resume_job_mismatch: evidence unit IDs referenced in narrative_brief must
    have counterparts in selected_evidence; candidate_id must not be blank.

    The narrative_brief dict does not directly carry evidence_unit_ids, so this
    rule checks the structural relationship: if narrative_brief has
    'story_strength_score' > 0 but selected_evidence is empty, the narrative
    is unsupported. It also confirms candidate_id consistency (non-blank),
    which is the primary cross-field identity check available from the context.
    """
    failures: list[str] = []

    # Candidate identity consistency: candidate_id must be non-blank
    # (structural check — deeper cross-table ID checks are deferred to Slice 6)
    if ctx.candidate_id is not None and not ctx.candidate_id.strip():
        failures.append(
            "[resume_job_mismatch] candidate_id is blank — cannot establish "
            "evidence-candidate identity"
        )

    # Narrative references evidence but selected_evidence is empty
    if (
        ctx.narrative_brief is not None
        and ctx.narrative_brief.get("story_strength_score", 0)
        and not ctx.selected_evidence
    ):
        failures.append(
            "[resume_job_mismatch] narrative_brief claims story evidence "
            "(story_strength_score > 0) but selected_evidence is empty"
        )

    return failures, []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_score(n_errors: int, n_warnings: int) -> float:
    raw = 1.0 - (n_errors * 0.2 + n_warnings * 0.05)
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_RULES = [
    _rule_required_field_absent,
    _rule_missing_decision_context,
    _rule_empty_evidence_units,
    _rule_narrative_empty,
    _rule_resume_job_mismatch,
]


def validate_authoring_context(ctx: AuthoringCaseContext) -> DocumentValidationResult:
    """Run all deterministic validation rules against ctx.

    Returns a DocumentValidationResult. The result is:
    - passed=True iff failures is empty (warnings alone do not fail)
    - score computed as clamp(1.0 - errors*0.2 - warnings*0.05, 0.0, 1.0)
    - failures lists all error-severity rule findings (prefixed [rule_id])
    - warnings lists all warning-severity rule findings (prefixed [rule_id])

    All rules are pure and offline. Safe to call without side effects.
    """
    all_failures: list[str] = []
    all_warnings: list[str] = []

    for rule in _RULES:
        rule_failures, rule_warnings = rule(ctx)
        all_failures.extend(rule_failures)
        all_warnings.extend(rule_warnings)

    return DocumentValidationResult(
        passed=len(all_failures) == 0,
        score=_compute_score(len(all_failures), len(all_warnings)),
        failures=all_failures,
        warnings=all_warnings,
    )
```

---

## 5. Test plan

Test file: `tests/test_authoring_validation.py`

Mirror the fixture helper pattern established in `tests/test_authoring_builder.py`
(confirmed present in the repo). All tests synchronous. No anyio, no async.

### Fixture helpers (at top of test file)

```python
import dataclasses
from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import DocumentValidationResult
from jobpipe.authoring.validation import validate_authoring_context

def _good_ctx(**overrides) -> AuthoringCaseContext:
    """Well-formed context that should pass all rules."""
    values = dict(
        candidate_id="cand-1",
        job_id="job-001",
        evaluation_id="run-abc:job-001",
        job_summary={
            "title": "Product Manager",
            "employer_name": "Acme AS",
            "sector": "Technology",
            "application_due": "2026-05-01",
            "source_url": "https://example.test/job-001",
            "role_summary": "Lead product discovery.",
        },
        decision_brief={
            "final_decision": "APPLY",
            "recommendation_reason": "Strong fit.",
            "cv_focus": ["roadmap"],
            "act_now": "pursue_now",
            "can_do_score": 84,
            "can_get_score": 76,
            "should_want_score": 81,
            "can_explain_score": 88,
        },
        selected_evidence=[
            {"evidence_unit_id": "evidence-1", "canonical_text": "Led roadmap work."}
        ],
        narrative_brief={
            "core_identity": ["Product leader"],
            "future_direction": ["AI services"],
            "motivation_themes": [],
            "pivot_thesis": ["Credible move"],
            "direction_fit_score": 82,
            "motivation_fit_score": 79,
            "story_strength_score": 88,
            "motivation_brief": "The role fits.",
        },
        artifact_plan=None,
    )
    values.update(overrides)
    return AuthoringCaseContext(**values)
```

### Test cases

**1. Golden path — zero issues**
```
test_validate_well_formed_context_passes
  ctx = _good_ctx()
  result = validate_authoring_context(ctx)
  assert result.passed is True
  assert result.failures == []
  assert result.warnings == []
  assert result.score == 1.0
```

**2. `required_field_absent` — blank candidate_id**
```
test_required_field_absent_blank_candidate_id
  ctx = _good_ctx(candidate_id="")
  result = validate_authoring_context(ctx)
  assert result.passed is False
  assert any("required_field_absent" in f for f in result.failures)
  assert any("candidate_id" in f for f in result.failures)
```

**3. `required_field_absent` — empty job_summary**
```
test_required_field_absent_empty_job_summary
  ctx = _good_ctx(job_summary={})
  result = validate_authoring_context(ctx)
  assert result.passed is False
  assert any("job_summary" in f for f in result.failures)
```

**4. `missing_decision_context` — missing required key**
```
test_missing_decision_context_missing_key
  brief = _good_ctx().decision_brief.copy()
  del brief["final_decision"]
  ctx = _good_ctx(decision_brief=brief)
  result = validate_authoring_context(ctx)
  assert result.passed is False
  assert any("missing_decision_context" in f for f in result.failures)
  assert any("final_decision" in f for f in result.failures)
```

**5. `missing_decision_context` — all eight keys present passes rule**
```
test_missing_decision_context_all_keys_present
  ctx = _good_ctx()
  result = validate_authoring_context(ctx)
  assert not any("missing_decision_context" in f for f in result.failures)
```

**6. `empty_evidence_units` — selected_evidence is empty list**
```
test_empty_evidence_units_fails
  ctx = _good_ctx(selected_evidence=[])
  result = validate_authoring_context(ctx)
  assert result.passed is False
  assert any("empty_evidence_units" in f for f in result.failures)
```

**7. `narrative_empty` — present but all values empty → warning, not error**
```
test_narrative_empty_produces_warning_not_error
  ctx = _good_ctx(narrative_brief={
      "core_identity": [], "future_direction": [], "motivation_themes": [],
      "pivot_thesis": [], "direction_fit_score": 0, "motivation_fit_score": 0,
      "story_strength_score": 0, "motivation_brief": "",
  })
  result = validate_authoring_context(ctx)
  assert result.passed is True      # warnings do not fail
  assert result.failures == []
  assert any("narrative_empty" in w for w in result.warnings)
```

**8. `narrative_empty` — None is valid (not a warning)**
```
test_narrative_empty_none_is_valid
  ctx = _good_ctx(narrative_brief=None)
  result = validate_authoring_context(ctx)
  assert not any("narrative_empty" in w for w in result.warnings)
```

**9. `resume_job_mismatch` — narrative claims evidence but selected_evidence empty**
```
test_resume_job_mismatch_narrative_without_evidence
  ctx = _good_ctx(
      selected_evidence=[],
      narrative_brief={
          **_good_ctx().narrative_brief,
          "story_strength_score": 88,
      },
  )
  result = validate_authoring_context(ctx)
  assert result.passed is False
  assert any("resume_job_mismatch" in f for f in result.failures)
```

**10. Score computation — one error, one warning**
```
test_score_one_error_one_warning
  # Induce 1 error (missing candidate_id) and 1 warning (narrative_empty)
  ctx = _good_ctx(
      candidate_id="",
      narrative_brief={k: ([] if isinstance(v, list) else 0 if isinstance(v, int) else "")
                       for k, v in _good_ctx().narrative_brief.items()},
  )
  result = validate_authoring_context(ctx)
  # score = clamp(1.0 - 1*0.2 - 1*0.05, 0.0, 1.0) = 0.75
  assert abs(result.score - 0.75) < 0.001
```

**11. Score clamped at 0.0 for many errors**
```
test_score_clamped_at_zero
  ctx = _good_ctx(
      candidate_id="",
      job_id="",
      job_summary={},
      decision_brief={},
      selected_evidence=[],
  )
  result = validate_authoring_context(ctx)
  assert result.score == 0.0
```

**12. `passed` is False when failures non-empty, True when only warnings**
```
test_passed_false_on_failures
  ctx = _good_ctx(candidate_id="")
  assert validate_authoring_context(ctx).passed is False

test_passed_true_on_warnings_only
  ctx = _good_ctx(narrative_brief={k: ([] if isinstance(_good_ctx().narrative_brief[k], list) else 0 if isinstance(_good_ctx().narrative_brief[k], int) else "") for k in _good_ctx().narrative_brief})
  result = validate_authoring_context(ctx)
  assert result.passed is True
  assert len(result.warnings) > 0
```

**13. `test_no_crewai_import`**

Mirror exact pattern from `tests/test_authoring_builder.py` lines 275–291:

```python
def test_no_crewai_import() -> None:
    env = None
    git_grep_dir = Path("C:/Program Files/Git/usr/bin")
    if git_grep_dir.exists():
        env = dict(os.environ)
        env["PATH"] = f"{git_grep_dir}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        ["grep", "-r", "crewai", "jobpipe/", "--include=*.py"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 1, f"Unexpected crewai reference found:\n{result.stdout}"
    assert result.stdout == ""
```

**14. `DocumentValidationResult` is a valid pydantic model (model_dump roundtrip)**
```
test_result_model_dump_roundtrip
  ctx = _good_ctx()
  result = validate_authoring_context(ctx)
  dumped = result.model_dump()
  assert set(dumped.keys()) == {"passed", "score", "failures", "warnings"}
  assert isinstance(dumped["passed"], bool)
  assert isinstance(dumped["score"], float)
```

---

## 6. Banned imports check

No import of any of the following is permitted in `jobpipe/authoring/validation.py`
or `tests/test_authoring_validation.py`:

- `crewai`
- `crewai_tools`
- `langchain`
- `openai`

The `test_no_crewai_import` grep assertion (test 13 above) enforces this at the
`crewai` level across all of `jobpipe/`. Codex must also visually confirm no
`langchain` or `openai` import is introduced.

---

## 7. Risks + open questions

**Schema constraint acknowledged:** `DocumentValidationResult.failures` and
`.warnings` are `list[str]`. Per-finding structured metadata (`rule_id` as a
discrete field, `path`, `severity`) cannot be added without modifying the schema,
which is out of scope. The bracket-prefix encoding
(`"[rule_id] message"`) preserves machine-parseability without a schema change.
If the coordinator wants a richer schema (e.g. `failures: list[ValidationFinding]`),
that requires a spec update and a separate slice.

**CLI flag deferred:** The optional `--validate` flag on
`jobpipe build-authoring-context` is **not** included in this slice. The smoke
CLI module (`jobpipe/cli/build_authoring_context.py`) is not touched here.
CLI integration is deferred to **Slice 6** (to be scoped after this slice merges).
Reason: adding a flag to the smoke CLI requires reading and editing Slice 4's
output file, which increases diff footprint and coordination risk. Keeping this
slice to one new file is safer.

**`resume_job_mismatch` scope:** The rule as implemented covers (a) blank
`candidate_id` and (b) narrative-claims-evidence-but-evidence-is-empty. Deep
cross-ID matching (evidence_unit_id in narrative_brief referencing a specific
entry in selected_evidence) is not implemented because `narrative_brief` does
not carry a structured list of referenced IDs — it is a flat dict of scores and
text fields. If a future slice adds `evidence_unit_ids` to `narrative_brief`,
this rule should be extended then.

**No open blocking questions.** Codex can proceed directly to implementation.

---

## 8. Project linkage

- Project: #6
- Item ID: PVTI_lAHOCSFbLc4BJUdazgqmusE
- Status (on brief approval): In progress
- Priority: P1
- Area: CV Authoring
- Issue: #63
- Branch: codex/T002-authoring-mvp (pre-staged at ffbfc4d)

---

## Self-review pass (8-item checklist per docs/ai-playbook.md)

1. **Scope** — ✅ One new file (`validation.py`) + one test file. Two-file diff.
   No changes to any existing file.
2. **Canonical-source map** — ✅ Every field read by the validator is mapped in
   §3 Signatures table and in `_DECISION_BRIEF_REQUIRED_KEYS` /
   `_NARRATIVE_BRIEF_EXPECTED_KEYS` constants, both derived from actual
   `builder.py` source.
3. **Escalation gates named** — ✅ None of the Approval Gates are tripped: no
   schema change, no auth, no billing, no migration, no deployment, no secret,
   no pipeline-semantic change, no model-cost change, no OSS/Workbench boundary.
4. **Contract purity** — ✅ `test_no_crewai_import` (test 13) is included. No
   crewai/langchain/openai import in module or tests (§6).
5. **Tests** — ✅ 14 named tests covering all 5 rules + score + roundtrip +
   crewai check. Pattern mirrors `test_authoring_builder.py` (proven in this repo).
   Test command uses `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -p no:debugging -p no:cacheprovider`.
6. **Reversibility** — ✅ Single commit, no migration, no runtime state change.
   Clean revert: `git revert <sha>` deletes one new file and one new test file.
7. **GitHub Project link** — ✅ Item ID `PVTI_lAHOCSFbLc4BJUdazgqmusE`, Issue #63,
   Project #6 listed in §8.
8. **Prompt self-containedness** — ✅ Codex prompt (below) contains all file paths,
   acceptance criteria, validation commands, escalation gates, and out-of-scope list.

---

## Codex worker prompt (ready-to-paste)

```
You are the Codex implementer on worktree ../Jobpipe-codex-v2, branch
codex/T002-authoring-mvp. Implement T002 Slice 5 (Issue #63): deterministic
validation rules on AuthoringCaseContext. Coordinator has APPROVED this slice.

Read first (in order):
  CLAUDE.md
  PRODUCT_VISION.md
  DEPENDENCY_POLICY.md
  docs/ai-playbook.md
  docs/current-state.json
  docs/execplans/T002-slice-5.md  ← primary instruction source
  jobpipe/authoring/case_context.py      (read only)
  jobpipe/authoring/output_models.py     (read only)
  jobpipe/authoring/builder.py           (read only)
  tests/test_authoring_builder.py        (pattern reference)
  tests/test_authoring_output_models.py  (pattern reference)

GOAL
Implement validate_authoring_context in a new jobpipe/authoring/validation.py
that runs 5 deterministic rules on an AuthoringCaseContext and returns a
DocumentValidationResult. Pure, offline, no LLM.

IN SCOPE
  jobpipe/authoring/validation.py   — new file, implement exactly
  tests/test_authoring_validation.py — new file, 14 tests

OUT OF SCOPE — do not touch, stop and escalate if any of these seem required:
  jobpipe/authoring/case_context.py        (do NOT modify)
  jobpipe/authoring/output_models.py       (do NOT modify — no schema change)
  jobpipe/authoring/builder.py             (do NOT modify)
  jobpipe/cli/build_authoring_context.py   (do NOT modify — CLI flag is Slice 6)
  jobpipe/stages/, jobpipe/decision/, jobpipe/model/  (do NOT touch)
  pyproject.toml                           (no new dependencies)

CONSTRAINTS
  - No crewai, langchain, openai, autogen import anywhere in the new files
  - No LLM calls, no network, no randomness, no time.time() / datetime.now()
  - Do NOT modify DocumentValidationResult schema
  - Encode findings as prefixed strings: "[rule_id] message" in failures/warnings
  - score = clamp(1.0 - errors*0.2 - warnings*0.05, 0.0, 1.0)
  - passed = True iff failures is empty

ACCEPTANCE CRITERIA
  - All 14 tests in tests/test_authoring_validation.py pass
  - python compile_check.py exits 0
  - test_no_crewai_import passes (grep returns exit 1, stdout empty)
  - validate_authoring_context(good_ctx).passed is True with score == 1.0
  - narrative_empty fires as warning only — passed stays True
  - missing_decision_context fires one finding per missing key

VALIDATION COMMANDS (run in order, paste verbatim output)
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_authoring_validation.py -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp
  python compile_check.py
  python -c "from jobpipe.authoring.validation import validate_authoring_context; print('ok')"
  grep -r "crewai" jobpipe/ --include="*.py" && echo "FAIL: crewai found" || echo "ok: no crewai"

ESCALATION GATES — stop and ask coordinator before acting if:
  - Any reason to modify case_context.py, output_models.py, or builder.py
  - Any reason to add an external dependency
  - Any ambiguity about DocumentValidationResult schema or field names
  - Any OSS/Workbench boundary question
  - Any reason to modify CLI files (deferred to Slice 6)

DELIVERABLE
  One commit on branch codex/T002-authoring-mvp
  PR into main, linked to Project #6 item PVTI_lAHOCSFbLc4BJUdazgqmusE (#63)
  Report: commands run, test output (verbatim), files touched, any surprises
```
