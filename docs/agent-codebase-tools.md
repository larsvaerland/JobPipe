# Codebase Navigation Tools — Agent Instructions

Two MCP tools are available for navigating this codebase efficiently.
**Always prefer these over reading raw files.** Reading files burns tokens.

---

## Tool 1: `codebase-index` — Structural navigation

Use for understanding code structure and dependencies WITHOUT reading file content.

### Key queries — call FIRST before touching any file

```
find_symbol("JobStage")                          # where is this defined?
find_references("run_pipeline")                  # what calls this?
get_change_impact("SyncBridge")                  # what breaks if I change this?
search_codebase("connector")                     # keyword search across repo
get_dependencies("jobpipe/core/pipeline.py")     # what does this file import?
get_function_source("JobStage.execute")          # source without reading whole file
```

### Rules
- MANDATORY: use codebase-index FIRST for all code navigation
- Only read files after a symbol query tells you exactly which file and line
- Run get_change_impact before any refactor
- Index auto-updates from git diff — no manual reindex needed

---

## Tool 2: `repomix` — Context packing for focused tasks

Use when an agent needs to work on a specific module and needs full file content.
Pack ONLY what is needed.

### Profiles — run from repo root

**Jobpipe**
```bash
repomix --profile core          # stages, runtime, model, decision
repomix --profile crewai        # CrewAI crews, agents, orchestration
repomix --profile cli           # CLI, connectors, integrations
repomix --profile tests         # test suite
repomix --profile configs       # config files and specs
repomix --profile docs          # documentation
```

**jobsync**
```bash
repomix --profile core                  # actions, models, lib
repomix --profile ui                    # components and pages
repomix --profile api                   # API routes only
repomix --profile db                    # Prisma schema
repomix --profile jobpipe-integration   # jobpipe-related files
```

**JobVibe / JobDesk**
```bash
repomix --profile core
repomix --profile api
repomix --profile ui
```

**jobsane** — small repo, pack whole thing
```bash
repomix --profile all
```

### Scoped include when no profile fits
```bash
repomix --include "jobpipe/connectors/**,jobpipe/integrations/**"
repomix --include "jobpipe/runtime/executor.py,tests/test_executor.py"
```

### Rules
- NEVER run repomix with no --profile or --include in Jobpipe, jobsync, JobDesk, JobVibe
- Output: repomix-output.xml — gitignored, safe to regenerate
- Per worktree task: pack only the profile for that task
- Cross-repo: one profile per repo, not full repos

---

## Decision guide

| Task                              | Tool           | Command                        |
|-----------------------------------|----------------|--------------------------------|
| Find where function is defined    | codebase-index | find_symbol("name")            |
| Find callers before refactor      | codebase-index | get_change_impact("name")      |
| Understand module structure       | codebase-index | get_dependencies("path")       |
| Fix bug in known module           | repomix        | repomix --profile core         |
| Work on CrewAI crew               | repomix        | repomix --profile crewai       |
| Review tests                      | repomix        | repomix --profile tests        |
| Full overview (jobsane only)      | repomix        | repomix --profile all          |

---

## Working in a worktree

```bash
# Run repomix from within the worktree directory
cd C:\Users\larsv\Jobpipe\.claude\worktrees\<name>
repomix --profile core

# codebase-index works per worktree — each maintains its own index via git
```

## Multi-agent coordination

- **Claude** (claude.ai / Claude Code): use both tools freely
- **Codex**: repomix profile at task start; codebase-index for symbol lookup during task
- **CrewAI crews**: receive repomix output as crew context; crews do NOT get raw file access

---

## What NOT to do

- Do NOT cat/Read entire source files — use find_symbol first
- Do NOT run repomix without --profile in large repos
- Do NOT feed full repomix output to all agents at once — scope per agent per task
- Do NOT commit repomix-output.xml or .codebase-index-cache.pkl (both gitignored)
