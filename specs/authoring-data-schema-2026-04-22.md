# Authoring Data Schema: Reactive Resume → AuthoringCaseContext → Cover Letter

**Date:** 2026-04-22
**Status:** Proposal — awaiting coordinator review before any implementation slice
**Governing spec:** `specs/ai-document-authoring-mvp-workflow-2026-04-21.md`
**Prerequisite reading:** `jobpipe/core/primary_db.py` (schema_version 8),
`jobpipe/decision/evidence.py`, `jobpipe/decision/narrative.py`,
`jobpipe/authoring/case_context.py`, `jobpipe/model/schema.py`

> **Note:** `specs/jobsync-integration-seam.md` and
> `specs/reactive-resume-integration-seam.md` were referenced in the task but
> do not exist on the current branch. This spec is grounded in the live DB
> schema (`primary_db.py`) and the existing projection/CLI files instead.

---

## Executive Summary

The current authoring pipeline has a clean machine-readable history source
(`resume_json` in `candidate_profiles`) but a brittle strategic input
(`profile_pack_md` — free-form markdown that `narrative.py` parses with
keyword heuristics). This spec defines:

1. A minimal structured **profile supplement** schema to replace the markdown
   strategic sections, stored in the existing `candidates` table (no new table
   required for MVP).
2. A complete **`build_authoring_case_context()`** function signature and data
   source map that reads from DB only — no artifact file traversal at build
   time.
3. A **cover letter output + storage** contract using the existing
   `generated_documents` table.
4. A **CV round-trip** field mapping from `tailored_cv_projection` back to
   JSON Resume variant format.
5. A **compatibility checklist** covering all field name and type seams.

---

## 1. Profile Supplement Schema

### 1.1 What Reactive Resume JSON already provides

`resume_json` (JSON Resume format, stored in `candidate_profiles.resume_json`)
already contains:

```
work[]       → company, position, startDate, endDate, summary, highlights[]
projects[]   → name, description, highlights[]
education[]  → institution, area, studyType, startDate, endDate
skills[]     → name, level, keywords[]
languages[]  → language, fluency
basics       → name, email, location, summary, profiles[]
```

`evidence.py:derive_candidate_evidence_units()` already processes
`work[].highlights`, `projects[]`, and `education[]` into structured
`CandidateEvidenceUnit` objects. No new evidence extraction logic is needed.

### 1.2 What is missing — the gap `profile_pack_md` was filling

The narrative builder (`narrative.py`) currently calls:
- `_future_direction_from_profile(profile_pack, ...)` — keyword-matches
  "product", "project", "change" in raw markdown text
- `_motivation_themes_from_profile(profile_pack, ...)` — keyword-matches
  "ownership", "structure", "impact", "pivot" in raw markdown text

These heuristics work because `profile_pack_md` contains free-form strategic
statements. The new schema must make these signals explicit and machine-readable.

### 1.3 Proposed YAML schema — `profile_supplement.yaml`

This file is imported via a bootstrap CLI command and stored as structured
columns in the `candidates` table (fields that already exist) plus a new
`profile_supplement_json` column (one migration).

