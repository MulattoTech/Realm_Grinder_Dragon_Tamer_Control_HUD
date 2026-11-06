"""
State machine and autonomous orchestrator for Realm Grinder Dragon Tamer.
Constantly progresses the game through normal UI interaction:
- Background spell casting (hotkeys 1-6) and burst Tax Collection
- Autonomous building and upgrade purchasing using calibrated client coordinates
- Threshold-based abdication with automatic save backup
- Automatic reincarnation progression guided by G00F Not-a-Wiki knowledge base
- Dragon Unlock stages (0 through 4) execution at R46+
- Persistent state management and survival across process restarts
"""

import os
import sys

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import time
import json
import math
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import win32gui
import win32con

from src.window import RealmGrinderWindow
from src.save_reader import extract_save_string_from_sol
from src.live_state import get_live_game_state
from src.progression_actions import ProgressionActions, actual_dragon_stage
from src.runtime_safety import input_allowed, require_interactive_session, WorkerLease
from src.atomic_store import write_json
from src.config import CONFIG_FILE, load_config
from src.save_reader import SOL_PATH
from src.idle_scheduler import IdleScheduler
from src.telemetry import ProgressionTracker
from src.ai_engine import SkynetOptimizationCore
from src.guardian import ProcessGuardian
from src.forecaster import MilestoneForecaster, MonteCarloArtifactForecaster
from src.wiki_data import (
    DRAGON_UNLOCK_STAGES,
    get_recommended_build,
    get_reincarnation_gem_requirement,
    load_knowledge_base
)
from src.gate_clearer import GateClearer

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "dragon_tamer_state.json")
STOP_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "STOP")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "backups")
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "bot.log")

os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")]
)


