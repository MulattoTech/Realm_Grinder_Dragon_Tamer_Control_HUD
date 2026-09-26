# Repository-first workflow

GitHub is canonical. A workstation folder is disposable.

## Start on a new machine
1. Download the newest GitHub Release or clone the repository.
2. Open PowerShell in the extracted/checked-out folder.
3. Run `./Install.ps1 -Dev`.
4. Run `./scripts/Verify-Repository.ps1`.
5. Launch from the logged-on Windows desktop with `.\.venv\Scripts\python.exe launcher.py`.

Runtime state is intentionally not portable source. The ignored `state/`, `backups/`, `logs/`, `screenshots/`, `scratch/`, `scraped_wiki/`, and generated `assets/templates/` directories must never be used as hidden build inputs.

## Development
Before editing:
```powershell
git fetch origin --prune
git status
git branch -vv
```

Create a branch, make bounded changes, and run:
```powershell
.\scripts\Verify-Repository.ps1 -AllowDirty
```
Commit intended files, rerun without `-AllowDirty`, then push.
## Release
The release artifact is produced only from committed Git content:
```powershell
.\scripts\Verify-Repository.ps1
.\scripts\Build-Release.ps1
```

The build script writes a ZIP plus SHA-256 manifest under ignored `dist/`.
Publish those files to a GitHub Release whose tag matches `VERSION`.

A release must not include private saves, logs, screenshots, runtime configuration, credentials, or generated local icon caches.

## GitHub Actions
An inactive Windows test workflow remains at `docs/ci/windows-tests.yml.example`.
The currently configured Git credential has repository access but not the separate workflow scope required to install a workflow file. Do not treat missing CI as a test bypass; local/clean-checkout verification remains mandatory until an authorized workflow is installed.
