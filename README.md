# Realm Grinder — Dragon Tamer Autonomous Bot

An autonomous Windows-native desktop automation system engineered to progress your live Steam instance of **Realm Grinder** to unlock the **Dragon Tamer** achievement and trophy through legitimate game UI interaction and save state monitoring.

---

## Architecture & Design

1. **Non-Invasive Game Connection (`src/window.py`)**
   - Connects directly to the live Adobe AIR window (`ApolloRuntimeContentWindow`, `RealmGrinderDesktop.exe`).
   - Uses thread-isolated attachment to `WinSta0\default` to guarantee reliable Win32 window messaging, window enumeration, coordinate mapping, and screenshot capture from any shell/CLI environment.
   - Sizing normalized to client dimensions (1280x752).

2. **Read-Only Save State Engine (`src/save_reader.py`)**
   - Directly inspects and decodes the local Adobe AIR `.sol` SharedObject in read-only mode using dox4242's MIT-licensed `savecodec2.js` and `pako.js`.
   - Never writes or injects save data into the game.
   - Creates immutable timestamped exports in `backups/realm-grinder-export-YYYYMMDD-HHMMSS.txt`.

3. **State Machine Orchestrator (`src/state_machine.py`)**
   - Persists execution state to `state/dragon_tamer_state.json`.
   - Manages the progression stages:
     - `REACH_R46`: Progressive gem accumulation and upgrades toward R46.
     - `ACQUIRE_EGG`: Unlocks Spiky Rough Egg at R46+ with 1500+ excavations (2% drop chance).
     - `WAIT_HATCH`: 12-hour real-time countdown.
     - `BUY_HATCH`: Purchases Hatch! when eligible.
     - `ACCUMULATE_HELLFIRE`: Maintains and monitors 12 hours of active Hellfire Blast.
     - `BUY_DRAKELING`: Purchases Drakeling when eligible.
     - `WAIT_DRAGON`: 12-hour real-time countdown.
     - `BUILD_FAIRY_ASSISTANTS`: Configures Fairy build to reach >= 3,750 assistants.
     - `BUY_DRAGON`: Purchases Dragon when eligible.
     - `WAIT_ELDER`: 12-hour real-time countdown.
     - `BUILD_MAX_MANA`: Reaches >= 50,000 max mana.
     - `BUY_ELDER_DRAGON`: Purchases Elder Dragon and unlocks Dragon Tamer.

---

## Operating Instructions

### Check Live Status
```powershell
.\status.ps1
```

### Stop the Bot (Panic / Emergency Stop)
```powershell
.\stop.ps1
```
*Note: This safely terminates the background worker process without affecting the running Realm Grinder game instance or Steam.*

### Start the Bot
```powershell
.\start.ps1
```

---

## Licenses & Third-Party Credits
See [`THIRD_PARTY.md`](file:///C:/Tools/Dev/RealmGrinder/THIRD_PARTY.md) for full licensing details and notices.
