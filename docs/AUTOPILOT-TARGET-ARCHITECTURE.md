# Target architecture: idle-efficient configurable autopilot

The goal is a Realm Grinder bot that can run unattended for long periods without needing an LLM in the action loop.

## Core rule
Ordinary gameplay must be deterministic local software. An optional Claude/Astra/OpenAI supervisor is a sparse strategic layer, not the click driver.

## Layers
1. **State plane** - read decoded save, verified process memory, and bounded UI observations.
2. **Policy engine** - finite-state progression policy for faction/build/setup, production, Abdication, Reincarnation, Dragon unlock stages, and recovery.
3. **Action plane** - semantic verified actions with one writer and transaction proofs.
4. **Scheduler** - adaptive polling/backoff; wake on meaningful state changes rather than fixed high-frequency loops.
5. **HUD** - existing Control HUD shows mode, objective, state age, next action, blocker, ETA confidence, safety gates, and optional model status.
6. **Supervisor adapter** - optional provider-neutral event interface for difficult decisions only.

## Model wake events
A model may be called for:
- a new reincarnation/ascension policy boundary;
- a newly unlocked mechanic without a verified local policy;
- repeated deterministic recovery failure;
- conflicting source/mechanic evidence;
- unknown UI or state;
- user-requested replanning.

Do not call a model after every click, purchase, spell cycle, or polling tick.
## Compact supervisor packet
The future provider adapter should send a compact JSON packet containing only:
- objective and current milestone;
- reincarnation/ascension/faction/alignment;
- current and potential gems plus next threshold;
- build verification and missing prerequisites;
- Dragon-stage state;
- recent significant actions/errors;
- explicit wake reason.

Static instructions should be cached when the provider supports caching. Persist decisions locally so the next call does not need the entire chat/log history.

## Idle efficiency
- Exponential/adaptive backoff while waiting on production or timed Dragon stages.
- Event-driven wakeups on save fingerprint/state transitions where possible.
- No screenshot capture unless a semantic action needs pixels.
- No model call when a local policy can decide.
- No duplicate workers.
- No busy-looping when paused, blocked, minimized incompatibly, or waiting on a timer.

## Customization
Expose policy knobs in the existing HUD/config:
- automation mode: Observe / Assist / Autopilot;
- allowed consequential actions;
- preferred factions/builds;
- Abdication strategy and minimum gain;
- spell/mana policy;
- excavation policy;
- reset/reincarnation policy;
- model provider/model/thinking budget and wake-event categories;
- maximum action rate, polling floor/ceiling, and quiet mode.

All defaults remain fail-closed for consequential actions until their semantic verification is proven.
