# Optional repository installation. A standalone extracted copy already runs.
param([Parameter(Mandatory=$true)][string]$Repository)
$ErrorActionPreference = 'Stop'
$RepoPath = (Resolve-Path -LiteralPath $Repository).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoPath '.git'))) {
    throw 'Choose the root of your existing Git repository.'
}
$Branch = & git -C $RepoPath branch --show-current
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the repository branch.' }
if ($Branch -ne 'MapUI') {
    throw 'This optional installer requires the MapUI branch. Review local work before switching.'
}
$Remote = & git -C $RepoPath remote get-url origin
if ($LASTEXITCODE -ne 0 -or $Remote -notmatch '[:/]ckoranec/devops-TheRobotProject(\.git)?$') {
    throw 'Origin must be ckoranec/devops-TheRobotProject.'
}
$Destination = Join-Path $RepoPath 'MAXX_MapUI_Live_Kit'
if (Test-Path -LiteralPath $Destination) {
    throw 'Destination exists. Preserve and compare it; nothing has been overwritten.'
}
# Copy only into a NEW folder. Never modify team map/backend files or run Git writes.
New-Item -ItemType Directory -Path $Destination | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object {
    $_.Name -notin @('__pycache__', '.venv', '.idea', 'runtime')
} | Copy-Item -Destination $Destination -Recurse
Write-Host "Added demo kit to: $Destination"
Write-Host 'Run server.py from that folder. No commit, push, merge or deployment was performed.'
