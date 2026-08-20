<#
.SYNOPSIS
  Fresh Windows machine -> working reels-scrap install, plus optional scheduled runs.

.DESCRIPTION
  Idempotent. Re-run it after pulling; it only does what is missing.

    .\scripts\setup-windows.ps1                 # install + verify
    .\scripts\setup-windows.ps1 -Schedule       # also register nightly sync + weekly discover
    .\scripts\setup-windows.ps1 -Autostart      # also start API + UI at logon

  What it does NOT do: export your Instagram cookies. That is a browser action and
  the resulting file is a live login — see docs/PRIVACY.md.
#>
[CmdletBinding()]
param(
    [switch]$Schedule,
    [switch]$Autostart,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$venv = Join-Path $repo ".venv-win"
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "repo: $repo" -ForegroundColor Cyan

# 1. python venv — .venv in this repo may be a Linux venv from another machine
if (-not (Test-Path $py)) {
    Write-Host "creating .venv-win…" -ForegroundColor Cyan
    & $Python -m venv $venv
}
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -e ".[docs,dev]"
Write-Host "python deps ok" -ForegroundColor Green

# 2. frontend
if (Test-Path (Join-Path $repo "web\package.json")) {
    Push-Location (Join-Path $repo "web")
    if (-not (Test-Path "node_modules\.bin\vite.cmd")) { npm install --silent }
    Pop-Location
    Write-Host "web deps ok" -ForegroundColor Green
}

# 3. git hooks — blocks cookies/media from ever being committed
git config core.hooksPath .githooks
Write-Host "pre-commit guard enabled" -ForegroundColor Green

# 4. local vision model (optional — skip silently when Ollama is absent)
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (Test-Path $ollama) {
    $models = & $ollama list
    if ($models -notmatch "reels-vision") {
        Write-Host "building reels-vision (downloads ~9GB the first time)…" -ForegroundColor Cyan
        & $ollama pull qwen2.5vl:7b-q8_0
        & $ollama create reels-vision -f scripts/ollama-vision.Modelfile
    }
    Write-Host "local vision model ok" -ForegroundColor Green
} else {
    Write-Host "Ollama not installed — local vision unavailable (winget install Ollama.Ollama)" -ForegroundColor Yellow
}

# 5. verify
& $py -m pytest tests -q -p no:warnings
if ($LASTEXITCODE -ne 0) { throw "tests failed — stopping before scheduling anything" }
Write-Host "tests pass" -ForegroundColor Green

if (-not (Test-Path (Join-Path $repo "cookies.txt"))) {
    Write-Host "NOTE: cookies.txt missing — sync cannot reach Instagram until you export it (docs/PRIVACY.md)" -ForegroundColor Yellow
}

# 6. scheduled tasks
function Register-ReelsTask($name, $trigger, $arguments, $desc) {
    $action = New-ScheduledTaskAction -Execute $py -Argument $arguments -WorkingDirectory $repo
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
        -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
        -Description $desc -Force | Out-Null
    Write-Host "scheduled: $name" -ForegroundColor Green
}

if ($Schedule) {
    # 03:00 nightly, matching the Linux box's reels-sync.timer
    Register-ReelsTask "reels-sync" (New-ScheduledTaskTrigger -Daily -At 3am) `
        "-m reels_scrap.cli sync -c config-local.yaml" "Nightly incremental reel sync (local GPU vision)"
    # discovery is read-heavy on Instagram — weekly, not nightly
    Register-ReelsTask "reels-discover" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am) `
        "-m reels_scrap.cli discover -c config.yaml --browser cookies.txt --max-requests 40" `
        "Weekly candidate discovery (request-budgeted)"
}

if ($Autostart) {
    Register-ReelsTask "reels-api" (New-ScheduledTaskTrigger -AtLogOn) `
        "-m reels_scrap.cli serve -c config.yaml --port 8000" "Reels research API on 127.0.0.1:8000"
    Write-Host "API will start at logon. UI: cd web; npm run dev" -ForegroundColor Green
}

Write-Host "`ndone." -ForegroundColor Cyan
Write-Host "  sync   : $py -m reels_scrap.cli sync -c config-local.yaml"
Write-Host "  serve  : $py -m reels_scrap.cli serve -c config.yaml --port 8000"
Write-Host "  health : curl http://127.0.0.1:8000/api/health?deep=true"