```yaml
# profile_supplement.yaml
# Minimal structured supplement — only what the authoring pipeline actually needs.
# Import with: jobpipe bootstrap-state-db --profile-supplement profile_supplement.yaml

schema_version: "1"
candidate_id: "default"                 # must match candidates.candidate_id

# --- Positioning (replaces profile_pack_md positioning section) ---
seniority_label: "Senior"               # → candidates.seniority_label
positioning_summary: |                  # → candidates.positioning_summary
  Product and change lead with 10+ years across digital transformation,
  service design, and cross-functional delivery in public sector and fintech.

# --- Strategic direction (replaces profile_pack_md goals section) ---
strategic_direction: |                  # → candidates.strategic_direction
  Moving toward product-facing roles with clearer ownership scope,
  AI-enabled services, and roles where delivery and coordination remain
  legible strengths.

# --- Targeting (new — stored in profile_supplement_json) ---
target_role_families:                   # list[str] — maps to _ROLE_FAMILY_PATTERNS keys
  - product
  - project_delivery
  - transformation

target_domains:                         # list[str] — maps to _DOMAIN_PATTERNS keys
  - public_sector
  - saas_software

# --- Pivot / transition framing (new — stored in profile_supplement_json) ---
pivot_thesis: |
  The move is credible because delivery, stakeholder coordination, and
  change-enabling capabilities transfer across adjacent titles. Not a
  narrow-specialist profile.

# --- Tone constraints (new — stored in profile_supplement_json) ---
tone_rules:
  - "Grounded, concrete, and not overexcited."
  - "Future-oriented without sounding vague or inflated."
  - "Specific about value and evidence, not adjective-heavy."

# --- Hard constraints (new — stored in profile_supplement_json) ---
avoid_roles:                            # roles/domains to exclude from evidence selection
  - []
avoid_claims:                           # claims the candidate does not want to make
  - "Do not claim deep technical/engineering ownership."

# --- Optional legacy import path ---
# profile_pack_md_path: "profile_pack.md"  # if set, profile_pack_md is read and stored
#                                           # as a legacy fallback only, not primary schema
```

### 1.4 Field-to-destination mapping

| YAML field | DB destination | Python source | Notes |
|---|---|---|---|
| `seniority_label` | `candidates.seniority_label` | Already a column | `UPDATE candidates SET seniority_label = ?` |
| `positioning_summary` | `candidates.positioning_summary` | Already a column | `UPDATE candidates SET positioning_summary = ?` |
| `strategic_direction` | `candidates.strategic_direction` | Already a column | `UPDATE candidates SET strategic_direction = ?` |
| `target_role_families` | `candidates.profile_supplement_json` → `target_role_families` | **New column** | Stored as JSON list |
| `target_domains` | `candidates.profile_supplement_json` → `target_domains` | **New column** | Stored as JSON list |
| `pivot_thesis` | `candidates.profile_supplement_json` → `pivot_thesis` | **New column** | String |
| `tone_rules` | `candidates.profile_supplement_json` → `tone_rules` | **New column** | Stored as JSON list |
| `avoid_roles` | `candidates.profile_supplement_json` → `avoid_roles` | **New column** | Stored as JSON list |
| `avoid_claims` | `candidates.profile_supplement_json` → `avoid_claims` | **New column** | Stored as JSON list |

**Required migration (one ALTER TABLE):**

```sql
ALTER TABLE candidates
ADD COLUMN profile_supplement_json TEXT NOT NULL DEFAULT '{}';
```

This must go through `_ensure_column()` in `primary_db.py` and increment
`SCHEMA_VERSION` to `"9"`. No data loss; existing rows get `'{}'`.

### 1.5 Legacy import path

`profile_pack_md` remains readable from `candidate_profiles.profile_pack_md`
as a fallback. The authoring builder reads structured fields first; falls
back to markdown heuristics only if `profile_supplement_json` is absent or
empty. The fallback is **not** the primary path going forward.

---

## 2. Authoring Context Builder Spec

### 2.1 Function signature

```python
def build_authoring_case_context(
    *,
    candidate_id: str,
    job_id: str,
    db_path: str | Path | None = None,
) -> AuthoringCaseContext:
```

**Changes from current builder in `jobpipe/authoring/builder.py`:**
- Current builder takes pre-built `job_ctx`, `decision_ctx`, `evidence_ctx`,
  `narrative_ctx` objects as positional args.
- This spec describes a **higher-level convenience wrapper** that loads from
  DB and constructs those objects internally.
- The existing low-level `build_authoring_case_context(job_ctx, decision_ctx,
  evidence_ctx, narrative_ctx, *, candidate_id, evaluation_id)` stays unchanged.
- The new wrapper should live at
  `jobpipe/authoring/context_loader.py` to avoid naming collision.

### 2.2 Data source map

