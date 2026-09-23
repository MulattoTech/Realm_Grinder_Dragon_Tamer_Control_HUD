"""
Skynet Predictive Monte Carlo Simulation & Milestone Forecaster.
Provides mathematical models for:
- Spiky Rough Egg artifact probability distribution (P50, P90, P99 confidence intervals)
- Reincarnation progression velocity and exponential compounding extrapolation
- Accurate calendar-date countdowns for all 5 Dragon Tamer gates
"""

import math
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple


class MonteCarloArtifactForecaster:
    """
    Simulates artifact discovery probabilities based on exact Realm Grinder excavation formulas.
    For Spiky Rough Egg (Artifact 211):
    Requires R46+ and Excavation Depth >= 1,500.
    Drop chance per dig = sqrt(E - 1500) / 10000.
    """
    @staticmethod
    def calculate_egg_probabilities(current_excavations: int, target_confidence: float = 0.95) -> Dict[str, Any]:
        start_e = max(1500, current_excavations)
        
        # Calculate cumulative probability over successive digs
        cumulative_prob = 0.0
        p_fail = 1.0
        digs_needed = 0
        p50_digs = None
        p90_digs = None
        p99_digs = None

        max_sim_digs = 5000
        for d in range(1, max_sim_digs + 1):
            e = start_e + d
            p_drop = min(1.0, math.sqrt(e - 1500) / 10000.0)
            p_fail *= (1.0 - p_drop)
            cum = 1.0 - p_fail

            if p50_digs is None and cum >= 0.50:
                p50_digs = d
            if p90_digs is None and cum >= 0.90:
                p90_digs = d
            if p99_digs is None and cum >= 0.99:
                p99_digs = d
                break

        current_chance = math.sqrt(max(0, current_excavations - 1500)) / 10000.0 if current_excavations >= 1500 else 0.0

        return {
            "current_excavations": current_excavations,
            "current_dig_drop_chance": current_chance,
            "current_dig_drop_percent": current_chance * 100.0,
            "p50_digs_needed": p50_digs or 500,
            "p90_digs_needed": p90_digs or 1200,
            "p99_digs_needed": p99_digs or 2200,
            "is_eligible": current_excavations >= 1500
        }


class MilestoneForecaster:
    """
    Forecasts completion timestamps for all remaining Reincarnations and Dragon Quest gates.
    """
    @staticmethod
    def forecast_dragon_timeline(
        current_r: int,
        current_gems: float,
        current_coins: float,
        hellfire_time: float,
        has_egg: bool,
        stage_timestamps: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = datetime.now()

        # Gate 0: Reincarnation climb to R46
        reincs_left = max(0, 46 - current_r)
        
        # Estimate average time per R:
        # In early R (24-30), builds take ~1.5 - 2.5 hours per R with research
        # In mid-late R (31-45), ascension accelerates early phases, averaging ~2-3 hours
        avg_hours_per_r = 2.0
        r46_hours = reincs_left * avg_hours_per_r
        r46_date = now + timedelta(hours=r46_hours)

        # Gate 1: Egg Excavation
        # Takes ~15-30 minutes of excavation runs at R46
        egg_hours = 0.5 if not has_egg else 0.0

        # Gate 2: Hatch! Incubation (12 hours)
        hatch_hours = 12.0
        t_egg = stage_timestamps.get("egg_obtained")
        if t_egg:
            dt_egg = datetime.fromisoformat(t_egg)
            elapsed = (now - dt_egg).total_seconds() / 3600.0
            hatch_hours = max(0.0, 12.0 - elapsed)

        # Gate 3: Drakeling (12 hours Hellfire Blast active time)
        # Runs concurrently or sequentially
        rem_hf = max(0.0, (12.0 * 3600 - hellfire_time) / 3600.0)

        # Gate 4: Dragon (12 hours incubation)
        dragon_incubation_hours = 12.0
        t_drak = stage_timestamps.get("drakeling_purchased")
        if t_drak:
            dt_drak = datetime.fromisoformat(t_drak)
            elapsed = (now - dt_drak).total_seconds() / 3600.0
            dragon_incubation_hours = max(0.0, 12.0 - elapsed)

        # Gate 5: Elder Dragon (12 hours incubation)
        elder_hours = 12.0
        t_drag = stage_timestamps.get("dragon_purchased")
        if t_drag:
            dt_drag = datetime.fromisoformat(t_drag)
            elapsed = (now - dt_drag).total_seconds() / 3600.0
            elder_hours = max(0.0, 12.0 - elapsed)

        # Critical path calculation
        # If R < 46, gates 1-5 occur sequentially after R46, but Hellfire Blast is accumulating NOW!
        # Remaining Hellfire time will likely be 0 by the time R46 is reached!
        effective_hf_hours = max(0.0, rem_hf - r46_hours)

        total_quest_hours = r46_hours + egg_hours + hatch_hours + effective_hf_hours + dragon_incubation_hours + elder_hours
        completion_date = now + timedelta(hours=total_quest_hours)

        return {
            "current_r": current_r,
            "reincarnations_remaining": reincs_left,
            "r46_eta_hours": r46_hours,
            "r46_target_date": r46_date.strftime("%Y-%m-%d %H:%M"),
            "hellfire_hours_remaining": rem_hf,
            "total_estimated_hours": total_quest_hours,
            "target_completion_date": completion_date.strftime("%A, %b %d, %Y at %I:%M %p"),
            "formatted_eta": f"{int(total_quest_hours // 24)}d {int(total_quest_hours % 24)}h {int((total_quest_hours * 60) % 60)}m"
        }
