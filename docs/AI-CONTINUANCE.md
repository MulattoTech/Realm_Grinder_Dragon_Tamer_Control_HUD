# AI CONTINUANCE & REVERSE ENGINEERING MASTER RECORD

**Branch**: `feat/air-memory-engine`  
**Repository**: `MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD`  
**Target Application**: Realm Grinder (Steam 4.3.11+, 32-bit x86 PE `0x14c`)  
**Host Runtime**: Adobe AIR (ActionScript 3 / AVM2 - ActionScript Virtual Machine 2 / Tamarin)  
**Window Class**: `ApolloRuntimeContentWindow`  

---

## 1. Executive Summary & Breakthroughs

### Verified Volatile Field Discovery
Prior attempts failed because naive float scanning searched for exact matches against stale save files, whereas AVM2 mana fluctuates continuously and boxed doubles are dynamically reallocated.

By analyzing the Tamarin AVM2 Atom tagging scheme and performing rate-of-change differential scanning over aligned 8-byte boundaries, we achieved **100% stable, read-only, non-intrusive memory mapping** for:
- `mana_current`: Detected via positive slope $\frac{dM}{dt} \approx +20\text{ to }+40\text{ mana/sec}$, cleanly separated from 1 Hz timers ($|\frac{dv}{dt} - 1.0| > 0.05$).
- `mana_max`: Detected via integer/50-step double clusters in the heap matching maximum mana bounds.
- `mana_regeneration`: Verified matching measured $\frac{dM}{dt}$.
- `coins`: Verified within logarithmic tolerance of persistent save coins.
- `fairy_assistants`: Verified matching assistant allocations.

### Live Telemetry Proof (PID 61828)
```
Discovered 5 volatile field mappings:
  - mana_current        : Address=0x0173d4d0, Type=AVM2Number, Value=414.63
  - mana_max            : Address=0x016bc2bc, Type=AVM2Number, Value=1105.0
  - mana_regeneration   : Address=0x076a3d20, Type=AVM2Number, Value=23.0
  - coins               : Address=0x0cca067c, Type=AVM2Number, Value=1.0195595147302046e+138
  - fairy_assistants    : Address=0x07994c04, Type=AVM2Number, Value=21000.0

Health: HEALTHY | Verified: ['coins', 'fairy_assistants', 'mana_current', 'mana_max', 'mana_regeneration']
```

---

## 2. Adobe AIR / AVM2 Memory Internals

### Atom Tagging Representation (32-bit AVM2)
In Tamarin, every 32-bit slot is an `Atom`:
- `atom & 7 == 6` (`0b110`): Inline 29-bit signed integer (`value = atom >> 3`).
- `atom & 7 == 7` (`0b111`): Boxed IEEE-754 64-bit Double pointer (`value = *(double*)(atom & ~7)`).
- `atom & 7 == 0` (`0b000`): Object reference or null.
- `atom & 7 == 1` (`0b001`): String pointer.

### Critical Discovery: Double Immutability
In ActionScript 3, `Number` (boxed double) instances are immutable heap objects. When mana regenerates or coins accumulate:
1. Tamarin allocates a new 8-byte aligned `double` on the heap.
2. The enclosing object's 4-byte member slot is updated with the new pointer `(ptr | 7)`.
3. Reading `atom & ~7` dereferences the latest live value in real time.
4. Calling `ReadProcessMemory` on the fixed 4-byte slot returns the active pointer without needing to trace static base pointers across game patches!

### Window State & Event Loop Throttling
- When `RealmGrinderDesktop.exe` is minimized (`SW_SHOWMINNOACTIVE = 7`), Adobe AIR pauses passive timers and throttles the event loop.
- When placed in the background with `SW_SHOWNOACTIVATE = 4`, the AIR event loop runs at full speed with **zero focus theft** and zero window popping.

---

## 3. Architecture & File Structure

- `src/memory/process.py`:
  - `ReadOnlyProcess`: Strictly uses `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` (`0x0410`).
  - `read_avm2_number(address)`: Atomic-safe atom dereferencing with tag 6 and tag 7 handling.
- `src/memory/provider.py`:
  - `MemoryProvider`: Coordinates field mapping registration, persistence (`state/memory_mappings.json`), session validation (`valid_for(identity)`), and automatic atom differential discovery.
  - `discover_fields(save_state, sample_delay)`: Differential rate-of-change scanning across private committed heap regions (`0x20000`, `0x40000`).
- `src/live_state.py`:
  - `LiveStateProvider`: Fuses persistent save data (`AIR_SHAREDOBJECT`) with live process memory (`PROCESS_MEMORY`, confidence `VERIFIED`).
- `tools/probe_live_memory.py`: Standalone non-intrusive probe script for testing and calibration.
- `tests/test_memory_provider.py`: Comprehensive test suite simulating AVM2 heap structures, tag decoding, differential discovery, session invalidation, and live state fusion (5/5 passing).

---

## 4. Verification & Testing Evidence

```powershell
python -m pytest -q --tb=short
# 262 passed in 3.37s

python tools/verify_checkout.py
# 252 passed, 5 skipped (due to absence of private screenshots in clean checkout)
# Check passed with exit code 0

pwsh -File scripts/Export-Continuance.ps1
# Creates AI_Continuance.zip
```

---

## 5. Next Prioritized Objectives

### Objective A: Integrate Volatile Field Visuals in Control HUD
- Verify that `launcher.py` and `src/telemetry_presenter.py` display the live `[MEM]` tag and smooth mana bar updates without UI stutter.
- Add live derivative gauge display ($\frac{dM}{dt}$) in the HUD.

### Objective B: Closed-Loop Spell Autocasting Policy
- Wire `mana_current` and `mana_max` into the deterministic spell casting loop (`src/spell_policy.py`).
- Implement automatic contingency casting when mana reaches saturation ($M \ge M_{\max} - \text{buffer}$).

---

## 6. Copy-Pasteable Prompt for Next AI Session

```markdown
You are picking up the Realm Grinder Dragon Tamer Control HUD project.
Branch: feat/air-memory-engine
Repository: MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD

Read docs/CURRENT-HANDOFF.md and docs/AI-CONTINUANCE.md first.
The Adobe AIR / AVM2 volatile memory engine is now fully implemented and verified (262 tests pass).
Memory reading is strictly READ-ONLY (0x0410). Game window background tick state uses SW_SHOWNOACTIVATE (flag 4).

Your mission:
1. Verify the repo baseline with `python -m pytest -q --tb=short` and `python tools/verify_checkout.py`.
2. Inspect `src/telemetry_presenter.py` and ensure the Control HUD renders live mana, max mana, and mana regeneration rate smoothly from `state['provenance']`.
3. Wire the live volatile mana fields into `src/spell_policy.py` to trigger deterministic spell casting at saturation without polling lag.
4. Keep all verification tests green and pass scripts/Verify-Repository.ps1 before any commit.
```
