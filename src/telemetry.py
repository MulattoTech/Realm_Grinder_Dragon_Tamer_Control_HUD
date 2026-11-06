"""
Telemetry and ETA estimation engine for Realm Grinder Dragon Tamer.
Continuously records progression checkpoints and computes live ETAs
for current Reincarnation, R46 gate, and Dragon quest stages.
"""

import os
import json
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

TELEMETRY_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "progression_history.json")


class ProgressionTracker:
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history = self.load_history()

    def load_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(TELEMETRY_FILE):
            try:
                with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_history(self):
        os.makedirs(os.path.dirname(TELEMETRY_FILE), exist_ok=True)
        from src.atomic_store import write_json
        write_json(TELEMETRY_FILE,self.history[-self.max_history:])

    def record_snapshot(self, r: int, gems: float, coins: float, stage: str, excavations: int = 0, hellfire_time: float = 0):
        now = time.time()
        # Avoid recording duplicate identical points within 3 seconds
        if self.history and now - self.history[-1]["time"] < 3.0:
            return

        entry = {
            "time": now,
            "iso": datetime.now().isoformat(),
            "r": r,
            "gems": gems,
            "coins": coins,
            "stage": stage,
            "excavations": excavations,
            "hellfire_time": hellfire_time
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.save_history()

    def observe_state(self,state,paused=False):
        token=state.get('save_fingerprint')
        previous=self.history[-1] if self.history else {}
        identity=[state.get('reincarnation'),state.get('gems'),state.get('faction'),state.get('alignment')]
        boundary=previous.get('identity')!=identity or previous.get('paused')!=bool(paused)
        if previous.get('save_fingerprint')==token and not boundary:return
        segment=int(previous.get('segment',0))+(1 if boundary else 0)
        entry={'time':state.get('save_timestamp',time.time()),'r':state['reincarnation'],
               'gems':state['gems'],'coins':state.get('coins_this_game',0),
               'potential_gems':state.get('potential_gems',0),'stage':state.get('current_stage',''),
               'identity':identity,'segment':segment,'run':identity+[segment,bool(paused)],
               'paused':bool(paused),'save_fingerprint':token}
        self.history.append(entry);self.history=self.history[-self.max_history:]
        self.save_history()

    def calculate_etas(self,current_r,current_gems,current_coins,stage_timestamps,hellfire_time=0,*,reload_history=False,ascension=0):
        from src.measured_eta import estimate_target
        from src.wiki_data import get_reincarnation_gem_requirement
        from src.config import load_config
        if reload_history:self.history=self.load_history()
        rows=[{'time':row['time'],'value':row.get('potential_gems',0),'run':row.get('run')}
              for row in self.history if row.get('r')==current_r and row.get('gems')==current_gems and row.get('run') is not None]
        paused=load_config().get('paused',True) or os.path.exists(os.path.join(os.path.dirname(TELEMETRY_FILE),'STOP'))
        estimate=estimate_target(rows,get_reincarnation_gem_requirement(current_r,ascension),paused=paused)
        seconds=estimate['seconds']
        unknown='Not established'
        return {'current_r_eta':self._format_duration(seconds) if seconds is not None else estimate['status'].replace('_',' ').title(),
                'current_r_eta_seconds':seconds,'current_r_estimate':estimate,
                'r46_eta':'Reached' if current_r>=46 else unknown,'r46_eta_seconds':0 if current_r>=46 else None,
                'hatch_eta':'Requires verified incubation start','drakeling_eta':'Requires measured post-Hatch activity',
                'dragon_eta':'Requires verified previous stage and assistants','elder_dragon_eta':'Requires verified previous stage and maximum mana',
                'total_eta':unknown,'total_eta_seconds':None,'target_completion_date':None,
                'r_progress_pct':min(100,100*current_gems/get_reincarnation_gem_requirement(current_r,ascension)),
                'remaining_r_count':max(0,48-current_r)}

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds <= 0:
            return "Ready"
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hrs > 24:
            days = hrs // 24
            rem_hrs = hrs % 24
            return f"{days}d {rem_hrs:02d}h {mins:02d}m"
        elif hrs > 0:
            return f"{hrs}h {mins:02d}m"
        else:
            return f"{mins}m {secs:02d}s"
