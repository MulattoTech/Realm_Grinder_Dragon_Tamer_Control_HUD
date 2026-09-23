"""
Skynet Omniscient AI Optimization Engine for Realm Grinder Dragon Tamer.
Provides mathematical modeling, real-time derivative analysis, inflection-point detection,
optimal build selection, and automated multi-reincarnation pathfinding to R46+.
"""

import time
import math
from typing import Dict, Any, List, Optional, Tuple
from collections import deque


class GemVelocityTracker:
    """
    Computes real-time calculus derivatives of gem and coin accumulation.
    Tracks velocity (dG/dt) and acceleration (d^2G/dt^2) to detect exact
    saturation inflection points for mathematically optimal abdications.
    """
    def __init__(self, history_size: int = 30):
        self.history = deque(maxlen=history_size)
        self.peak_velocity = 0.0
        self.run_start_time = time.time()
        self.last_pot_gems = 0.0

    def reset_run(self):
        self.history.clear()
        self.peak_velocity = 0.0
        self.run_start_time = time.time()
        self.last_pot_gems = 0.0

    def record_sample(self, pot_gems: float, coins: float) -> Dict[str, float]:
        now = time.time()
        self.history.append((now, pot_gems, coins))

        if len(self.history) < 2:
            return {
                "velocity": 0.0,
                "acceleration": 0.0,
                "efficiency": 0.0,
                "saturation": 0.0,
                "elapsed_seconds": now - self.run_start_time
            }

        # Calculate instantaneous velocity over recent window
        t_prev, g_prev, _ = self.history[-2]
        dt = max(0.001, now - t_prev)
        dg = max(0.0, pot_gems - g_prev)
        v_current = dg / dt

        # Update peak velocity for this run
        if v_current > self.peak_velocity:
            self.peak_velocity = v_current

        # Calculate acceleration (change in velocity)
        acceleration = 0.0
        if len(self.history) >= 3:
            t_older, g_older, _ = self.history[-3]
            dt_old = max(0.001, t_prev - t_older)
            v_older = max(0.0, g_prev - g_older) / dt_old
            acceleration = (v_current - v_older) / dt

        # Calculate saturation ratio (how much current speed has decayed from peak)
        saturation = 0.0
        if self.peak_velocity > 0:
            saturation = 1.0 - min(1.0, v_current / self.peak_velocity)

        return {
            "velocity": v_current,
            "acceleration": acceleration,
            "saturation": saturation,
            "elapsed_seconds": now - self.run_start_time
        }


