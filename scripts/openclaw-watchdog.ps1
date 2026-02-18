<#
.SYNOPSIS
    OpenClaw watchdog — restarts gateway if it crashes. Runs forever.
    Used by the "OpenClaw Watchdog" Scheduled Task.
#>

$logFile = "$env:USERPROFILE\.openclaw\logs\watchdog.log"
New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $logFile -Append
}

Log "Watchdog started"

while ($true) {
    Log "Starting openclaw gateway..."
    try {
        $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"C:\Users\hharp\AppData\Roaming\npm\openclaw.cmd`" gateway" `
            -NoNewWindow -PassThru -RedirectStandardOutput "$env:USERPROFILE\.openclaw\logs\gateway-stdout.log" `
            -RedirectStandardError "$env:USERPROFILE\.openclaw\logs\gateway-stderr.log"
        $proc.WaitForExit()
        $exitCode = $proc.ExitCode
        Log "openclaw exited with code $exitCode"
    } catch {
        Log "ERROR: $_"
    }
    Log "Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
