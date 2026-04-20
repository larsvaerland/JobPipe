# Workspace Cleanup Inventory

Last updated: 2026-04-20

Purpose:
- capture the current local project landscape under `C:\Users\larsv`
- separate the active keep set from review/archive candidates
- support a human-in-the-loop cleanup pass later

## Keep set

These are the only clearly active tracked projects the user wants left in the working set:

| Path | Type | Current note |
|---|---|---|
| `C:\Users\larsv\Jobpipe` | git repo | active canonical repo |
| `C:\Users\larsv\jobsync` | git repo | active companion repo |
| `C:\Users\larsv\reactive-resume` | git repo | active companion dependency |

## Archived in local cleanup pass

Archive root:
- `C:\Users\larsv\_archived_projects\2026-04-20`

| Original path | Archive result | Note |
|---|---|---|
| `C:\Users\larsv\agentic_jobpilot` | archived | zip created at `agentic_jobpilot.zip`; archive folder also exists under the same archive root from the earlier failed move attempt |
| `C:\Users\larsv\deepagents-jobpipe` | archived | zip created at `deepagents-jobpipe.zip` |
| `C:\Users\larsv\nav-google-sheet-feed` | archived | zip created at `nav-google-sheet-feed.zip` |

## Deleted in local cleanup pass

| Original path | Result |
|---|---|
| `C:\Users\larsv\jobpipe_openclaw` | deleted |
| `C:\Users\larsv\Jobpipe-clean` | deleted |
| `C:\Users\larsv\openai_agentic` | deleted |
| `C:\Users\larsv\openai_agentic_jobpipe_v1` | deleted |

## Remaining review set

After the approved local cleanup pass, there are no extra first-level git repos left under `C:\Users\larsv` besides:
- `Jobpipe`
- `jobsync`
- `reactive-resume`

## Notes

- `C:\Users\larsv\agentic_jobpilot` was the wrong worktree that caused the latest documentation/runtime confusion and is now archived.
- `C:\Users\larsv\Jobpipe` currently has both `origin=https://github.com/larsvaerland/Jobpipe.git` and `legacy=https://github.com/larsvaerland/Job-Hunter-Pilot.git`.
- The `legacy` remote points to GitHub repo `larsvaerland/Job-Hunter-Pilot`.
- No first-level local folder matching `Job-Hunter-Pilot` remains after the local cleanup pass.
- `prototype/` inside `C:\Users\larsv\Jobpipe` is local material and should not be treated as a tracked product repo.

## Human review checklist

For each review candidate, decide one of:
- keep for now
- archive locally
- delete locally after backup check
- keep remote but archive local copy
- archive/delete matching GitHub repo later

## Safety rule

No deletion or move should happen until this inventory has been reviewed and approved path by path.

GitHub-side cleanup is still pending a separate explicit review.