class SkynetOptimizationCore:
    """
    Omniscient decision-making brain.
    Evaluates live game metrics against mathematical optimization criteria to determine
    the single most productive action at any given millisecond.
    """
    def __init__(self):
        self.velocity_tracker = GemVelocityTracker()
        self.last_abdication_gems = 0.0
        self.consecutive_stalls = 0

    def evaluate(self, game_st: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an omniscient evaluation of the current game state.
        Returns a prioritized strategic directive with detailed reasoning.
        """
        r = game_st.get("reincarnation", 0)
        gems = game_st.get("gems", 0.0)
        coins = game_st.get("coins", 0.0)
        excavations = game_st.get("excavations", 0)
        has_egg = game_st.get("has_egg", False)
        hellfire = game_st.get("hellfire_time", 0)
        assistants = game_st.get("assistants", 0)
        mana = game_st.get("mana", 0)

        # Potential gems: use the value from save_reader which correctly uses
        # coins_this_abdication (statsReset) — the value shown on the in-game Abdicate button.
        pot_gems = game_st.get("potential_gems", 0.0)

        # Required gems for Reincarnation
        from src.wiki_data import get_reincarnation_gem_requirement, get_recommended_build
        req_gems = get_reincarnation_gem_requirement(r)

        # Calculus velocity update
        v_metrics = self.velocity_tracker.record_sample(pot_gems, coins)
        velocity = v_metrics["velocity"]
        saturation = v_metrics["saturation"]
        elapsed = v_metrics["elapsed_seconds"]
        ultron_burst = bool(cfg.get("ultron_burst", True))

        # Strategy Decision Tree
        decision = "COMPOUND_PRODUCTION"
        priority = 10
        reasoning = []
        if ultron_burst:
            reasoning.append("⚡ [UltronBurst Mode Active]")
        action_type = "IDLE"
        payload = {"ultron_burst": ultron_burst}

        # -------------------------------------------------------------
        # 1. Gate 5: Dragon Tamer Claim (Final Stage)
        # -------------------------------------------------------------
        if has_egg and r >= 46:
            # Check dragon stages
            if mana >= 50000 and coins >= 1e73:
                decision = "CLAIM_DRAGON_TAMER"
                priority = 100
                action_type = "PURCHASE_ELDER_DRAGON"
                reasoning.append("Elder Dragon requirements met! 50k Max Mana + 1e73 coins achieved.")
                return self._package(decision, priority, action_type, reasoning, payload)

        # -------------------------------------------------------------
        # 2. Gate 0: Reincarnation Ready Check (Top Priority in R24-R45)
        # -------------------------------------------------------------
        if r < 46:
            if gems >= req_gems:
                decision = "REINCARNATE_NOW"
                priority = 90
                action_type = "EXECUTE_REINCARNATION"
                reasoning.append(f"Gems ({gems:.2e}) meet required threshold ({req_gems:.2e}) for R{r+1}!")
                return self._package(decision, priority, action_type, reasoning, payload)

            if pot_gems >= req_gems:
                decision = "ABDICATE_FOR_REINCARNATION"
                priority = 85
                action_type = "EXECUTE_ABDICATION"
                reasoning.append(f"Potential gems ({pot_gems:.2e}) exceed required threshold for R{r+1}! Abdicating to trigger Reincarnation.")
                return self._package(decision, priority, action_type, reasoning, {"gems_to_claim": pot_gems})

            # ---------------------------------------------------------
            # 3. Mathematical Abdication Inflection Point
            # ---------------------------------------------------------
            gem_multiplier = pot_gems / max(1.0, gems)
            min_mult = float(cfg.get("abdicate_multiplier_threshold", 2.0))

            # Optimal abdication condition:
            # A) Gem multiplier exceeds threshold (e.g. >= 2.0x, or >= 50x for deep runs)
            # B) Growth velocity has saturated / plateaued (diminishing returns)
            # C) Run has lasted at least 25 seconds to establish momentum
            is_significant_gain = (gem_multiplier >= min_mult) and (pot_gems > 1e12)
            is_plateaued = (saturation > 0.85) and (elapsed > 40.0)

            if is_significant_gain and (gem_multiplier >= 2.0 or is_plateaued):
                decision = "OPTIMAL_ABDICATION"
                priority = 70
                action_type = "EXECUTE_ABDICATION"
                reasoning.append(
                    f"Mathematical inflection point reached: +{pot_gems:.2e} gems "
                    f"({gem_multiplier:.1f}x gain). Velocity saturation: {saturation*100:.1f}%."
                )
                return self._package(decision, priority, action_type, reasoning, {"gems_to_claim": pot_gems})

        # -------------------------------------------------------------
        # 4. Gate 1: R46 Spiky Rough Egg Hunting
        # -------------------------------------------------------------
        if r >= 46 and not has_egg:
            decision = "EXCAVATE_FOR_EGG"
            priority = 80
            action_type = "EXECUTE_EXCAVATION"
            rem = max(0, 1500 - excavations)
            if rem > 0:
                reasoning.append(f"Excavating to 1,500 milestone ({rem} remaining to unlock Egg drops).")
            else:
                p_drop = min(1.0, math.sqrt(max(0, excavations - 1500)) / 10000.0)
                reasoning.append(f"Digging for Spiky Rough Egg artifact. Current drop probability per dig: ~{p_drop*100:.3f}%.")
            return self._package(decision, priority, action_type, reasoning, payload)

        # -------------------------------------------------------------
        # 5. Routine High-Speed Production Routine
        # -------------------------------------------------------------
        rec_build = get_recommended_build(r, gems)
        reasoning.append(
            f"Active Reincarnation R{r}. Target: {req_gems:.2e} gems. "
            f"Build: {rec_build['name']} ({rec_build['faction']}). "
            f"Current potential gems: {pot_gems:.2e} ({pot_gems/max(1.0, gems):.2f}x)."
        )

        return self._package(
            decision="COMPOUND_PRODUCTION",
            priority=10,
            action_type="ROUTINE_CYCLE",
            reasoning=reasoning,
            payload={
                "recommended_build": rec_build,
                "velocity": velocity,
                "saturation": saturation,
                "elapsed": elapsed
            }
        )

    def _package(self, decision: str, priority: int, action_type: str, reasoning: List[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "decision": decision,
            "priority": priority,
            "action_type": action_type,
            "reasoning": " ".join(reasoning),
            "payload": payload,
            "timestamp": time.time()
        }
