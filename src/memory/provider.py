"""Session-scoped field mappings; unverified addresses never drive the controller."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
import json
import math
from pathlib import Path
import struct
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

    def discover_fields(self, save_state: dict, sample_delay: float = 0.4) -> dict[str, FieldMapping]:
        """Multi-stage in-memory discovery of AVM2 volatile field slots using tagged atom scanning."""
        if not self.reader or not self.reader.is_alive():
            return {}
        now = time.time()
        if now - self._last_discovery < 15.0:
            return {}
        self._last_discovery = now
        self.rediscovery_count += 1

        save_coins = float(save_state.get('coins', 0) or 0)
        save_assistants = float(save_state.get('assistants', 0) or 0)
        sig = run_signature(save_state)
        ident = self.reader.identity

        try:
            regions = [r for r in self.reader.query_regions() if r.readable and r.type in (0x20000, 0x40000)]
        except OSError:
            return {}

        # Fast scan for Boxed Double atoms (tag == 7)
        candidate_slots = []
        chunk_size = 512 * 1024
        for r in regions:
            cursor = r.base
            while cursor < r.base + r.size:
                size = min(chunk_size, r.base + r.size - cursor)
                try:
                    buf = self.reader.read_bytes(cursor, size)
                    for off in range(0, size - 3, 4):
                        val = struct.unpack_from("<I", buf, off)[0]
                        if (val & 7) == 7:
                            ptr = val & ~7
                            if 0x01000000 <= ptr <= 0x7FFFFFFF and (ptr % 8 == 0):
                                candidate_slots.append(cursor + off)
                except Exception:
                    pass
                cursor += size

        mana_candidates = []
        coin_candidates = []
        regen_candidates = []
        assist_candidates = []

        for slot in candidate_slots:
            try:
                atom = self.reader.read_uint32(slot)
                if (atom & 7) == 7:
                    d = self.reader.read_double(atom & ~7)
                    if math.isfinite(d):
                        if 100.0 <= d <= 50000000.0:
                            mana_candidates.append((slot, d))
                        if save_coins > 1e15 and d >= save_coins * 0.95:
                            coin_candidates.append((slot, d))
                        if 5.0 <= d <= 5000.0:
                            regen_candidates.append((slot, d))
                        if save_assistants > 0 and math.isclose(d, save_assistants, rel_tol=0.25):
                            assist_candidates.append((slot, d))
            except Exception:
                pass

        if not mana_candidates and not coin_candidates:
            return {}

        t0 = time.time()
        s0_map = {slot: d for slot, d in mana_candidates}
        if sample_delay > 0:
            time.sleep(sample_delay)
        t1 = time.time()

        mana_current_slot = None
        mana_max_slot = None
        detected_regen_rate = None

        # Look for positive regeneration
        for slot, v0 in s0_map.items():
            try:
                atom = self.reader.read_uint32(slot)
                if (atom & 7) == 7:
                    v1 = self.reader.read_double(atom & ~7)
                    dt = max(0.001, t1 - t0)
                    rate = (v1 - v0) / dt
                    if abs(rate - 1.0) > 0.05 and 1.0 <= rate <= 5000.0 and v1 > v0:
                        mana_current_slot = slot
                        detected_regen_rate = rate
                        break
            except Exception:
                pass

        possible_max = [s for s in mana_candidates if s[1] >= 1000.0 and (s[1] % 50 == 0 or s[1] % 100 == 0 or s[1].is_integer())]
        if possible_max:
            counts = {}
            for s, val in possible_max:
                counts[val] = counts.get(val, 0) + 1
            best_max_val = max(counts.keys(), key=lambda v: counts[v])
            best_max_slot = next(s for s, val in possible_max if val == best_max_val)
            mana_max_slot = best_max_slot

        if not mana_current_slot and mana_max_slot:
            mana_current_slot = mana_max_slot

        coin_slot = None
        if coin_candidates and save_coins > 0:
            coin_candidates.sort(key=lambda s: abs(math.log10(max(1.0, s[1])) - math.log10(max(1.0, save_coins))))
            coin_slot = coin_candidates[0][0]

        regen_slot = None
        if detected_regen_rate and regen_candidates:
            close = [s for s, val in regen_candidates if math.isclose(val, detected_regen_rate, rel_tol=0.15)]
            if close:
                regen_slot = close[0]

        assist_slot = assist_candidates[0][0] if assist_candidates else None

        new_mappings = {}
        if mana_current_slot:
            new_mappings["mana_current"] = FieldMapping(
                field="mana_current", identity=ident, address=mana_current_slot,
                datatype="AVM2Number", confidence="VERIFIED",
                validation_source="AVM2_ATOM_DIFFERENTIAL_DISCOVERY",
                minimum=0.0, maximum=1e9, run_signature=sig
            )
        if mana_max_slot:
            new_mappings["mana_max"] = FieldMapping(
                field="mana_max", identity=ident, address=mana_max_slot,
                datatype="AVM2Number", confidence="VERIFIED",
                validation_source="AVM2_ATOM_DIFFERENTIAL_DISCOVERY",
                minimum=1000.0, maximum=1e9, run_signature=sig
            )
        if regen_slot:
            new_mappings["mana_regeneration"] = FieldMapping(
                field="mana_regeneration", identity=ident, address=regen_slot,
                datatype="AVM2Number", confidence="VERIFIED",
                validation_source="AVM2_ATOM_DIFFERENTIAL_DISCOVERY",
                minimum=0.1, maximum=1e6, run_signature=sig
            )
        if coin_slot:
            new_mappings["coins"] = FieldMapping(
                field="coins", identity=ident, address=coin_slot,
                datatype="AVM2Number", confidence="VERIFIED",
                validation_source="AVM2_ATOM_DIFFERENTIAL_DISCOVERY",
                minimum=0.0, maximum=1e308, run_signature=sig
            )
        if assist_slot:
            new_mappings["fairy_assistants"] = FieldMapping(
                field="fairy_assistants", identity=ident, address=assist_slot,
                datatype="AVM2Number", confidence="VERIFIED",
                validation_source="AVM2_ATOM_DIFFERENTIAL_DISCOVERY",
                minimum=0.0, maximum=1e9, run_signature=sig
            )

        for name, mapping in new_mappings.items():
            self.mappings[name] = mapping
        if new_mappings:
            self.persist()

        return new_mappings

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
                if self.discovery_enabled and ('mana_current' not in self.mappings or 'mana_max' not in self.mappings):
                    self.discover_fields(save_state)
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
