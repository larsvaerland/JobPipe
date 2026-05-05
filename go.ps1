# JobPipe - one-shot runner
# Usage: .\go.ps1
# Options:
#   .\go.ps1 -DryRun             2 jobs only, no browser (test mode)
#   .\go.ps1 -NoOpen             full run, skip auto-opening browser
#   .\go.ps1 -WithSuggestions    scan Gmail for suggestions + fetch queued FINN jobs
#                                + scrape FINN search by keyword (all daytime only, 09-19 Oslo)
#   .\go.ps1 -ConfigOverlay <path>  apply one or more private overlay YAML files

param(
    [switch]$DryRun,
    [switch]$NoOpen,
    [switch]$WithSuggestions,
    [string[]]$ConfigOverlay,
    [switch]$Serve        # Start local dashboard server (direct status updates, notes, generation)
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot          # ensure CWD = project root (editable install needs this)
$py = "$PSScriptRoot\.venv\Scripts\python.exe"
$dataRoot = if ($env:JOBPIPE_DATA_ROOT) { $env:JOBPIPE_DATA_ROOT } else { Join-Path $HOME "JobpipeData" }
$dashboardPath = Join-Path $dataRoot "exports\dashboard.html"

if (-not (Test-Path $py)) {
    Write-Error "Venv not found at $py - run: python -m venv .venv && .venv\Scripts\pip install -e ."
    exit 1
}

$env:OPENAI_AGENTS_DISABLE_TRACING = "1"
$maxJobs = if ($DryRun) { 2 } else { 100 }
$overlayArgs = @()
if ($ConfigOverlay) {
    foreach ($overlay in $ConfigOverlay) {
        if ($overlay) {
            $overlayArgs += @("--config-overlay", $overlay)
        }
    }
}

Write-Host ""
Write-Host "=== JobPipe ===" -ForegroundColor Cyan
Write-Host "Data root: $dataRoot"
if ($DryRun) {
    Write-Host "Mode: DRY RUN (max 2 jobs)"
} else {
    Write-Host "Mode: FULL RUN (max 100 jobs)"
}
if ($WithSuggestions) {
    Write-Host "Suggestions: ON (FINN/LinkedIn email scan + fetch)"
}
if ($overlayArgs.Count -gt 0) {
    Write-Host "Config overlays: $($ConfigOverlay -join ', ')"
}
if ($Serve) {
    Write-Host "Dashboard server: ON (http://localhost:5100)"
}
Write-Host ""

# -Serve: start local dashboard server only (no pipeline run)
if ($Serve) {
    Write-Host "Starting dashboard server on http://localhost:5100..." -ForegroundColor Cyan
    Write-Host "(Press Ctrl+C to stop)"
    & $py -m jobpipe.cli.dashboard_server `
        @overlayArgs
    exit 0
}

Write-Host "Running canonical scheduled flow..." -ForegroundColor Yellow

$runArgs = @(
    "-m", "jobpipe.cli.run_scheduled_flow",
    "--data-root", $dataRoot,
    "--max-jobs", $maxJobs
)
if ($WithSuggestions) {
    $runArgs += "--with-suggestions"
}
$runArgs += $overlayArgs

& $py @runArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "run_scheduled_flow failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host ""
Write-Host "Tips:" -ForegroundColor DarkGray
Write-Host "  .\go.ps1 -Serve   # Start live server (localhost:5100) for direct status updates + notes" -ForegroundColor DarkGray
Write-Host "  Dashboard export: $dashboardPath" -ForegroundColor DarkGray
Write-Host ""

if (-not $NoOpen -and -not $DryRun) {
    Write-Host "Opening dashboard..." -ForegroundColor Cyan
    Start-Process $dashboardPath
}
