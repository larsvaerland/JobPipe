# Configuration

## Baseline setup

Start from:

1. create `.env` from `.env.example`
2. create `profile_pack.md` from `profile_pack.example.md`
3. create and activate a virtual environment
4. install the package with `python -m pip install -e .`

At minimum, set:

- `OPENAI_API_KEY`
- `JOBPIPE_CSV_URL`

## Recommended runtime layout

For normal use, keep user data outside the repo with `JOBPIPE_DATA_DIR`.

Examples:

- Windows: `JOBPIPE_DATA_DIR=C:\Users\yourname\JobpipeData`
- macOS/Linux: `JOBPIPE_DATA_DIR=~/JobpipeData`

Conceptually, the runtime layout should look like:

```text
JOBPIPE_DATA_DIR/
  db/
  artifacts/
  exports/
  documents/
  cache/
  secrets/
```

This is the intended boundary between:

- repo code/docs/specs
- persistent candidate and runtime state

## Important env vars

### Required

- `OPENAI_API_KEY`
- `JOBPIPE_CSV_URL`

### Common optional

- `JOBPIPE_DATA_DIR`
- `JOBPIPE_CANDIDATE_ID`
- `JOBPIPE_PROFILE_PATH`
- `JOBPIPE_RESUME_JSON`
- `JOBPIPE_DB_PATH`
- `JOBPIPE_EXPORT_DIR`
- `JOBPIPE_ARTIFACT_DIR`
- `JOBPIPE_DOCUMENTS_DIR`

### Gmail-related

- `JOBPIPE_GMAIL_CREDENTIALS_PATH`
- `JOBPIPE_GMAIL_TOKEN_PATH`

## Candidate inputs

Current practical candidate inputs include:

- `profile_pack.md`
- `resume.json`

These are still valid working files, but the intended direction is:

- structured candidate state in the primary DB
- working files as import/export and compatibility surfaces

Under `JOBPIPE_DATA_DIR`, the current canonical defaults are:

- `documents/profile_pack.md`
- `documents/resume.json`
- `db/application_state.json`
- `db/suggested_jobs.jsonl`
- `cache/profile_embedding.npy`
- `secrets/gmail_credentials.json`
- `secrets/gmail_token.json`

For single-user clean installs that already have a flat `JOBPIPE_DATA_DIR`, JobPipe still accepts these legacy compatibility locations if they already exist:

- `profile_pack.md`
- `resume.json`
- `gmail_credentials.json`
- `gmail_token.json`

Use `bootstrap-state-db` to import current local candidate data into the DB.

For a controlled post-refactor rebuild of generated runtime state, use:

```text
jobpipe reset-runtime
jobpipe bootstrap-state-db
```

`reset-runtime` archives generated state under `<JOBPIPE_DATA_DIR>/_archives/` and recreates fresh runtime folders. It is designed for the current hybrid layout too, so flat compatibility files such as `profile_pack.md`, `resume.json`, Gmail secrets, and preserved application-state inputs are not silently destroyed.

A full first-pass queue rebuild remains separate:

```text
jobpipe drain-queue --reset-state
```

Use that only when you intentionally want to repull the large source queue. It is not required for normal smoke validation after a reset.

## Transitional compatibility files

Some file-shaped runtime data still exists during migration, including items such as:

- `application_state.json`
- `suggested_jobs.jsonl`
- embedding cache files

These should be treated as compatibility bridges or derived runtime support, not as the preferred long-term source of truth.

## Pipeline configuration

Pipeline behavior is controlled in:

- `configs/pipeline.v1.yaml`

This file defines:

- stage order
- model choices
- thresholds
- regex rules
- search defaults

## Source-specific notes

### Sheet intake

The main batch path expects a published CSV URL, not a private edit URL, unless you are explicitly using sheet URL mode.

### Gmail

Gmail integration is optional.

It currently supports:

- application-status detection
- suggestion-email ingestion

The repo direction is toward provider-neutral mail ingestion over time.

## Canonical runtime interface

Use:

```text
jobpipe run
jobpipe run --dry-run
```

Fallback:

```text
python -m jobpipe.cli.main run
```

`go.ps1` is a Windows wrapper over the same workflow.

## Safe change strategy

1. Change one control point at a time.
2. Prefer dry runs after config or threshold changes.
3. Keep candidate data separate from code.
4. Treat exported files as derived outputs, not configuration.
