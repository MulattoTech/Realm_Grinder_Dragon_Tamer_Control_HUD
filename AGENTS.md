# Realm Grinder Dragon Tamer - agent contract

This repository is the source of truth. Do not treat any existing local checkout as authoritative when it differs from GitHub.

## Preserve the existing application
- Improve the current Gemini-built Control HUD in place; do not replace it with a new UI framework or rewrite the project from scratch.
- Read README.md, docs/CURRENT-HANDOFF.md, docs/CLAUDE-HANDOFF.md, and the newest verification report before editing.
- Keep game memory read-only. Never edit Realm Grinder saves, inject into the game process, or call Steam achievement APIs.
- Runtime state, saves, screenshots, logs, generated icon caches, credentials, and backups stay local and ignored.

## Evidence standard
- Never claim a reset, purchase, achievement, ETA, background-input guarantee, or mechanic is proven without current evidence.
- Source/reference coverage is not executable automation coverage.
- A clean source checkout must pass tools/verify_checkout.py before main is considered releasable.
- Preserve fail-closed behavior for uncertain consequential actions.
- One worker/action owner only; never create competing automation loops.

## Development workflow
- Fetch/reconcile GitHub before editing.
- Work on a branch, run scripts/Verify-Repository.ps1, commit, push, and then promote tested commits to main.
- Do not weaken tests or safety gates to make automation appear complete.
- Keep the HUD usable without any LLM/API connection.
- Prefer deterministic local logic for ordinary gameplay; reserve external models for sparse strategic exceptions.

## Target product behavior
The finished bot should be highly configurable, idle-efficient, event-driven, restart-safe, and observable. It should:
- read authoritative game state locally;
- execute deterministic policies without token usage;
- wake an optional model supervisor only for milestone transitions, unknown states, repeated failures, or policy gaps;
- persist compact state and decision history on disk;
- back off while waiting instead of polling aggressively;
- expose automation mode, current objective, next action, blockers, and model wake reason in the existing HUD.

## Release discipline
VERSION is the release version. scripts/Build-Release.ps1 creates the source artifact from committed Git content only. GitHub Releases are the supported redistribution point until an authorized Actions workflow is installed.
