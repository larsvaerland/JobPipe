# T002 Sprint 3 — Orchestrator Prompt

**Branch:** `codex/T002-authoring-mvp`  
**Base:** `origin/main` (post-PR-#101)  
**Decision record:** `specs/crewai-integration-decision.md`

You are the orchestrator for Sprint 3. You run Step 0 yourself. Then you
delegate each task to a fresh sub-agent. You commit after each sub-agent
succeeds. You open the final PR after Task 3 commits.

Do not carry implementation details in your own context. Delegate to sub-agents
and verify their reported results only.

---

## STOP GATES — halt at any point if:

- Step 0 verification fails
- A sub-agent reports a validation failure it could not fix
- A sub-agent reports a STOP GATE hit (crewai import inside jobpipe/, signature mismatch, scope creep)
- A commit or push fails unexpectedly

When stopped: report what happened and what decision is needed.

---

## Step 0 — Run yourself before spawning any sub-agent

```cmd
cd C:\Users\larsv\Jobpipe-codex-v2
git fetch origin
git reset --hard origin/main
python -m jobpipe.cli.main author-package --help
python compile_check.py
dir C:\Users\larsv\envs\crewai-env\Scripts\python.exe
```

Expected:
- `author-package --help` shows `--job`, `--model`, `--no-persist`, `--validate`
- `compile_check.py` passes
- crewAI env python exists at `C:\Users\larsv\envs\crewai-env\Scripts\python.exe`

If any check fails: stop and report. Do not spawn sub-agents.

---

## Task 1 — Spawn sub-agent

Spawn a sub-agent with the full contents of the Task 1 brief below.
Wait for it to report back. The sub-agent must report:
- whether all 5 tests passed
- whether compile_check passed
- list of files it created

If success: commit and proceed to Task 2.
If failure: report to coordinator. Do not proceed.

**Commit after Task 1 success:**
```cmd
cd C:\Users\larsv\Jobpipe-codex-v2
git add jobpipe_crewai/ tests_crewai/
git commit -m "feat(crewai): CrewAIAuthor skeleton — isolated module, AuthorAdapter seam"
```

---

### TASK 1 SUB-AGENT BRIEF
*(Pass this entire section as the sub-agent prompt)*

You are implementing Task 1 of T002 Sprint 3 for the JobPipe codebase.

**Repo:** `C:\Users\larsv\Jobpipe-codex-v2` (branch `codex/T002-authoring-mvp`, based on `origin/main`)

**Your job:** Create the `jobpipe_crewai/` isolated module with a `CrewAIAuthor` skeleton that satisfies the `AuthorAdapter` Protocol. Also create the `tests_crewai/` test directory with 5 seam tests.

**The one invariant you must never violate:** `jobpipe/` must never contain `import crewai` or `from crewai`. `jobpipe_crewai/` may import crewai freely.

**Files to create — no others:**

| Path | Action |
|---|---|
| `jobpipe_crewai/__init__.py` | CREATE — empty |
| `jobpipe_crewai/author.py` | CREATE |
| `jobpipe_crewai/prompts.py` | CREATE |
| `tests_crewai/__init__.py` | CREATE — empty |
| `tests_crewai/test_crewai_author_skeleton.py` | CREATE |

**Step 0 — read before writing:**
Confirm these do not exist yet:
```cmd
dir jobpipe_crewai 2>nul || echo NOT FOUND
dir tests_crewai 2>nul || echo NOT FOUND
```
Read `jobpipe/authoring/adapter.py` to confirm `AuthorAdapter` Protocol shape.
Read `jobpipe/authoring/case_context.py` to confirm `AuthoringCaseContext` fields and whether it is a dataclass or pydantic model.
Read `jobpipe/authoring/output_models.py` to confirm `GeneratedApplicationPackage` fields.

**`jobpipe_crewai/prompts.py`:**
```python
AUTHOR_SYSTEM = (
    "You are an expert CV and cover letter author. "
    "You write evidence-backed, ATS-safe application documents. "
    "You only include claims supported by the provided evidence units."
)

CRITIC_SYSTEM = (
    "You are an application quality critic. "
    "You validate CV and cover letter drafts against provided evidence refs and job claim targets. "
    "You flag unsupported claims, missing evidence, and ATS hygiene issues."
)
```

**`jobpipe_crewai/author.py`:**
```python
import dataclasses
import json

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage


class CrewAIAuthor:
    """crewAI implementation of AuthorAdapter. May import crewai freely.
    jobpipe/ must never import this module statically."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage:
        """Skeleton — real crew wired in Task 3."""
        return GeneratedApplicationPackage(
            job_id=ctx.job_id,
            cover_letter_draft="[stub — crewAI crew not yet wired]",
            tailored_cv_projection={},
            evidence_refs=[],
            gap_notes=["CrewAIAuthor skeleton — real crew wired in Task 3"],
        )
```

**`tests_crewai/test_crewai_author_skeleton.py`:**
```python
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_crewai_author_satisfies_protocol():
    from jobpipe.authoring.adapter import AuthorAdapter
    from jobpipe_crewai.author import CrewAIAuthor
    assert isinstance(CrewAIAuthor(), AuthorAdapter)


def test_crewai_author_returns_package():
    import dataclasses
    from jobpipe.authoring.case_context import AuthoringCaseContext
    from jobpipe.authoring.output_models import GeneratedApplicationPackage
    from jobpipe_crewai.author import CrewAIAuthor

    # Build ctx — adapt field names if AuthoringCaseContext differs from below
    ctx = AuthoringCaseContext(
        candidate_id="c1",
        job_id="j1",
        evaluation_id=None,
        job_summary={"title": "Engineer"},
        decision_brief={"match_score": 0.8},
        selected_evidence=[],
        narrative_brief=None,
        artifact_plan=None,
    )
    pkg = CrewAIAuthor().generate(ctx)
    assert isinstance(pkg, GeneratedApplicationPackage)
    assert pkg.job_id == "j1"


def test_no_crewai_in_jobpipe():
    jobpipe_dir = REPO_ROOT / "jobpipe"
    for py_file in jobpipe_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "import crewai" not in content, f"crewai import in {py_file}"
        assert "from crewai" not in content, f"crewai import in {py_file}"


def test_no_jobpipe_internals_in_crewai():
    crewai_dir = REPO_ROOT / "jobpipe_crewai"
    forbidden = ["jobpipe.core", "jobpipe.runtime", "primary_db"]
    for py_file in crewai_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in content, f"{term!r} in {py_file}"


def test_seam_json_roundtrip():
    import dataclasses
    from jobpipe.authoring.case_context import AuthoringCaseContext

    ctx = AuthoringCaseContext(
        candidate_id="c1",
        job_id="j1",
        evaluation_id="e1",
        job_summary={"title": "Engineer"},
        decision_brief={"match_score": 0.8},
        selected_evidence=[{"id": "ev1", "bullets": ["Did X"]}],
        narrative_brief={"tone": "confident"},
        artifact_plan=None,
    )
    # Try pydantic first, fall back to dataclass
    try:
        serialised = ctx.model_dump_json()
    except AttributeError:
        serialised = json.dumps(dataclasses.asdict(ctx))
    recovered = json.loads(serialised)
    assert recovered["job_id"] == "j1"
```

**Important:** If `AuthoringCaseContext` constructor signature differs from the above, adapt the test to match the real signature. Do not guess — read the source first.

**Validation:**
```cmd
C:\Users\larsv\envs\crewai-env\Scripts\python.exe -m pytest tests_crewai/test_crewai_author_skeleton.py -v
python compile_check.py
```

All 5 tests must pass. compile_check must pass.

**Report back:** pass/fail for each test, compile_check result, list of files created.

---

## Task 2 — Spawn sub-agent

Spawn a sub-agent with the full contents of the Task 2 brief below.
Wait for it to report back. Must report: all tests pass, `--author` in `--help`, compile_check pass.

If success: commit and proceed to Task 3.
If failure: report to coordinator. Do not proceed.

**Commit after Task 2 success:**
```cmd
cd C:\Users\larsv\Jobpipe-codex-v2
git add jobpipe/authoring/author_factory.py jobpipe/authoring/author_cli.py tests/test_author_factory.py
git commit -m "feat(authoring): AuthorAdapter factory + --author flag"
```

---

### TASK 2 SUB-AGENT BRIEF
*(Pass this entire section as the sub-agent prompt)*

You are implementing Task 2 of T002 Sprint 3 for the JobPipe codebase.

**Repo:** `C:\Users\larsv\Jobpipe-codex-v2` (branch `codex/T002-authoring-mvp`)

**Your job:** Add `author_factory.py` (a factory that builds the right `AuthorAdapter` by name) and wire a `--author` flag into the existing `author_cli.py`. The factory uses `importlib` for the crewai branch so `jobpipe/` never statically imports crewai.

**Files to create/touch — no others:**

| Path | Action |
|---|---|
| `jobpipe/authoring/author_factory.py` | CREATE |
| `jobpipe/authoring/author_cli.py` | MODIFY — add `--author` arg, replace instantiation |
| `tests/test_author_factory.py` | CREATE |

**Step 0 — read before writing:**
Read `jobpipe/authoring/author_cli.py` — find the line that instantiates `SimpleAgentAuthor`. You will replace only that line and add one argument.
Read `jobpipe/authoring/adapter.py` — confirm `AuthorAdapter` Protocol import path.
Read `jobpipe/authoring/simple_agent_author.py` — confirm class name.

**`jobpipe/authoring/author_factory.py`:**
```python
"""Factory for AuthorAdapter implementations.

Uses importlib for crewai so jobpipe/ never statically imports crewai.
"""
import importlib
from jobpipe.authoring.adapter import AuthorAdapter


def build_author(name: str = "simple", model: str = "gpt-4o-mini") -> AuthorAdapter:
    if name == "simple":
        from jobpipe.authoring.simple_agent_author import SimpleAgentAuthor
        return SimpleAgentAuthor(model=model)
    elif name == "crewai":
        mod = importlib.import_module("jobpipe_crewai.author")
        return mod.CrewAIAuthor(model=model)
    else:
        raise ValueError(f"Unknown author {name!r}. Valid: 'simple', 'crewai'")
```

**`author_cli.py` changes — two edits only:**

1. In `add_arguments(p)`, add after the existing `--validate` argument:
```python
p.add_argument(
    "--author",
    default="simple",
    choices=["simple", "crewai"],
    help="Author implementation (default: simple)",
)
```

2. Replace the line that instantiates `SimpleAgentAuthor(model=args.model)` with:
```python
from jobpipe.authoring.author_factory import build_author
author = build_author(name=args.author, model=args.model)
```

Do not change any other line in `author_cli.py`.

**`tests/test_author_factory.py`:**
```python
import pytest
from jobpipe.authoring.adapter import AuthorAdapter
from jobpipe.authoring.author_factory import build_author
from jobpipe.authoring.simple_agent_author import SimpleAgentAuthor


def test_factory_returns_simple_by_default():
    assert isinstance(build_author(), SimpleAgentAuthor)


def test_factory_simple_explicit():
    assert isinstance(build_author("simple"), SimpleAgentAuthor)


def test_factory_satisfies_protocol():
    assert isinstance(build_author("simple"), AuthorAdapter)


def test_factory_unknown_raises():
    with pytest.raises(ValueError, match="Unknown author"):
        build_author("nonsense")


def test_factory_no_static_crewai_import():
    from pathlib import Path
    src = (
        Path(__file__).resolve().parent.parent
        / "jobpipe" / "authoring" / "author_factory.py"
    ).read_text(encoding="utf-8")
    assert "import crewai" not in src
    assert "from crewai" not in src
```

**Validation:**
```cmd
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_author_factory.py tests/test_author_cli.py -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp
python -m jobpipe.cli.main author-package --help
python compile_check.py
```

All 5 factory tests must pass. All 5 existing `test_author_cli.py` tests must still pass. `--author` must appear in `--help`. compile_check must pass.

**Report back:** pass/fail for each test file, whether `--author` is in `--help`, compile_check result.

---

## Task 3 — Spawn sub-agent

Spawn a sub-agent with the full contents of the Task 3 brief below.
Wait for it to report back. Must report: all 5 crew tests pass, all prior test files still pass, compile_check pass.

If success: commit and open PR.
If failure: report to coordinator.

**Commit after Task 3 success:**
```cmd
cd C:\Users\larsv\Jobpipe-codex-v2
git add jobpipe_crewai/ tests_crewai/
git commit -m "feat(crewai): author+critic crew — 2 agents, bounded revision loop"
```

---

### TASK 3 SUB-AGENT BRIEF
*(Pass this entire section as the sub-agent prompt)*

You are implementing Task 3 of T002 Sprint 3 for the JobPipe codebase.

**Repo:** `C:\Users\larsv\Jobpipe-codex-v2` (branch `codex/T002-authoring-mvp`)

**Your job:** Wire a real 2-agent crewAI crew (Author + Critic) inside `CrewAIAuthor.generate()`. All tests must be monkeypatched — no real LLM calls.

**Files to create/touch — no others:**

| Path | Action |
|---|---|
| `jobpipe_crewai/crew.py` | CREATE |
| `jobpipe_crewai/author.py` | MODIFY — replace stub with real crew call |
| `jobpipe_crewai/prompts.py` | MODIFY — add task prompt templates |
| `tests_crewai/test_crewai_crew.py` | CREATE |

**Step 0 — read before writing:**
Read `jobpipe_crewai/author.py` — this is the stub from Task 1. You are replacing `generate()`.
Read `jobpipe_crewai/prompts.py` — you are adding `AUTHOR_TASK_TEMPLATE` and `CRITIC_TASK_TEMPLATE`.
Read `jobpipe/authoring/case_context.py` — note whether it's a pydantic model or dataclass (affects serialisation in `generate()`).

**`jobpipe_crewai/prompts.py` additions** (append to existing content):
```python
AUTHOR_TASK_TEMPLATE = """
Write a job application for the following case. Use ONLY the evidence units provided.
Do not invent experience or skills not present in the evidence.

Context:
{context}

Return a JSON object with these exact keys:
- cover_letter_draft: string (3-paragraph plain text cover letter, no markdown)
- tailored_cv_projection: dict with keys: headline (str), summary_text (str), sections (list)
- evidence_refs: list of evidence unit ID strings you drew from
- gap_notes: list of strings describing gaps between job requirements and available evidence
"""

CRITIC_TASK_TEMPLATE = """
Review the cover letter and CV projection from the Author.
Check against the job context and evidence units below.

Context:
{context}

Return a JSON object with these exact keys:
- passed: boolean (true if acceptable, false if significant issues)
- issues: list of strings (unsupported claims, ATS problems, missing evidence)
- suggestions: list of strings (concrete improvements)
"""
```

**`jobpipe_crewai/crew.py`:**
```python
import json
from crewai import Agent, Crew, Process, Task
from jobpipe_crewai.prompts import (
    AUTHOR_SYSTEM, CRITIC_SYSTEM,
    AUTHOR_TASK_TEMPLATE, CRITIC_TASK_TEMPLATE,
)


def build_authoring_crew(payload: dict, model: str) -> Crew:
    context_str = json.dumps(payload, indent=2)

    author_agent = Agent(
        role="CV and Cover Letter Author",
        goal=(
            "Draft a tailored CV projection and cover letter from candidate evidence. "
            "Only include claims supported by the provided evidence units."
        ),
        backstory=AUTHOR_SYSTEM,
        llm=model,
        verbose=False,
        max_iter=2,
    )

    critic_agent = Agent(
        role="Application Quality Critic",
        goal=(
            "Validate the draft against evidence refs and job claim targets. "
            "Flag unsupported claims, missing evidence, and ATS hygiene issues."
        ),
        backstory=CRITIC_SYSTEM,
        llm=model,
        verbose=False,
        max_iter=2,
    )

    author_task = Task(
        description=AUTHOR_TASK_TEMPLATE.format(context=context_str),
        expected_output=(
            "JSON with: cover_letter_draft (str), tailored_cv_projection (dict), "
            "evidence_refs (list), gap_notes (list)"
        ),
        agent=author_agent,
    )

    critic_task = Task(
        description=CRITIC_TASK_TEMPLATE.format(context=context_str),
        expected_output="JSON with: passed (bool), issues (list), suggestions (list)",
        agent=critic_agent,
        context=[author_task],
    )

    return Crew(
        agents=[author_agent, critic_agent],
        tasks=[author_task, critic_task],
        process=Process.sequential,
        verbose=False,
    )
```

**`jobpipe_crewai/author.py` — replace `generate()` only:**
```python
import dataclasses
import json

from jobpipe.authoring.case_context import AuthoringCaseContext
from jobpipe.authoring.output_models import GeneratedApplicationPackage
from jobpipe_crewai.crew import build_authoring_crew


class CrewAIAuthor:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self._model = model

    def generate(self, ctx: AuthoringCaseContext) -> GeneratedApplicationPackage:
        try:
            payload = ctx.model_dump()        # pydantic
        except AttributeError:
            payload = dataclasses.asdict(ctx) # dataclass fallback

        crew = build_authoring_crew(payload, self._model)
        result = crew.kickoff()
        raw = str(result) if result else ""

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return GeneratedApplicationPackage(
                job_id=ctx.job_id,
                cover_letter_draft=raw,
                tailored_cv_projection={},
                evidence_refs=[],
                gap_notes=["crewAI output was not valid JSON — raw text returned"],
            )

        return GeneratedApplicationPackage(
            job_id=ctx.job_id,
            cover_letter_draft=parsed.get("cover_letter_draft", raw),
            tailored_cv_projection=parsed.get("tailored_cv_projection", {}),
            evidence_refs=parsed.get("evidence_refs", []),
            gap_notes=parsed.get("gap_notes", []),
        )
```

**`tests_crewai/test_crewai_crew.py`:**
```python
import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_ctx():
    from jobpipe.authoring.case_context import AuthoringCaseContext
    return AuthoringCaseContext(
        candidate_id="c1",
        job_id="j1",
        evaluation_id="e1",
        job_summary={"title": "Engineer", "company": "Acme"},
        decision_brief={"match_score": 0.85, "claim_targets": ["Python"]},
        selected_evidence=[{"id": "ev1", "role": "Backend Eng", "bullets": ["Built APIs"]}],
        narrative_brief={"tone": "confident"},
        artifact_plan=None,
    )


def test_crew_has_two_agents():
    from jobpipe_crewai.crew import build_authoring_crew
    ctx = _make_ctx()
    try:
        payload = ctx.model_dump()
    except AttributeError:
        payload = dataclasses.asdict(ctx)
    crew = build_authoring_crew(payload, "gpt-4o-mini")
    assert len(crew.agents) == 2


def test_crew_has_two_tasks():
    from jobpipe_crewai.crew import build_authoring_crew
    ctx = _make_ctx()
    try:
        payload = ctx.model_dump()
    except AttributeError:
        payload = dataclasses.asdict(ctx)
    crew = build_authoring_crew(payload, "gpt-4o-mini")
    assert len(crew.tasks) == 2


def test_crew_output_parses_to_package():
    from jobpipe_crewai.author import CrewAIAuthor
    from jobpipe.authoring.output_models import GeneratedApplicationPackage

    fake = json.dumps({
        "cover_letter_draft": "Dear Hiring Manager...",
        "tailored_cv_projection": {"headline": "Backend Engineer", "summary_text": "...", "sections": []},
        "evidence_refs": ["ev1"],
        "gap_notes": [],
    })

    with patch("jobpipe_crewai.author.build_authoring_crew") as mock_build:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = fake
        mock_build.return_value = mock_crew
        pkg = CrewAIAuthor().generate(_make_ctx())

    assert isinstance(pkg, GeneratedApplicationPackage)
    assert pkg.cover_letter_draft == "Dear Hiring Manager..."
    assert pkg.evidence_refs == ["ev1"]


def test_crew_handles_non_json_output():
    from jobpipe_crewai.author import CrewAIAuthor
    from jobpipe.authoring.output_models import GeneratedApplicationPackage

    with patch("jobpipe_crewai.author.build_authoring_crew") as mock_build:
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Here is your letter. Dear Hiring Manager..."
        mock_build.return_value = mock_crew
        pkg = CrewAIAuthor().generate(_make_ctx())

    assert isinstance(pkg, GeneratedApplicationPackage)
    assert len(pkg.cover_letter_draft) > 0
    assert any("not valid JSON" in n for n in pkg.gap_notes)


def test_no_langchain_or_autogen():
    crewai_dir = REPO_ROOT / "jobpipe_crewai"
    for py_file in crewai_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "langchain" not in content, f"langchain in {py_file}"
        assert "autogen" not in content, f"autogen in {py_file}"
```

**Validation:**
```cmd
REM crewAI env — all crewai tests
C:\Users\larsv\envs\crewai-env\Scripts\python.exe -m pytest tests_crewai/ -v

REM Main suite — no regressions
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_author_factory.py tests/test_author_cli.py -v -p no:debugging -p no:cacheprovider --basetemp .pytest-tmp

python compile_check.py
```

All 10 `tests_crewai/` tests must pass. All 10 main-suite tests must pass. compile_check must pass.

**Report back:** pass/fail for each test file, count of tests, compile_check result.

---

## Final PR — open after Task 3 commit

```cmd
cd C:\Users\larsv\Jobpipe-codex-v2
git push origin codex/T002-authoring-mvp
gh pr create --title "T002 Sprint 3: crewAI author/critic loop (isolated module, AuthorAdapter seam)" --body "$(cat <<'EOF'
## Sprint 3

Adds a crewAI authoring layer behind the existing AuthorAdapter Protocol seam.
`jobpipe/` contains zero crewai imports — enforced by test.

### Task 1 — CrewAIAuthor skeleton (isolated module)
- `jobpipe_crewai/__init__.py`, `author.py`, `prompts.py`
- `tests_crewai/test_crewai_author_skeleton.py` (5 tests)

### Task 2 — AuthorAdapter factory + --author flag
- `jobpipe/authoring/author_factory.py` (importlib pattern, no static crewai import)
- `jobpipe/authoring/author_cli.py` (--author simple|crewai)
- `tests/test_author_factory.py` (5 tests)

### Task 3 — Real 2-agent Author/Critic crew
- `jobpipe_crewai/crew.py` (sequential crew, max_iter=2)
- `jobpipe_crewai/author.py` (real crew wired, defensive JSON parse)
- `tests_crewai/test_crewai_crew.py` (5 tests, all monkeypatched)

### Results
- tests_crewai/: 10/10 (Python 3.12 crewAI env)
- tests/ factory + cli: 10/10 (Python 3.14)
- compile_check: passed
- No crewai import under jobpipe/: confirmed

### Sprint 3 exit test (run after merge)
```
C:\Users\larsv\envs\crewai-env\Scripts\python.exe -m jobpipe.cli.main author-package --job <apply_job_id> --author crewai --no-persist
```
EOF
)"
```
