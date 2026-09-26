# Current implementation handoff - 2026-09-23

## Read this first

## Continuation checkpoint - 2026-09-24 11:45 CDT

- The 15-minute read-only save watcher ended normally without observing an excavation, Royal Market purchase or Abdication. Latest decoded save remains R24/A0, Fairy/alignment 1, `5.1893444080398605e69` gems, `3.5457585943893085e65` potential gems, `6.286202004842822e142` run coins, 1,540 excavations, no egg; fingerprint `1790268287739328300:6162`, age about 25 seconds.
- Game PID 5400 and reloaded HUD PID 42500 remain open. The bot is paused (`paused=true`, STOP exists, worker false). Automatic is selected; planner remains `maintain_faction` on active Fairy and retains Neutral Mercenary for the next run. Abdication dialog remains open and unconfirmed.
- Live installed-ID audit: Gem Power ID 20 is owned; Royal Market ID 579 is not owned. `KnowledgeService.plan_target('Dragon Tamer', save)` reports its next prerequisite as Reach R46. Saved selected goal is still Build only; preserve pending the user's manual sequence and goal-setting direction.

## Continuation checkpoint - 2026-09-24 11:22 CDT

This is the newest runtime checkpoint and supersedes prior process/route/pause notes.

- Game PID 5400 remains open. HUD PID 42500 was reloaded from the existing launcher at 11:22; its start time is later than the route-source edit. The game was not restarted.
- Fresh decoded save remains R24/A0, Fairy/alignment 1, `5.1893444080398605e69` gems, `3.1543185321382033e65` potential gems, `4.974862701095254e142` run coins, 1,540 excavations and no egg (fingerprint `1790266967758152100:6170`, age about 11 seconds).
- Bot config is still paused with `state/STOP` present; worker reports `is_running=false`. Automatic remains selected, with Build only / Reach R46 preserved. The refreshed Abdication dialog remains open and unconfirmed.
- The reloaded planner now reports `action=maintain_faction`, `active_path=Fairy`, `selected_path=Automatic`, and `next_run_recommendation.faction=Neutral Mercenary`. This is live planner output while paused; no game action was sent.
- Installed-ID/save comparison: Gem Power ID 20 is already owned (`u1=true`); Royal Market ID 579 (installed icon `RoyalExchange`) has no owned save record. Do not treat these as the same purchase.
- The user's planned excavation, Royal Exchange purchase and Abdication still had not registered in the latest save. Leave the game controls untouched until the user performs that sequence or gives new direction. No project tests were run for the source edit.

## Continuation checkpoint - 2026-09-24 11:16 CDT

This checkpoint supersedes earlier process, pause, route, and Abdication-dialog observations below where they differ.

- Latest decoded save: R24/A0, faction 0/Fairy, alignment 1, `5.1893444080398605e69` gems, `3.0327892775804614e65` potential gems, `4.598905401103508e142` run coins, 1,540 excavations, no egg. Fingerprint `1790266547755514500:6166`; reported save age about 28 seconds. Realm Grinder remains PID 5400.
- The HUD is PID 34236. It remains safely paused (`bot_config.json.paused=true`, `state/STOP` present, worker `is_running=false`), selected route Automatic, selected goal Build only, named goal Reach R46. Do not resume before the current user-directed game actions are reconciled.
- The stale Abdication dialog was closed and reopened. The refreshed live dialog showed a gain of `7.92e60` gems and `966.60%` production increase. No confirmation was clicked. The user said they would perform an excavation, buy a gem upgrade on the Royal Exchange, then Abdicate; the latest decoded save had not yet shown an excavation, gem purchase, or reset. Continue observation without sending game input while the user is doing this.
- The user approved a bounded Automatic-route correction. `selected_route()` now uses the recognized active faction for the current run when Automatic's recommendation requires a faction change, and carries the recommendation forward as `next_run_recommendation`. Build and route diagnostics distinguish configured `selected_path=Automatic` from `active_path`. This is source-only so far: the running HUD predates the edit and has not loaded it; no tests were run for this change.
- After the user's sequence, verify the fresh save, then reload only the HUD with the game left open to activate the route change. Preserve the selected goal unless the user changes it; Build only does not track the requested R46/Dragon Tamer target.

