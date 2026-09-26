# Current handoff - repository-first baseline

Date: 2026-09-26

## Canonical source
GitHub repository: `MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD`.

The repository is now the source of truth. The old local folder is only a checkout. Any future machine should be able to start from a GitHub release or a fresh clone and reconstruct the development environment without copying local runtime state.

## Reconciliation result
- Original remote `main` and the local committed HEAD both pointed to `b628761`.
- The local working tree contained substantial uncommitted Sep. 24 work: reset/modal recognition, runtime safety changes, route/progression changes, tests, seven calibration anchors, and verification notes.
- That exact pre-reconciliation state was preserved on GitHub first as branch `reconcile/local-wip-2026-09-26`, commit `8189d4b`.
- Clean-checkout reset tests originally depended on an ignored generated icon registry. Commit `5107942` fixes that dependency without weakening named-icon checks.

## Verification state
On the fully provisioned local checkout: 257 tests pass.
From a committed source-only archive: 252 tests pass and 5 visual integration tests skip with explicit missing-private-fixture reasons.

No source-only checkout requires a save, runtime log, screenshot collection, or generated icon cache to pass its portable test set.
## Product state
The existing Gemini-built Control HUD remains the product UI. Keep improving it in place.

Implemented foundations include read-only save/process inspection, source-backed progression knowledge, named goals, verified purchases, transaction guards, automatic route selection, conservative ETA logic, quest observation, reset/modal visual recognition, and a single worker/action owner.

Still not certified end-to-end:
- autonomous R24 -> R46 progression;
- safe reincarnation confirmation and same-R permanent-milestone audit;
- robust version-specific post-R40 strategy;
- complete Dragon-stage execution and final Steam achievement confirmation;
- fully proven minimized/background interaction for every action;
- stable field-specific volatile-memory coverage.

## Repository workflow
Run `Install.ps1 -Dev` on a fresh checkout, then `scripts/Verify-Repository.ps1`.
Build a release artifact from clean committed HEAD with `scripts/Build-Release.ps1`.
Until GitHub workflow permission is authorized, release publication is manual via GitHub CLI/API.

Historical runtime notes were moved to `docs/archive/CURRENT-HANDOFF-2026-09-24.md`.
Read `docs/CLAUDE-HANDOFF.md` and `docs/AUTOPILOT-TARGET-ARCHITECTURE.md` before the next major implementation pass.
