$folders = @('Desktop','Downloads','Videos','Pictures','Documents','.claude','AppData')
foreach ($f in $folders) {
    $p = "C:\Users\hharp\$f"
    if (Test-Path $p) {
        $size = (Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $gb = [math]::Round($size/1GB,1)
        Write-Output "$gb GB  $f"
    }
}
