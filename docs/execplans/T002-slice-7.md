# T002 Slice 7 — AuthorAdapter protocol + SimpleAgentAuthor

**Written:** 2026-04-22  
**Issues:** #66 (AuthorAdapter protocol), #67 (SimpleAgentAuthor), #71 (CV projection shape)  
**Branch:** `codex/T002-authoring-mvp`  
**Base:** `origin/main` (post-PR-#99)  
**Governing spec:** `specs/ai-document-authoring-mvp-workflow-2026-04-21.md`

---

## Goal

Define the `AuthorAdapter` Protocol and its first concrete implementation
`SimpleAgentAuthor`. The implementation wraps a single `agents.Agent` call
(openai-agents SDK) that takes `AuthoringCaseContext` as JSON and returns a
`GeneratedApplicationPackage`. No persistence (Slice 8). No crewAI.

---

## Files to create / touch

| Path | Action |
|---|---|
| `jobpipe/authoring/adapter.py` | CREATE — `AuthorAdapter` Protocol |
| `jobpipe/authoring/simple_agent_author.py` | CREATE — `SimpleAgentAuthor` |
| `tests/test_author_adapter.py` | CREATE — 5 tests, all monkeypatched |

No other files may be touched. Do not edit `smoke_cli.py`, `builder.py`,
`output_models.py`, `case_context.py`, `validation.py`, or any file outside
`jobpipe/authoring/` and `tests/`.

---

## Signatures Block (verified against `origin/main` @ `bc9edbe`)

```python
# jobpipe/authoring/case_context.py
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

# jobpipe/authoring/output_models.py
class GeneratedApplicationPackage(BaseModel):
    job_id: str
    cover_letter_draft: str
    tailored_cv_projection: dict
    evidence_refs: list[dict]
    gap_notes: list[str]
    validation: dict | None = None

# jobpipe/stages/_common.py
def run_agent(agent, input_text: str, trace=None):
    # Returns Runner.run_sync(...) — result.final_output is the typed output

# jobpipe/stages/application_pack.py (usage pattern)
agent = Agent(
    name="application_pack_agent",
    model=model,
    instructions=PACK_INSTRUCTIONS,
    output_type=ApplicationPackOut,   # pydantic model
)
result = run_agent(agent, json.dumps(payload))
pack_data: ApplicationPackOut = result.final_output
```

---

## Implementation spec

### `jobpipe/authoring/adapter.py`

```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage

@runtime_checkable
class AuthorAdapter(Protocol):
    """Swappable interface for the author/revise layer.

    Any object implementing generate() satisfies this protocol.
    Concrete implementations must not import crewai, autogen, or langchain.
    """
    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage: ...
```

### `jobpipe/authoring/simple_agent_author.py`

Internal output model (NOT exported — only used by this module):

```python
class _AuthorOutput(BaseModel):
    cover_letter_draft: str
    tailored_cv_projection: dict
    evidence_refs: list[dict]
    gap_notes: list[str]
```

`SimpleAgentAuthor`:
- Constructor: `__init__(self, model: str = "gpt-4o-mini") -> None`
- Creates `self._agent = Agent(name="simple_author_agent", model=model, instructions=AUTHOR_INSTRUCTIONS, output_type=_AuthorOutput)`
- `generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage`:
  - Builds payload dict from ctx fields: `job_id`, `job_summary`, `decision_brief`, `selected_evidence`, `narrative_brief`
  - Calls `run_agent(self._agent, json.dumps(payload, ensure_ascii=False))`
  - Reads `result.final_output` as `_AuthorOutput`
  - Returns `GeneratedApplicationPackage(job_id=ctx.job_id, cover_letter_draft=out.cover_letter_draft, tailored_cv_projection=out.tailored_cv_projection, evidence_refs=out.evidence_refs, gap_notes=out.gap_notes)`

System prompt (`AUTHOR_INSTRUCTIONS`) must instruct the agent to:
- Write a cover letter draft in Norwegian (matching existing codebase language convention)
- Produce `tailored_cv_projection` as a dict with keys `highlights` (list[str], 4-6 bullets) and `experience_refs` (list[str], same length)
- Populate `evidence_refs` from `selected_evidence` input
- Note any gaps in `gap_notes`

Imports allowed: `from __future__ import annotations`, `json`, `from agents import Agent`, `from pydantic import BaseModel`, `from jobpipe.authoring.case_context import AuthoringCaseContext`, `from jobpipe.authoring.output_models import GeneratedApplicationPackage`, `from jobpipe.stages._common import run_agent`.

No other imports from jobpipe. No crewai, autogen, langchain.

### `tests/test_author_adapter.py`

All tests monkeypatch `run_agent` — no real API calls, no network.

Monkeypatch target: `jobpipe.authoring.simple_agent_author.run_agent`

Fake result helper:
```python
class _FakeRunResult:
    def __init__(self, output):
        self.final_output = output
```

Required tests (5):

1. `test_simple_author_implements_protocol` — `isinstance(SimpleAgentAuthor(), AuthorAdapter)` is True (runtime_checkable)
2. `test_generate_returns_generated_application_package` — monkeypatch run_agent, call `author.generate(ctx)`, assert `isinstance(result, GeneratedApplicationPackage)`
3. `test_generate_propagates_job_id` — result.job_id == ctx.job_id
4. `test_generate_cover_letter_and_projection_populated` — result.cover_letter_draft != "" and isinstance(result.tailored_cv_projection, dict)
5. `test_no_crewai_import` — scan `jobpipe/authoring/adapter.py` and `jobpipe/authoring/simple_agent_author.py` for the string "crewai" using subprocess or pathlib.read_text; assert not found

Build a minimal `AuthoringCaseContext` fixture for the tests using the exact frozen dataclass signature above.

---

## Validation commands

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_author_adapter.py -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp
python compile_check.py
python -c "from jobpipe.authoring.adapter import AuthorAdapter; from jobpipe.authoring.simple_agent_author import SimpleAgentAuthor; print('import ok')"
```

All 5 tests must pass. compile_check must pass. Import must succeed.

---

## Acceptance criteria (11 items)

1. `jobpipe/authoring/adapter.py` exists with `AuthorAdapter` as a `runtime_checkable` Protocol.
2. `AuthorAdapter.generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage` is the only method on the protocol.
3. `jobpipe/authoring/simple_agent_author.py` exists with `SimpleAgentAuthor`.
4. `SimpleAgentAuthor.__init__` accepts `model: str = "gpt-4o-mini"` and creates `self._agent` via `Agent(...)`.
5. `SimpleAgentAuthor.generate` calls `run_agent(self._agent, ...)` and reads `result.final_output`.
6. `isinstance(SimpleAgentAuthor(), AuthorAdapter)` is `True` at runtime.
7. `GeneratedApplicationPackage` is returned by `generate()`; all required fields populated.
8. `_AuthorOutput` is module-private (underscore prefix); not exported.
9. No import of `crewai`, `autogen`, or `langchain` in any new file or its tests.
10. All 5 tests in `test_author_adapter.py` pass under the PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 workaround.
11. `compile_check.py` passes (no syntax errors across all files).

---

## No-go list

- Do not import crewai, autogen, or langchain anywhere.
- Do not edit files outside the three listed above.
- Do not call `run_agent` without monkeypatching in tests (no live API calls).
- Do not add persistence logic (that is Slice 8).
- Do not add a new CLI command (that is Slice 8).
- Do not expand `GeneratedApplicationPackage` or `AuthoringCaseContext` fields.

---

## Escalation gates

Stop and ask the coordinator before:
- Any import of crewai/autogen/langchain anywhere in the slice.
- Any signature on `AuthoringCaseContext` or `GeneratedApplicationPackage` that does not match the Signatures Block above.
- Any file touch outside the three listed files.
