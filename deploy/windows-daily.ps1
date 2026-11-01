# Daily stream refresh on ben@windows (scheduled task "usatv-daily", 06:00 local).
# Prunes dead streams, harvests and injects working ones, gates on the tests, then pushes main
# with the repository's deploy key. Log: C:\Users\ben\logs\usatv-daily.log
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$repo = Split-Path -Parent $PSScriptRoot
$log = "C:\Users\ben\logs\usatv-daily.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
Start-Transcript -Append -Path $log | Out-Null

function Step($name, [scriptblock]$cmd) {
    Write-Output "== $(Get-Date -Format o) $name"
    & $cmd
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
    if (-not $changed) { Write-Output "No stream changes"; return }
    Step "commit" { git add -- catalog meta stream; git commit -q -m "feat: daily refresh - prune dead and inject working streams" }
    Step "push" { git push -q origin HEAD:main }
    Write-Output "Pushed $(git rev-parse --short HEAD)"
} finally {
    Stop-Transcript | Out-Null
}
