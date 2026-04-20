# JobPipe Windows convenience wrapper.
# Canonical interface: `jobpipe run` (or `python -m jobpipe.cli.main run`).
# This script exists to keep one-shot operation convenient on Windows.

param(
    [switch]$DryRun,
    [switch]$NoOpen,
    [switch]$WithSuggestions
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = "$PSScriptRoot\.venv\Scripts\python.exe"

function Set-Utf8Runtime {
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $global:OutputEncoding = $utf8
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
}

function Import-DotEnv {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($raw in Get-Content -LiteralPath $Path) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        if (-not $key -or [Environment]::GetEnvironmentVariable($key, "Process")) {
            continue
        }

        $value = $parts[1].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

Set-Utf8Runtime
Import-DotEnv (Join-Path $PSScriptRoot ".env")

if (-not (Test-Path $py)) {
    Write-Error "Venv not found at $py - run: python -m venv .venv && python -m pip install -e ."
    exit 1
}

$env:OPENAI_AGENTS_DISABLE_TRACING = "1"

$cliArgs = @("-m", "jobpipe.cli.main", "run", "--env-file", (Join-Path $PSScriptRoot ".env"))
if ($DryRun) {
    $cliArgs += "--dry-run"
}
if ($NoOpen) {
    $cliArgs += "--no-open"
}
if ($WithSuggestions) {
    $cliArgs += "--with-suggestions"
}

& $py @cliArgs
exit $LASTEXITCODE
