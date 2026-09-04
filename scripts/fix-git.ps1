if (Test-Path ".git\index.lock") {
    Remove-Item ".git\index.lock" -Force
}

if (Test-Path ".git\index") {
    Remove-Item ".git\index" -Force
}

git reset
git status