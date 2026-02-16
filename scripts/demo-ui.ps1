<#
.SYNOPSIS
    Manage FactoryLM Demo UI on PLC laptop
.DESCRIPTION
    Start, stop, or check status of Demo UI remotely
.EXAMPLE
    .\demo-ui.ps1 start
    .\demo-ui.ps1 stop
    .\demo-ui.ps1 status
    .\demo-ui.ps1 open
#>

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status", "open", "help")]
    [string]$Command = "status"
)

$PLC_HOST = "100.72.2.99"
$DEMO_PORT = 8080
$DEMO_URL = "http://${PLC_HOST}:${DEMO_PORT}"
$MAGIC_DNS_URL = "http://laptop-0ka3c70h:${DEMO_PORT}"

function Show-Help {
    Write-Host ""
    Write-Host "FactoryLM Demo UI Manager" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start   - Start Demo UI on PLC laptop"
    Write-Host "  stop    - Stop Demo UI on PLC laptop"
    Write-Host "  status  - Check if Demo UI is running"
    Write-Host "  open    - Open Demo UI in browser"
    Write-Host "  help    - Show this message"
    Write-Host ""
    Write-Host "URLs:"
    Write-Host "  MagicDNS:  $MAGIC_DNS_URL" -ForegroundColor Green
    Write-Host "  Direct:    $DEMO_URL" -ForegroundColor Green
    Write-Host ""
}

function Start-DemoUI {
    Write-Host "Starting Demo UI on PLC laptop..." -ForegroundColor Yellow
    ssh hharp@$PLC_HOST "cd 'C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\matrix'; Start-Process python -ArgumentList 'demo_ui.py'"
    Start-Sleep -Seconds 3
    Get-Status
}

function Stop-DemoUI {
    Write-Host "Stopping Demo UI on PLC laptop..." -ForegroundColor Yellow
    ssh hharp@$PLC_HOST "Get-Process python -ErrorAction SilentlyContinue | Where-Object { `$_.Path -and (Get-Process -Id `$_.Id).CommandLine -like '*demo_ui*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
    Write-Host "[OK] Demo UI stopped" -ForegroundColor Green
}

function Get-Status {
    Write-Host "Checking Demo UI status..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "$DEMO_URL/health" -TimeoutSec 5
        Write-Host ""
        Write-Host "[ONLINE] Demo UI is running" -ForegroundColor Green
        Write-Host "  Service:    $($response.service)"
        Write-Host "  Matrix API: $($response.matrix_api)"
        Write-Host "  NVIDIA API: $($response.nvidia_api)"
        Write-Host ""
        Write-Host "Access URLs:" -ForegroundColor Cyan
        Write-Host "  $MAGIC_DNS_URL" -ForegroundColor White
        Write-Host "  $DEMO_URL" -ForegroundColor White
    } catch {
        Write-Host ""
        Write-Host "[OFFLINE] Demo UI is not running" -ForegroundColor Red
        Write-Host "Run: .\demo-ui.ps1 start" -ForegroundColor Yellow
    }
}

function Open-DemoUI {
    Write-Host "Opening Demo UI in browser..." -ForegroundColor Yellow
    Start-Process $MAGIC_DNS_URL
}

switch ($Command) {
    "start"  { Start-DemoUI }
    "stop"   { Stop-DemoUI }
    "status" { Get-Status }
    "open"   { Open-DemoUI }
    "help"   { Show-Help }
    default  { Get-Status }
}
