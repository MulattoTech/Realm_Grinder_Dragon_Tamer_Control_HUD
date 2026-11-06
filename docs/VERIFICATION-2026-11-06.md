# Verification report - 2026-11-06

Checked at 2026-11-06 12:07 UTC. The scoped source change is commit `68ce7b1275d3c5956064a0e8dddd9f2e76d1c1ac`, based on `main` at `6a748707f9af7c60e85ea010c97ef3e157425048`, on branch `codex/plain-hud-controls`.

## Changes covered

- Removed the redundant “Auto-Climb R (Force Cycle)” button and its alias handler. It only called the normal Start admission path and did not perform the behavior its label implied.
- Made the Stoic compatibility-note search test use a temporary database seeded from the tracked note. The test no longer depends on an ignored local wiki database.

## Automated verification

| Check | Result |
| --- | --- |
| Targeted control and compatibility-note tests | PASS - 2 passed |
| Full test suite on the source worktree | PASS - 412 passed, 5 skipped |
| `scripts/Verify-Repository.ps1` installed checkout | PASS - 417 passed |
| Clean source archive suite | PASS - 412 passed, 5 skipped |
| `compileall` | PASS |
| `git diff --check` | PASS |
| Clean bootstrap | PASS - no game binary, 0 network requests, 0 game input, configuration preserved |

The five skips are visual integration cases requiring private screenshots or icon templates that are intentionally not in the clean source archive. The complete verification command ran from `C:\Tools\Dev\RealmGrinder` at commit `68ce7b1`.

## Live environment and limits

- The existing HUD restarted as PID 68128 while the existing Realm Grinder process PID 45836 remained open. Config stayed paused, `state/STOP` remained present, and auto-abdication, auto-reincarnation, and auto-excavation remained disabled.
- A read-only save sample remained R24 with about `6.83e72` gems against the R25 requirement of `1e99`. Stat 81 remained zero, and neither stat 81 nor Hellfire time changed during a 15-second observation. This does not identify the stat updater's gameplay conditions.
- No game click, purchase, reset, Dragon stage, or achievement was performed or verified. Minimized input and actual out-of-focus game action remain unproven.
- The desktop shortcut still targets `C:\Tools\Dev\RealmGrinder\launcher.py`; it was not replaced.

## Status

This is a tested UI and test-isolation slice, not Dragon Tamer completion or a new release. Continue with supported live-action proof and the unresolved stat 81 and reset-review gates. Keep reset permissions off until the existing safety requirements are satisfied.

## Viewport recognition follow-up

Follow-up checked at 2026-11-06 12:43 UTC on `codex/live-viewport-scaling`, based on `main` at `513ec6463e591580c2fdd6bb56e7e149affc44d5`.

- Added an anisotropic viewport regression at 1433x822. It failed before the recognizer change because the search crop began below the target and the averaged scale missed its native rendered size.
- Adjusted the icon search region and evaluated native, averaged, and per-axis template scales while retaining the existing confidence and uniqueness-margin gates.
- Added a first-column regression at the same viewport size. Before the fix, the search crop excluded the visible Stoic icon at `(120,566)`. The recognizer now includes that column; targeted responsive-input suite: **15 passed**.
- Full `scripts/Verify-Repository.ps1` on `513ec64`: **414 passed, 5 skipped** in the source worktree and clean archive; installed-checkout suite: **419 passed**. Clean bootstrap reported **0 network requests** and **0 game input**.
- Read-only matching against the saved live capture of the real out-of-focus 1433x822 client found Gem Power at `(180, 145)`, score `0.941`, uniqueness margin `0.312`.
- The installed 513ec64 recognizer found Stoic Resistance in a fresh real out-of-focus capture at `(120,566)`, score `0.998`, margin `0.505`.
- Through the normal HUD admission button, the helper made out-of-focus Gem Power (ID 20) and Stoic Resistance (ID 552) purchases. Runtime receipts recorded the ownership transitions; `state/window-input-calibration-test.png`, `state/live-after-bounded-test.png`, and `state/live-after-stoic-test.png` show both icons in Purchased Upgrades and the displayed coin balance progressing from 25,000 to 24,999 and then `1e15`. The Stoic upgrade awarded the visible coin balance; `coins_this_game` remains unmapped. The next configured building-buy cycle raised Farm, Inn, and Blacksmith from 10 to 100 each. STOP then blocked the next Proof of Evil Deed action before dispatch.
- STOP is present and the helper is paused. Abdication, reincarnation, and excavation remain disabled. The current Dragon Tamer plan reports Reach R42 as the next milestone while the game remains R24 with about `6.83e72` gems; no ETA is validated. Background capture and these clicks were demonstrated at 1433x822; minimized operation and sustained AFK progression are unproven.
- The original desktop shortcut still points to `C:\Tools\Dev\RealmGrinder\launcher.py`; the installed checkout is at `2aa0118` and the one live purchase ran from that checkout. No new GitHub release has been created.

