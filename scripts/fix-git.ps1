[CmdletBinding()]
param(
    [switch]$ForceRebuild
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed (exit $LASTEXITCODE): git $($args -join ' ')"
    }
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw "Run this script inside the Git working tree."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
Set-Location -LiteralPath $repoRoot

$gitDirText = (& git rev-parse --git-dir)
if ($LASTEXITCODE -ne 0 -or -not $gitDirText) {
    throw "Unable to resolve the Git directory."
}

$gitDir = if ([System.IO.Path]::IsPathRooted($gitDirText)) {
    (Resolve-Path -LiteralPath $gitDirText).Path
} else {
    (Resolve-Path -LiteralPath (Join-Path $repoRoot $gitDirText)).Path
}

$indexPath = Join-Path $gitDir "index"
$lockPath = Join-Path $gitDir "index.lock"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (Test-Path -LiteralPath $lockPath) {
    $lock = Get-Item -LiteralPath $lockPath -Force
    throw @"
Found $lockPath (last written $($lock.LastWriteTime.ToString('o'))).
This script will not delete a lock automatically because it may belong to a live Git process.
Close VS Code/agents, verify that no git.exe process is running, then archive the stale lock manually.
"@
}

$indexHealthy = $false
if (Test-Path -LiteralPath $indexPath) {
    & git ls-files --stage *> $null
    $indexHealthy = ($LASTEXITCODE -eq 0)
}

if ($indexHealthy -and -not $ForceRebuild) {
    Write-Output "Git index is healthy; no rebuild was performed."
    Invoke-Git status --short
    exit 0
}

if (Test-Path -LiteralPath $indexPath) {
    $indexBackup = Join-Path $gitDir "index.before-repair-$stamp"
    Copy-Item -LiteralPath $indexPath -Destination $indexBackup -Force
    Write-Output "Index backup: $indexBackup"

    if ($indexHealthy) {
        $stagedPatch = Join-Path $gitDir "index-staged-$stamp.patch"
        & git diff --cached --binary --output=$stagedPatch
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to back up staged changes; index rebuild aborted."
        }
        if ((Get-Item -LiteralPath $stagedPatch).Length -eq 0) {
            Remove-Item -LiteralPath $stagedPatch -Force
        } else {
            Write-Output "Staged-change backup: $stagedPatch"
        }
    }

    Move-Item -LiteralPath $indexPath -Destination (Join-Path $gitDir "index.quarantined-$stamp")
}

# Rebuild only the index from HEAD. This command does not update working-tree files.
Invoke-Git read-tree HEAD
Invoke-Git status --short
Invoke-Git fsck --full

Write-Output "Index rebuilt safely. Working-tree files were not reset or deleted."