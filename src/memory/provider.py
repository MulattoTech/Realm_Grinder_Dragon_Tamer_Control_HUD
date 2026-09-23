"""Session-scoped field mappings; unverified addresses never drive the controller."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
import json
import math
from pathlib import Path
import time
from .process import ProcessIdentity, ReadOnlyProcess
from .scanner import BoundedScanner
from src.atomic_store import write_json

VOLATILE_FIELDS = frozenset({'mana_current', 'mana_max', 'mana_regeneration', 'coins',
    'assistants_current', 'fairy_assistants', 'hellfire_active', 'hellfire_remaining_seconds'})

@dataclass
class FieldMapping:
    field: str
    identity: ProcessIdentity
    address: int
    datatype: str = 'Float64'
    confidence: str = 'LOW'
    validation_source: str = ''
    minimum: float = 0.0
    maximum: float = 1e300
    validated_at: float = field(default_factory=time.time)
    run_signature: list = field(default_factory=list)

    def valid_for(self, identity):
        return bool(identity is not None and identity == self.identity and self.address > 0 and
                    self.confidence in ('VERIFIED', 'HIGH') and self.validation_source and
                    self.field in VOLATILE_FIELDS)

    def accepts(self, value):
        return isinstance(value, (float, int)) and math.isfinite(value) and self.minimum <= value <= self.maximum

    @classmethod
    def from_dict(cls, item):
        item = dict(item)
        item['identity'] = ProcessIdentity(**item['identity'])
        return cls(**item)


def game_pid():
    """Use the established native finder, including its interactive-desktop handling."""
    from src.window import RealmGrinderWindow
    window = RealmGrinderWindow()
    return window.pid if window.find_window() else None


def run_signature(state):
    return [state.get('reincarnation'), state.get('gems'), state.get('faction'), state.get('alignment')]

class MemoryProvider:
    def __init__(self, state_dir, pid_resolver=game_pid, process_factory=ReadOnlyProcess,
                 discovery_enabled=False):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir/'memory_mappings.json'
        self.pid_resolver, self.process_factory = pid_resolver, process_factory
        self.reader = None
        self.mappings = {}
        self.discovery_enabled = discovery_enabled
        self._last_discovery = 0.0
        self._tracking = None
        self._mapping_mtime = None
        self.rediscovery_count = 0
        self.invalidations = []
        self.last_error = None

    def close(self):
        if self.reader:
            self.reader.close()
        self.reader = None
        self.mappings.clear()
        self._tracking = None
        self._mapping_mtime = None

    def _connect(self):
        if self.reader and self.reader.is_alive():
            return
        self.close()
        pid = self.pid_resolver()
        if pid:
            reader = self.process_factory(pid)
            reader.open()
            self.reader = reader
            self._last_discovery = 0

    def _load(self):
        if not self.reader or not self.path.exists():
            return
        mtime = self.path.stat().st_mtime_ns
        if mtime == self._mapping_mtime:
            return
        data = json.loads(self.path.read_text(encoding='utf-8'))
        loaded = {}
        for item in data.get('mappings', []):
            mapping = FieldMapping.from_dict(item)
            if mapping.valid_for(self.reader.identity):
                loaded[mapping.field] = mapping
        self.mappings = loaded
        self._mapping_mtime = mtime

    def persist(self):
        write_json(self.path, {'schema_version': 1, 'updated_at': time.time(),
            'mappings': [asdict(m) for m in self.mappings.values()],
            'invalidations': self.invalidations[-20:]})
        self._mapping_mtime = self.path.stat().st_mtime_ns

    def register(self, mapping):
        if not self.reader or not mapping.valid_for(self.reader.identity):
            raise ValueError('Cannot register an unverified or different-session mapping')
        value = self.reader.read_value(mapping.address, mapping.datatype)
        if not mapping.accepts(value):
            raise ValueError('Mapped field is outside its validated range')
        self.mappings[mapping.field] = mapping
        self.persist()

    def _rediscover_mana(self, state):
        """Bounded, input-free recovery. Promotion requires changing independent save anchors.

        Static exact matches stay candidates, never authoritative mappings. A controlled
        cast/regen calibration can instead register a VERIFIED mapping through the probe.
        """
        if 'mana_current' in self.mappings or not self.discovery_enabled:
            return
        now = time.time()
        anchor = state.get('mana_current')
        if anchor is None or now-state.get('save_timestamp', 0) > 1.5:
            return
        fingerprint = state.get('save_fingerprint', state.get('save_timestamp'))
        if self._tracking and self._tracking['identity'] == self.reader.identity:
            tracking = self._tracking
            if fingerprint == tracking['fingerprint'] or math.isclose(anchor, tracking['anchor'], abs_tol=1e-6):
                return
            matches = []
            for candidate in tracking['result'].candidates:
                try:
                    current = self.reader.read_double(candidate.address)
                    if math.isfinite(current) and math.isclose(current, anchor, rel_tol=1e-7, abs_tol=1.0):
                        matches.append(candidate)
                except OSError:
                    pass
            tracking['result'].candidates = matches
            tracking['fingerprint'], tracking['anchor'] = fingerprint, anchor
            tracking['changes'] += 1
            # A full mana bar can match maximum-mana and display caches.
            # Passive coincidences are discovery candidates, never live-field proof.
            if matches:
                write_json(self.state_dir/'memory_discovery.json', {
                    'identity':asdict(self.reader.identity),'timestamp':time.time(),
                    'candidate_count':len(matches),'save_anchor_changes':tracking['changes'],
                    'confidence':'LOW','status':'NEEDS_CONTROLLED_FIELD_VALIDATION'})
            else:
                self._tracking=None
            return
        if now-self._last_discovery < 45:
            return
        self._last_discovery = now
        self.rediscovery_count += 1
        regions = [r for r in self.reader.query_regions() if r.readable and r.type in (0x20000, 0x40000)]
        result = BoundedScanner(self.reader, max_bytes=512*1024*1024, max_seconds=6,
                                max_candidates=2048).scan_exact(anchor, regions=regions)
        self._tracking = {'identity': self.reader.identity, 'result': result,
                          'fingerprint': fingerprint, 'anchor': anchor, 'changes': 0}

    def sample(self, save_state):
        observations = {}
        self.last_error = None
        try:
            self._connect()
            if self.reader:
                self._load()
                changed = False
                for name, mapping in list(self.mappings.items()):
                    try:
                        if not mapping.valid_for(self.reader.identity):
                            raise ValueError('Expired process session')
                        if mapping.run_signature and mapping.run_signature != run_signature(save_state):
                            raise ValueError('Run changed; volatile mapping needs revalidation')
                        value = self.reader.read_value(mapping.address, mapping.datatype)
                        if not mapping.accepts(value):
                            raise ValueError('Non-finite or out-of-range memory value')
                        observations[name] = {'value': value, 'source': 'PROCESS_MEMORY',
                            'timestamp': time.time(), 'confidence': mapping.confidence,
                            'validation_source': mapping.validation_source,
                            'last_validation': mapping.validated_at,
                            'pid': mapping.identity.pid, 'process_start_time': mapping.identity.start_time}
                    except (OSError, ValueError) as exc:
                        del self.mappings[name]
                        self.invalidations.append({'field': name, 'timestamp': time.time(), 'reason': str(exc)})
                        changed = True
                if changed:
                    self.persist()
                self._rediscover_mana(save_state)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.last_error = str(exc)
        connected = bool(self.reader and self.reader.is_alive())
        identity = self.reader.identity if connected else None
        health = {'process_connected': connected, 'memory_handle_open': connected,
            'pid': identity.pid if identity else None, 'process_start_time': identity.start_time if identity else None,
            'pointer_size': identity.pointer_size if identity else None,
            'memory_provider_health': 'HEALTHY' if observations else ('CONNECTED_UNMAPPED' if connected else 'DISCONNECTED'),
            'mapped_fields': sorted(self.mappings), 'verified_fields': sorted(observations),
            'unmapped_fields': sorted(VOLATILE_FIELDS-set(observations)),
            'invalid_fields': [x['field'] for x in self.invalidations[-10:]],
            'rediscovery_count': self.rediscovery_count,
            'discovery_candidates': len(self._tracking['result'].candidates) if self._tracking else 0,
            'last_memory_read': time.time() if observations else None, 'memory_error': self.last_error}
        return observations, health
