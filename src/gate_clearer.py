"""
Gate Clearer Engine for Realm Grinder Dragon Tamer.
Provides autonomous routines and 1-click clearance mechanisms for every locked gate:
- Gate 0: Reincarnation Progression to R46 (Abdication compounding, reincarnation, and optimal build deployment)
- Gate 1: Spiky Rough Egg Gate (Artifact 211 - automated excavations to 1,500+)
- Gate 2: Hatch! Gate (catalog validation required - 12h incubation and upgrade purchase)
- Gate 3: Drakeling Gate (catalog validation required - 12h Hellfire Blast time accumulation and upgrade purchase)
- Gate 4: Dragon Gate (catalog validation required - 3,750 Fairy Assistants surge and upgrade purchase)
- Gate 5: Elder Dragon Gate (catalog validation required - 50,000 Max Mana surge and Dragon Tamer achievement unlock)
"""

import os
import sys
import time
import json
import math
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from src.window import RealmGrinderWindow
from src.save_reader import extract_save_string_from_sol
from src.live_state import get_live_game_state
from src.progression_actions import ProgressionActions
from src.runtime_safety import input_allowed, modal_dismissal_allowed
from src.config import load_config
from src.wiki_data import (
    DRAGON_UNLOCK_STAGES,
    get_recommended_build,
    get_reincarnation_gem_requirement
)

import win32gui
import win32con

BACKUP_DIR = os.path.join(WORKSPACE_DIR, "backups")
STATE_FILE = os.path.join(WORKSPACE_DIR, "state", "dragon_tamer_state.json")
LOG_FILE = os.path.join(WORKSPACE_DIR, "logs", "bot.log")


class GateClearer:
    def __init__(self,window=None,actions=None):
        self.window=window or RealmGrinderWindow()
        self.actions=actions or ProgressionActions(self.window)

    def send_hover_click(self,cx,cy,delay_after=0.05):
        if not input_allowed(self.window): return False
        self.window.click(cx,cy,delay_after=delay_after)
        return True

    def send_key(self,ch,delay_after=0.015):
        if not input_allowed(self.window): return False
        self.window.press_key(ch,delay_after=delay_after)
        return True

    def open_tab(self, tab_name: str):
        """Switches to the specified left sidebar tab reliably."""
        tab_coords = {
            "upgrades": (30, 160),
            "excavations": (30, 235),
            "research": (30, 310),
            "trophies": (30, 420),
            "challenges": (30, 510)
        }
        coord = tab_coords.get(tab_name.lower())
        if not coord:
            return
        self.send_hover_click(coord[0], coord[1], delay_after=0.3)

    def buy_all_upgrades(self):
        return self.actions.purchase_all('upgrades')

    def buy_all_buildings(self):
        return self.actions.purchase_all('buildings')

    def dismiss_modals(self, force: bool = False):
        """Close only a pixel-verified Offline Production dialog; never guess at modal controls."""
        if not modal_dismissal_allowed(self.window):
            return False
        from src.semantic_ui import locate_offline_production_dialog
        frame = self.window.capture()
        target = locate_offline_production_dialog(frame)
        if not target:
            return False
        self.window.click(*target['close'], delay_after=0.15, auto_scale=False)
        # Verify the specific modal disappeared; do not send another input on uncertainty.
        remaining = locate_offline_production_dialog(self.window.capture())
        return remaining is None

    def backup_save(self) -> str:
        """Creates an immediate verified safe backup of the live save."""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = os.path.join(BACKUP_DIR, f"gate_clearer_backup_{ts}.txt")
        raw_str = extract_save_string_from_sol()
        with open(target, "w") as f:
            f.write(raw_str)
        logging.info(f"GateClearer created save backup: {target}")
        return target

    # =========================================================================
    # GATE 0: REINCARNATION PROGRESSION (R24 -> R46)
    # =========================================================================
    def clear_reincarnation_gate(self):
        return self.actions.advance_reincarnation()

    # =========================================================================
    # GATE 1: SPIKY ROUGH EGG (Artifact 211 - 1,500 Excavations)
    # =========================================================================
    def clear_excavation_gate(self,target_excavations=1500):
        return self.actions.excavate(target_excavations)

    # =========================================================================
    # GATE 2: HATCH! UPGRADE (Upgrade 1244 - 12h Incubation)
    # =========================================================================
    def clear_hatch_gate(self):
        return self.actions.purchase_milestone('hatch')

    # =========================================================================
    # GATE 3: DRAKELING UPGRADE (Upgrade 1245 - 12h Hellfire Blast)
    # =========================================================================
    def clear_drakeling_gate(self):
        return self.actions.purchase_milestone('drakeling')

    # =========================================================================
    # GATE 4: DRAGON UPGRADE (Upgrade 1246 - 3,750 Fairy Assistants)
    # =========================================================================
    def clear_dragon_gate(self):
        return self.actions.purchase_milestone('dragon')

    # =========================================================================
    # GATE 5: ELDER DRAGON (Upgrade 1247 / Trophy 466)
    # =========================================================================
    def clear_elder_dragon_gate(self):
        return self.actions.purchase_milestone('elder_dragon')

    # =========================================================================
    # MASTER SOLVER: AUTO-CLEAR ACTIVE GATE
    # =========================================================================
    def auto_clear_active_gate(self):
        return self.actions.auto_clear()
