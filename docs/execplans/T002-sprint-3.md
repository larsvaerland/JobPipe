# T002 Sprint 3 — crewAI author/critic loop

**Written:** 2026-04-22  
**Status:** Planning  
**Governing spec:** `specs/ai-document-authoring-mvp-workflow-2026-04-21.md`  
**Decision record:** `specs/crewai-integration-decision.md`  
**Base:** `origin/main` (post-PR-#101, commit e73b001)

---

## Sprint goal

Replace `SimpleAgentAuthor` as the default authoring engine with a crewAI-powered author/critic crew — isolated in its own Python 3.12 environment, communicating with JobPipe only through the `AuthorAdapter` Protocol seam. End state: `jobpipe author-package --job <id> --author crewai` produces a structurally valid `GeneratedApplicationPackage` from a real APPLY-decision job.

---

## Non-goals for this sprint

- No `jobpipe-mcp-server` (Sprint 4+).
- No Reactive Resume UI integration (Sprint 4+).
- No crewAI import inside `jobpipe/` (invariant, forever).
- No Supabase, hosted shell, AutoGen, LangChain.
- No new candidate data model fields or DB schema changes.

---

## Isolation rule (repeating from decision record for worker agents)

`jobpipe/` never imports `crewai`. `jobpipe_crewai/` never imports `jobpipe` internals. The only shared surface is:

- **In:** `AuthoringCaseContext` serialised as JSON string
- **Out:** `GeneratedApplicationPackage`-compatible JSON parsed back by JobPipe

Any slice that puts a `crewai` import inside `jobpipe/` is a routing violation. Reject in review.

---

## Ordered slices

### Slice 9 — crewAI environment setup + smoke test

**Purpose:** Establish the isolated Python 3.12 environment for crewAI. Verify all required imports work. Produce a pinned `requirements-crewai.txt`.

**Issues:** No GitHub issue yet — create `Task: Set up isolated crewAI Python 3.12 environment`

**Python target:** Python 3.12.5 (`python` on Lars's machine, `C:\Users\larsv\AppData\Local\Programs\Python\Python312\python.exe`). Do NOT use Python 3.14 — pydantic-core's pyo3 ceiling blocks crewAI there.

**Files to create:**

| Path | Action |
|---|---|
| `crewai_env/requirements-crewai.txt` | CREATE — pinned crewAI deps |
| `crewai_env/smoke_crewai.py` | CREATE — import smoke test |
| `crewai_env/README.md` | CREATE — setup instructions |

**Location:** `crewai_env/` at repo root, NOT inside `jobpipe/`. This is a sibling directory, not a Python package.

**Smoke test must verify:**
```python
import crewai; print(crewai.__version__)
from crewai import Agent, Task, Crew, Process
from mcp import ClientSession
print("crewAI + MCP OK")
```

**Setup command (coordinator-validated):**
```cmd
python -m venv C:\Users\larsv\envs\crewai-env
C:\Users\larsv\envs\crewai-env\Scripts\activate
pip install crewai
pip freeze > crewai_env/requirements-crewai.txt
python crewai_env/smoke_crewai.py
```

**Acceptance criteria:**
1. `crewai_env/requirements-crewai.txt` exists and includes `crewai==1.14.2`.
2. `python crewai_env/smoke_crewai.py` exits 0 with "crewAI + MCP OK" printed.
3. No crewAI package installed under Python 3.14 or in `jobpipe/`.
4. `crewai_env/README.md` documents the setup steps and Python version requirement.

---

### Slice 10 — `jobpipe_crewai` module + `CrewAIAuthor` skeleton

**Purpose:** Create the isolated `jobpipe_crewai` module tree with a `CrewAIAuthor` class that satisfies the `AuthorAdapter` Protocol. Stub crew (one agent, placeholder output) — just proving the boundary holds.

**Issues:** Create `Feature: CrewAIAuthor adapter skeleton (isolated module)`

**Files to create:**

| Path | Action |
|---|---|
| `jobpipe_crewai/__init__.py` | CREATE — empty |
| `jobpipe_crewai/author.py` | CREATE — `CrewAIAuthor` class |
| `jobpipe_crewai/prompts.py` | CREATE — system prompts for agents |
| `tests_crewai/test_crewai_author_skeleton.py` | CREATE — seam tests |

**Module location:** `jobpipe_crewai/` at repo root, sibling to `jobpipe/`. It is NOT inside `jobpipe/`. It imports `crewai` freely.

**`CrewAIAuthor` skeleton:**
```python
# jobpipe_crewai/author.py
import json
from crewai import Agent, Task, Crew
from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage

class CrewAIAuthor:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage:
        payload = json.loads(ctx.model_dump_json() if hasattr(ctx, "model_dump_json") else json.dumps(dataclasses.asdict(ctx)))
        # Crew construction + run in Slice 12
        # Skeleton: return a structurally valid stub package
        return GeneratedApplicationPackage(
            job_id=ctx.job_id,
            cover_letter_draft="[stub — crewAI crew not yet wired]",
            tailored_cv_projection={},
            evidence_refs=[],
            gap_notes=["CrewAIAuthor skeleton — no real output yet"],
        )
```

**Tests** (`tests_crewai/` — runs under Python 3.12 crewAI env, NOT under the main Python 3.14 pytest suite):
1. `test_crewai_author_satisfies_protocol` — `isinstance(CrewAIAuthor(), AuthorAdapter)` is True
2. `test_crewai_author_returns_package` — `generate(mock_ctx)` returns a `GeneratedApplicationPackage`
3. `test_no_crewai_in_jobpipe` — grep `jobpipe/` for `import crewai`; assert not found
4. `test_no_jobpipe_internals_in_crewai_init` — verify `jobpipe_crewai/__init__.py` doesn't import db/core
5. `test_seam_json_roundtrip` — `AuthoringCaseContext` can be serialised to JSON and deserialised without error

**Acceptance criteria:**
1. `jobpipe_crewai/author.py` exists with `CrewAIAuthor`.
2. `CrewAIAuthor` satisfies `isinstance(CrewAIAuthor(), AuthorAdapter)`.
3. `generate()` returns a valid `GeneratedApplicationPackage`.
4. No `crewai` import anywhere under `jobpipe/`.
5. All 5 tests pass under the Python 3.12 crewAI env.

---

### Slice 11 — Author factory + `--author` CLI flag

**Purpose:** Add a factory to JobPipe that selects the `AuthorAdapter` implementation by name, and wire `--author` flag to `jobpipe author-package`. This is the connector-style modularisation seam: swapping author runtimes is a one-flag change.

**Issues:** Create `Feature: AuthorAdapter factory + --author CLI flag`

**Files to create/touch:**

| Path | Action |
|---|---|
| `jobpipe/authoring/author_factory.py` | CREATE — `build_author(name, model)` |
| `jobpipe/authoring/author_cli.py` | MODIFY — add `--author` flag |
| `tests/test_author_factory.py` | CREATE — factory tests |

**`author_factory.py`:**
```python
def build_author(name: str = "simple", model: str = "gpt-4o-mini") -> AuthorAdapter:
    if name == "simple":
        from jobpipe.authoring.simple_agent_author import SimpleAgentAuthor
        return SimpleAgentAuthor(model=model)
    elif name == "crewai":
        # Import isolated — crewai module lives outside jobpipe/
        import importlib
        mod = importlib.import_module("jobpipe_crewai.author")
        return mod.CrewAIAuthor(model=model)
    else:
        raise ValueError(f"Unknown author: {name!r}. Valid: simple, crewai")
```

Note: `importlib.import_module` is the correct pattern here — it keeps `crewai` off the import path unless explicitly selected. `jobpipe/` still does not statically import `crewai`.

**CLI change:** Add `--author` to `author_cli.py` (default `"simple"`). Pass to `build_author()`. One-line change to the `SimpleAgentAuthor()` instantiation.

**Tests (`tests/test_author_factory.py`, 4 tests, Python 3.14 suite):**
1. `test_factory_returns_simple_by_default` — `build_author()` returns a `SimpleAgentAuthor`
2. `test_factory_simple_explicit` — `build_author("simple")` returns `SimpleAgentAuthor`
3. `test_factory_unknown_raises` — `build_author("nonsense")` raises `ValueError`
4. `test_factory_no_crewai_static_import` — grep `jobpipe/authoring/author_factory.py` for `import crewai`; assert not found (importlib is fine)

**Acceptance criteria:**
1. `author_factory.py` exists with `build_author(name, model) -> AuthorAdapter`.
2. `--author` flag present in `jobpipe author-package --help`.
3. `--author simple` (default) passes all existing `test_author_cli.py` tests unchanged.
4. `build_author("crewai")` returns a `CrewAIAuthor` when `jobpipe_crewai` is importable.
5. All 4 factory tests pass.
6. `compile_check.py` passes.

---

### Slice 12 — Author + Critic crew (2 agents, real output)

**Purpose:** Wire the real crewAI 2-agent crew inside `CrewAIAuthor.generate()`. Author agent drafts; Critic agent validates against evidence refs and claim targets. Output: non-stub `GeneratedApplicationPackage` with a real cover letter draft and CV projection structure.

**Issues:** Create `Feature: crewAI author+critic crew (2 agents)`

**Files to touch:**

| Path | Action |
|---|---|
| `jobpipe_crewai/author.py` | MODIFY — wire real crew |
| `jobpipe_crewai/prompts.py` | MODIFY — author + critic system prompts |
| `jobpipe_crewai/crew.py` | CREATE — crew factory function |
| `tests_crewai/test_crewai_crew.py` | CREATE — crew unit tests |

**Crew structure:**
```python
# Two-agent crew
author_agent = Agent(
    role="CV and Cover Letter Author",
    goal="Draft a tailored CV projection and cover letter from the provided candidate evidence and job context",
    backstory="...",
    llm=self._model,
)
critic_agent = Agent(
    role="Application Quality Critic",
    goal="Validate the draft against the provided evidence refs and claim targets. Flag gaps, unsupported claims, and ATS issues.",
    backstory="...",
    llm=self._model,
)
# Tasks: author task → critic task (sequential)
# Crew: Process.sequential
```

**Bounded revision:** critic outputs a structured critique JSON. If critic flags failures, author gets one revision pass. Max 2 iterations — no infinite loops.

**Output parsing:** Crew final output is parsed into `GeneratedApplicationPackage` fields. If parsing fails, return the raw text as `cover_letter_draft` with a gap note.

**Tests (`tests_crewai/test_crewai_crew.py`, monkeypatched, 5 tests):**
1. `test_crew_author_and_critic_tasks_exist` — crew has exactly 2 tasks
2. `test_crew_output_parses_to_package` — monkeypatched crew output parses into `GeneratedApplicationPackage`
3. `test_crew_bounded_iterations` — crew config does not set `max_iter` above 2
4. `test_crew_no_langchain_import` — grep `jobpipe_crewai/` for `langchain`; assert not found
5. `test_crew_uses_litellm_model_string` — model string is a LiteLLM-compatible format (e.g. `"gpt-4o-mini"`, not vendor-specific SDK object)

**Acceptance criteria:**
1. `CrewAIAuthor.generate()` returns a `GeneratedApplicationPackage` with non-empty `cover_letter_draft`.
2. Crew has 2 agents (author + critic).
3. Bounded: max 2 iterations, no infinite loops.
4. No `langchain` import anywhere in `jobpipe_crewai/`.
5. All 5 tests pass under Python 3.12 env.

---

### Slice 13 — Live pipeline run + Sprint 3 exit test

**Purpose:** Run the full pipeline end-to-end against a real APPLY-decision job using `CrewAIAuthor`. This is both the Sprint 2 deferred exit test and the Sprint 3 validation.

**Issues:** Create `Task: Sprint 3 exit test — live author-package run with crewAI`

**Prerequisite:** At least one job with `decision = "APPLY"` in the primary DB. If the dev DB has only SKIP decisions, run the NAV pipeline scrape first:
```cmd
python -m jobpipe.cli.main run-nav  # or equivalent pipeline command
```

**Exit commands:**
```cmd
# 1. Confirm APPLY job exists
python -m jobpipe.cli.main inspect-db --show-decisions | findstr APPLY

# 2. Run with SimpleAgentAuthor (baseline, should already work from Sprint 2)
python -m jobpipe.cli.main author-package --job <apply_job_id> --no-persist

# 3. Run with CrewAIAuthor (Sprint 3 target)
C:\Users\larsv\envs\crewai-env\Scripts\python.exe -m jobpipe.cli.main author-package --job <apply_job_id> --author crewai --no-persist
```

Note on Python env for crewAI run: since crewAI is in the Python 3.12 venv, `author-package --author crewai` must be invoked from that venv. JobPipe CLI runs under Python 3.12 for this command. The `simple` author continues to run under Python 3.14.

**Sprint 3 is successful when:**
1. `--author crewai` produces valid JSON with non-empty `cover_letter_draft`.
2. `tailored_cv_projection` is a non-empty dict.
3. `evidence_refs` references at least one evidence unit from the job's selected evidence.
4. No crewAI import appears anywhere under `jobpipe/`.
5. `compile_check.py` passes on main.

---

## Dependency ordering

```
Slice 9  (crewAI env)
  └── Slice 10 (CrewAIAuthor skeleton)
        └── Slice 11 (factory + --author flag)  ← runs in parallel with Slice 12
        └── Slice 12 (real crew)
              └── Slice 13 (live run)
```

Slice 11 and 12 can be developed in parallel — factory doesn't care about crew internals, crew doesn't care about the factory.

---

## Worker routing

| Slice | Worker | Lane |
|---|---|---|
| Slice 9 (env setup) | Coordinator / Lars manually | Not a code slice |
| Slice 10 (skeleton) | Codex | `codex/T002-authoring-mvp` |
| Slice 11 (factory) | Codex | `codex/T002-authoring-mvp` |
| Slice 12 (real crew) | Codex | `codex/T002-authoring-mvp` |
| Slice 13 (live run) | Coordinator + Lars | Validation, not implementation |

Slices 10, 11, 12 should be handed to Codex sequentially (wait for merge before briefing next) given the dependency chain.

---

## GitHub Project #6 items to create

Create these before handing Slice 10 to Codex:

- `Task: Set up isolated crewAI Python 3.12 environment` (Slice 9)
- `Feature: CrewAIAuthor adapter skeleton (isolated module)` (Slice 10)
- `Feature: AuthorAdapter factory + --author CLI flag` (Slice 11)
- `Feature: crewAI author+critic crew (2 agents)` (Slice 12)
- `Task: Sprint 3 exit test — live author-package run with crewAI` (Slice 13)
- Close `#86` (crewAI spike — done)

---

## Escalation gates (for Codex workers)

Stop and ask coordinator before:
- Any `import crewai` inside `jobpipe/` (invariant violation)
- Any change to `AuthoringCaseContext`, `GeneratedApplicationPackage`, or `DocumentValidationResult` shapes
- Any new DB schema change
- Adding `langchain`, `autogen`, or Supabase
- More than 2 revision iterations in the crew loop
- Touching files outside the slice's listed files

---

## Post-Sprint 3: what comes next

Sprint 4 candidates (not scoped yet):
- `jobpipe-mcp-server` — FastAPI/Starlette MCP server exposing evidence, decision brief, narrative profile as read-only tools; consumed by crewAI agents and Claude in Word
- Reactive Resume `tailored_cv_projection` → RR patch flow (structured JSON export)
- Cover letter DOCX render + final document refs
- JobSync status write-back after apply
- First live APPLY submission with tracked outcome
