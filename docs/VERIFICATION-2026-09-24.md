# Verification report - 2026-09-24

## Source verification

| Check | Result |
| --- | --- |
| Python 3.12 full project suite | Last recorded checkpoint: 254 passed; later Abdication transaction edits are not covered by that run |
| `git diff --check` | Passed at the recorded checkpoint; not rerun for later edits |
| HUD reload | HUD PID 42500 reloaded at 11:22; game PID 5400 remained unchanged |
| Assistant-initiated game input | Closed and reopened only the Abdication dialog; no confirmation or reset was sent |
| Assistant save write or game process restart | None |
| Dragon Tamer achievement | Not achieved |

## Watch checkpoint - 2026-09-24 11:45 CDT

The bounded 15-minute read-only watcher exited normally without detecting an excavation, Royal Market purchase, or Abdication. A fresh decode still reports R24/A0 Fairy, `5.1893444080398605e69` gems, `3.5457585943893085e65` potential gems, `6.286202004842822e142` run coins, 1,540 excavations, and no egg (fingerprint `1790268287739328300:6162`, age about 25 seconds). Gem Power ID 20 is owned; Royal Market ID 579 is not.

Game PID 5400 and HUD PID 42500 remain open. The HUD is paused; the loaded Automatic planner selects active Fairy maintenance and retains Neutral Mercenary for the next run. A direct Dragon Tamer rule plan identifies Reach R46 as the next prerequisite. The UI selection remains Build only; the save and game were not changed by the watcher.

## Runtime route checkpoint - 2026-09-24 11:22 CDT

The HUD reloaded after the Automatic-route source change. With the bot paused, its live planner output is `maintain_faction` on active Fairy, retains `selected_path=Automatic`, and records Neutral Mercenary as the next-run recommendation. This confirms the planner loaded and took the intended branch; it does not prove a gameplay purchase or production improvement.

The live save is still R24/A0, Fairy/alignment 1, `5.1893444080398605e69` gems, `3.1543185321382033e65` potential gems, `4.974862701095254e142` run coins, 1,540 excavations and no egg (fingerprint `1790266967758152100:6170`, age about 11 seconds). The paused HUD remains PID 42500, the game remains PID 5400, and the refreshed Abdication dialog remains unconfirmed. User-planned excavation, Royal Exchange purchase and Abdication are not yet reflected.

## Latest live checkpoint - 2026-09-24 11:16 CDT

The latest decoded save reports R24/A0, Fairy/alignment 1, `5.1893444080398605e69` gems, `3.0327892775804614e65` potential gems, `4.598905401103508e142` run coins, 1,540 excavations and no egg (fingerprint `1790266547755514500:6166`, age about 28 seconds). Game PID 5400 remains open. The HUD PID 34236 is paused with Automatic selected, `state/STOP` present, and the worker stopped.

After closing and reopening the stale dialog, the live Abdication confirmation showed `7.92e60` gems and a `966.60%` production increase. It was left unconfirmed. The user's intended excavation, Royal Exchange purchase, and Abdication were not present in the save at this checkpoint.

The user approved changing Automatic route planning to continue the recognized active faction when its selected next-run build requires an Abdication first. The active-faction plan and next-run recommendation are now recorded separately in source. The current HUD has not loaded this source change. No tests were run for it; the last recorded full suite predates both the Abdication transaction changes and this route correction.

## Live progression checkpoint

The current save reader reports healthy, connected live state: R24, Ascension 0, faction 0, alignment 1, 5.1893444080398605e69 gems, 1.3932882113177629e65 potential gems, 1,540 excavations and no Spiky Rough Egg. The last observed fingerprint is `1790260475372117200:6166`. The R24 reincarnation gem requirement is 1e99, so the save is far below that threshold.

At the later 2026-09-24 live check, the existing worker was active (`paused=false`, no `state/STOP`, `is_running=true`) and logged `COLLECT_RESOURCES` cycles about every seven seconds. A fresh decoded save (fingerprint `1790263470763174000:6170`, about 23 seconds old) showed R24/A0, 5.1893444080398605e69 gems, 2.1483910876496505e65 potential gems, 2.307792132746224e142 coins this run, 1,540 excavations and no egg. Coins rose from about 2.165e142 in the 10:18 history sample; reincarnation and current gems had not advanced. Config remains `Build only`, named target `Reach R46`, Fairy path. This records normal worker activity, not a reset or achievement.

