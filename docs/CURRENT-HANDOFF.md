# Current implementation handoff - 2026-09-23

## Read this first

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