Status remains PARTIAL: visual recognition and two background purchase transitions are demonstrated, but progression toward R42, reset handling, Dragon milestones, trophy/achievement completion, minimized support, and a new GitHub release are not established.

## Exact research-ID resolution follow-up

Checked at 2026-11-06 13:51 UTC on `codex/live-viewport-scaling`, based on `main` at `fff03314f961126664e68e46ccce4ad8e3ff5bf6`.

- Static SWF tracing showed template token `S50` maps through the source reference to `130002` (Conjuration), while supported game version 4.3.22 serializes Conjuration as upgrade ID `300`. Version 4.3.11 has the same serialized ID, but manifests are pinned separately to the exact binary hash and save version.
- `compile_template` now resolves source token names against definitions from the exact supported SWF/schema pair. Missing or ambiguous installed definitions and unsupported/mismatched identities leave the manifest unverified. Manifest ownership checks require the active identity and schema to match the compiled manifest.
- Regression tests cover the `S50` to `300` mapping, rejection of source ID `130002` as the save key, mismatched SWF hash rejection, and malformed missing identity. All seven packaged build manifests resolve against supported 4.3.22 definitions.
- Targeted compiler, bootstrap, route, and action-verification suites: **60 passed** before adding the malformed-identity regression; the full source suite then reported **418 passed, 5 skipped**. A clean archive run reported **417 passed, 5 skipped**. Clean bootstrap made zero network requests and sent zero game input. The verifier then stopped at its clean-worktree gate as designed; committed-byte verification remains pending.
- The live game was not touched for this code check. Existing R24 game and paused helper status remain as in the collection follow-up above. This compiler fix does not calibrate or automate non-Mercenary Research UI selection, and does not establish any reset, Dragon stage, or achievement.

The verifier passed on commit `25f4097120aac6f26f368a51e2584e05cb9c56dc` from the source checkout: **418 passed, 5 skipped** in both source and clean archive. The install path was fast-forwarded from origin/main to the same commit; its verifier reported **423 installed tests passed** and **418 passed, 5 skipped** in the clean archive. Clean bootstrap recognized the installed 4.3.22 hash/schema, made zero network requests, and sent zero game input. The existing desktop shortcut still targets Python 3.12 `pythonw.exe` with `C:\Tools\Dev\RealmGrinder\launcher.py`; the updated HUD relaunched through it as PID 64768. Game PID 45836 stayed open, config stayed paused, STOP stayed present, and reset actions stayed disabled.

A live read-only capture at 1433x822 shows the R24 Goblin game view with no Research sidebar tab. No click or purchase was sent. The research deployment path remains fail-closed with `RESEARCH_UI_NOT_CALIBRATED`; the research panel prerequisite and click targets are not yet verified for this save. The community research walkthrough describes panel access after unlocking a facility and buying unique buildings in later runs: https://realm-grinder.fandom.com/wiki/Research:_Step_by_step. This was not validated against the current save.

Status remains PARTIAL. The ID compiler and existing collection automation are verified; non-Mercenary research UI selection, progression to R42, reset handling, Dragon stages, minimized operation, and Dragon Tamer achievement completion remain unproven.

## Non-Mercenary route blocker follow-up

