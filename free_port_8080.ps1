# Port 8080 (app_kickr) freimachen — beendet verwaiste Prozesse.
# Ausfuehrung vom Repo-Root: .\free_port_8080.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root "scripts\free_port_8080.py"
if (Test-Path $script) {
    Set-Location $root
    python $script
    Write-Host "Danach App neu starten: python -m app_kickr"
} else {
    Write-Host "free_port_8080.py nicht gefunden unter scripts/"
}
