# CLI Reference

## Main workflow

Normal run:

```powershell
.\go.ps1
```

Useful variants:

```powershell
.\go.ps1 -DryRun
.\go.ps1 -NoOpen
.\go.ps1 -WithSuggestions
```

## Source intake and batch processing

Pull from the published sheet export:

```powershell
python -m jobpipe.cli.pull_sheets_csv --csv-url "<published-csv-url>"
```

Drain the queue and run the pipeline in batches:

```powershell
python -m jobpipe.cli.drain_queue --csv-url "<published-csv-url>" --candidate-id default
```

FINN helpers:

```powershell
python -m jobpipe.cli.pull_finn_search --config .\configs\pipeline.v1.yaml
python -m jobpipe.cli.pull_finn_ext
python -m jobpipe.cli.pull_suggested --dry-run
```

## Evaluation sync and dashboard export

Mirror latest evaluations into the primary DB and export a reporting CSV:

```powershell
python -m jobpipe.cli.sync_evaluations --out .\out_runs --candidate-id default
```

Rebuild the dashboard:

```powershell
python -m jobpipe.cli.export_dashboard --candidate-id default
```

## Candidate state and inspection

Bootstrap current candidate files into the primary DB:

```powershell
python -m jobpipe.cli.bootstrap_state_db
```

Generate a capability-gap report from current evaluation evidence:

```powershell
python -m jobpipe.cli.gap_analysis_report --candidate-id default
```

Record explicit manual feedback for later calibration:

```powershell
python -m jobpipe.cli.record_feedback JOB_ID good_recommendation
python -m jobpipe.cli.record_feedback JOB_ID bad_recommendation --notes "Prestigious role, but unrealistic ask"
python -m jobpipe.cli.record_feedback JOB_ID promote --notes "Non-obvious role family, but strong real match"
python -m jobpipe.cli.record_feedback JOB_ID demote
python -m jobpipe.cli.record_feedback JOB_ID good_fit
python -m jobpipe.cli.record_feedback JOB_ID bad_fit --json
```

Inspect DB state:

```powershell
python -m jobpipe.cli.inspect_primary_db --show summary --show applications --show suggestions
python -m jobpipe.cli.inspect_primary_db --show events --limit 20 --json
python -m jobpipe.cli.inspect_primary_db --show feedback --show gaps --show gap_assessments --limit 20
```

## Application tracking

Manual status updates:

```powershell
python -m jobpipe.cli.mark_status JOB_ID shortlisted
python -m jobpipe.cli.mark_status JOB_ID applied
python -m jobpipe.cli.mark_status JOB_ID interview
python -m jobpipe.cli.mark_status JOB_ID rejected --notes "Form letter"
python -m jobpipe.cli.mark_status JOB_ID dismissed
python -m jobpipe.cli.mark_status --list
```

## Gmail integration

One-time setup:

```powershell
python -m jobpipe.cli.scan_gmail --setup
```

Status scan:

```powershell
python -m jobpipe.cli.scan_gmail
python -m jobpipe.cli.scan_gmail --dry-run --verbose
```

Suggestion scan:

```powershell
python -m jobpipe.cli.scan_gmail --scan-suggestions
python -m jobpipe.cli.scan_gmail --scan-suggestions --dry-run
```

## Notes

- The primary DB is the canonical runtime state layer.
- `JOBPIPE_CANDIDATE_ID` defaults to `default` if not set.
- For the normal workflow, `go.ps1` is the intended entry point. Use the lower-level CLIs when debugging or operating a specific slice.