## Continuation checkpoint - 2026-09-24

This checkpoint supersedes earlier live-state and UI-reload statements below where they differ.

### Live progression resumed - 2026-09-24

- A fresh check shows `state/bot_config.json` has `paused=false`, `state/STOP` is absent, and the existing worker reports `is_running=true`. Its log records `COLLECT_RESOURCES` cycles about every seven seconds. The old `last_action_result.json` still says a Fairy Trade Treaty was blocked by a previous unresolved action; that result is stale. The current pending ledger is `RECONCILED_NO_TEMPLATE_TEXT`.
- A later decoded save read (fingerprint `1790265037760608800:6170`, age about 26 seconds) reports R24/A0, faction 0, alignment 1, `5.1893444080398605e69` gems, `2.5673123684031356e65` potential gems, `3.2955463984778593e142` coins this run, 1,540 excavations and no egg. R24 requires `1e99` gems for the next reincarnation, so current gems are `5.19e-30` of that cost. Potential gems are `4.95e-5` of current gems, so an Abdication is not eligible yet. The 20-second ownership comparison still showed 322/350 upgrade records and 25,250 buildings. R and gems have not advanced.
- The saved mode is still `Build only` with named target `Reach R46` and Fairy path. Preserve that selection. The worker is active; do not restart it while unpaused or launch a duplicate. Reincarnation remains gated by its uncalibrated dialog and missing same-R milestone audit.
- At the current save, `selected_route(state, 'Automatic')` recommends `Neutral Mercenary (Assisted Advancement)` with a template, while the configured Fairy route resolves to generic `Fairy faction progression` with no template. The current save is Fairy/alignment 1; faction and alignment cannot be switched within this run, so the Mercenary template is a post-Abdication route, not a compatible mid-run replacement ([Mercenary faction guide](https://realm-grinder.fandom.com/wiki/Mercenary)). Keep Fairy for this run until a profitable Abdication is available, then plan the next faction. The live build check is false because a current-version ownership manifest is not verified. Across a 20-second observation the save remained at 322/350 owned upgrades and 25,250 total buildings while run coins rose from `3.084e142` to `3.106e142`; this shows production growth but no newly purchased upgrades/buildings in that interval.
- The running HUD PID 25136 started at 09:40, before `src/progression_actions.py` was updated at 10:05. Python does not hot-reload imported modules; the live worker cannot use the new pixel-gated Abdication path yet. Its older transaction path is fail-closed because `ui_actions.json` has no verified reset actions. Before automated resets can work, pause the bot, close only the HUD, and reopen it through the existing launcher while the game remains open; then review the saved goal and resume from the refreshed HUD.
- At 10:35 one worker cycle failed when Windows denied the atomic replacement of `state/build_verification.json` (`WinError 5`). The file ACL allows modification, and the same file was successfully replaced at 10:36; production cycles continued and the worker again reported `is_running=true` at 10:37. The denial was transient; its underlying cause is unknown. Current HUD diagnostics still show the build unverified because the current-version ownership manifest is missing.

### Live Abdication dialog recognition

- On 2026-09-24 the user opened the Abdication confirmation for calibration. A fresh live frame from Realm Grinder PID 5400 at 1180x810 matched the paired Abdication title, close control and confirm button. Scores were 0.9999998, 0.9964 and 0.99997; predicted client points were close `(1053,276)` and confirm `(522,488)`. This validates the recognizer against a live dialog, beyond its historical screenshot fixture.
- No button was clicked; the game state and save were not changed. A later shell-side reacquisition failed, so no screenshot file was retained and this is detector evidence rather than a saved visual review.
- `ProgressionActions.abdicate()` now has a live-pixel-gated transaction path, but the bot remains paused. Reincarnation still has no live modal calibration or wired semantic transaction; the empty `ui_actions.json` profile and absent same-R milestone audit remain gates.

- The earlier checkpoint had the game paused. The newer resumed state above supersedes that status. Game PID 5400 and HUD PID 25136 remain present; the game was not restarted.
- The stale `MERCENARY_TEMPLATE` transaction `496e18d36e484d5fb31f95fa24aeccfb` is now recorded as `RECONCILED_NO_TEMPLATE_TEXT`. Its exact error is emitted after the Import dialog check and before the input-field click or character typing loop. Its original record and backup path remain intact; the reconciliation includes a fresh same-R save snapshot. No retry or game input was sent.
- The current UI selection is `Build only`, while the saved named target is `Reach R46` and path is Fairy. Start explains that Build only pauses once the active build verifies and that Named goal gives explicit R46 target tracking; it does not block a valid Start request. Settings were preserved.
- The live goal plan still reports R46 as the next strategic target. Reincarnation cannot yet run safely: `ui_actions.json` has zero verified actions and no calibrated client size, and `state/permanent_milestone_audit.json` does not exist. The reincarnation transaction requires both verified reset UI actions and a same-R audit. Do not enable autonomous resets by weakening these checks.
- The Offline Production recognizer now uses its two small calibration images under `assets/modal-calibration/`. It runs before the pause return and closes only a paired, pixel-verified dialog on the same interactive game session.
- Added pixel recognizers for the reset controls and Abdication confirmation. The live R24 screenshot matched the Abdication and Reincarnation labels at client pixels (215,20) and (380,20) with scores above 0.999. The Abdication confirmation anchors were subsequently matched together against the user's live dialog; no reset was dispatched. Reincarnation remains uncalibrated.
- Corrected the reviewed Dragon stage scopes: Hatch!, Drakeling, Dragon and Elder Dragon now allow ascension 0 as well as 1, consistent with the current R46 guide's R46+ requirements. A regression fixture confirms the Hatch! plan is actionable at R46/A0 when its listed wait and costs are satisfied; this is planner evidence, not live acquisition.
- Last recorded full suite: 254 passed on Python 3.12 before the current Abdication transaction edits; those edits remain unverified. The last recorded `git diff --check` also predates them. Changes remain uncommitted because this environment denied creation of `.git/index.lock`.

Next progression work is to validate an Abdication transaction only when the user resumes automation, calibrate the Reincarnation dialog, and add a same-R milestone audit producer. Dragon Tamer and Steam achievement are not achieved.

This handoff supersedes earlier failure reports and aspirational completion claims. Work is in the existing project and is being committed to the requested private GitHub repository. Do not rebuild the application from scratch or re-run old blind-click scripts.

At the start of this integration pass, later local work already existed: actual R24 Neutral Mercenary, Fairy Bloodline, twelve selected Mercenary upgrades, and both desired spells. That setup was achieved before this pass; preserve it. Baseline tests were 161 passed and one failed, not the older 87/13 handoff.

## Applied in this pass

- Preserved the existing source and merged the repository's initial README without force-pushing or discarding remote history.
- Corrected production routing: completed builds now reach the working RouteExecutor rather than the obsolete fixed-profile purchase loop.
- Isolated ETA history by R, permanent gems, faction/alignment and pause segment; invalid, stale, inconsistent or nonstationary samples do not generate a deadline.
- Added the reviewed rule graph, separate currency budgets, explicit unknown requirements, bounded arithmetic interpretation, named-goal dispatch and HUD inspection.
- Compiled 2,664 source cards from 120 existing attributed documents. 442 cards contain differing field text across sources; this is not a claim of 442 proven mechanical contradictions. There are 24 reviewed recipes and 3 reviewed formula models. Most cards remain reference-only.
- Persisted observed Dragon ownership transitions and conservative elapsed bounds. Preexisting ownership stays time-unknown. Counter regressions do not produce artificial progress.
- Removed fabricated Dragon Tamer directives based only on current mana/coins, and removed the legacy two-hours-per-R completion forecast. Eligible egg probabilities use the source's 2% conditional model and require R46 as well as excavations.
- Added a reproducible paused bootstrap, bundled factual code/ID mappings, version-bound small UI anchors, explicit integration-test prerequisites, a clean-checkout verifier and an inactive Windows CI example.
- Resume uses Start's connection/geometry/unresolved-action checks instead of bypassing them.

## Live observations and limitations

The actual game stayed in Windows session 1; remote shells run in session 0. A normal interactive task request to reload the HUD was blocked by the tool. No privileged workaround or task-script repurposing was used. Source changes do NOT hot-reload the currently running HUD.

An offline withdrawn-window HUD smoke check constructed the updated interface, confirmed all four goal modes and 24 named targets, and refreshed state without an error. Its worker was mocked, so this is NOT live gameplay acceptance.

Two read-only current-mana candidates were tested against fresh saves. Both stayed at 9,850 while fresh saved mana changed through 10,338 to 10,391. They were rejected, not promoted to verified mappings. No newly validated live mana field exists. Process attachment and the generic reader/scanner are tested; those are different claims.

The game remained R24 during this pass. In-game autocasts and an already running HUD continued activity; do not attribute live coin gains to source edits that were not loaded. The last checked reset switches were both disabled. Configuration was observed to be resumed after the development pause; do not overwrite user preferences from stale in-memory HUD config.

## Remaining acceptance work

1. Close/reopen only the HUD from the logged-on desktop; leave Realm Grinder open. Confirm the updated Named goal controls and measured ETA states are visible.
2. Exercise the corrected ongoing production path with resets disabled; verify fresh building/upgrade/coin deltas and spell behavior, then record a bounded acceptance report.
3. Find and validate a stable volatile field through repeated legitimate spend/regeneration behavior with independent save/UI checks. Dynamic AIR heap copies and full-mana caches are not authoritative.
4. Calibrate research-template UI and semantic reset/ascension confirmation. Existing empty verified UI profiles and missing same-R milestone audit intentionally prevent automatic resets. Do not replace them with unconditional approval.
5. Validate post-R40 formulas and installed-version costs before claiming long-range automation. Complete R24 -> R25 with fresh state evidence before certifying any end-to-end run.
6. Expand reviewed recipes from the reference corpus. Preserve unparsed conditions and conflicting historical variants; never mark all 2,664 reference cards executable by flipping a flag.

## Files and evidence

- `docs/progression-integration-2026-09-23.md`: initial plan and baseline.
- `data/source_manifest.json`: reusable source URLs, hashes and capture provenance, not full scraped pages.
- `data/progression_rules.json`: reviewed recipes; `data/reference_identifiers.json`: template-code identifiers.
- `data/installed_identifiers.json`: literal name/ID facts scoped to a known binary, not executable game code.
- `src/mechanics.py`, `src/knowledge_service.py`, `src/source_cards.py`: source-backed planning and reference separation.
- `src/quest_observer.py`: persisted ownership transition journal.
- `src/route_executor.py`, `src/progression_actions.py`: selected path and shared action execution.
- `tools/bootstrap.py`, `tools/knowledge.py`, `tools/verify_checkout.py`: reproducibility and diagnostics.
- Local-only baseline checkpoint: `backups/progression-source-20260923-121719.zip`.
- Local-only traces: `state/readonly-mana-candidate-study.json`, `state/passive-mana-slot-observation.json`.

## Safety and continuation

Keep game memory read-only, preserve saves, retain one worker/action owner and all cancellation checks. Never launch or change DevFleet or another project. Never infer a new implementation from old success messages. Verify both working-tree cleanliness and the pushed SHA before saying GitHub is current.

Final measured test/clean-checkout/remote results belong in `docs/VERIFICATION-2026-09-23.md`.

## GitHub workflow permission boundary
The normal Git credential can push application source but cannot install an Actions workflow. GitHub rejected the unpublished feature push solely because it included `.github/workflows/windows-tests.yml`. That unpublished commit was amended to preserve the same workflow as the inactive `docs/ci/windows-tests.yml.example`; no published history was rewritten, no force push was used, and no credentials/permissions were changed. Installing CI later requires the owner's authorized workflow access.
