# Current handoff

Date: 2026-11-06

## Current source and release state

Canonical repository: `MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD` (public). The published `0.1.0-alpha.2` source is commit `ebd43d7df16db422f60cbff2554c7298d5998679`; this handoff also records the later installation smoke check. It is a development prerelease, not an end-to-end Dragon Tamer release. The release is [v0.1.0-alpha.2](https://github.com/MulattoTech/Realm_Grinder_Dragon_Tamer_Control_HUD/releases/tag/v0.1.0-alpha.2).

The original desktop shortcut still targets `C:\Tools\Dev\RealmGrinder\launcher.py`. The verified commit is pushed to `main` and installed in that folder; the shortcut did not need to change.

## Implemented and locally verified

- Existing Tk/Win32 HUD retained. The UI reports the selected objective, planner-derived Dragon milestones, blockers, and live/persisted STOP state in plain language. Ultron/Skynet mode branding and the cosmetic Ultron configuration option are removed.
- Dragon planning is bound to installed Realm Grinder 4.3.22 SWF SHA-256 `7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b` and save schema 58. Static facts cover Egg eligibility at R42 and 1,500 excavations, stage reincarnations R42/R44/R46/R48, and the stat 81 purchase threshold. The gameplay counter updater and its advancement semantics are unknown; stage readiness remains blocked until its save evidence satisfies the planner.
- Unknown or mismatched game identity/schema, stale save observations, missing purchase proof, unreviewed reset coverage, and uncertain action records fail closed. Reset, abdication, and excavation settings default off.
- Ordinary observations do not scan the process heap. Save decoding and its fingerprint use the same byte snapshot. The HUD observation cache avoids blocking UI refreshes, and idle scheduling backs off when waiting or paused.
- Semantic visual matching scales with the visible client viewport. A target click is bound to the recognized frame dimensions and is rejected if the client is resized or minimized before dispatch. Minimized/background input is not claimed as working.
- Installer checks native command exit codes; clean source verification is pinned to Python 3.12; release archives are built atomically from committed Git content only.

## Verification on this branch

`scripts/Verify-Repository.ps1` completed on commit `ebd43d7df16db422f60cbff2554c7298d5998679`: compile passed, installed-checkout suite **412 passed, 5 skipped**, and source-only archive suite **412 passed, 5 skipped**. The five skips require private visual screenshots/icons omitted from a clean checkout. Responsive visual matching was separately exercised against the ignored GemPower fixture at 976x669, 781x535, and 1171x803; all returned the proportionally scaled expected center. This was image matching only, not a live click/purchase test.

The installed game was observed read-only at R24 with roughly `6.83e72` gems versus the 4.3.22 A0 R25 threshold `1e99`. No live input was sent, and no reset, purchase, Egg, Dragon stage, or achievement was verified. The available live state therefore cannot demonstrate the irreversible or later-stage flows. Windows actions require a visible game window and live semantic recognition; minimized input remains unsupported.

## Local installation safety checkpoint

Before the updated HUD launch, `state/bot_config.json` at the original installation was copied to ignored `state/bot_config.before-safe-pause-20261106-053315.json`, then set to `paused=true`, `auto_abdicate=false`, `auto_reincarnate=false`, `auto_excavate=false`; `state/STOP` was created. `Install.ps1 -Dev` preserved this configuration and recognized the installed 4.3.22 game with zero network requests and zero game input. The existing desktop shortcut then launched the HUD. Its visible state reported `Bot Paused`, displayed STOP and Emergency Stop, and showed current R24 with Dragon counter requirements as UNKNOWN. No game click, purchase, or reset was performed.

## Remaining acceptance work

Keep actual progression marked partial until the counter updater, reset review/calibration, purchases, and trophy outcome are evidenced. Do not bypass reset gates or claim minimized automation.
