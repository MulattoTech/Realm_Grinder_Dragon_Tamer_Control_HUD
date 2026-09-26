# MASTER DIRECTIVE FOR CLAUDE 3.7 / SONNET 4.6 (THINKING): FULL AUTONOMOUS GOAL PIPELINE & CONTROL HUD COMPLETION

```markdown
You are acting as the Lead Systems Architect and Autonomous Game Engine Engineer for the **Realm Grinder Dragon Tamer Control HUD** project.
Your mission is to complete the autonomous pipeline so that clicking a single **"⚡ Automate Straight to Goal"** button in the Control HUD executes complete end-to-end progression—applying the most optimal templates in-game, automatically kickstarting production after abdications and reincarnations, casting spells via live memory saturation triggers, and advancing straight to the target goal (e.g., Reach R46 / Dragon Tamer).

---

### MISSION CONTEXT & SYSTEM BASELINE

1. **Target Game**: Realm Grinder (Steam version 4.3.11+, 32-bit x86 PE `0x14c`).
   - Binary: `C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder\RealmGrinderDesktop.exe`
   - Engine: Adobe AIR (Tamarin AVM2 / ActionScript 3).
   - Window Class: `ApolloRuntimeContentWindow`.
2. **Current Verified Baseline (Commit `a71c982` on `feat/air-memory-engine`)**:
   - **Full test suite**: 262 passed in 3.3s (`python -m pytest`).
   - **Clean-checkout verification**: 252 passed, 5 skipped (`tools/verify_checkout.py`).
   - **Release verification**: `scripts/Verify-Repository.ps1` passes with zero dirty working tree.
   - **Read-Only AVM2 Volatile Memory Engine**: Completed & verified against live PID 61828:
     - `mana_current`: Tracked via dynamic rate-of-change $\frac{dM}{dt} > 0$.
     - `mana_max`: Tracked via aligned boxed double clusters matching maximum bounds.
     - `mana_regeneration`: Tracked and verified against dynamic derivative.
     - `coins`: Verified against logarithmic tolerance of save coins.
     - `fairy_assistants`: Verified matching active assistant counts.
     - Memory readings are strictly READ-ONLY (`PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` = `0x0410`).
   - **Background Window Dynamics**:
     - Minimized (`SW_SHOWMINNOACTIVE = 7`): Adobe AIR pauses passive timers and throttles event loop.
     - Backgrounded (`SW_SHOWNOACTIVATE = 4`): Adobe AIR event loop runs at full speed with **zero focus theft** and zero window popping.

---

### REPOSITORY RULES & NON-NEGOTIABLE SAFETY CONSTRAINTS

From `AGENTS.md` and repository standards:
1. **READ-ONLY MEMORY OPERATIONS**:
   - Under NO circumstances may you call `WriteProcessMemory`, `VirtualProtectEx`, inject DLLs, patch game memory, or modify game binaries.
   - Strictly `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION` (`0x0410`).
   - Never write to or synthesize Realm Grinder save files to cheat progression.
   - Never invoke Steam achievement APIs.
2. **PRESERVE THE PRODUCT**:
   - Improve the existing Gemini-built Tkinter/Win32 Control HUD in place (`src/monitor_window.py`). Do not replace it with a new UI framework or rewrite the project from scratch.
   - One worker/action owner only (`WorkerLease`, single background loop); never create competing automation loops.
   - The HUD must remain fully functional offline without requiring an LLM/API connection.
3. **FAIL-CLOSED VERIFICATION**:
   - Never claim an action or purchase succeeded without verified before/after game state proof (`TransactionRunner`).
   - A clean source checkout must pass `python tools/verify_checkout.py` and `scripts/Verify-Repository.ps1`.

---

### ARCHITECTURAL BLUEPRINT & CORE TASKS

```
[ Control HUD (src/monitor_window.py) ]
       │
       ▼ (Clicks "⚡ Automate Straight to Goal")
