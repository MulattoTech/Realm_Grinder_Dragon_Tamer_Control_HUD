# CLAUDE.md - Realm Grinder Dragon Tamer Control HUD

This file provides primary guidance for Claude Code and Anthropic models working in this repository.

---

## 1. Project Overview & Architecture
- **Application**: Windows-native automation and progression engine for Steam Realm Grinder (v4.3.11+).
- **Executable**: `C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder\RealmGrinderDesktop.exe`
- **Target Process**: 32-bit x86 PE (`IMAGE_FILE_MACHINE_I386` / `0x14c`).
- **Engine**: Adobe AIR / ActionScript 3 (AVM2 - ActionScript Virtual Machine 2).
- **Save File**: `%APPDATA%\com.kongregate.mobile.realmgrinder.air\Local Store\#SharedObjects\RealmGrinderDesktop.swf\realm-grinder.sol`.
- **Primary Mission**: Read `docs/PROMPT-SONNET-MEMORY-ENGINE.md` for full implementation roadmap.

---

## 2. Developer Commands & Workflow
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run full test suite
python -m pytest -q --tb=short -p no:cacheprovider

# Run clean-checkout verification (tests committed HEAD in isolated temp dir)
python tools\verify_checkout.py

# Full repository verification gate (must pass before commits are promoted)
powershell -ExecutionPolicy Bypass -File scripts\Verify-Repository.ps1

# Export AI Continuance package (when approaching session/message limits)
powershell -ExecutionPolicy Bypass -File scripts\Export-Continuance.ps1

# Launch Control HUD
python launcher.py
```

---

## 3. Non-Negotiable Safety Contract (AGENTS.md)
1. **READ-ONLY MEMORY OPERATIONS**:
   - Access rights must strictly be `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` (`0x0410`).
   - NEVER call `WriteProcessMemory`, `VirtualProtectEx`, `CreateRemoteThread`, inject DLLs, or patch memory.
   - Never write to or synthesize Realm Grinder save files to advance progression.
   - Never invoke Steam achievement APIs.
2. **PRESERVE THE PRODUCT**:
   - Improve the existing Gemini-built Tkinter/Win32 Control HUD in place (`launcher.py`, `src/monitor_window.py`).
   - One worker/action owner only; never create competing automation loops.
3. **FAIL-CLOSED VERIFICATION**:
   - Every consequential action requires semantic verification and post-action state proof.
   - All tests must pass cleanly.

---

## 4. Memory Engineering Guidance (Adobe AIR / AVM2)
- **Tagged Atoms**: In 32-bit AVM2, pointers and numbers are 4-byte Atoms.
  - Tag 6 (`atom & 7 == 6`): 29-bit signed integer (`atom >> 3`).
  - Tag 7 (`atom & 7 == 7`): Pointer to boxed IEEE-754 64-bit double (`val & ~7`).
  - See `src/memory/process.py` (`read_avm2_number`).
- **Heap Layout**: In ActionScript 3, core game stats (`mana`, `maxMana`, `manaRegen`, `coins`, `gems`, `assistants`) are member properties of the central game/save controller object.
- **Discovery Strategy**:
  - Scan for stable anchors (`mana_max`, `reincarnation`, `gems`).
  - Trace enclosing object pointers to identify fixed property slot offsets for volatile fields (`mana_current`, `mana_max`, `mana_regeneration`, `coins`, `fairy_assistants`).
  - Or use controlled spell-cast calibration (`src/memory/calibration.py`).

---

## 5. Session Limit Protocol (AI Continuance)
If approaching rate limits or context boundaries:
1. Update `docs/AI-CONTINUANCE.md` and `docs/CURRENT-HANDOFF.md`.
2. Run `powershell -ExecutionPolicy Bypass -File scripts\Export-Continuance.ps1` to produce `AI_Continuance.zip`.