```
INPUT: candidate_id, job_id, db_path
       ↓
LOAD: candidate row
      └─ candidates WHERE candidate_id = ?
         → positioning_summary, strategic_direction, seniority_label,
           profile_supplement_json (target_role_families, target_domains,
           pivot_thesis, tone_rules, avoid_claims)

LOAD: active candidate profile
      └─ candidate_profiles WHERE candidate_id = ? AND is_active = 1
         ORDER BY updated_at DESC LIMIT 1
         → resume_json           (primary evidence source)
         → profile_pack_md       (legacy fallback for narrative only)

LOAD: job evaluation
      └─ job_evaluations WHERE candidate_id = ? AND job_id = ?
         → title, employer, sector, applicationDue, source_url,
           triage_explanation, triage_signals,
           fit_score, pivot_score,
           final_decision, recommendation_reason, cv_focus,
           raw_match_json (→ overlaps, gaps, hard_blockers, match_notes),
           raw_moderator_json (→ final_decision, cv_focus)

LOAD: decision table
      └─ job_decision_tables WHERE candidate_id = ? AND job_id = ?
         → can_do_score, can_get_score, should_want_score, can_explain_score,
           act_now

LOAD: selection assessment (optional — for focus_terms)
      └─ job_selection_assessments WHERE candidate_id = ? AND job_id = ?
         → overlaps, gaps (to seed focus_terms alongside cv_focus)

DERIVE: evaluation_id = latest run_id from job_evaluations.run_id + ":" + job_id

DERIVE: evidence units
        derive_candidate_evidence_units(resume_json, candidate_id=candidate_id)

DERIVE: focus_terms
        union(cv_focus[], overlaps[]) from job_evaluations

DERIVE: selected evidence
        select_candidate_evidence_units(
            job_view,
            evidence_units,
            focus_terms=focus_terms,
            limit=6,
        )

DERIVE: job_view dict (for decision/narrative builders)
        {title, employer, sector, description_snip, triage_explanation,
         triage_signals, fit_score, pivot_score, final_decision,
         recommendation_reason, detail: {overlaps, gaps, hard_blockers}}

DERIVE: decision_ctx
        build_decision_context(job_view, candidate_profile=supplement_dict)
        where supplement_dict = {
            "strategic_direction": candidates.strategic_direction,
            "target_role_families": supplement_json["target_role_families"],
            "target_domains": supplement_json["target_domains"],
        }
        # replaces parse_profile_pack(profile_pack_md)

DERIVE: narrative_ctx
        build_candidate_narrative_context(
            job_view,
            profile_text,           # see §2.3
            evidence_units,
            selected_evidence_units,
            candidate_id=candidate_id,
            decision_table=decision_ctx.decision_table,
        )

OUTPUT: AuthoringCaseContext(
    candidate_id=candidate_id,
    job_id=job_id,
    evaluation_id=evaluation_id,
    job_summary={title, employer_name, sector, application_due, source_url, role_summary},
    decision_brief={final_decision, recommendation_reason, cv_focus, act_now,
                    can_do_score, can_get_score, should_want_score, can_explain_score},
    selected_evidence=[CandidateEvidenceSelection.model_dump() × 0-6],
    narrative_brief={core_identity, future_direction, motivation_themes,
                     pivot_thesis, direction_fit_score, motivation_fit_score,
                     story_strength_score, motivation_brief},
    artifact_plan=None,
)
```

### 2.3 Narrative profile_text construction

`narrative.py:build_candidate_narrative_context()` currently takes a
`profile_pack: str` argument. Rather than changing its signature now, pass a
synthesized text string built from structured fields:

```python
def _build_profile_text(
    positioning_summary: str,
    strategic_direction: str,
    pivot_thesis: str,
    tone_rules: list[str],
    target_role_families: list[str],
    target_domains: list[str],
) -> str:
    """Synthesize a profile text string from structured supplement fields.

    This preserves compatibility with narrative.py's keyword-matching logic
    while making the input machine-readable at the source.
    The resulting string is NOT stored; it is ephemeral per build call.
    """
    lines = []
    if positioning_summary:
        lines.append(positioning_summary)
    if strategic_direction:
        lines.append(strategic_direction)
    if pivot_thesis:
        lines.append(pivot_thesis)
    if target_role_families:
        lines.append(f"Target role families: {', '.join(target_role_families)}.")
    if target_domains:
        lines.append(f"Target domains: {', '.join(target_domains)}.")
    lines.extend(tone_rules)
    return "\n".join(lines)
```

