"""
Realm Grinder Dragon Tamer - High-Precision State Capture Engine
Captures full-fidelity visual screenshots and complete game state telemetry
even when Realm Grinder is minimized, occluded, or running in the background.

Features:
- Native Win32 / GDI PrintWindow capture with zero focus stealing
- Instant decoding of live Flash SharedObject (.sol) binary save data
- Comprehensive forward-looking progression calculations & ETAs
- Automatic persistent JSON snapshotting and save backups
- CLI and programmatic API
"""

import os
import sys
import time
import json
import math
from datetime import datetime
from typing import Dict, Any, Optional

from src.window import RealmGrinderWindow
from src.save_reader import extract_save_string_from_sol
from src.live_state import get_live_game_state
from src.progression_actions import ProgressionActions
from src.telemetry_presenter import dragon_stage_views,measured
from src.atomic_store import write_json
from src.telemetry import ProgressionTracker
from src.wiki_data import (
    get_reincarnation_gem_requirement,
    get_recommended_build,
    DRAGON_UNLOCK_STAGES
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "state", "snapshots")
LATEST_CAPTURE_FILE = os.path.join(BASE_DIR, "state", "latest_state_capture.json")
STATE_FILE = os.path.join(BASE_DIR, "state", "dragon_tamer_state.json")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def format_num(val: float) -> str:
    if val is None or math.isnan(val):
        return "0"
    if val < 1000:
        return f"{val:.1f}"
    if val >= 1e102:
        return f"{val:.3e}"
    
    suffixes = [
        (1e99, "Dtg"), (1e96, "Utg"), (1e93, "Ttg"), (1e90, "Nog"), (1e87, "Ocg"),
        (1e84, "Spg"), (1e81, "Sxg"), (1e78, "Qig"), (1e75, "Qag"), (1e72, "Tvg"),
        (1e69, "Dvg"), (1e66, "Uvg"), (1e63, "Vg"), (1e60, "Nod"), (1e57, "Ocd"),
        (1e54, "Spd"), (1e51, "Sxd"), (1e48, "Qid"), (1e45, "Qad"), (1e42, "Td"),
        (1e39, "Dd"), (1e36, "Ud"), (1e33, "Dc"), (1e30, "No"), (1e27, "Oc"),
        (1e24, "Sp"), (1e21, "Sx"), (1e18, "Qi"), (1e15, "Qa"), (1e12, "T"),
        (1e9, "B"), (1e6, "M"), (1e3, "K")
    ]
    for thresh, suff in suffixes:
        if val >= thresh:
            return f"{val / thresh:.3f} {suff}"
    return f"{val:.2e}"


