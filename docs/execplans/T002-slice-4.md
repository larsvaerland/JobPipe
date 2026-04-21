# T002 Slice 4 — build-authoring-context smoke CLI hook (Issue #61)

**Sprint:** T002 Sprint 1
**Issue:** #61
**GitHub title (spec):** `Story: Invoke authoring from the CLI smoke flow for one job`
**T002.md scope (canonical):** Smoke CLI that reads canonical JobPipe artifacts
for a single job, assembles the four context inputs, calls
`build_authoring_case_context(...)`, and prints/saves the resulting
`AuthoringCaseContext` as JSON. **No generation. No agent call. No pipeline
edit.**

**Branch:** `codex/T002-authoring-mvp` (rebase on latest main before starting;
coordinator pre-stages with `git fetch && git rebase origin/main && git
push --force-with-lease`)
**Worker:** Codex (implementation)
**Planner:** Claude Sonnet (this document, round 3, coordinator-corrected)
**Reviewer/Orchestrator:** Claude Opus (coordinator)
**Risk label:** Green
**Date:** 2026-04-21
**Depends on:** eae36db (Slice 3 — `build_authoring_case_context`),
f15b883 (Slice 2 — output contracts), ee555bf (Slice 1 —
`AuthoringCaseContext`).

---

## Coordinator correction applied in round 3

The planner's draft `build_context_for_job` constructed
`JobContext.model_construct(... moderator=None, ...)` after already loading
`moderator_data` from disk. The Slice 3 builder's first guard raises
`ValueError` when `job_ctx.moderator is None`, so every smoke CLI invocation
would fail.

**Corrected by coordinator before handoff** — see the module template below:

```python
moderator=ModeratorOut.model_validate(moderator_data),
```

symmetric to how `parsed_data` is converted to `JobParse.model_validate(...)`.
The existence check on `moderator_data` (non-empty dict) is already performed
earlier in `build_context_for_job`, so the `.model_validate` call is safe.

**Do not revert this.** If moderator output is actually missing (not just
empty), the CLI must exit early with a readable error before ever reaching
`JobContext.model_construct`. The builder guard is a last-resort assert, not
the primary validation.

---

## One-sentence objective

Ship a one-shot CLI command `jobpipe build-authoring-context --job <job_id>`
that loads the seven canonical stage artifacts from
`<artifacts_root>/<run_id>/<job_id>/`, constructs the four context objects,
calls `build_authoring_case_context(...)`, and writes the resulting
`AuthoringCaseContext` as pretty-printed JSON to stdout (or `--out` path).

## Why this slice is fourth

Slice 3 proved the constructor works against hand-built context fixtures. Slice
4 proves it works against real pipeline output end-to-end — without touching
the pipeline itself. This is the first time the authoring contract touches
real-world JobPipe state, so it doubles as a smoke test for the four context
builders (`build_decision_context`, `build_candidate_evidence_context`,
`build_candidate_narrative_context`, `JobContext.model_construct`) against
real artifacts.