**Longer-term (post-MVP):** `narrative.py` should accept a structured
`CandidateStrategyProfile` dataclass instead of free-form text. That is a
Yellow gate — it changes a shared module signature used by the full pipeline.
Deferred to a future spec.

### 2.4 What drives evidence selection

Evidence selection (`select_candidate_evidence_units`) is driven by:
1. `job_view["detail"]["overlaps"]` — from `raw_match_json`
2. `cv_focus` — from `job_evaluations.cv_focus` (JSON text → list)
3. Job title, sector, `description_snip`
4. Optionally: `target_role_families` and `target_domains` from supplement
   can be added to `focus_terms` to bias toward candidate's stated direction

These are already the `focus_terms` fed to `_job_terms()` in `evidence.py`.
No change to evidence.py is needed for MVP.

### 2.5 Error handling

The loader must raise `ValueError` (not `SystemExit`) for:
- No active `candidate_profiles` row → `"No active candidate profile for candidate_id=?"`
- No `job_evaluations` row → `"No evaluation found for candidate_id=?, job_id=?"`
- No moderator output (`final_decision` blank) → `"Job evaluation has no moderator output"`

These map to the same guards in `builder.py` (`moderator is None`, `parsed is None`).

---

## 3. Cover Letter Round-Trip

### 3.1 Should Claude refine the CrewAI output?

**Recommendation: yes, as an optional second pass, not mandatory.**

- CrewAI (via `ApplicationPackOut`) produces `cover_letter_draft: str` — a
  full draft in Norwegian.
- A Claude refinement pass (tone/voice polish) should be opt-in, triggered by
  `--refine` flag or explicit user request.
- The unrefined draft is stored first (status `"draft"`); refined output is
  stored as a second row (status `"refined"`).
- Rationale: storing the raw CrewAI output preserves provenance and allows
  regeneration without re-running the crew.

### 3.2 Output format

Cover letter draft is stored as **plain text (UTF-8 string)**. No markdown
sections, no JSON envelope. The draft itself may contain natural paragraph
breaks (double newlines). If a DOCX render is requested, it is produced as a
separate artifact by a future render step — not at draft generation time.

```python
# Cover letter storage schema (conceptual — not a new model)
cover_letter_record = {
    "document_id": "<uuid>",
    "candidate_id": candidate_id,
    "job_id": job_id,
    "evaluation_id": evaluation_id,
    "kind": "cover_letter",             # → generated_documents.kind
    "producer": "crewai_author",        # → generated_documents.producer
    "status": "draft",                  # "draft" | "refined" | "final"
    "storage_path": "",                 # empty for MVP (stored inline)
    "preview_text": draft[:300],        # first 300 chars
    "document_json": {
        "cover_letter_draft": draft,    # full text
        "evaluation_id": evaluation_id,
        "evidence_refs": [...],         # from GeneratedApplicationPackage.evidence_refs
        "gap_notes": [...],             # from GeneratedApplicationPackage.gap_notes
        "validation": {...},            # DocumentValidationResult.model_dump()
        "producer_version": "1",
    },
}
```

### 3.3 Storage path

Stored via `insert_generated_document()` in `jobpipe/core/primary_db.py`
into the existing `generated_documents` table. No new table required.

For MVP: `storage_path = ""` (document stored inline in `document_json`).
For post-MVP: `storage_path = f"documents/{candidate_id}/{job_id}/cover_letter_{document_id}.txt"` under `JOBPIPE_DATA_DIR/documents/`.

CLI command:

```bash
jobpipe build-authoring-context --job-id <job_id> --generate-cover-letter
# or two-step:
jobpipe build-authoring-context --job-id <job_id> --out ctx.json
jobpipe generate-cover-letter --ctx ctx.json
```

### 3.4 Fields most important for cover letter vs. CV tailoring

