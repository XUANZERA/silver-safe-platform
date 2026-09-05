[CmdletBinding()]
param(
    [switch]$ForceRebuild,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

# 1. 自动定位仓库根目录（支持从任意目录运行或资源管理器双击）
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
$candidateRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

if (Test-Path (Join-Path $candidateRoot ".git")) {
    Set-Location -LiteralPath $candidateRoot
}

function Invoke-Git {
    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw ("Git command failed with exit code " + $LASTEXITCODE + ": git " + ($args -join " "))
    }
}

try {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
        throw ("Not inside a Git repository: " + (Get-Location).Path)
    }

    $repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
    Set-Location -LiteralPath $repoRoot

    $gitDirText = (& git rev-parse --git-dir)
    if ($LASTEXITCODE -ne 0 -or -not $gitDirText) {
        throw "Unable to resolve .git directory."
    }

    $gitDir = if ([System.IO.Path]::IsPathRooted($gitDirText)) {
        (Resolve-Path -LiteralPath $gitDirText).Path
    } else {
        (Resolve-Path -LiteralPath (Join-Path $repoRoot $gitDirText)).Path
    }

    $indexPath = Join-Path $gitDir "index"
    $lockPath = Join-Path $gitDir "index.lock"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"

    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Git Repository Health & Repair Tool" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ("Repo root: " + $repoRoot) -ForegroundColor Gray

    # Check stale lock
    if (Test-Path -LiteralPath $lockPath) {
        $lock = Get-Item -LiteralPath $lockPath -Force
        $runningGit = Get-Process -Name git -ErrorAction SilentlyContinue
        if ($runningGit) {
            Write-Host ("[WARN] Live git.exe process detected (PID: " + ($runningGit.Id -join ", ") + ").") -ForegroundColor Yellow
            Write-Host "Please close VS Code / terminal running Git and retry." -ForegroundColor Yellow
            exit 1
        } else {
            Write-Host ("[WARN] Stale index.lock found (timestamp: " + $lock.LastWriteTime + ")") -ForegroundColor Yellow
            Remove-Item -LiteralPath $lockPath -Force
            Write-Host "[OK] Removed stale index.lock." -ForegroundColor Green
        }
    }

    # Check index health
    $indexHealthy = $false
    if (Test-Path -LiteralPath $indexPath) {
        & git ls-files --stage *> $null
        $indexHealthy = ($LASTEXITCODE -eq 0)
    }

    if ($indexHealthy -and -not $ForceRebuild) {
        Write-Host "[PASS] Git index is 100% HEALTHY; no rebuild needed." -ForegroundColor Green
        Write-Host ""
        Write-Host "Current Working Tree Status:" -ForegroundColor Gray
        & git --no-optional-locks status --short
        Write-Host ""
        Write-Host "[INFO] Your repository is in good shape. You do not need to repeatedly run this script." -ForegroundColor Green
    } else {
        Write-Host "[ACTION] Safely rebuilding Git index (git read-tree HEAD)..." -ForegroundColor Yellow

        if (Test-Path -LiteralPath $indexPath) {
            $indexBackup = Join-Path $gitDir ("index.before-repair-" + $stamp)
            Copy-Item -LiteralPath $indexPath -Destination $indexBackup -Force
            Write-Host ("Backup created: " + $indexBackup) -ForegroundColor Gray

            Move-Item -LiteralPath $indexPath -Destination (Join-Path $gitDir ("index.quarantined-" + $stamp))
        }

        # Rebuild index from HEAD without touching working tree files
        Invoke-Git read-tree HEAD
        Write-Host "[OK] Index rebuilt successfully from HEAD. Working files were NOT modified!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Current Working Tree Status:" -ForegroundColor Gray
        & git --no-optional-locks status --short
    }
} catch {
    Write-Host ("[ERROR] Failed: " + $_.Exception.Message) -ForegroundColor Red
} finally {
    if (-not $NonInteractive -and ($Host.Name -eq "ConsoleHost")) {
        Write-Host ""
        Write-Host "Press Enter to exit..." -ForegroundColor Gray
        [void][System.Console]::ReadLine()
    }
}
