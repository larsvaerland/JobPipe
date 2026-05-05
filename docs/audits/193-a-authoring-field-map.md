# Audit: Authoring Field Map — Issue #193-A

**Date:** 2026-05-06
**Issue:** [#194 — 193-A: Audit data fed to CrewAI authoring flows vs v3 pipeline outputs](https://github.com/larsvaerland/Jobpipe/issues/194)
**Status:** Read-only audit; no production code changed.

---

## Purpose

Map every field available in the v3 pipeline output (dashboard row dict) against what
`AuthoringCaseContext` currently accepts. Identify fields that are already produced but
silently discarded before the authoring crew receives them.

---

## Source Files Audited

| File | Role |
|---|---|
| `jobpipe/authoring/case_context.py` | Immutable authoring contract — the target struct |
| `jobpipe/authoring/builder.py` | Builds `AuthoringCaseContext` from `JobContext` |
| `jobpipe/cli/generate_cover_letter.py` | CLI path: builds context from dashboard row |
| `jobpipe/cli/export_dashboard.py` | Projects v3 stage JSONs into row dict |
| `jobpipe/stages/application_pack.py` | Reference: correctly wired v3 path |
| `jobpipe/authoring/smoke_cli.py` | Smoke CLI path; loads stage JSONs directly |

---

## Field Inventory

### Fields Currently in `AuthoringCaseContext`

| Field | Type | Source |
|---|---|---|
| `candidate_id` | `str` | `JobContext.meta["candidate_id"]` |
| `job_id` | `str` | `JobContext.job_id` |
| `evaluation_id` | `str \| None` | `JobContext.meta.get("evaluation_id")` |
| `job_summary` | `dict` | `JobContext.job` + `JobParse.role_summary` |
| `decision_brief` | `dict` | `ModeratorOut` + `JobDecisionTable` signals |
| `selected_evidence` | `list[dict]` | `CandidateEvidenceSelection` serialized |
| `narrative_brief` | `dict \| None` | `CandidateNarrativeProfile` + `JobNarrativeAssessment` |
| `artifact_plan` | `dict \| None` | Reserved; `None` in MVP |

### v3 Fields Available in Dashboard Row (from `export_dashboard._build_detail_row`)

These fields are **already computed** by the pipeline and projected into the dashboard row
dict at lines 259–274 of `export_dashboard.py`, but are **not mapped** into
`AuthoringCaseContext`:

| Row Key | Source Stage JSON | Source Key | Type | Currently in `AuthoringCaseContext`? |
|---|---|---|---|---|
| `advantage_type` | `advantage_assessment_v3.json` | `advantage_type` | `str` | ❌ Missing |
| `differentiation_signals` | `advantage_assessment_v3.json` | `differentiation_signals` | `list[str]` | ❌ Missing |
| `neutralizing_evidence` | `advantage_assessment_v3.json` | `neutralizing_evidence` | `list[str]` | ❌ Missing |
| `recruiter_hook` | `advantage_assessment_v3.json` | `recruiter_hook` | `str` | ❌ Missing |
| `narrative_positioning_angle` | `narrative_strategy_v3.json` | `positioning_angle` | `str` | ❌ Missing |
| `narrative_brand_frame` | `narrative_strategy_v3.json` | `brand_frame` | `str` | ❌ Missing |
| `narrative_why_me_now` | `narrative_strategy_v3.json` | `why_me_now` | `str` | ❌ Missing |
| `cover_letter_strategy` | `narrative_strategy_v3.json` | `cover_letter_strategy` | `str` | ❌ Missing |

---

## Gap Analysis

### Path 1: `application_pack` stage (`stages/application_pack.py`)

`_build_application_pack_payload()` reads `job_ctx.advantage_assessment_v3` and
`job_ctx.narrative_strategy_v3` directly from `JobContext` and includes them in the
OpenAI payload. **This path is correctly wired. It is the reference implementation.**

### Path 2: `generate-cover-letter` / `prepare-application` CLI

`generate_cover_letter.build_authoring_context()` reads from the dashboard row dict.
The row already contains all 8 v3 fields listed above, but **`build_authoring_context()`
never maps them** into `AuthoringCaseContext`. They are silently discarded.

### Path 3: `smoke_cli.build_context_for_job()`

Loads stage JSONs directly from disk. Currently does NOT load
`advantage_assessment_v3.json` or `narrative_strategy_v3.json`. The stub
`_build_application_pack_contexts()` raises `NotImplementedError`.

### Cover Letter Generator (`authoring/cover_letter_generator.py`)

The OpenAI payload sent by `generate_cover_letter()` contains only:
`job_summary`, `decision_brief`, `selected_evidence[:8]`, `narrative_brief`,
`artifact_plan`. The system prompt `_SYSTEM_PROMPT` has no instructions for v3 signals.
Even if v3 fields were wired in, the model would not know how to use them.

---

## Remediation Plan (follow-up issues)

| Issue | Slice | Scope |
|---|---|---|
| #195 | 193-B | Add 8 optional v3 fields to `AuthoringCaseContext` as `str \| None` / `list[str]` |
| #196 | 193-C | Wire v3 fields into `generate_cover_letter.build_authoring_context()` |
| #197 | 193-D | Wire v3 fields into `builder.build_authoring_case_context()` from `JobContext` |
| #198 | 193-E | Wire v3 stage JSONs into `smoke_cli.build_context_for_job()` |
| #199 | 193-F | Update `cover_letter_generator.py` system prompt to instruct on v3 signals |
| #200 | 193-G | End-to-end smoke test on a real APPLY job |

---

## Conclusion

Eight v3 signal fields are produced by the pipeline and projected into the dashboard row
but are never passed to the authoring crew. The `application_pack` stage correctly wires
them; the CLI and smoke paths do not. All three code paths need to be brought to parity
with `application_pack` before the CrewAI authoring crew can use v3 positioning signals.