Slice 5 (#63) will add deterministic validation rules on the produced context.

---

## Out of scope (do NOT implement)

- Any call to an LLM, crewAI, autogen, langchain, or any agent runtime.
- Any generation of CV text, cover-letter text, or application artifacts.
- Any write to `jobpipe/stages/*` or `jobpipe/core/runner.py`.
- Any change to existing pipeline CLI commands (`run-feed`, `sync-evaluations`,
  `run-triage`, etc.).
- Any schema change to `AuthoringCaseContext` or the four context types.
- Any network call.
- Any use of `asyncio` or `anyio` (this is a sync CLI).

If Codex finds it needs to change any of the above to make this slice work,
**stop and escalate** — do not paper over it.

---

## Module layout

```
jobpipe/
  authoring/
    __init__.py          # existing
    case_context.py      # existing (Slice 1)
    builder.py           # existing (Slice 3)
    smoke_cli.py         # NEW — this slice
  cli/
    __main__.py          # existing — add one subcommand registration here
tests/
  test_authoring_smoke_cli.py   # NEW — this slice
```

`smoke_cli.py` is the only new runtime file. `cli/__main__.py` gets a single
subparser registration (3–6 lines).

---

## Canonical stage artifact layout

Run artifacts live at:

```
<artifacts_root>/<run_id>/<job_id>/NN_<stage>.json
```

Canonical (reverse_triage disabled, the common case):

```
00_input.json
01_triage.json
02_parsed.json
03_profile_match.json
04_pivot.json
05_moderator.json
06_application_pack.json        # not read by this CLI
```

Legacy (reverse_triage enabled, older runs):

```
00_input.json
01_triage.json
02_reverse_triage.json
03_parsed.json
04_profile_match.json
05_pivot.json
06_moderator.json
07_application_pack.json        # not read by this CLI
```

**Loader contract.** `_load_stage(job_dir, *candidates)` opens the first file
that exists from `candidates` and returns its JSON as a dict. Raise
`FileNotFoundError` with a clear message listing all candidates that were
checked if none exist.

Use the fallback pattern verified in `jobpipe/cli/sync_evaluations.py` around
line 200:

```python
parsed_data  = _load_stage(job_dir, "02_parsed.json",         "03_parsed.json")
pm_data      = _load_stage(job_dir, "03_profile_match.json",  "04_profile_match.json")
pivot_data   = _load_stage(job_dir, "04_pivot.json",          "05_pivot.json")
moderator_data = _load_stage(job_dir, "05_moderator.json",    "06_moderator.json")
```

`00_input.json` and `01_triage.json` never shift index. Read them by their
canonical name only.

---

## Module template — `jobpipe/authoring/smoke_cli.py`

This is the shape Codex must implement. Variable names, helper names, and
ordering are fixed by this template unless noted otherwise.

```python
"""Smoke CLI: build one AuthoringCaseContext from canonical run artifacts.

Reads the canonical JobPipe stage JSON files for a single job in a single run,
assembles the four context inputs, calls build_authoring_case_context, and
writes the result to stdout (or --out path).

No agent call. No generation. No pipeline edit. See
docs/execplans/T002-slice-4.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jobpipe.authoring.builder import build_authoring_case_context
from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.core.candidate_data import (
    default_candidate_id,
    load_candidate_profile_pack,
    load_candidate_resume_json,
)
from jobpipe.decision import (
    build_candidate_evidence_context,
    build_candidate_narrative_context,
    build_decision_context,
)
from jobpipe.model.schema import (
    JobContext,
    JobParse,
    ModeratorOut,
    RunMeta,
)


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def _load_stage(job_dir: Path, *candidates: str) -> dict[str, Any]:
    """Load the first candidate stage file that exists; raise if none."""
    tried: list[str] = []
    for name in candidates:
        path = job_dir / name
        tried.append(str(path))
        if path.is_file():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        f"No stage artifact found for job_dir={job_dir}. Tried: {tried}"
    )


def _resolve_job_dir(artifacts_root: Path, run_id: str | None, job_id: str) -> Path:
    """Resolve <artifacts_root>/<run_id>/<job_id>. If run_id is None, pick latest."""
    if run_id is not None:
        candidate = artifacts_root / run_id / job_id
        if not candidate.is_dir():
            raise FileNotFoundError(
                f"job_dir does not exist: {candidate}"
            )
        return candidate
    # Pick the most recent run_id directory that contains this job_id.
    if not artifacts_root.is_dir():
        raise FileNotFoundError(f"artifacts_root does not exist: {artifacts_root}")
    matches = [
        d for d in artifacts_root.iterdir()
        if d.is_dir() and (d / job_id).is_dir()
    ]
    if not matches:
        raise FileNotFoundError(
            f"No run under {artifacts_root} contains job_id={job_id}"
        )
    # Sort by mtime descending; the caller can still override with --run.
    matches.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return matches[0] / job_id


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def _compact_resume(resume: dict[str, Any]) -> dict[str, Any]:
    """Mirror of jobpipe.stages.application_pack._load_resume_context compaction.

    Keep the top-level shape that the narrative builder expects; this helper
    exists only to avoid passing a 50kB resume blob into the narrative context
    when a small subset will do. If the upstream shape is already compact,
    this is a no-op.
    """
    # Deliberately conservative: return a shallow copy. If real runs prove we
    # need further trimming, Slice 5 (#63) is the right place to add it.
    return dict(resume)


def build_context_for_job(
    *,
    artifacts_root: Path,
    run_id: str | None,
    job_id: str,
    candidate_id: str | None = None,
) -> AuthoringCaseContext:
    """Assemble all four contexts from artifacts and call the builder."""
    job_dir = _resolve_job_dir(artifacts_root, run_id, job_id)
    effective_run_id = run_id or job_dir.parent.name
    effective_candidate_id = candidate_id or default_candidate_id()

    # --- Load raw stage JSON --------------------------------------------------
    input_data     = _load_stage(job_dir, "00_input.json")
    parsed_data    = _load_stage(job_dir, "02_parsed.json",        "03_parsed.json")
    pm_data        = _load_stage(job_dir, "03_profile_match.json", "04_profile_match.json")
    pivot_data     = _load_stage(job_dir, "04_pivot.json",         "05_pivot.json")
    moderator_data = _load_stage(job_dir, "05_moderator.json",     "06_moderator.json")

    if not moderator_data:
        raise ValueError(
            f"[job_id={job_id}] moderator stage JSON is empty; cannot build authoring context"
        )
    if not parsed_data:
        raise ValueError(
            f"[job_id={job_id}] parse stage JSON is empty; cannot build authoring context"
        )

    # --- Candidate static inputs ---------------------------------------------
    profile_pack_text = load_candidate_profile_pack(candidate_id=effective_candidate_id)
    resume_json = load_candidate_resume_json(candidate_id=effective_candidate_id)
    resume_view = _compact_resume(resume_json)

    # --- Assemble JobContext --------------------------------------------------
    # COORDINATOR-FIXED: moderator must be validated, not None. Builder guards
    # on job_ctx.moderator is None and job_ctx.parsed is None.
    job_ctx = JobContext.model_construct(
        meta=RunMeta(
            run_id=effective_run_id,
            pipeline_name="smoke_cli",
            created_at=_now_iso(),
        ),
        job_id=job_id,
        job=input_data,
        profile_pack=profile_pack_text,
        triage=None,
        reverse_triage=None,
        parsed=JobParse.model_validate(parsed_data),
        profile_match=pm_data,
        pivot=pivot_data,
        moderator=ModeratorOut.model_validate(moderator_data),
        notes={},
    )

    # --- Build the three derived contexts ------------------------------------
    decision_ctx = build_decision_context(job_ctx)
    evidence_ctx = build_candidate_evidence_context(job_ctx, resume_view)
    # Narrative is optional; build it if the three priors exist, else pass None.
    try:
        narrative_ctx = build_candidate_narrative_context(
            job_ctx, decision_ctx, evidence_ctx, resume_view
        )
    except Exception:  # pragma: no cover — covered by Slice 5 validation
        narrative_ctx = None

    # --- Call the pure constructor -------------------------------------------
    evaluation_id = f"{effective_run_id}:{job_id}"
    return build_authoring_case_context(
        job_ctx,
        decision_ctx,
        evidence_ctx,
        narrative_ctx,
        candidate_id=effective_candidate_id,
        evaluation_id=evaluation_id,
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _to_jsonable(obj: Any) -> Any:
    """Convert AuthoringCaseContext (frozen dataclass) to a JSON-ready dict."""
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register 'build-authoring-context' with the main jobpipe CLI."""
    p = subparsers.add_parser(
        "build-authoring-context",
        help="Build one AuthoringCaseContext from canonical run artifacts (smoke).",
    )
    p.add_argument("--job", required=True, help="job_id to build context for")
    p.add_argument("--run", default=None, help="run_id (defaults to latest run containing --job)")
    p.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root artifacts directory (default: ./artifacts)",
    )
    p.add_argument("--candidate", default=None, help="candidate_id (default: default_candidate_id())")
    p.add_argument("--out", default=None, help="Write JSON to this path instead of stdout")
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    ctx = build_context_for_job(
        artifacts_root=Path(args.artifacts_root),
        run_id=args.run,
        job_id=args.job,
        candidate_id=args.candidate,
    )
    payload = _to_jsonable(ctx)
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
        sys.stdout.write("\n")
    return 0
```

**One-line registration in `jobpipe/cli/__main__.py`**. Follow the existing
pattern for other subcommands (e.g., `run_feed.add_subparser(subparsers)`):

```python
from jobpipe.authoring import smoke_cli as authoring_smoke_cli
# ...inside build_parser():
authoring_smoke_cli.add_subparser(subparsers)
```

Do not change any other CLI code paths. Do not re-order existing registrations.

---

## Tests — `tests/test_authoring_smoke_cli.py`

All tests synchronous. Use `pytest`'s `tmp_path` fixture and
`monkeypatch` for candidate loaders. Do not import `anyio`, `asyncio`, or
anything agent-runtime-shaped.

8 required tests:

1. **`test_load_stage_canonical_layout`** — create `00_input.json`,
   `02_parsed.json`, `05_moderator.json` in a tmp dir; assert `_load_stage`
   returns the expected dicts.
2. **`test_load_stage_legacy_layout`** — same but with `03_parsed.json`,
   `06_moderator.json`; assert the fallback name is picked.
3. **`test_load_stage_missing_raises`** — empty dir; assert
   `FileNotFoundError` whose message lists all candidate paths.
4. **`test_resolve_job_dir_explicit_run`** — `--run` given; returns the
   exact path.
5. **`test_resolve_job_dir_latest_run`** — two runs in the root, only the
   second contains `job_id`; asserts the second is picked.
6. **`test_build_context_for_job_happy_path`** — stage the full canonical
   layout with minimal valid JSON for each stage; monkeypatch
   `load_candidate_profile_pack` and `load_candidate_resume_json`;
   monkeypatch `build_authoring_case_context` to assert it receives a
   `JobContext` with `moderator` not None and `parsed` not None; return a
   sentinel `AuthoringCaseContext`.
7. **`test_cli_run_writes_stdout`** — call `_run` with a fake `Namespace`;
   capture stdout with `capsys`; assert the printed text is valid JSON with
   the expected top-level keys of `AuthoringCaseContext`
   (`candidate_id, evaluation_id, job_summary, decision_brief, selected_evidence,
   narrative_brief, artifact_plan`).
8. **`test_no_crewai_import`** — `grep -R "crewai\|autogen\|langchain"
   jobpipe/authoring/smoke_cli.py` returns empty (reuse the existing helper
   from Slice 3's test file if it's exposed; otherwise inline `pathlib.read_text`
   and `assert` substrings).

Fixture layout for test 6:

```python
def _write_canonical_run(root: Path, run_id: str, job_id: str) -> Path:
    job_dir = root / run_id / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "00_input.json").write_text(json.dumps({"title": "Test Role"}))
    (job_dir / "01_triage.json").write_text(json.dumps({"verdict": "actionable"}))
    (job_dir / "02_parsed.json").write_text(json.dumps(_minimal_parsed_dict()))
    (job_dir / "03_profile_match.json").write_text(json.dumps({"score": 0.7}))
    (job_dir / "04_pivot.json").write_text(json.dumps({"angle": "data+product"}))
    (job_dir / "05_moderator.json").write_text(json.dumps(_minimal_moderator_dict()))
    return job_dir
```

`_minimal_parsed_dict()` must return every required field of `JobParse`
(inspect via `JobParse.model_fields`). Same for `_minimal_moderator_dict()`
against `ModeratorOut.model_fields`. Do not guess — if either raises a
validation error during test authoring, read the schema and add the missing
fields. Common ones:

- `JobParse`: `role_summary`, `responsibilities`, `requirements_must`,
  `requirements_nice`, `seniority`, `employment_type`, `location`, `remote_mode`.
- `ModeratorOut`: `final_decision`, `confidence`, `recommendation_reason`,
  `cv_focus`, `feedback_flags`.

If fields change upstream, fix the fixtures; do not change the tests to paper
over a schema mismatch.

---

## Binary acceptance criteria

All 11 must be true for this slice to be considered done.

1. `jobpipe/authoring/smoke_cli.py` exists and exports
   `build_context_for_job`, `add_subparser`, `_run`, `_load_stage`,
   `_resolve_job_dir`.
2. `jobpipe build-authoring-context --help` prints the new subcommand with
   all five flags (`--job`, `--run`, `--artifacts-root`, `--candidate`,
   `--out`).
3. `jobpipe build-authoring-context --job <j> --artifacts-root <path>`
   succeeds on a canonical layout and prints valid JSON containing the seven
   top-level `AuthoringCaseContext` keys.
4. Legacy-layout artifacts (`03_parsed.json`, `06_moderator.json`) also
   succeed without code change.
5. `moderator_data` empty → clean `ValueError` with `job_id` in message,
   raised in `build_context_for_job` before reaching the builder.
6. `parsed_data` empty → same pattern.
7. Missing `00_input.json` → `FileNotFoundError` listing all checked paths.
8. `--out PATH` writes the same bytes that stdout would have printed,
   UTF-8, sorted keys, 2-space indent.
9. All 8 unit tests pass under the repo venv with the Windows anyio
   workaround:
   `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp tests/test_authoring_smoke_cli.py -v`.
10. `python compile_check.py` passes cleanly on the full repo.
11. `grep -r "crewai\|autogen\|langchain" jobpipe/authoring/smoke_cli.py`
    returns empty. No new runtime dependency in `pyproject.toml`.

---

## Risks and mitigations

- **Risk: narrative context builder raises on some real runs.** Mitigation:
  try/except wrapper sets `narrative_ctx=None` (Slice 5 adds validation).
  This keeps the smoke path alive on sparse data.
- **Risk: `load_candidate_profile_pack` signature drifts.** Mitigation: this
  slice calls it with the verified keyword-only `candidate_id=` form
  (verified in `jobpipe/core/candidate_data.py:55`). If the signature
  changes, Codex must stop and escalate — do not positional-pass.
- **Risk: `_compact_resume` is too shallow for real narrative builders.**
  Mitigation: conservative shallow copy; Slice 5 owns the real compaction.
- **Risk: `build_decision_context` signature assumed.** Mitigation: Codex
  must verify `jobpipe/decision/__init__.py` exports the three builders and
  their argument shapes before wiring; if the signature is not
  `(job_ctx)` / `(job_ctx, resume)` / `(job_ctx, decision, evidence, resume)`,
  stop and escalate.

---

## Handoff protocol

1. Coordinator pre-stages `codex/T002-authoring-mvp`: `git fetch origin &&
   git checkout codex/T002-authoring-mvp && git reset --hard origin/main &&
   git push --force-with-lease origin codex/T002-authoring-mvp`.
2. Coordinator delivers the Codex worker prompt (separate artifact).
3. Codex implements; commits; pushes to `codex/T002-authoring-mvp`.
4. Codex reports: files changed, test run output, compile_check output,
   grep result.
5. Coordinator reviews, opens PR, merges via squash, flips Project #6 item
   to Done, advances `docs/current-state.json` to Slice 5.

---

## Planner stamp

- **Planner:** Claude Sonnet (round 3)
- **Coordinator:** Claude Opus
- **Coordinator correction:** `moderator=None` → `ModeratorOut.model_validate(moderator_data)` (applied inline above).
- **Status:** Approved for Codex handoff — 2026-04-21.