Static tracing on the current main head found that the R24 Goblin `deploy_build` request was diverted to generic collection without modeling Research access. The executor now treats Research Facility upgrade ID 295 as the exact-hash Goblin prerequisite. While that upgrade is absent, the route continues ordinary collection; a fresh same-process ownership transition is required to report `RESEARCH_FACILITY_PURCHASED`. If a facility appears without a fresh transition and non-null matching process identity, STOP is written and the result stays uncertain. Once ID 295 is owned, non-Mercenary research dispatch reports `RESEARCH_UI_NOT_CALIBRATED` without sending research input. TDD regressions cover prerequisite collection, verified ownership transition, and uncertain ownership. `scripts/Verify-Repository.ps1` passed on `181a123`: source and clean archive each report **421 passed, 5 skipped**; compile and diff checks passed; clean bootstrap made **0 network requests** and sent **0 game input**. Installed verification and live gameplay after this update remain pending.

The installed 4.3.22 SWF tutorial identifies the unlock chain as upgrading a base building to its unique building to unlock the first Research Facility, then purchasing that facility to expose the Research panel. Goblin Bank is upgrade ID 412 and its description enables Research Facilities. ResearchFacilityUpgrade ID 295 is directly linked by its `onPurchase` method to the tutorial step saying the purchase grants the Research panel. The same fresh read-only save snapshot at fingerprint `1793975504530707900:4774:8a2187b5d63eb1253e96ecaf40fe67cf1416eb0295c15103bd7269c89a7f62a5` was R24 Goblin and contained neither ID 412 nor ID 295, and zero purchased buildings. The new path has not yet been installed or exercised in the game. The helper remains paused with STOP present and all reset actions disabled; no game input or save write was sent. Progression, reset eligibility, Dragon stages, and the Dragon Tamer achievement remain unverified.

## Delayed production-save observation follow-up

Checked at 2026-11-06 13:09 UTC on `codex/live-viewport-scaling`, based on `main` at `35be6c50b7c02a37980e959b2d33952e36b44edb`.

- The latest bounded Goblin production attempt logged `COLLECT_RESOURCES` as `OBSERVING`. Local progression history showed `coins_this_game` rising from about `1.252e12` to `1.683e12`; the collector previously read only once immediately after dispatch, so a save update that arrived later in the cycle could be missed.
- Added an eight-second bounded observation loop. It reports `VERIFIED` only after a fresh save fingerprint from the same process shows higher run coins, and includes before/after values and fingerprints. The message explicitly describes an observed increase during the collection window, not a causal guarantee that a particular click produced all of it.
- The regression failed before the change and passed afterward. Affected local suites: **68 passed**.
- The initial dirty-worktree verifier run passed both test suites and then stopped at its clean-worktree release gate. After committing the code, the complete `scripts/Verify-Repository.ps1` passed on `45b6b8fb5d9c37dfb4bf5cf45ec100560b17bf80`: source suite **417 passed, 5 skipped**; clean archive suite **417 passed, 5 skipped**; compile and diff checks passed; clean bootstrap made **0 network requests** and sent **0 game input**. This report-only follow-up changes no executable files.
- The installed checkout was fast-forwarded to `c403adb` and passed `scripts/Verify-Repository.ps1`: **422 installed tests passed**; clean archive **417 passed, 5 skipped**; bootstrap made **0 network requests** and sent **0 game input**. The existing desktop shortcut still targets `C:\Tools\Dev\RealmGrinder\launcher.py`; it launched the updated HUD without changing the shortcut.
- A bounded out-of-focus Start/Stop smoke run through the HUD verified one production observation on the same game process: run coins increased from `4,329,526,450,109` to `4,496,029,698,752` with a changed save fingerprint. A subsequent cycle without a new fingerprint or coin increase remained `OBSERVING`, not verified. The HUD Stop control restored `paused=true`, STOP present, and `auto_abdicate=false`, `auto_reincarnate=false`, `auto_excavate=false`. Game PID 45836 remained open at R24. No reset, Dragon stage, or achievement was performed; end-to-end progression is still PARTIAL.