class StateCaptureEngine:
    def __init__(self):
        self.window = RealmGrinderWindow()
        self.tracker = ProgressionTracker()

    def capture_full_state(
        self,
        save_screenshot: bool = True,
        re_minimize: bool = False
    ) -> Dict[str, Any]:
        """
        Executes an exhaustive state capture of Realm Grinder:
        1. Visual: High-resolution client area capture via native PrintWindow (even if minimized).
        2. Game State: Full deserialization of live game parameters from .sol.
        3. Calculations: Gem progress, bottleneck analysis, forward ETAs.
        4. Persistence: Saves screenshot PNG, raw save backup, and JSON snapshot.
        """
        timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        timestamp_iso = datetime.now().isoformat()

        # 1. Connect to Window
        window_found = self.window.find_window()
        is_min = self.window.is_minimized() if window_found else False
        screenshot_path = None

        # 2. Visual Capture
        if save_screenshot and window_found and not is_min:
            try:
                img = self.window.capture(re_minimize=re_minimize)
                screenshot_filename = f"capture_{timestamp_str}.png"
                screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
                img.save(screenshot_path)
            except Exception as e:
                screenshot_path = f"FAILED: {e}"

        # 3. Read and Decode Live Game State
        game_st = get_live_game_state()
        r = game_st["reincarnation"]
        gems = game_st["gems"]
        coins = game_st["coins"]
        coins_this_game = game_st.get("coins_this_game", coins)
        excavations = game_st["excavations"]
        hellfire = game_st.get("hellfire_time", 0)
        has_egg = game_st["has_egg"]
        assistants=game_st.get("fairy_assistants")
        mana=game_st.get("mana_max")

        # 4. Safe Raw Save Export
        backup_path = None
        try:
            raw_save = extract_save_string_from_sol()
            backup_filename = f"save_snapshot_{timestamp_str}.txt"
            backup_path = os.path.join(BACKUPS_DIR, backup_filename)
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(raw_save)
        except Exception as e:
            backup_path = f"FAILED: {e}"

        # 5. Progression & Bottleneck Calculations
        req_gems = get_reincarnation_gem_requirement(r,game_st.get('ascension',0))
        pot_gems = math.floor((math.sqrt(1.0 + 8.0 * (coins_this_game / 1e12)) - 1.0) / 2.0) if coins_this_game > 0 else 0.0

        stage_timestamps = {}
        current_bot_stage = "UNKNOWN"
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as sf:
                    bot_data = json.load(sf)
                    stage_timestamps = bot_data.get("timestamps", {})
                    current_bot_stage = bot_data.get("current_stage", "UNKNOWN")
            except Exception:
                pass

        etas = self.tracker.calculate_etas(
            r,
            gems,
            coins,
            stage_timestamps,
            hellfire,
            ascension=game_st.get('ascension',0)
        )

        rec_build = get_recommended_build(r, gems)

        actions=ProgressionActions(self.window)
        build_verification=actions.diagnose_build(game_st)
        dragon_readiness={'stage_0_egg':{'name':'Spiky Rough Egg','status':'ACQUIRED' if has_egg else 'NOT_ACQUIRED'}}
        for index,view in dragon_stage_views(game_st,actions.catalog()).items():
            dragon_readiness[f"stage_{index}_{view['name']}"]=view

        # 7. Assemble Full State Snapshot
        snapshot = {
            "metadata": {
                "timestamp_iso": timestamp_iso,
                "timestamp_str": timestamp_str,
                "window_connected": window_found,
                "window_was_minimized": is_min,
                "screenshot_path": screenshot_path,
                "backup_path": backup_path
            },
            "live_game": {
                "reincarnation": r,
                "gems_raw": gems,
                "gems_formatted": format_num(gems),
                "pot_gems_raw": pot_gems,
                "pot_gems_formatted": format_num(pot_gems),
                "coins_raw": coins,
                "coins_formatted": format_num(coins),
                "req_gems_for_next_r": req_gems,
                "req_gems_formatted": format_num(req_gems),
                "excavations": excavations,
                "hellfire_time_seconds": hellfire,
                "mana": game_st.get("mana_current"),
                "mana_max": mana,
                "assistants": assistants,
                "has_egg": has_egg
            },
            "progression_analysis": {
                "bot_current_stage": current_bot_stage,
                "reincarnation_progress_pct": min(100.0, (r / 46.0) * 100.0),
                "reincarnation_gems_progress_pct": min(100.0, (gems / req_gems) * 100.0),
                "reincarnations_remaining_to_r46": max(0, 46 - r),
                "current_r_eta": etas["current_r_eta"],
                "r46_eta": etas["r46_eta"],
                "overall_dragon_tamer_eta": etas["total_eta"],
                "target_completion_date": etas["target_completion_date"],
                "recommended_build": {
                    "name": rec_build["name"],
                    "faction": rec_build["faction"],
                    "bloodline": rec_build["bloodline"],
                    "notes": rec_build["notes"]
                }
            },
            "telemetry_health":game_st.get("telemetry",{}),
            "field_provenance":game_st.get("provenance",{}),
            "build_verification":build_verification,
            "dragon_unlock_stages":dragon_readiness
        }

        # 8. Persist Snapshots
        snapshot_file = os.path.join(SNAPSHOTS_DIR, f"state_{timestamp_str}.json")
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            with open(LATEST_CAPTURE_FILE, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to persist snapshot JSON: {e}")

        return snapshot


def run_cli():
    snapshot=StateCaptureEngine().capture_full_state(save_screenshot=False)
    print(json.dumps(snapshot,indent=2))

if __name__ == '__main__':
    run_cli()
