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

Follow-up checked at 2026-11-06 12:22 UTC on `codex/live-viewport-scaling`, based on the then-current `origin/main` at `d538277c7e3e13afef28c234809e76c55ec71b66`.

- Added an anisotropic viewport regression at 1433x822. It failed before the recognizer change because the search crop began below the target and the averaged scale missed its native rendered size.
- Adjusted the icon search region and evaluated native, averaged, and per-axis template scales while retaining the existing confidence and uniqueness-margin gates.
- Responsive-input suite: **14 passed**. Full `scripts/Verify-Repository.ps1`: **413 passed, 5 skipped**; the skips require private visual fixtures. Clean bootstrap reported **0 network requests** and **0 game input**.
- Read-only matching against the saved live capture of the real out-of-focus 1433x822 client found Gem Power at `(180, 145)`, score `0.941`, uniqueness margin `0.312`. No click was sent. This proves frame capture and semantic target detection for the visible, non-minimized game window, not background click delivery or minimized operation.
- The first AFK attempt had stopped at a failed target lookup. STOP was set and the bot remained paused; no purchase or reset was made. Resets and excavation remain disabled.
- The original desktop shortcut still points to `C:\Tools\Dev\RealmGrinder\launcher.py`. This source change has not yet been installed, released, or used for a live purchase.

Status remains PARTIAL: this patch repairs visual recognition, but purchase transition proof, game progression, trophy state, minimized support, and a new GitHub release are not established.
