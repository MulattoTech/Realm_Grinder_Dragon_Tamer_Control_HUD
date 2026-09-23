# In-place progression repair and source-backed planning
Goal: working selected-faction setup and verifiable progression, not a dashboard simulation.
Existing supplied design and this turn authorize native in-place implementation.
1. Preserve current state; reproduce and fix all 13 integration failures.
2. Index cached and retrievable requested wiki sources with provenance, gaps, licensing, and dates. Archived material stays dated; conflicting rules stay explicit.
3. Add dependency-driven selected paths: initial resources, Stoic Resistance, alignment, faction, bloodline, contracts, template selections, upgrades and spells. Verify purchases against game state.
4. Derive ETAs from observed progress; never assume a default 20-minute reincarnation or unknown future stages.
5. Preserve the HUD layout; connect controls to one worker and show the route, next prerequisite, blockers, telemetry and knowledge coverage.
6. Validate read-only memory against cast/regeneration; do not promote coincidental anchors.
7. Full tests, normal-input acceptance, save backup and handoff.
Constraints: no writes to game save/RAM, injection or achievement APIs; no blind reset sweeps or foreground theft; preserve pause and single action ownership; no unrelated changes.
