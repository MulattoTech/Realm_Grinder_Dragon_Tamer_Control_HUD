"""Field-specific fusion of persistent saves and validated, read-only process telemetry."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import threading
import time
from src.save_reader import get_current_game_state
from src.memory.provider import MemoryProvider, VOLATILE_FIELDS
from src.atomic_store import write_json

STATE_DIR = Path(__file__).resolve().parents[1]/'state'
UNKNOWN_FIELDS = {'mana_max', 'mana_regeneration', 'assistants_total', 'assistants_current',
                  'fairy_assistants', 'hellfire_since_hatch'}

class LiveStateProvider:
    def __init__(self, save_reader=get_current_game_state, memory=None, state_dir=STATE_DIR,
                 max_save_age=90.0, max_memory_age=2.0):
        self.save_reader = save_reader
        self.state_dir = Path(state_dir)
        self.memory = memory if memory is not None else MemoryProvider(self.state_dir)
        self.max_save_age, self.max_memory_age = max_save_age, max_memory_age
        self._last_good = None
        self._lock = threading.RLock()
        self._last_health_write = 0
        self.fallback_count = 0
        from src.quest_observer import QuestObserver
        catalog_path=self.state_dir/'milestone_catalog.json'
        catalog=json.loads(catalog_path.read_text(encoding='utf-8')).get('milestones',{}) if catalog_path.exists() else {}
        self.quest_observer=QuestObserver(self.state_dir/'quest_observations.json',catalog)

    def get(self):
        with self._lock:
            now, save_error = time.time(), None
            try:
                saved = self.save_reader()
                self._last_good = copy.deepcopy(saved)
            except (OSError, ValueError, KeyError) as exc:
                if self._last_good is None:
                    raise
                save_error = str(exc)
                saved = copy.deepcopy(self._last_good)
            state = copy.deepcopy(saved)
            timestamp = saved.get('save_timestamp', now-saved.get('save_age_seconds', 0))
            age = max(0.0, now-timestamp)
            save_healthy = save_error is None and age <= self.max_save_age
            provenance = {}
            for name, value in state.items():
                if name == 'raw_data' or isinstance(value, (dict, list)):
                    continue
                source = 'AIR_SHAREDOBJECT'
                confidence = 'HIGH' if save_healthy else 'LOW'
                validation = 'stable_file_decode'
                if value is None:
                    source, confidence, validation = 'UNKNOWN', 'INVALID', 'not_mapped'
                elif name in ('assistants', 'legacy_stat_12'):
                    confidence, validation = 'LOW', 'ambiguous_legacy_stat_not_assistants_evidence'
                elif name in ('potential_gems', 'gems_gain'):
                    source, validation = 'DERIVED', 'save_coins_this_game_formula'
                provenance[name] = {'value': value, 'source': source, 'timestamp': timestamp,
                    'age_ms': round(age*1000, 3), 'confidence': confidence, 'validation_source': validation}
            try:
                observations, health = self.memory.sample(saved)
            except (OSError, ValueError) as exc:
                observations, health = {}, {'process_connected': False, 'memory_error': str(exc)}
            rejected = []
            for name, observation in observations.items():
                value = observation.get('value')
                observed = observation.get('timestamp', 0)
                valid = (name in VOLATILE_FIELDS and observation.get('confidence') in ('HIGH', 'VERIFIED')
                         and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
                         and 0 <= now-observed <= self.max_memory_age)
                # Reads may finish slightly after 'now'; allow that narrow, measured interval.
                if observed > now and observed <= time.time():
                    valid = (name in VOLATILE_FIELDS and observation.get('confidence') in ('HIGH', 'VERIFIED')
                             and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0)
                if valid:
                    state[name] = value
                    provenance[name] = dict(observation, age_ms=round(max(0, time.time()-observed)*1000, 3))
                else:
                    rejected.append(name)
            if provenance.get('mana_current', {}).get('source') == 'PROCESS_MEMORY':
                state['mana'] = state['mana_current']
                provenance['mana'] = dict(provenance['mana_current'])
            else:
                self.fallback_count += 1
            health = dict(health)
            health.update(timestamp=time.time(), save_provider_health='STALE_ERROR' if save_error else
                          ('HEALTHY' if save_healthy else 'STALE'), save_error=save_error,
                          last_save_read=now, last_save_change=timestamp, save_age_seconds=age,
                          fallback_count=self.fallback_count, rejected_memory_fields=rejected,
                          consequential_actions_allowed=bool(save_healthy and health.get('process_connected')),
                          vision_dependency='NONE_FOR_TELEMETRY')
            state['provenance'], state['telemetry'] = provenance, health
            state=self.quest_observer.observe(state)
            if time.time()-self._last_health_write >= 1:
                try:
                    write_json(self.state_dir/'telemetry_health.json', health)
                    self._last_health_write = time.time()
                except OSError as exc:
                    health['health_persistence_error'] = str(exc)
            return state

    def close(self):
        with self._lock:
            self.memory.close()

_PROVIDER = None
_PROVIDER_LOCK = threading.Lock()

def get_live_game_state():
    global _PROVIDER
    with _PROVIDER_LOCK:
        if _PROVIDER is None:
            _PROVIDER = LiveStateProvider()
    return _PROVIDER.get()
