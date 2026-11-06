# Realm Grinder Dragon Tamer Control HUD

Windows-native automation and a source-backed progression workbench for the Steam version of Realm Grinder. This is the existing application, improved in place. It plays through normal game-window input and reads the save and process memory; it does not edit saves, patch the game, inject code, or invoke Steam achievement APIs.

**Current status: verified development prerelease; Dragon Tamer progression is not end-to-end certified.** The exact 4.3.22 Dragon prerequisites are version-scoped, but quest-counter progression, reset permissions, later purchases, and final achievement remain unverified. See `docs/CURRENT-HANDOFF.md`. Restart the HUD after updating source.

## What is implemented

- Select Automatic, a supported faction, or a Mercenary alignment; execute the next missing prerequisite rather than blindly sweeping icons.
- Named upgrade targeting, transactional purchase verification, compiled Mercenary templates, actual faction/bloodline/upgrade/spell ownership checks, and one shared production/action owner.
- Separate goals for Build only, Next reincarnation, Dragon Tamer, and a named reviewed upgrade/trophy/goal. Inspect requirements before starting.
- Same-run, observation-based gem ETA with explicit paused/stale/nonstationary states. A long-range completion date is not fabricated from a fixed duration per reincarnation.
- Read-only Win32 process reader/scanner, tagged AVM2 numeric reads, process-session invalidation, and field-by-field save/memory provenance. **No live mana mapping has yet passed field-specific calibration in this checkpoint.**
- Persistent quest observations: a preexisting egg does not receive a made-up acquisition time; Hellfire progress is not credited from before observed Hatch ownership.
- Local, attributed wiki index, structured source cards with conflicting variants, a bounded arithmetic/formula interpreter, and reviewed prerequisite/resource recipes. **Searchable reference coverage is not the same as executable mechanic coverage.**

## Install from GitHub

Use Python 3.12 on Windows. From a normal terminal in your logged-on desktop:

```powershell
git clone https://github.com/MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD.git
cd Realm_Grinder_Dragon_Tamer_Control_HUD
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python tools/bootstrap.py
python launcher.py
```

Use your normal authorized Git credentials for the public repository. No credentials belong in configuration files or commits. A non-default Steam location can be supplied with `python tools/bootstrap.py --game-dir "D:\SteamLibrary\steamapps\common\Realm Grinder"` or the `REALM_GRINDER_GAME_DIR` environment variable.

Bootstrap creates a paused configuration, leaves reset actions disabled, reconstructs build manifests from bundled factual IDs, and validates the supported local game binary before extracting matching icon metadata. It makes no network request or game input. It preserves an existing configuration and STOP file. Game files are read only.

## Operate the HUD

Keep the game visible and unobscured at the intended action point for semantic actions. The window may be out of focus when it is topmost there; a point covered by another window is rejected even when `PrintWindow` can capture the game behind it. Minimized semantic input is not supported. Window coordinates and icon matching scale with the visible client area; if the window changes size between recognition and dispatch, the click is canceled. Start with **Build only** to check basic connection and profile behavior. The helper buys one verified prerequisite at a time and uses the shared production executor for ordinary purchases and budgeted spells.

Select **Named goal**, choose a reviewed target, and use **Inspect requirements** to see dependencies, missing measurements, and separate currency budgets. Unknown recipes remain reference-only. Resume and Start share the same admission checks; an unresolved action cannot be silently discarded by the Resume button.

Pause stops bot input, not the game's own autocasting. `stop.ps1` sets the project STOP/configuration pause and does not close Realm Grinder. Opening the launcher preserves the existing pause state. No service/session-0 launch should be used for game control.

## Source knowledge

```powershell
python tools/import_knowledge.py --refresh --max-pages 160
python tools/knowledge.py compile
python tools/knowledge.py coverage
python tools/knowledge.py search "Stoic Resistance"
python tools/knowledge.py plan "Dragon Tamer"
python tools/knowledge.py formula "(r + 1) * r / 2" --variables '{"r":24}'
```

The importer uses musicfamily.org, the Realm Grinder Fandom wiki, and dated Archive.org fallbacks. `data/source_manifest.json` preserves the prior source URLs and capture provenance so a checkout can rebuild its local cache. Failed requests stay recorded. Historical and current source variants are not silently reconciled. Raw fetched pages live in the ignored local cache and are never executed as code.

For example, older Stoic Resistance descriptions differ from the installed 4.3.11 behavior observed during development. The installed upgrade provides ordinary coins, not faction coins. Costs and prerequisites marked as wiki estimates remain subordinate to actual game availability and verified ownership changes.

## Known acceptance gaps

Live volatile memory calibration, quest-counter advancement semantics, research-template UI calibration, reset/ascension UI calibration, complete R24-to-Dragon progression, later-stage purchases, and final achievement are unverified. Reset remains fail-closed without a pinned milestone review. Version 4.3.22 mechanics are bound to the installed SWF hash and save schema; unknown profiles cannot authorize purchases. Generic references and candidate builds are not complete game support.

## Tests and continuation

```powershell
python -m pytest -q --tb=short -p no:cacheprovider
python -m compileall -q src tools launcher.py
python tools/verify_checkout.py
```

Local read-only game and visual integration tests run when their prerequisites exist. On a fresh checkout/CI, tests needing a private save, installed binary, or private captured frames are explicitly skipped with named reasons. Logic, source handling, safety, and controlled helper-process tests still run. The clean-checkout verifier tests committed HEAD without copying your private runtime directories.

A Windows CI workflow is preserved as the inactive example `docs/ci/windows-tests.yml.example`. GitHub rejected installation because the available Git credential lacks the workflow permission. No credentials were changed, and no GitHub Actions run is claimed. Runtime state, saves, logs, full screenshots, caches, and extracted texture atlases are excluded from Git. Small version-bound UI matching snippets carry their own attribution in `data/ui_reference/manifest.json`. See `THIRD_PARTY.md`; no new application license is implied.

Legacy standalone scripts and the JavaScript decoder are preserved for provenance and debugging but are not the production control path. Do not use their old formulas or success messages as current evidence.

## Repository origin

Realm_Grinder_Dragon_Tamer_Control_HUD - source continuity for the existing Dragon Tamer control project.