| AuthoringCaseContext field | Cover letter | CV tailoring | Notes |
|---|---|---|---|
| `narrative_brief.motivation_brief` | ⭐⭐⭐ primary | ○ minor | Opening hook and fit statement |
| `narrative_brief.pivot_thesis` | ⭐⭐ | ○ | Credibility framing for adjacent move |
| `decision_brief.recommendation_reason` | ⭐⭐ | ○ | Why this role |
| `decision_brief.cv_focus` | ⭐ | ⭐⭐⭐ primary | Which bullets to surface |
| `selected_evidence` | ⭐ | ⭐⭐⭐ primary | The raw material for bullets |
| `narrative_brief.core_identity` | ⭐⭐ | ⭐ | Headline / summary |
| `decision_brief.act_now` | ⭐ | ○ | Urgency/confidence signal |
| `job_summary.role_summary` | ⭐ | ⭐⭐ | Mirror role language back |
| `decision_brief.can_do_score` | ○ | ⭐⭐ | Guide gap mitigation framing |

**Implication for CrewAI prompt design:** the cover letter agent should receive
`narrative_brief` and `decision_brief.recommendation_reason` as primary inputs.
The CV projection agent should receive `selected_evidence` and
`decision_brief.cv_focus` as primary inputs. These are currently blended into
one `AuthoringCaseContext` payload — which is correct — but the agent
instructions should weight them differently.

---

## 4. Tailored CV Round-Trip Back to Reactive Resume

### 4.1 Current output shape

`ReactiveResumeTailoredCVProjection` (from `jobpipe/model/schema.py` line 214):

```python
class ReactiveResumeTailoredCVProjection(BaseModel):
    headline: str = ""
    summary_text: str = ""
    section_plan: list[dict] = []      # ordered section list with display hints
    selected_bullets: list[str] = []   # evidence-backed bullet strings
    provenance: dict = {}              # evidence_unit_ids → bullet mapping
    render_target: ReactiveResumeRenderTarget = "reactive_resume_json"
```

### 4.2 Mapping to JSON Resume variant

A **variant** is a copy of the base `resume_json` with targeted fields patched.
It is stored as a new `candidate_profiles` row (`is_active = 0`, `source_kind
= "tailored_variant"`) — NOT overwriting the base profile.

| `tailored_cv_projection` field | JSON Resume variant field | Notes |
|---|---|---|
| `headline` | `basics.headline` | Replaces or adds the JSON Resume headline field |
| `summary_text` | `basics.summary` | Replaces the summary; base summary preserved in provenance |
| `selected_bullets` | Distributed to `work[n].highlights[]` | Assignment driven by `provenance` map: each bullet traces back to `source_ref` of the evidence unit, which encodes `work:{company}:{position}:{index}` |
| `section_plan` | `sections` (Reactive Resume metadata) | Reactive Resume uses a `sections` key for ordering; this maps to `section_plan` ordering |
| `provenance` | `metadata.tailoring_provenance` | Stored in `resume_json.metadata` for auditability |

**Bullet distribution algorithm (deterministic):**

1. For each `selected_bullets[i]`, look up `provenance[i].source_ref`.
2. Parse `source_ref` format: `work:{company}:{position}:{highlight_index}`.
3. Find matching `work` entry in base `resume_json` by company + position.
4. Replace `highlights[highlight_index]` with the tailored bullet text.
5. If `highlight_index` exceeds existing highlights, append.
6. Bullets without a `work:` source_ref (e.g. `project:` or `education:`)
   are appended to the summary block or a new `projects` highlight.

**Variant storage:**

```python
variant_profile = {
    "profile_version_id": f"tailored_{job_id}_{uuid4().hex[:8]}",
    "candidate_id": candidate_id,
    "source_kind": "tailored_variant",     # distinguishes from base import
    "is_active": 0,                        # never the active profile
    "content_hash": sha1(variant_json),
    "profile_pack_md": "",                 # empty — variant has no markdown
    "profile_json": "{}",                  # not used for variants
    "resume_json": json.dumps(variant_resume_json),
    "created_at": now_iso(),
    "updated_at": now_iso(),
}
upsert_candidate_profile(conn, variant_profile)
```