[ Autonomous Goal Engine (src/state_machine.py & src/progression_actions.py) ]
       │
       ├──► 1. Post-Reset Kickstart (Gem Power -> Realm Click -> Buy Buildings -> Alignment/Treaty)
       ├──► 2. Optimal Template Engine (Scraped Wiki DB -> SemanticUI Template Entry -> Verify Ownership)
       ├──► 3. Live Volatile Saturation Loop (AVM2 Read-Only Memory -> Spell Saturation Autocasting)
       ├──► 4. Production & Purchase Loop (Buy All Upgrades -> Excavate -> Faction Milestone Purchases)
       └──► 5. Verified Milestone / Reset Guard (Abdicate at Plateau -> Reincarnate -> Next Cycle)
```

---

### TASK BREAKDOWN

#### TASK 1: Volatile Field Visuals in Control HUD
**Target Files**: `src/telemetry_presenter.py`, `src/monitor_window.py`
1. Connect `state['telemetry']` and `state['provenance']` to the HUD display.
2. When volatile memory is active (`memory_provider_health == 'HEALTHY'`), display:
   - `[MEM]` status indicator badge with green cybernetic glow.
   - Real-time Mana Bar: `Current / Max` (e.g. `415 / 1,105 Mana`) with dynamic fill percentage.
   - Real-time Mana Regeneration Rate: `+XX.X mana/s`.
   - Real-time live coins updating multiple times per second without requiring `.sol` file writes.
3. Ensure UI updates smoothly using Tkinter `after()` intervals (e.g. 250ms) without frame stutter or thread deadlocks.

#### TASK 2: "⚡ Automate Straight to Goal" 1-Click GUI Button
**Target File**: `src/monitor_window.py`
1. Add an unmissable, prominent primary action button in the HUD header or main card:
   - Text: `⚡ Automate Straight to Goal` (Styled with cyan/gold cybernetic accent).
2. Button Action Handler (`action_automate_straight_to_goal`):
   - Verifies the game is running (or starts it non-intrusively).
   - Sets game window to non-intrusive background state (`SW_SHOWNOACTIVATE = 4`) so AIR passive timers and mana regeneration tick at full speed without taking focus.
   - Reads current goal configuration (defaults to `Named goal: Dragon Tamer` or user-selected `Reach R46`).
   - Unpauses the bot worker (removes `state/STOP`, sets `config['paused'] = False`).
   - Starts or signals `DragonBot.run_loop()` in the dedicated background worker thread with `WorkerLease`.
   - Updates HUD feedback banner: `🚀 Automating straight to {Goal}: Autonomous progression active.`

#### TASK 3: Robust Post-Reset Auto-Kickstart (Getting Money Flowing Again)
**Target Files**: `src/route_executor.py`, `src/progression_actions.py`, `src/state_machine.py`
1. After an Abdication or Reincarnation, coins reset to 0. A fresh run requires an immediate, deterministic sequence to bootstrap production:
   - **Step 1 (Gem Power / Realm Click)**: If gems > 0, activate Gem Power / click Realm 5-10 times via `SemanticUI` to generate initial seed coins ($10^2$ to $10^6$).
   - **Step 2 (Buy Base Buildings)**: Trigger `buy_all_buildings` via `ProgressionActions.purchase_all('buildings')` or calibrated coordinates to get Farm/Inn/Blacksmith production running.
   - **Step 3 (Proof of Alignment & Trade Treaty)**:
     - Check `rec['alignment']` and `rec['faction']`.
     - Purchase `Proof of Good/Evil/Neutrality` via `RouteExecutor.purchase_named`.
     - Purchase `Faction Trade Treaty` or `Mercenary First Contract` once target coins are reached.
   - **Step 4 (Buy All Upgrades)**: Fire `buy_all_upgrades` to purchase all unlocked production upgrades and faction trade bonuses.
   - **Step 5 (Bloodline Selection)**: If the recommended build specifies a bloodline (e.g. `Druid Bloodline`, `Titan Bloodline`), verify and purchase it via `RouteExecutor.purchase_named`.
2. Ensure fail-safe transitions: if coins are insufficient for a treaty or alignment, the bot casts Tax Collections / clicks realm until the exact threshold is met, then immediately continues the kickstart sequence.

#### TASK 4: Automated In-Game Optimal Template Deployment
**Target Files**: `src/route_executor.py`, `src/build_catalog.py`, `src/wiki_data.py`, `src/semantic_ui.py`
1. **Dynamic Build Selection**:
   - For R0 to R39: Query `get_recommended_build(reincarnation, gems)` to select the highest-performing Mercenary build (e.g. `R24_MERC_NEUTRAL` / Diamond Forge / Harlequin / Lightning Forge).
   - For R40 to R45: Select optimal Ascension 1 research builds.
   - For R46+: Select Dragon unlock progression builds.
2. **In-Game Template Entry**:
   - `RouteExecutor.deploy_template(template)` currently checks `state['faction'] == 11` (Mercenary).
   - Ensure the template entry flow through `SemanticUI.enter_mercenary_template`:
     - Opens the Mercenary / Template dialog cleanly in the background.
     - Enters the template string via `InputController.type_text` or clipboard paste (`Ctrl+V`).
     - Clicks "Import" or confirms entry.
     - Confirms upgrade ownership and spell assignment via `template_progress(before, after, manifest)`.
3. If partial upgrades are purchased (due to coin limits), the bot must maintain production, cast spells to accumulate coins, and re-attempt the remaining template upgrades until `build_verified == True`.

#### TASK 5: Closed-Loop Volatile Saturation Spell Autocasting
**Target File**: `src/spell_policy.py`
1. Update `plan_spells(state)` to utilize the newly available live memory fields:
   - `mana_current = state['mana_current']`
   - `mana_max = state.get('mana_max', 1000.0)`
   - `mana_regen = state.get('mana_regeneration', 20.0)`
2. **Saturation Autocasting Policy**:
   - Calculate headroom: `headroom = mana_max - mana_current`.
   - If `mana_current >= mana_max - 50.0` (or `mana_current >= mana_max * 0.95`), mana is saturating and wasting regen!
   - Immediately schedule contingent Tax Collection bursts or priority tier spells to dump saturated mana into production.
   - Ensure spells are cast in descending priority order (`PRIORITY = (6, 9, 8, 13, 10, 2, 15, 11, 14, 7, 1, 12, 3, 17)`).

#### TASK 6: Verification & Test Suite Expansion
**Target Files**: `tests/test_autonomous_goal.py`, `tests/test_kickstart.py`
1. Create unit tests verifying:
   - Post-reset kickstart state transitions (from 0 coins to base buildings and faction alignment).
   - Template deployment and partial vs complete build verification.
   - Closed-loop spell saturation casting with volatile memory state.
   - "Automate Straight to Goal" button handler dispatching the worker safely.
2. Run full verification:
   ```powershell
   python -m pytest -q --tb=short
   python tools/verify_checkout.py
   pwsh -ExecutionPolicy Bypass -File scripts\Verify-Repository.ps1
   ```

---

### STEP-BY-STEP EXECUTION PLAN FOR CLAUDE

1. **Review Local Context & Branch**:
   - Ensure you are on `feat/air-memory-engine` (or create `feat/autonomous-goal-pipeline`).
   - Run `python -m pytest -q --tb=short` to confirm the 262-test baseline.
2. **Implement Task 1 & 5 (HUD Volatiles & Saturation Autocasting)**:
   - Update `src/telemetry_presenter.py` and `src/spell_policy.py`.
3. **Implement Task 3 & 4 (Post-Reset Kickstart & Template Deployment)**:
   - Enhance `RouteExecutor.collect()` and `ProgressionActions.setup_build()`.
4. **Implement Task 2 (1-Click Goal Button in HUD)**:
   - Add the `⚡ Automate Straight to Goal` button and orchestration logic in `src/monitor_window.py`.
5. **Run Verification Suite**:
   - Pass all unit tests and `Verify-Repository.ps1`.
6. **Package AI Continuance & Commit**:
   - Run `pwsh -File scripts/Export-Continuance.ps1`.
   - Commit and push to GitHub.
```
