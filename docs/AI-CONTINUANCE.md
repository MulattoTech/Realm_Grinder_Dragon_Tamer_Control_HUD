# AI Continuance Master Handoff

**Target Audience**: Any AI Agent (Claude Sonnet/Opus, Google Gemini, OpenAI GPT, DeepSeek, etc.) resuming work on this repository.

---

## 1. Quick Orientation

- **Repository**: `MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD` (Windows-native Realm Grinder automation).
- **Primary Game**: Steam version of Realm Grinder 4.3.11+ (`C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder\RealmGrinderDesktop.exe`).
- **Engine**: Adobe AIR / ActionScript 3 (AVM2 - 32-bit x86).
- **UI Framework**: Python Tkinter / Win32 Control HUD (`launcher.py`).
- **Safety Standard**: **READ-ONLY MEMORY**. No DLL injection, no memory writing, no save editing, no Steam achievement API calls.

---

## 2. Environment Bootstrap (Clean Machine / Fresh Clone)

To rebuild and verify everything from scratch:

```powershell
# 1. Clone repository
git clone https://github.com/MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD.git
cd Realm_Grinder_Dragon_Tamer_Control_HUD

# 2. Setup virtual environment (Python 3.12 64-bit on Windows)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

# 3. Bootstrap configuration and assets
python tools/bootstrap.py

# 4. Verify baseline tests
python -m pytest -q --tb=short
python tools/verify_checkout.py
scripts\Verify-Repository.ps1

# 5. Launch HUD
python launcher.py
```

---

## 3. Work In Progress & Active Focus: Volatile Memory Engine

- **Architecture**:
  - `src/memory/process.py`: `ReadOnlyProcess` opens the target with `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` (`0x0410`). Includes `read_avm2_number` for tagged 32-bit AVM2 Atoms (tag 6 = inline 29-bit int, tag 7 = boxed double).
  - `src/memory/scanner.py`: `BoundedScanner` for chunked, time/memory-bounded exact and differential scans.
  - `src/memory/calibration.py`: `validate_mana_trace` for verifying controlled spell-cast drops and linear regeneration.
  - `src/memory/provider.py`: `MemoryProvider` session manager and mapping cache (`memory_mappings.json`).
  - `src/live_state.py`: Combines `.sol` save data with `PROCESS_MEMORY` observations.

- **Current Task**:
  - Implement stable live mapping for volatile properties: `mana_current`, `mana_max`, `mana_regeneration`, `coins`, and `fairy_assistants`.
  - Strategy: Use stable anchor discovery (e.g. `mana_max` or gem count) to resolve the player state object, followed by relative slot offset mapping, or controlled spell-cast calibration.

---

## 4. How to Continue Development

1. Check current git status: `git status`, `git branch`, `git log -5 --oneline`.
2. Read `docs/CURRENT-HANDOFF.md` and `docs/CLAUDE-HANDOFF.md`.
3. If this handoff was unpacked from `AI_Continuance.zip`:
   - Inspect `git_uncommitted.patch` if present.
   - You can fetch from `continuance.bundle` or pull the latest branch from GitHub.
4. Run tests before and after making changes:
   ```powershell
   python -m pytest -q --tb=short
   scripts\Verify-Repository.ps1
   ```
5. When completing your session or approaching rate limits, run:
   ```powershell
   .\scripts\Export-Continuance.ps1
   ```
