# Realm Grinder memory upgrade ? implementation handoff

Recorded: 2026-09-23T03:56:31.821959-05:00
Repository: C:\Tools\Dev\RealmGrinder
Status: INCOMPLETE ? NOT RELEASE-READY. Keep STOP present and paused=true.

## Verified final result
- Full suite: 87 passed, 13 failed, 100 total tests.
- Python compilation completed successfully before this report was written.
- Save: R24, gems 2.4070655276028232e+68, faction ID 5.
- No live mana mapping was validated or registered; memory_mappings.json is absent.
- R24 -> R25 and Dragon Tamer have NOT been achieved.
- No game save editing, game-memory writing, injection or achievement manipulation was performed.
- The service-session game was backed up and closed normally. No game launch in the user desktop was completed.

## Work actually applied
- Added minimal read-only Win32 process reader (OpenProcess 0x410), bounded scanner, target pointer-size detection, session identity, and AVM2 numeric-Atom reading.
- Proved attachment and real reads against a controlled helper process and the actual 32-bit Realm Grinder process.
- Added hybrid state provider, field provenance, explicit unknowns, freshness checks and atomic bot-state persistence.
- Corrected save normalization: current mana is not max mana; Hellfire is spell 11, with active0/active1/active2 counters; trophy ownership differs from upgrade u1.
- Serialized the reusable save decoder for concurrent callers and corrected legacy JSON-format branch selection.
- Added shared transactional actions and locks; integrated worker and GateClearer; removed their duplicate reset implementations and resource/timer-only success claims.
- Added interactive-session guards and one-worker lease. Opening the launcher no longer clears STOP automatically.
- Marked minimized synthetic frames as non-UI evidence. HUD and state-capture migration remains unfinished.

## Confirmed R24 diagnosis
- Saved faction ID 5 (Demon), not the recommended Neutral Mercenary build.
- mercSpell1 and mercSpell2 were zero; Fairy bloodline upgrade 194 and Druid bloodline upgrade 136 were absent.
- The legacy assistant value 23,590 equaled total buildings; it is not evidence of Fairy assistants.
- A historical after-abdication screenshot still displayed the confirmation dialog. Button coordinates in the controller did not match that screenshot.
- Current minimized-window geometry is not calibrated; do not promote historical coordinates to verified actions.

## Live-memory experiments
- Exact Float64 scan of about 271 MiB took approximately 0.453 seconds with no read errors and found four full-mana candidates.
- Normal spell inputs changed saved cast counts, proving input delivery in that process session.
- Expensive spell input produced a fresh saved current-mana value around 20,479 while the four candidates stayed around 23,161. Those candidates are NOT validated current mana.
- Differential scanning did not produce a valid field. Candidate addresses may represent caches, maximum mana or recycled numeric objects.
- AVM2 Atom reader passed synthetic tests, but no stable live game Atom slot was identified.

## Critical unresolved implementation issues
1. MemoryProvider currently promotes passive, changing save-anchor matches to HIGH confidence. A regression proves this can mistake full-bar/max-mana cache values for current mana. The attempted correction was blocked and was NOT applied. Do not run autonomous gameplay.
2. config.load_config does not accept Windows UTF-8 BOM JSON correctly; options fall back to defaults. The attempted correction was blocked and was NOT applied.
3. src/monitor_window.py and src/state_capture.py still use the old save-only API and old readiness presentation. src/telemetry_presenter.py was not created because the integration write was blocked.
4. UI action profiles are reference-only: verified_actions is empty and client_size is null. Build manifests are empty. Dragon upgrade/trophy IDs remain unverified legacy candidates except the egg. No same-R permanent milestone audit is complete.
5. End-to-end HUD behavior, restart recovery, semantic build deployment, actual progression and Steam achievement behavior remain unverified.

## External blockers and leftover task
- Remote commands were running in Windows session 0. Dylan's interactive console is session 1.
- A one-shot task successfully ran an observation-only probe in session 1; no game existed there.
- Windows denied changing the task action to launch the game (0x80070005). No alternate task or privilege workaround was used.
- Final HUD/source corrections were blocked by remote execution safety checks; blocked requests were not applied.
- Cleanup was attempted for our task 'RealmGrinder - Interactive Telemetry Diagnostics', but Windows denied deletion too. It remains a no-trigger, manual one-shot observation task, not ongoing automation.

## Evidence and rollback files
- Original focused checkpoint: backups/source-checkpoint-20260923-024147.zip
- Checkpoint SHA256: d33b55a08657962c7e74b1d31658bd4a419fdefd76e07121bbb547246f5c72db
- Pre-session-migration game backup: backups/before-session-migration-20260923-032803.sol
- Final test text: logs/memory-upgrade-verification-20260923.txt
- Final test XML: logs/memory-upgrade-verification-20260923.xml
- Experiment records: state/mana_discovery_candidates.json, mana_calibration_evidence.json, mana_burst_calibration_evidence.json, mana_spells_calibration_evidence.json, mana_differential_discovery.json.
- Baseline: state/memory-upgrade-baseline.json. Early plan: docs/memory-upgrade-plan.md (this report supersedes its incomplete status ledger).
- No Git repository or commits were created. Existing source changes remain in place, not rolled back.

## Failing tests
- test_high_value_consumers_use_hybrid_state[src/monitor_window.py]
- test_high_value_consumers_use_hybrid_state[src/state_capture.py]
- test_gui_refresh_does_not_launch_game_or_run_guardian_actions
- test_passive_save_anchor_matches_do_not_claim_live_mana_verification
- test_windows_utf8_bom_configuration_preserves_options
- test_banner_distinguishes_save_current_mana_and_unknown_maximum
- test_banner_labels_verified_process_memory
- test_max_mana_none_cannot_show_elder_ready
- test_lifetime_or_run_hellfire_is_not_since_hatch
- test_unknown_fairy_assistants_not_rendered_as_zero_or_total_buildings
- test_verified_upgrade_ownership_overrides_guessed_timers
- test_uncatalogued_legacy_id_is_not_ownership_proof
- test_unknown_number_formats_without_crashing

## Safe continuation boundary
Leave the bot paused. Starting Realm Grinder through Steam on Dylan's normal desktop resolves the missing interactive game instance only; it does not resolve the failing software checks. Complete and verify the listed code/integration gaps before enabling autonomous input. Do not declare R25 or Dragon Tamer without fresh save and normal Steam evidence.
