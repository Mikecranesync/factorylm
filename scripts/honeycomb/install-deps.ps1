# install-deps.ps1 — Install OpenTelemetry npm packages globally (Windows)
# Usage: .\install-deps.ps1

$ErrorActionPreference = "Stop"

$packages = @(
    "@opentelemetry/sdk-node"
    "@opentelemetry/auto-instrumentations-node"
    "@opentelemetry/exporter-trace-otlp-http"
    "@opentelemetry/resources"
    "@opentelemetry/semantic-conventions"
)

Write-Host "=== Installing OpenTelemetry packages globally ===" -ForegroundColor Cyan
Write-Host ""

foreach ($pkg in $packages) {
    Write-Host "-> npm install -g $pkg" -ForegroundColor Yellow
    npm install -g $pkg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install $pkg" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "=== Installed packages ===" -ForegroundColor Cyan
foreach ($pkg in $packages) {
    npm ls -g $pkg --depth=0 2>$null | Select-String $pkg | ForEach-Object { Write-Host "  $_" }
}

Write-Host ""
Write-Host "Done. All OTel dependencies installed globally." -ForegroundColor Green
