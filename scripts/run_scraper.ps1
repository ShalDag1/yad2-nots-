$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir "scraper.log"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$Timestamp] $Message" -Encoding UTF8
}

try {
    $IsraelTimeZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("Israel Standard Time")
    $IsraelNow = [System.TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $IsraelTimeZone)
    $Hour = [int]$IsraelNow.ToString("HH")

    if ($Hour -lt 8 -or $Hour -ge 24) {
        Write-Log "Skipped outside Israel time window. Israel time: $($IsraelNow.ToString('yyyy-MM-dd HH:mm:ss'))"
        exit 0
    }

    if (-not (Test-Path $PythonExe)) {
        $PythonExe = "python"
    }

    Write-Log "Starting scraper. Israel time: $($IsraelNow.ToString('yyyy-MM-dd HH:mm:ss'))"
    Push-Location $RepoRoot
    try {
        & $PythonExe scraper.py 2>&1 | ForEach-Object {
            Add-Content -Path $LogFile -Value $_ -Encoding UTF8
        }
        $ExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($ExitCode -ne 0) {
        Write-Log "Scraper failed with exit code $ExitCode"
        exit $ExitCode
    }

    Write-Log "Scraper completed successfully"
}
catch {
    Write-Log "Task failed: $($_.Exception.Message)"
    exit 1
}
