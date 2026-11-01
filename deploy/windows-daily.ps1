# Daily stream refresh on ben@windows (scheduled task "usatv-daily", 06:00 local).
# Prunes dead streams, harvests and injects working ones, gates on the tests, then pushes main
# with the repository's deploy key. Log: C:\Users\ben\logs\usatv-daily.log
param([switch]$NoPush)  # -NoPush: commit locally only, for a supervised run
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
# FFmpeg 9 verifies TLS certificates and prunes streams that play (tests/test_tester_tls.py).
$env:PATH = "C:\Users\ben\tools\ffmpeg-8.1.2-full_build\bin;$env:PATH"
$repo = Split-Path -Parent $PSScriptRoot
$log = "C:\Users\ben\logs\usatv-daily.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$env:NO_COLOR = "1"
function Log($line) { Add-Content -Encoding utf8 $log $line }

function Step($name, [scriptblock]$cmd) {
    Log "== $(Get-Date -Format o) $name"
    & $cmd 2>&1 | ForEach-Object { "$_" } | Add-Content -Encoding utf8 $log
    if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
}

try {
    Set-Location $repo
    Step "pull" { git pull -q --ff-only origin main }
    Step "sync" { uv sync -q }
    Step "prune" { uv run python -m harvester prune }
    Step "harvest+inject" { uv run python -m harvester run --no-resume }
    Step "tests" { uv run python -m unittest discover -s tests }
    $changed = git status --porcelain -- catalog meta stream
    if (-not $changed) { Log "No stream changes"; return }
    Step "commit" { git add -- catalog meta stream; git commit -q -m "feat: daily refresh - prune dead and inject working streams" }
    if ($NoPush) { Log "Committed $(git rev-parse --short HEAD), not pushed"; return }
    Step "push" { git push -q origin HEAD:main }
    Log "Pushed $(git rev-parse --short HEAD)"
} catch {
    Log "FAILED: $_"
    throw
}
