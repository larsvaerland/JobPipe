# Orchestrator — Git Workflow (sandbox vs Windows)

**Purpose:** Prevent the orchestrator (Claude Desktop / Cowork session) from burning tokens trying to run git against the mounted worktree from inside the Linux sandbox. This doc is canonical; the `jobpipe-orchestrator` SKILL.md points at it.

## The problem

The three JobPipe worktrees live on Lars's Windows machine:

- `C:\Users\larsv\Jobpipe-orchestrator-v2` → `ops/orchestrator-v2`
- `C:\Users\larsv\Jobpipe-codex-v2` → `codex/T00X-<slug>`
- `C:\Users\larsv\Jobpipe-claude-v2` → `claude/T00X-<slug>`

Cowork mounts the orchestrator worktree into the sandbox at `/sessions/<session>/mnt/Jobpipe-orchestrator-v2`. **File I/O works** (Read, Write, Edit, grep). **Git does not**, because each worktree's `.git` file references a Windows-native path:

```
gitdir: C:/Users/larsv/Jobpipe/.git/worktrees/Jobpipe-orchestrator-v2
```

Running `git` via `Bash` inside the sandbox against that mount fails with:

```
fatal: not a git repository: .../C:/Users/larsv/Jobpipe/.git/worktrees/Jobpipe-orchestrator-v2
```

This is the expected state, not an error to debug. Do not try `GIT_DIR=`, symlinks, or re-initializing.

## The rules

### Reads — OK via PowerShell/Desktop Commander

For git state you need to make a routing decision (status, branch, log, diff), run via `mcp__Desktop_Commander__start_process` → PowerShell:

```powershell
git -C C:\Users\larsv\Jobpipe-orchestrator-v2 status --short
git -C C:\Users\larsv\Jobpipe-orchestrator-v2 branch --show-current
git -C C:\Users\larsv\Jobpipe-orchestrator-v2 log --oneline -10
```

Same pattern for the other two worktrees. Chain with `echo "---"` separators so the output is parseable.

### Writes — never executed by the orchestrator

Commits, pushes, fetches, resets, rebases, merges, branch creates, tag ops — **all run by Lars on Windows**. The orchestrator's job is to prepare the exact command sequence as text and hand it to him.

Why: writes are how damage happens (wrong branch, wrong message, missed hook, force-push to main). The orchestrator can see what needs to happen without owning the execution risk. This matches the role contract in `CLAUDE.md` — orchestrator plans, implementers execute.

### The commit handoff template

When the orchestrator has edited files in the mounted worktree and wants a commit, produce a block like this for Lars to paste into PowerShell:

```powershell
cd C:\Users\larsv\Jobpipe-orchestrator-v2
git status --short
# expect only: the intended files, no diagnostic helpers

git add <exact-paths>
git commit -m "<scope>: <what changed>

<1-3 sentence why>

Refs: <execplan path or decision record>"
git push origin ops/orchestrator-v2
```

Rules for the commit block:

- **Stage files explicitly** (`git add path1 path2`) — never `git add -A` or `git add .`; the orchestrator shouldn't risk pulling in Lars's Windows-side stray files.
- **Single-line subject under 72 chars**, conventional scope prefix (`docs:`, `pipeline:`, `contract:`, `orchestrator:`).
- **Body explains why**, not what — the diff is the what.
- **Refs line** points at the execplan or decision that authorizes the change.
- **Push explicitly** to the orchestrator branch, never `git push` without a remote/branch spec.

### Codex handoff pre-stage

Before pasting a Codex prompt, reset the Codex worktree from the orchestrator side:

```powershell
git -C C:\Users\larsv\Jobpipe-codex-v2 fetch origin
git -C C:\Users\larsv\Jobpipe-codex-v2 checkout -B codex/<slug> origin/main
# or, if branch exists and you want to force-refresh:
git -C C:\Users\larsv\Jobpipe-codex-v2 reset --hard origin/main
git -C C:\Users\larsv\Jobpipe-codex-v2 push -f origin codex/<slug>
```

Include `git fetch origin && git reset --hard origin/<branch>` at the top of every Codex prompt itself — never trust worktree state.

## Symptom → action cheat sheet

| Symptom | Action |
|---|---|
| `fatal: not a git repository` from `Bash` on `/sessions/.../mnt/...` | Use PowerShell via Desktop Commander for reads; hand commands to Lars for writes. |
| `docs/current-state.json` edited in sandbox but not in git | Normal — orchestrator stages docs, founder commits. Produce the add+commit block. |
| Untracked `.bat` / `smoke_*.py` in worktree | Stale diagnostics. Do not stage them. Note in handoff. |
| Codex branch doesn't match `implementation_branch` in `current-state.json` | Flag the drift. Pre-stage the correct branch before issuing the Codex prompt. |
| PowerShell `git` command times out | Lars's machine is offline or VPN is interfering. Stop and ask. |

## Cross-refs

- `CLAUDE.md` — orchestrator role + escalation gates
- `docs/ai-playbook.md` — branch/worktree rules, PR conventions, approval gates
- `docs/current-state.json` → `worktrees` — live paths + branches
- `.claude/skills/jobpipe-orchestrator/SKILL.md` — session-start procedure (reads this file)
