# `profile/` — candidate profile contract

This folder holds the candidate's profile as a set of flat files. Layout mirrors
the CrewAI Job Hunter Crew contract so profile state is portable across
JobPipe and upstream-fork tooling.

**Personal files stay local.** They are listed in `.gitignore`. Only the
`.example` templates and this README are committed.

## Files

| File | Purpose | Tracked? |
|---|---|---|
| `profile_pack.md` | Canonical candidate brief consumed by triage, match, and pack. Sibling files below get stitched onto this at load time. | local only |
| `resume.json` | JSON Resume 1.0 schema. Source of truth for structured experience/skills. | local only |
| `constraints.md` | Hard constraints (location, language, comp floor, etc.). Loader appends to profile_pack. | local only |
| `motivation.md` | Career motivation / narrative frame for cover letters + match reasoning. Loader appends to profile_pack. | local only |
| `cover_letter_voice.md` | Voice/tone reference for application_pack author. | local only |
| `*.example` | Scrubbed templates showing the expected shape of each personal file. | tracked |
| `README.md` | This file. | tracked |

## How loading works

`jobpipe.core.candidate_data._apply_profile_siblings()` stitches `constraints.md`
and `motivation.md` onto `profile_pack.md` at load time. The stitch is
idempotent — guarded by a `<!-- PROFILE_SIBLINGS_APPLIED -->` marker so repeated
loads don't duplicate content.

`jobpipe/runtime/paths.py` prefers `profile/` over the legacy repo-root paths
via `_prefer_existing()`, so an older layout with `profile_pack.md` at the repo
root still works as fallback.

## First-time setup

1. Copy each `*.example` to its non-example counterpart:
   ```powershell
   Copy-Item profile\resume.json.example profile\resume.json
   Copy-Item profile\constraints.md.example profile\constraints.md
   Copy-Item profile\motivation.md.example profile\motivation.md
   ```
2. Author `profile/profile_pack.md` and `profile/cover_letter_voice.md` from
   scratch (no templates shipped — too personal to template meaningfully).
3. Run `jobpipe import-reactive-resume` once to regenerate derived state.

## Reactive-Resume import

`jobpipe import-reactive-resume` accepts an optional positional path argument:

```powershell
jobpipe import-reactive-resume
# equivalent to:
jobpipe import-reactive-resume profile\resume.json
```

Pass an explicit path to import from a different JSON Resume export.

## Why files, not a DB

Profile edits are low-frequency, version-sensitive, and need to survive
reinstalls. Flat files in a well-known folder are the simplest durable contract
and let the user edit in any text editor. A DB would add an import/export
surface for no real benefit at this scale.
