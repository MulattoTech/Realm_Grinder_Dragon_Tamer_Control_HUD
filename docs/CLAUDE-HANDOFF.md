# Claude continuation handoff

## Mission
Finish the existing Realm Grinder Dragon Tamer Control HUD into a highly configurable, genuinely idle-efficient autopilot capable of progressing from the user's legitimate game state through R46 and the Dragon Tamer unlock path.

Do not rebuild the app. The existing Gemini-built Tk/Win32 HUD and Python automation stack are the product being improved.

## Source of truth
Use the latest pushed GitHub branch/main, not assumptions from an old local folder. Before editing:
```powershell
git fetch origin --prune
git status --short --branch
git log -5 --oneline --decorate
.\Install.ps1 -Dev
```

Read, in order:
1. `AGENTS.md`
2. `README.md`
3. `docs/CURRENT-HANDOFF.md`
4. `docs/AUTOPILOT-TARGET-ARCHITECTURE.md`
5. newest `docs/VERIFICATION-*.md`

Historical handoffs are evidence/history, not current directives.

## Verified portable baseline
The reconciliation pass preserved all unique Sep. 24 local work in GitHub before modification.
The fully provisioned local suite reached 257 passing tests. A committed source-only checkout reached 252 passing tests with 5 explicit skips for private visual fixtures.

Do not reduce those gates. Add tests for every consequential action path you change.
## Priority implementation order
1. **Reincarnation transaction**
   - Calibrate and require a full semantic confirmation path comparable to Abdication.
   - Produce and verify the same-R permanent-milestone audit.
   - Preserve transaction ledger/reconciliation and no-duplicate-input behavior.

2. **R24 -> R46 deterministic progression**
   - Validate version-specific gem thresholds, builds, alignment/faction transitions, research/unlocks, and post-R40 assumptions.
   - Encode strategy as local policy/FSM, not prompt text.
   - Every policy transition must have explicit preconditions, action, proof, recovery, and timeout/backoff.

3. **Dragon unlock FSM**
   - R46 prerequisite -> egg eligibility/excavation -> Hatch! -> Drakeling -> Dragon -> Elder Dragon -> Dragon Tamer ownership verification.
   - Timed stages must persist across process restarts and must not fabricate elapsed time.

4. **Idle scheduler**
   - Replace unnecessary fixed-rate work with adaptive backoff and state-change wakeups.
   - Avoid screenshots and UI probing when waiting.
   - Keep one worker/action owner and preserve pause/STOP semantics.

5. **HUD configurability**
   - Keep the current HUD but improve information hierarchy and controls.
   - Add Observe / Assist / Autopilot modes, action permissions, strategy knobs, scheduler limits, and optional supervisor settings.
   - Surface exact blocker/evidence instead of optimistic status text.

6. **Optional model supervisor**
   - Provider-neutral interface; Claude Sonnet/Opus should be optional.
   - Never require a model for normal purchase/click/spell/reset loops.
   - Wake only on meaningful events/policy gaps and send compact state packets.
## Non-negotiable safety/evidence constraints
- Read game memory only; never write/inject.
- Never edit or synthesize a Realm Grinder save to advance the account.
- Never invoke Steam achievement APIs.
- Consequential UI actions require semantic evidence and post-action state proof.
- Do not silently focus/restore the game when a policy says it must remain undisturbed.
- Do not claim minimized/background support for an action until that action is actually verified under that condition.
- Unknown mechanics stay blocked/reference-only.
- Runtime/private artifacts stay ignored and out of releases.

## Definition of done for the next major milestone
A fresh GitHub checkout can:
- install with `Install.ps1 -Dev`;
- pass `scripts/Verify-Repository.ps1`;
- launch the existing HUD;
- reconstruct required public/generated metadata through bootstrap;
- run deterministic automation without any model/API dependency;
- stop/restart without losing policy state;
- demonstrate one verified Abdication and one verified Reincarnation on legitimate live state when naturally eligible;
- package with `scripts/Build-Release.ps1`.

For every completed milestone, update `docs/CURRENT-HANDOFF.md`, add a dated verification report, commit, push, and leave the repo clean.