A reference to the variant is also written to `generated_documents`:

```python
{
    "kind": "tailored_cv_variant",
    "producer": "crewai_author",
    "document_json": {
        "profile_version_id": variant_profile_version_id,
        "tailored_cv_projection": projection.model_dump(),
        "evaluation_id": evaluation_id,
    },
}
```

### 4.3 CLI command that closes the loop

```bash
# Export the tailoring plan for one job, apply to resume, write variant
jobpipe export-reactive-resume-plan <job_id> [--out reactive_resume_<job_id>.json]
```

This command already exists (`export_reactive_resume_plan.py`). The missing
step is persisting the variant back to the DB and writing a `generated_documents`
record. That is a post-MVP slice (#72 / #73).

---

## 5. Compatibility Checklist

### 5.1 Field name audit

| Field | Reactive Resume JSON | `candidate_profiles` | `AuthoringCaseContext` | `GeneratedApplicationPackage` | `generated_documents` | Mismatch? |
|---|---|---|---|---|---|---|
| Candidate identity | `basics.name` | `candidates.display_name` | `candidate_id` (str, not name) | — | `candidate_id` | ⚠️ name vs. ID |
| Job identity | — | — | `job_id: str` | `job_id: str` | `job_id` | ✅ consistent |
| Evaluation identity | — | — | `evaluation_id: str \| None` | — | `evaluation_id` | ✅ consistent |
| Work history | `work[].highlights[]` | `resume_json` (JSON text) | `selected_evidence[].canonical_text` | `evidence_refs[].canonical_text` | `document_json.evidence_refs` | ✅ consistent |
| CV headline | `basics.headline` | (in resume_json) | `job_summary` dict (no headline field) | `tailored_cv_projection.headline` | `document_json` | ⚠️ missing in AuthoringCaseContext — headline not surfaced |
| Cover letter text | — | — | — | `cover_letter_draft: str` | `document_json.cover_letter_draft` | ✅ consistent |
| Document status | — | — | — | `validation: dict \| None` | `status: str` | ⚠️ type mismatch: validation is structured dict, status is a flat string |
| Narrative profile | — | `candidate_narrative_profiles` table | `narrative_brief: dict \| None` | — | — | ✅ consistent |
| Evidence refs | — | `candidate_evidence_units` table | `selected_evidence: list[dict]` | `evidence_refs: list[dict]` | `document_json.evidence_refs` | ⚠️ field name differs: `selected_evidence` vs `evidence_refs` |

### 5.2 Type mismatches

| Location | Field | Current type | Expected type | Resolution |
|---|---|---|---|---|
| `job_evaluations.cv_focus` | `cv_focus` | `TEXT` (JSON text of list) | `list[str]` | `json.loads(cv_focus)` at read time |
| `job_evaluations.triage_signals` | `triage_signals` | `TEXT` (JSON text of list) | `list[str]` | `json.loads(triage_signals)` at read time |
| `generated_documents.document_json` | `cover_letter_draft` | `TEXT` blob | `str` (plain text) | Stored under key in JSON blob; OK |
| `candidate_profiles.resume_json` | `resume_json` | `TEXT` (JSON text) | `dict` | `json.loads(resume_json)` at read time |
| `AuthoringCaseContext.selected_evidence` | items | `dict` (from `.model_dump()`) | `dict` | ✅ already flat |
| `GeneratedApplicationPackage.evidence_refs` | items | `dict` | `dict` | ✅ but schema not enforced — no model |

### 5.3 Field name mismatches to fix

| Issue | Current | Should be | Action |
|---|---|---|---|
| evidence_refs vs selected_evidence | `AuthoringCaseContext.selected_evidence`, `GeneratedApplicationPackage.evidence_refs` | Same name | Use `selected_evidence` consistently; `evidence_refs` is a serialized subset — document the distinction clearly |
| `basics.headline` not in `job_summary` | Missing from `AuthoringCaseContext.job_summary` | `job_summary.headline` from tailored projection | Add to job_summary or keep in `tailored_cv_projection` only — not blocking for cover letter |
| `JobSyncDocumentRef.status` (str) vs `DocumentValidationResult` (structured) | Two different status concepts | Keep separate | No change needed — they are different layers |

### 5.4 JobSync seam (ExternalAuthoringSyncEnvelope)

`JobSyncDocumentRefEvent` (from `schema.py` line 177) carries:
- `job_id`, `candidate_id`, `document_kind`, `storage_path`, `status`, `created_at`, `source`

This maps cleanly to `generated_documents` rows via:
```python
JobSyncDocumentRefEvent(
    job_id=doc["job_id"],
    candidate_id=doc["candidate_id"],
    document_kind=doc["kind"],           # "cover_letter" | "tailored_cv_variant"
    storage_path=doc["storage_path"],    # "" for MVP inline storage
    status=doc["status"],               # "draft" | "refined" | "final"
    created_at=doc["created_at"],
    source="jobpipe_authoring",
)
```

No schema change needed. The `storage_path` will be empty for inline storage;
JobSync should treat empty storage_path as "preview only".

---

## 6. Recommended Implementation Sequence

### Slice ordering (post current Sprint 1)

All items below are **new slices** for Sprint 2 and beyond. They depend on
Sprint 1 (Slices 1–5 / #58–#63) being merged.

| Slice | Issue | Title | Depends on | Risk | Implement-now? |
|---|---|---|---|---|---|
| S2-A | #72 | Profile supplement YAML schema + bootstrap CLI import | Sprint 1 done | 🟡 Yellow (DB migration) | **Now** — blocks everything below |
| S2-B | #60/#66 | `context_loader.py` — DB-backed `build_authoring_case_context` wrapper | S2-A | 🟢 Green | **Now** |
| S2-C | #64 | Persist cover letter draft to `generated_documents` | S2-B | 🟢 Green | **Now** |
| S2-D | #73 | Persist tailored CV variant to `candidate_profiles` + `generated_documents` | S2-B | 🟡 Yellow (variant logic) | Soon |
| S2-E | #72 | CV round-trip: `selected_bullets` → JSON Resume `work[].highlights` reassignment | S2-D | 🟢 Green | Soon |
| S2-F | #68 | Refine cover letter — second-pass Claude polish, store as `status=refined` | S2-C | 🟢 Green | Later |
| S2-G | narrative.py | Replace heuristic markdown parsing with structured supplement input | S2-A + Yellow gate | 🔴 Red (shared module) | Coordinator must approve |

### Gate: S2-G requires coordinator approval

Changing `narrative.py:build_candidate_narrative_context()` signature affects
the full pipeline (application_pack stage). This is a pipeline-semantic change
and requires Opus-level review before implementation.

### What can start immediately (Green gates only)

1. **S2-A** (DB migration + YAML bootstrap): single `ALTER TABLE` through
   `_ensure_column()`, one new CLI command, no pipeline path change.
2. **S2-B** (context_loader.py): new file, DB reads only, wraps existing
   low-level builder.
3. **S2-C** (persist cover letter): `insert_generated_document()` call, already
   exists in primary_db.py.

---

## Appendix: Open Questions for Coordinator

1. **S2-G gate**: Is changing `narrative.py` signature in-scope for Sprint 2,
   or is the synthesized `profile_text` string approach (§2.3) acceptable for
   the full MVP? The string approach is safe but leaves the heuristic parsing
   in place.

2. **Inline vs. file storage**: For MVP, is storing the cover letter text
   inline in `document_json` acceptable, or should a `JOBPIPE_DATA_DIR/documents/`
   path be required from day one? (Affects S2-C scope.)

3. **`basics.headline` in AuthoringCaseContext**: Should `job_summary` include
   a `headline` key (from tailored projection), or is `tailored_cv_projection`
   the canonical place for this? Current `AuthoringCaseContext.job_summary`
   does not carry it.

4. **Variant vs. patch**: Should the tailored CV variant be a full JSON Resume
   copy (safe, verbose) or a patch document (compact, harder to debug)?
   Recommendation is full copy as a `candidate_profiles` row with
   `source_kind="tailored_variant"`.