class DragonBot:
    def __init__(self):
        self.window = RealmGrinderWindow()
        self.ai = SkynetOptimizationCore()
        self.guardian = ProcessGuardian()
        self.state = self.load_state()
        self.tracker = ProgressionTracker()
        self.actions = ProgressionActions(self.window)
        self.clearer = GateClearer(window=self.window, actions=self.actions)
        self.last_full_snapshot_time = 0.0

    def load_state(self) -> Dict[str, Any]:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Could not load state file: {e}")

        return {
            "current_stage": "DISCOVER",
            "detection_confidence": "HIGH",
            "current_known_r": 0,
            "timestamps": {
                "started": datetime.now().isoformat(),
                "last_check": None,
                "egg_obtained": None,
                "hatch_purchased": None,
                "drakeling_purchased": None,
                "dragon_purchased": None,
                "elder_dragon_purchased": None
            },
            "observed_hellfire_time": -1,
            "excavations": 0,
            "gems": "0",
            "latest_screenshot_path": None,
            "most_recent_backup": None,
            "retry_count": 0,
            "last_successful_action": "Initialized",
            "next_expected_action": "Perform game discovery and state inspection",
            "is_running": False
        }

    def save_state(self):
        write_json(STATE_FILE,self.state)

    def backup_save(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = os.path.join(BACKUP_DIR, f"realm-grinder-export-{timestamp}.txt")
        raw_str = extract_save_string_from_sol()
        with open(target, "w") as out:
            out.write(raw_str)
        self.state["most_recent_backup"] = target
        self.save_state()
        logging.info(f"Safe save backup created: {target}")
        return target

    def capture_screenshot(self, name_prefix: str = "state") -> str:
        im = self.window.capture()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{timestamp}.png")
        im.save(path)
        self.state["latest_screenshot_path"] = path
        self.save_state()
        return path

    def click_post(self,cx,cy,delay_after=0.04):
        if not input_allowed(self.window): return False
        self.window.click(cx,cy,delay_after=delay_after)
        return True  # Input dispatch only, not proof of game progress.

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
        if coord:
            self.click_post(coord[0], coord[1], delay_after=0.2)

    def send_key(self,ch,delay_after=0.015):
        if not input_allowed(self.window): return False
        self.window.press_key(ch,delay_after=delay_after)
        return True

    def is_upgrades_panel_open(self) -> bool:
        """Checks if the left upgrades panel is open without forcing capture if minimized."""
        if self.window.is_minimized():
            return True
        try:
            im = self.window.capture()
            p = im.getpixel((100, 30))
            # Upgrades panel top bar is dark slate/grey (r < 60, g < 60, b < 60)
            return p[0] < 60 and p[1] < 60 and p[2] < 60
        except Exception:
            return True

    def ensure_upgrades_panel_open(self):
        """Ensures upgrades panel is open safely without toggling it closed."""
        if not self.is_upgrades_panel_open():
            self.click_post(30, 160, delay_after=0.3)

    def buy_all_upgrades(self):
        return self.actions.purchase_all('upgrades')

    def purchase_secret_upgrades(self):
        """Clicks the 4 secret/hidden upgrade slots in Row 0 of Unpurchased Upgrades."""
        for ux in (95, 150, 205, 260, 315):
            self.click_post(ux, 175, delay_after=0.05)

    def buy_all_buildings(self):
        return self.actions.purchase_all('buildings')

    def dismiss_modals(self, force: bool = False):
        """Delegate to the pixel-verified, narrowly scoped modal handler."""
        return self.clearer.dismiss_modals(force=force)

    def cast_spells_combo(self):
        """Casts higher tier spells (6 through 2) in descending order."""
        for ch in ['6', '5', '4', '3', '2']:
            self.send_key(ch, delay_after=0.015)

    def burst_tax_collection(self, count: int = 25):
        """Fires a burst of Tax Collections (key 1)."""
        for _ in range(count):
            self.send_key('1', delay_after=0.008)

    def is_paused(self) -> bool:
        """Checks if the bot is currently paused by the user."""
        cfg = load_config()
        return bool(cfg.get("paused", False) or os.path.exists(STOP_FILE))

    def sync_game_state(self) -> Dict[str, Any]:
        game_st = get_live_game_state()
        self.state["current_known_r"] = game_st["reincarnation"]
        self.state["excavations"] = game_st["excavations"]
        self.state["gems"] = f"{game_st['gems']:.4e}"
        self.state["observed_hellfire_time"] = game_st["hellfire_time"]
        self.state["timestamps"]["last_check"] = datetime.now().isoformat()
        return game_st

    def deploy_template(self,template_str):
        result=self.actions.deploy_template(template_str)
        self.state['last_action_result']=result
        self.state['next_expected_action']=result['message']
        if result['success']: self.state['last_successful_action']=result['message']
        self.save_state()
        return result['success']

    def perform_abdication(self,pot_gems):
        result=self.actions.abdicate()
        self.state['last_action_result']=result
        self.state['next_expected_action']=result['message']
        if result['success']:
            self.state['last_successful_action']=result['message']
            self.ai.velocity_tracker.reset_run()
            self.sync_game_state()
        self.save_state()
        return result

    def kickstart_new_run(self):
        result=self.actions.setup_build()
        self.state['last_action_result']=result
        self.state['next_expected_action']=result['message']
        if result['success']:self.state['last_successful_action']=result['message']
        self.save_state()
        return result

    def perform_reincarnation(self,r,current_gems,req_gems):
        # Supplied UI estimates never replace fresh transaction preconditions.
        result=self.actions.reincarnate()
        self.state['last_action_result']=result
        self.state['next_expected_action']=result['message']
        if result['success']:
            self.sync_game_state()
            self.state['last_successful_action']=result['message']
            self.ai.velocity_tracker.reset_run()
        self.save_state()
        return result

    def fast_track_gate(self):
        # Manual shortcut uses the same action owner; step() never calls a second reset path.
        return self.actions.auto_clear()

    def step(self):
        """Observe first; select exactly one decision path; commit only state-proven progress."""
        game_st=self.sync_game_state()
        try:
            self.dismiss_modals()
        except Exception:
            logging.exception('Offline Production modal recognition/dismissal failed safely')
        self.state['telemetry']=game_st.get('telemetry',{})
        self.state['build_verification']=self.actions.diagnose_build(game_st)
        self.state['selected_route']=self.actions.route.plan(game_st)
        self.tracker.observe_state(game_st,paused=self.is_paused())
        stage=actual_dragon_stage(game_st,self.actions.catalog())
        self.state['current_stage']=stage
        if self.is_paused():
            self.state['is_running']=False
            self.state['next_expected_action']='Paused. Review live telemetry, build validation and the pending-action ledger before resuming.'
            self.save_state();return
        require_interactive_session()
        cfg=load_config()
        if not self.window.find_window():
            self.state['is_running']=False
            pulse=self.guardian.pulse_check(allow_relaunch=bool(cfg.get('auto_recover_game',False)))
            self.state['next_expected_action']='Waiting for the game in this interactive desktop; no input was sent.'
            self.state['guardian']=pulse
            self.save_state();return
        if not input_allowed(self.window):
            self.state['is_running']=False
            self.state['next_expected_action']='Input is blocked: pause, game session, or minimized-window guard.'
            self.save_state();return
        selected_goal=cfg.get('selected_goal','Dragon Tamer')
        reached=(selected_goal=='Next reincarnation' and game_st['reincarnation']>=cfg.get('goal_target_r',game_st['reincarnation']+1))
        reached=reached or (selected_goal=='Build only' and self.state['build_verification']['build_verified'])
        if selected_goal=='Named goal':
            from src.knowledge_service import KnowledgeService
            target_plan=KnowledgeService(state_dir=self.actions.state_dir).plan_target(cfg.get('named_goal','Dragon Tamer'),game_st)
            self.state['named_goal_plan']=target_plan
            reached=reached or target_plan['complete']
        if reached:
            from src.config import save_config
            cfg['paused']=True;save_config(cfg)
            with open(STOP_FILE,'w',encoding='utf-8') as output:output.write('Selected goal verified')
            self.state['is_running']=False
            self.state['next_expected_action']='Selected goal verified from game state; automation paused.'
            self.save_state();return
        self.state['is_running']=True
        ai_eval=self.ai.evaluate(game_st,cfg)
        self.state['ai_eval']=ai_eval
        # The tracker was updated from the actual save timestamp and fingerprint above.
        result=self.actions.auto_clear(ai_eval.get('decision'))
        self.state['last_action_result']=result
        self.state['next_expected_action']=result['message']
        if result.get('success') and result.get('status')=='VERIFIED':
            self.state['last_successful_action']=result['message']
            after=self.sync_game_state()
            self.state['current_stage']=actual_dragon_stage(after,self.actions.catalog())
            milestones={'HATCH_PURCHASED':'hatch_purchased','DRAKELING_PURCHASED':'drakeling_purchased',
                        'DRAGON_PURCHASED':'dragon_purchased','ELDER_DRAGON_PURCHASED':'elder_dragon_purchased'}
            key=milestones.get(result.get('action'))
            if key:self.state['timestamps'][key]=datetime.now().isoformat()
            if result.get('action') in ('ABDICATED','REINCARNATED'):
                self.ai.velocity_tracker.reset_run()
            if result.get('action')=='HATCH_PURCHASED':
                self.state['hellfire_at_verified_hatch']=after['hellfire_active_time_total']
        if 'hellfire_at_verified_hatch' in self.state:
            self.state['hellfire_since_hatch']=game_st.get('hellfire_since_hatch')
        if self.state['current_stage']=='COMPLETED':
            self.state['steam_achievement_status']='NOT_INDEPENDENTLY_VERIFIED'
        logging.info('[Verified controller] %s: %s',result.get('action'),result.get('message'))
        self.save_state()

    def run_loop(self, stop_event=None):
        require_interactive_session()
        try:
            with WorkerLease():
                logging.info('Starting the sole DragonBot worker for this project.')
                scheduler=IdleScheduler(CONFIG_FILE,STOP_FILE,SOL_PATH)
                while stop_event is None or not stop_event.is_set():
                    watched=scheduler.snapshot()
                    pause_message='Paused by user via configuration or STOP file; resume explicitly to continue.'
                    outcome={"kind":"waiting","status":"WAITING","action":"PAUSED","message":pause_message}
                    try:
                        # Pause is a cheap config/STOP read and must gate every cycle
                        # before state observation or an action can be dispatched.
                        if self.is_paused():
                            if self.state.get('is_running',False) or self.state.get('next_expected_action')!=pause_message:
                                self.state['is_running']=False
                                self.state['next_expected_action']=pause_message
                                self.save_state()
                        else:
                            self.step()
                            result=self.state.get('last_action_result') or {}
                            if result.get('status') in ('BLOCKED','UNCERTAIN'):
                                outcome={"kind":"blocked",**result}
                            elif not self.state.get('is_running',False):
                                outcome={"kind":"waiting","status":"WAITING","action":"NO_DISPATCH",
                                         "message":self.state.get('next_expected_action','Waiting for game state')}
                            else:
                                outcome=result or {"kind":"cycle","status":"ACTIVE","action":"PROGRESS"}
                    except Exception as exc:
                        logging.error('Worker observation/action failed: %s',exc,exc_info=True)
                        self.state['is_running']=False
                        self.state['retry_count']=self.state.get('retry_count',0)+1
                        self.state['next_expected_action']=str(exc)
                        self.save_state()
                        outcome={"kind":"error","status":"ERROR","action":"WORKER_CYCLE","message":str(exc)}
                    delay=scheduler.delay_after(outcome,load_config())
                    scheduler.wait_for_change(delay,watched,stop_event=stop_event)
        except RuntimeError as exc:
            logging.warning('%s',exc)


if __name__ == "__main__":
    bot = DragonBot()
    bot.run_loop()
