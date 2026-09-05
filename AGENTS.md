# Repository Git safety policy

- Only one human or agent may perform Git write operations in this working tree at a time.
- Agents may autonomously run standard development and Git inspection/working commands without asking: `git status`, `git diff`, `git log`, `git show`, `git branch`, `git add`, `git commit`, `git checkout`, `git switch`.
- Agents must ONLY ask for explicit confirmation before high-risk or destructive actions:
  - Deleting the whole project or critical project directories
  - `git reset --hard`
  - `git clean -f` / `git clean -fd`
  - Pushing code to remote (`git push`)
  - Modifying system-level configuration or deleting files under `.git`
- Before an authorized Git write, record `git status --short`, verify that `.git/index.lock` is absent, and verify that no other agent is performing Git work in this repository.
- Do not run `scripts/fix-git.ps1 -ForceRebuild` while VS Code source control, GitLens, Antigravity, Codex, or another Git client is writing to this repository.