The live HUD PID 25136 started at 09:40; `src/progression_actions.py` was updated at 10:05. Since Python does not reload imported modules, this running HUD has not loaded the new pixel-gated Abdication path. Its old transaction path is fail-closed by the empty verified-action profile. Pause the bot before closing and reopening only the HUD; leave the game running. Then review the goal selection before resuming.

At the current R24 save, a read-only planner comparison shows `Automatic` selects `Neutral Mercenary (Assisted Advancement)` with a template; configured `Fairy` selects generic `Fairy faction progression` with no template. The live save is Fairy/alignment 1. The Mercenary recommendation is for a later run: faction/alignment choice changes at Abdication, not during this run ([Mercenary faction guide](https://realm-grinder.fandom.com/wiki/Mercenary)). Build verification remains false because the current-version ownership manifest is absent. Across a 20-second observation, save ownership stayed at 322 of 350 upgrade records and 25,250 total buildings while run coins increased from 3.084e142 to 3.106e142. This is production growth without a newly purchased upgrade/building in that interval. The Fairy selection was not changed.

At 10:35 the worker logged one `WinError 5` while atomically replacing `state/build_verification.json`; the existing file ACL allows modification, and a subsequent cycle replaced the file successfully by 10:36. The worker returned to `is_running=true` by 10:37 and continued production. A later save read (fingerprint `1790265037760608800:6170`, about 26 seconds old) remained R24/A0 with 5.1893444080398605e69 gems, 2.5673123684031356e65 potential gems, 3.2955463984778593e142 coins this run, 1,540 excavations and no egg. The 1e99 next-R cost is 5.19e-30 of current gems; potential gems are 4.95e-5 of current gems, so no reset is presently eligible. Build verification remains false because the current-version ownership manifest is not verified.

The old `last_action_result.json` still says a Fairy Trade Treaty was blocked by an unresolved action, but the authoritative `pending_action.json` is reconciled as `RECONCILED_NO_TEMPLATE_TEXT`. Treat the result message as stale display data; no current pending action is unresolved.

The reviewed Hatch!, Drakeling, Dragon and Elder Dragon rules previously excluded ascension 0, even though the R46 progression guide states R46+ for the egg and stage requirements without an ascension-1 prerequisite. Their rule scopes now include ascensions 0 and 1. A synthetic, fully satisfied Hatch! fixture is actionable at R46/A0; this verifies planning scope only, not live availability or purchase.

The Abdication and Reincarnation button labels were recognized in a fresh live 1180x810 frame at client points (215,20) and (380,20). Later, the user opened the Abdication confirmation and the paired title/close/confirm detector matched it live at the same client size: scores 0.9999998, 0.9964 and 0.99997, with close point (1053,276) and confirm point (522,488). No button was clicked and no reset input was sent. The detector evidence was not saved as a screenshot because a later shell-side window reacquisition failed.

The current source wires Abdication through a guarded, fresh-save transaction, but that newer path has not been run or covered by the last recorded full-suite result. A focused test attempt previously failed during pytest temporary-directory setup, before the test body ran.

The HUD is paused and `state/STOP` exists. The selected goal remains `Build only`; the saved named target is `Reach R46`. Start explains that Build only pauses once the active build verifies, while Named goal provides explicit R46 tracking. The message does not block Start. Settings were not changed.

The pending `MERCENARY_TEMPLATE` transaction remains in the ledger with its original ID, before snapshot, error and backup path. It is now `RECONCILED_NO_TEMPLATE_TEXT` because the recorded exception occurs before the template input field click and typing loop. A fresh same-R save snapshot was attached. This is an audited no-template-text resolution, not a claim that the template was applied or that the achievement progressed.

## Remaining automation gates

- `state/ui_actions.json` has no verified actions and no calibrated client size. Abdication now has a live-validated pixel-gated transaction path; Reincarnation remains uncalibrated and unwired.
- `state/permanent_milestone_audit.json` is absent. Reincarnation requires a verified audit for the current R as well as sufficient gems and UI transaction evidence.
- Dragon Tamer trophy ownership and Steam achievement status remain unverified and unearned.
- Changes are in the working tree. Git staging was denied because this environment could not create `.git/index.lock`; nothing was committed or pushed.
