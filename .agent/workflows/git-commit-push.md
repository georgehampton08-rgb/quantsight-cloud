---
description: How to commit and push changes to quantsight-cloud without hanging
---

# Git Commit + Push Workflow (quantsight-cloud)

## Root Cause Fixed

- WSL `git commit` in `/mnt/c/` paths was hanging due to Windows GCM (Git Credential Manager) interop
- Fix: SSH key `georgehampton08-wsl-quantsight` added to GitHub (Feb 24, 2026), remote switched to SSH in WSL

## Standard Workflow

### Step 1: Stage files (Windows git — fast, no hang)

```powershell
git -C "c:\Users\georg\quantsight_engine\quantsight_cloud_build" add <files...>
```

### Step 2: Commit (Windows git — fast, no hang)

```powershell
$env:GIT_TERMINAL_PROMPT = "0"
git -C "c:\Users\georg\quantsight_engine\quantsight_cloud_build" commit --no-verify -m "your message"
```

### Step 3: Push (WSL SSH — required, HTTPS would hang)

```powershell
wsl -d Ubuntu --exec bash -c "cd /mnt/c/Users/georg/quantsight_engine/quantsight_cloud_build && GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new' git push origin main 2>&1"
```

## If commit hangs

- Kill the process immediately
- Check: `Get-ChildItem "c:\Users\georg\quantsight_engine\quantsight_cloud_build\.git" -Filter "*.lock"` and delete any `.lock` files
- The staged changes are still safe — re-commit with Windows git (Step 2 above)

## SSH Key Info

- Key: `~/.ssh/id_ed25519` in WSL Ubuntu
- GitHub title: `georgehampton08-wsl-quantsight`
- Added: Feb 24, 2026
