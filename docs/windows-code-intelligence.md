# Windows Code Intelligence

This file captures the standard local code-intelligence setup for JobPipe when
working from Windows Git worktrees.

Use it together with:

- [docs/ai-playbook.md](C:/Users/larsv/Jobpipe-codex-v2/docs/ai-playbook.md)
- [docs/module-ownership.md](C:/Users/larsv/Jobpipe-codex-v2/docs/module-ownership.md)
- [docs/deprecation-map.md](C:/Users/larsv/Jobpipe-codex-v2/docs/deprecation-map.md)

## Default stack

Use three layers:

1. `Axon` for structural graph queries
2. `Repomix` for AI-friendly context packing
3. `rg` plus targeted tests plus `python compile_check.py` as final truth

`CodeGraphContext` is a useful secondary graph tool for cross-checking results.

`GitNexus` is not part of the default Windows-worktree path today. Keep it as
an optional research tool on a Linux-side clone or other alternate runtime.

## Tool roles

### Axon

Primary graph tool on Windows worktrees.

Use it for:

- caller and callee inspection
- blast-radius checks before refactors
- dead-code candidate generation
- seam mapping across CLI, runtime, stages, and DB helpers

Typical commands:

```powershell
& "$env:USERPROFILE\tool-evals\axon\Scripts\axon.exe" analyze . --no-embeddings
& "$env:USERPROFILE\tool-evals\axon\Scripts\axon.exe" context build_stages
& "$env:USERPROFILE\tool-evals\axon\Scripts\axon.exe" impact connect_primary_db
& "$env:USERPROFILE\tool-evals\axon\Scripts\axon.exe" dead-code
```

Operational note:

- Axon stores a repo-local `.axon/` cache directory.
- Treat `.axon/` as local-only state, not repo content.

### Repomix

Primary context packer for AI handoff and review packets.

Use it for:

- bounded code snapshots for AI review
- feature-scope handoff packets
- quick token-heavy repo summaries outside the graph tools

Typical command:

```powershell
$repomix = "$env:USERPROFILE\tool-evals\repomix\node_modules\.bin\repomix.cmd"
$out = "$env:USERPROFILE\tool-evals\repomix\jobpipe-repomix.xml"

& $repomix . -o $out --ignore ".axon/**,.cgcignore" --top-files-len 10
```

Operational note:

- Write Repomix output outside the repo.

### CodeGraphContext

Secondary graph tool and cross-check surface.

Use it for:

- exact-name symbol lookup
- caller/callee checks on known symbols
- cross-checking Axon on important seams

Typical commands:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
chcp 65001 > $null

& "$env:USERPROFILE\tool-evals\codegraphcontext\Scripts\cgc.exe" doctor
& "$env:USERPROFILE\tool-evals\codegraphcontext\Scripts\cgc.exe" index . --force
& "$env:USERPROFILE\tool-evals\codegraphcontext\Scripts\cgc.exe" find name connect_primary_db -t function
& "$env:USERPROFILE\tool-evals\codegraphcontext\Scripts\cgc.exe" analyze callers connect_primary_db -f jobpipe/core/primary_db.py
```

Operational notes:

- Use UTF-8 console settings on Windows before `doctor` or other rich output.
- `cgc` may auto-create `.cgcignore` in repo root. Treat it as local-only unless
  the repo explicitly adopts it later.

### GitNexus

Not the default Windows-worktree tool.

Current status:

- native Windows worktree path still does not complete indexing cleanly
- Linux-side clone path can work, but that is not the primary edit loop

Use only when:

- evaluating alternate graph behavior
- investigating WSL-side results
- comparing with Axon or CodeGraphContext for a specific issue

## Local install locations

Keep tool installs outside the repo:

- `C:\Users\larsv\tool-evals\axon`
- `C:\Users\larsv\tool-evals\codegraphcontext`
- `C:\Users\larsv\tool-evals\repomix`

Do not vendor these tools into the JobPipe repo.

## Repo hygiene rules

Local-only artifacts must stay out of commits:

- `.axon/`
- `.cgcignore`
- `.gitnexus/`
- Repomix output files
- ad hoc tool logs and cache directories

Do not let repo-root temp directories accumulate again:

- `.pytest-tmp`
- `.pytest-tmp-slice4-run`
- `.tmp-authoring-smoke`
- `pytest-cache-files-*`

If those reappear and develop broken ACLs, remove them from an elevated `cmd`
session before blaming the code-intelligence tools.

## Daily workflow

### Before a non-trivial refactor

1. Run Axon `context` on the symbol you intend to change.
2. Run Axon `impact` on the same symbol or owning class/function.
3. Cross-check with `rg` or direct file reads if the seam is sensitive.
4. Run targeted tests and `python compile_check.py` after the change.

### Before an AI handoff or review request

1. Generate a Repomix pack outside the repo.
2. Use file filters or ignore patterns if the scope should stay narrow.
3. Prefer Repomix for bounded context; do not rely on it as a graph tool.

### When tool answers disagree

Use this order of trust:

1. direct code read
2. targeted repo search
3. tests and compile checks
4. graph tool output

Graph tools are for navigation and blast-radius reduction, not for replacing
source inspection.
