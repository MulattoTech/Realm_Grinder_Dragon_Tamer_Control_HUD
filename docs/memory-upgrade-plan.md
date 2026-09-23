# Realm Grinder memory telemetry implementation plan ? 2026-09-23
Goal: improve this bot in place; preserve the save decoder and PostMessage action plane; prove live telemetry and R24 -> R25 before claiming long-range success.
Spec: user-supplied Pasted markdown(20260923-073809).md, 74 sections.
Architecture: minimal ctypes read-only reader/scanner -> session-scoped mappings -> LiveStateProvider; shared verified actions; existing controller and HUD.
Constraints: only this project; game stays minimized; OpenProcess=0x410; no game/save writes, injection, time manipulation or achievement APIs; preserve STOP/paused.
No Git present. Rollback: backups/source-checkpoint-20260923-024147.zip (source, config, state and original SOL).

Tasks / ledger
- [x] Inspect and checkpoint; baseline pytest: 1 passed.
- [ ] Reader/scanner: failing tests, implementation, helper-process proof, passing suite.
- [ ] Save semantics: separate current/max mana and spell timer/active time; decoder concurrency; tests.
- [ ] Provider: session invalidation, fallback, provenance/confidence, atomic health; tests.
- [ ] Live mana: launch minimized, validate exact executable, scan/cast/regen twice; evidence.
- [ ] Shared verified actions: reset/purchase proofs, cancellation, one decision owner; tests.
- [ ] Actual-build verification, bracket switching, bounded stall handling and R24 diagnosis.
- [ ] Existing HUD/state capture integration; full suite, live acceptance and handoff.

Review focus: PID reuse; partial/guard reads; moving heaps/NaN; stale/partial saves; concurrent decoder and action callers; STOP during input sequences; no success based on clicks alone.
Baseline: R24, gems 2.407065527602823e68, faction=5, alignment=2, bFaction=0, mercSpell1=mercSpell2=0, saved mana=22158.
Spell 3 t=-1 but active0=520: current code incorrectly labels t as accumulated Hellfire time.
Game absent at first inspection; save ~2.9h old; STOP present; paused=true.
Defects: duplicate fast-track/AI resets; unconditional template success; unverified reset/Dragon transitions; ambiguous maximum mana and assistants.
Ruling: user requested in-place implementation of the supplied design; use focused checkpoint, not a new checkout. Keep gameplay paused until safety/provider tests pass.
