# Publishing this project to GitHub

Everything is prepared: all code, `data/`, the paper PDF, `README.md`, `.gitignore`
(excludes `.venv/` and the reproducible `records/`), `requirements.txt`, and a verified
git commit. You just need to create the GitHub repo (that step needs your account) and push.

> First, delete the leftover broken git folder created during setup:
> in PowerShell, from this folder: `rd /s /q .git`  (or delete the hidden `.git` folder in Explorer)

## Option A — one command, if you have the GitHub CLI (`gh`)

```powershell
cd "D:\Claude\EWT test\Elliott wave theory RCT"
rd /s /q .git
git init -b main
git add .
git commit -m "Elliott Wave reliability study: engine, tester, weighers, data, paper"
gh repo create elliott-wave-rct --public --source . --push
```

## Option B — create the repo on the web, then push

1. Go to https://github.com/new, name it (e.g. `elliott-wave-rct`), **Public**, do **not** add a
   README/.gitignore/license (this repo already has them). Create.
2. Then:

```powershell
cd "D:\Claude\EWT test\Elliott wave theory RCT"
rd /s /q .git
git init -b main
git add .
git commit -m "Elliott Wave reliability study: engine, tester, weighers, data, paper"
git remote add origin https://github.com/<your-username>/elliott-wave-rct.git
git push -u origin main
```

## Option C — use the prepared bundle (keeps the ready-made commit)

`EWT_repo.bundle` is a portable, full-history copy of the repo. To publish from it:

```powershell
git clone "D:\Claude\EWT test\Elliott wave theory RCT\EWT_repo.bundle" elliott-wave-rct
cd elliott-wave-rct
git remote add origin https://github.com/<your-username>/elliott-wave-rct.git
git push -u origin main
```

## Updating it later (as we make more progress here)

From this folder on Windows, after we change files:

```powershell
git add -A
git commit -m "describe the change"
git push
```

The `.gitignore` keeps `.venv/` and `records/` out automatically, so `git add -A` is safe.
