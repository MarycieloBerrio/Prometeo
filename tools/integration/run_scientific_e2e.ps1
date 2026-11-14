# Run curated NASA BASS-II scientific E2E battery (Yulian).
# Usage from repo root:  pwsh tools/integration/run_scientific_e2e.ps1

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location (Join-Path $root "apps\backend")

Write-Host "== prometeo validate-data =="
uv run prometeo validate-data

Write-Host "== pytest tests/integration =="
uv run pytest tests/integration -q

Write-Host "OK: scientific E2E battery finished."
