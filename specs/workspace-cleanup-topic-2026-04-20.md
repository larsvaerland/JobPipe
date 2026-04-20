# Workspace Cleanup Topic

Last updated: 2026-04-20

Purpose:
- reduce local worktree confusion around `C:\Users\larsv`
- keep only the current working set clearly active
- prevent future mix-ups between `Jobpipe` and older or sidecar worktrees

This is an operational cleanup topic, not a product-feature roadmap item.

## Goal

Create one reviewed retain/archive/delete plan for local project folders and related GitHub repos so the only clearly active tracked projects left in the day-to-day working set are:
- `C:\Users\larsv\Jobpipe`
- `C:\Users\larsv\jobsync`
- `C:\Users\larsv\reactive-resume`

## Hard rule

No deletion or move happens without explicit human approval per path.

## Scope

In scope:
- local repo/worktree inventory under `C:\Users\larsv`
- path-by-path classification
- legacy/wrong-worktree confusion reduction in docs
- explicit keep set and review set
- GitHub hygiene plan for matching repos

Out of scope unless explicitly approved later:
- deleting local folders
- deleting or archiving GitHub repos
- rewriting product roadmap around this cleanup

## Current confusion sources

Known local confusion sources include:
- `C:\Users\larsv\agentic_jobpilot`
- `C:\Users\larsv\deepagents-jobpipe`
- `C:\Users\larsv\nav-google-sheet-feed`
- non-git local copies such as `Jobpipe-clean`, `jobpipe_openclaw`, `openai_agentic`, and `openai_agentic_jobpipe_v1`

## Required sequence

1. Build a local inventory.
2. Mark each path as one of:
   - keep active
   - keep archived
   - review before archive/delete
   - unknown
3. Confirm the keep set with the human.
4. Confirm archive/delete actions with the human.
5. Only then move, archive, or delete anything.
6. After local cleanup, review GitHub repo relevance against the same keep set.

## Acceptance criteria

- one explicit local inventory exists
- one explicit keep set exists
- one explicit review/archive candidate set exists
- no destructive action is taken without human approval
- current Jobpipe docs no longer leave old `agentic_jobpilot` filenames as dead ends

## Validation

- verify the inventory document paths exist
- verify the keep set matches the user's stated active project set
- verify no delete/move command was run as part of this topic setup

## Execution note

Human approval was later provided for the first cleanup pass.

Executed local actions:
- archived:
  - `agentic_jobpilot`
  - `deepagents-jobpipe`
  - `nav-google-sheet-feed`
- deleted:
  - `jobpipe_openclaw`
  - `Jobpipe-clean`
  - `openai_agentic`
  - `openai_agentic_jobpipe_v1`

Archive location:
- `C:\Users\larsv\_archived_projects\2026-04-20`

This topic still does not authorize GitHub-side deletion or archive changes without a separate review.
