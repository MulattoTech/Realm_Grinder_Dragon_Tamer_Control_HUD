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

## Delayed production-save observation follow-up

Checked at 2026-11-06 13:09 UTC on `codex/live-viewport-scaling`, based on `main` at `35be6c50b7c02a37980e959b2d33952e36b44edb`.

- The latest bounded Goblin production attempt logged `COLLECT_RESOURCES` as `OBSERVING`. Local progression history showed `coins_this_game` rising from about `1.252e12` to `1.683e12`; the collector previously read only once immediately after dispatch, so a save update that arrived later in the cycle could be missed.
- Added an eight-second bounded observation loop. It reports `VERIFIED` only after a fresh save fingerprint from the same process shows higher run coins, and includes before/after values and fingerprints. The message explicitly describes an observed increase during the collection window, not a causal guarantee that a particular click produced all of it.
- The regression failed before the change and passed afterward. Affected local suites: **68 passed**.
- The initial dirty-worktree verifier run passed both test suites and then stopped at its clean-worktree release gate. After committing the code, the complete `scripts/Verify-Repository.ps1` passed on `45b6b8fb5d9c37dfb4bf5cf45ec100560b17bf80`: source suite **417 passed, 5 skipped**; clean archive suite **417 passed, 5 skipped**; compile and diff checks passed; clean bootstrap made **0 network requests** and sent **0 game input**. This report-only follow-up changes no executable files.
- The installed checkout was fast-forwarded to `c403adb` and passed `scripts/Verify-Repository.ps1`: **422 installed tests passed**; clean archive **417 passed, 5 skipped**; bootstrap made **0 network requests** and sent **0 game input**. The existing desktop shortcut still targets `C:\Tools\Dev\RealmGrinder\launcher.py`; it launched the updated HUD without changing the shortcut.
- A bounded out-of-focus Start/Stop smoke run through the HUD verified one production observation on the same game process: run coins increased from `4,329,526,450,109` to `4,496,029,698,752` with a changed save fingerprint. A subsequent cycle without a new fingerprint or coin increase remained `OBSERVING`, not verified. The HUD Stop control restored `paused=true`, STOP present, and `auto_abdicate=false`, `auto_reincarnate=false`, `auto_excavate=false`. Game PID 45836 remained open at R24. No reset, Dragon stage, or achievement was performed; end-to-end progression is still PARTIAL.
