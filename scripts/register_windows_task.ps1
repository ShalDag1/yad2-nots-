$ErrorActionPreference = "Stop"

$TaskName = "Yad2 Coffee Machines Scraper"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunnerScript = Join-Path $PSScriptRoot "run_scraper.ps1"

if (-not (Test-Path $RunnerScript)) {
    throw "Missing runner script: $RunnerScript"
}

$TaskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`""

schtasks.exe /Create `
    /TN $TaskName `
    /TR $TaskCommand `
    /SC MINUTE `
    /MO 15 `
    /ST 00:00 `
    /F | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Schedule: every 15 minutes. The runner skips outside 08:00 to 00:00 Israel time."
Write-Host "Logs: $(Join-Path $RepoRoot 'logs\scraper.log')"
