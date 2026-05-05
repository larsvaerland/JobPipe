# Changelog

## Unreleased

### Added
- primary DB architecture docs and runtime documentation
- dashboard and Apps Script docs under `docs/`

### Changed
- normalized runtime naming around evaluation sync
- consolidated product and technical docs around the DB-first local-first model
- `build_stages` consolidated: `jobpipe/stages/pipeline.py` is now the single
  source of truth; `run_feed.py` no longer carries a duplicate definition
  (`582b2a4`). The live path was already `run_feed.py`'s version; this makes both
  callers use the same code and removes ~160 lines of drift.

### Fixed
- **Pipeline crash on long LLM strings** (`6daa5f1`): `AdvantageAssessmentV3.recruiter_hook`,
  `applicant_pool_hypothesis`, and `summary` now truncate to 237 chars + "…" via a
  `before`-mode Pydantic validator instead of raising a `ValidationError` that
  silently left jobs with no `final_decision`.

- **`applicationDue` date normalisation — root fix** (`2a9ba91`): `pull_sheets_csv`
  now applies `_normalize_due()` at ingest time, converting `dd.mm.yyyy`,
  `dd/mm/yyyy`, and `dd-mm-yyyy` (Norwegian/European formats from Google Sheets) to
  ISO `YYYY-MM-DD` before writing to the connector JSONL. The deadline-expiry filter
  also uses the normalised value, so a hyphen-formatted date is now correctly
  evaluated instead of falling through to the epoch sentinel.

- **`_parse_date_maybe` hyphen separator + typo-year guard** (`a07ba60`): The
  downstream normaliser in `sync_ledger` and `sync_evaluations` gains the same
  hyphen-separator support as a safety net for records already queued before the
  root fix. Also tightens the year-part check to require exactly 4 digits, so a
  typo like `01.04.20226` is returned raw instead of being silently parsed as `2022`.

- **Open-deadline keyword inconsistency** (`64a2f4d`): Three independent keyword
  sets (`snarest`, `asap`, `fortløpende`, …) have been consolidated into a single
  `_OPEN_DEADLINE_PREFIXES` tuple matched via `startswith`. This catches multi-word
  variants (`snarest mulig`, `snarest mulig oppstart`) that the old exact-match sets
  missed, adds the missing `løpende` to the `pull_sheets_csv` deadline filter, and
  adds `rolling` as an English synonym.

---

## v1.0.0

Initial public baseline.
