"""Comprehensive automated tests for AVM2 read-only memory provider,
heap structure simulation, differential discovery, session invalidation, and live state fusion.
"""
from __future__ import annotations
import math
from pathlib import Path
import struct
import time
import pytest

from src.memory.process import ProcessIdentity, MemoryRegion
from src.memory.provider import MemoryProvider, FieldMapping, VOLATILE_FIELDS
from src.live_state import LiveStateProvider

ROOT = Path(__file__).resolve().parents[1]

class MockAVM2Process:
    """Simulates an Adobe AIR / AVM2 32-bit process heap with tagged atoms and boxed doubles."""
    def __init__(self, pid: int = 42, start_time: int = 1000):
        self.identity = ProcessIdentity(pid, start_time, 'RealmGrinderDesktop.exe', 4)
        self.alive = True
        self.memory = bytearray(1024 * 1024) # 1 MB simulated heap
        self.base = 0x04000000

    def is_alive(self) -> bool:
        return self.alive

    def query_regions(self):
        # 0x1000 = MEM_COMMIT, 0x04 = PAGE_READWRITE, 0x20000 = MEM_PRIVATE
        yield MemoryRegion(self.base, len(self.memory), 0x1000, 0x04, 0x20000)

    def read_bytes(self, address: int, size: int) -> bytes:
        if not self.alive:
            raise OSError("Process terminated")
        offset = address - self.base
        if offset < 0 or offset + size > len(self.memory):
            raise OSError(f"Segmentation fault reading {address:#x}")
        return bytes(self.memory[offset:offset + size])

    def write_test_bytes(self, address: int, data: bytes):
        offset = address - self.base
        self.memory[offset:offset + len(data)] = data

    def write_test_double(self, address: int, value: float):
        self.write_test_bytes(address, struct.pack("<d", value))

    def write_test_atom(self, address: int, atom_value: int):
        self.write_test_bytes(address, struct.pack("<I", atom_value))

    def read_uint32(self, address: int) -> int:
        return struct.unpack("<I", self.read_bytes(address, 4))[0]

    def read_double(self, address: int) -> float:
        return struct.unpack("<d", self.read_bytes(address, 8))[0]

    def read_pointer(self, address: int) -> int:
        return self.read_uint32(address)

    def read_avm2_number(self, address: int):
        atom = self.read_pointer(address)
        tag = atom & 7
        if tag == 6: # inline int29
            signed = atom - (1 << 32) if atom & 0x80000000 else atom
            return signed >> 3
        if tag == 7 and (atom & ~7) != 0:
            return self.read_double(atom & ~7)
        raise ValueError(f"Not a numeric atom: {atom:#x}")

    def read_value(self, address: int, datatype: str):
        if datatype == 'AVM2Number':
            return self.read_avm2_number(address)
        if datatype == 'Float64':
            return self.read_double(address)
        if datatype == 'UInt32':
            return self.read_uint32(address)
        raise ValueError(f"Unknown datatype: {datatype}")

    def open(self):
        self.alive = True
        return self

    def close(self):
        self.alive = False


def test_field_mapping_validation_and_bounds():
    ident = ProcessIdentity(42, 1000, 'RealmGrinderDesktop.exe', 4)
    m = FieldMapping(
        field='mana_current', identity=ident, address=0x04001000,
        datatype='AVM2Number', confidence='VERIFIED',
        validation_source='AVM2_ATOM_DIFFERENTIAL_DISCOVERY',
        minimum=0.0, maximum=10000.0
    )
    assert m.valid_for(ident)
    assert not m.valid_for(ProcessIdentity(42, 2000, 'RealmGrinderDesktop.exe', 4))
    assert not m.valid_for(ProcessIdentity(99, 1000, 'RealmGrinderDesktop.exe', 4))
    assert not m.valid_for(None)

    assert m.accepts(500.0)
    assert m.accepts(0.0)
    assert m.accepts(10000.0)
    assert not m.accepts(-1.0)
    assert not m.accepts(10001.0)
    assert not m.accepts(float('nan'))
    assert not m.accepts(float('inf'))


def test_avm2_tagged_atom_unpacking(tmp_path):
    proc = MockAVM2Process(pid=10, start_time=500)
    # 1. Test inline Int29 (tag 6)
    # 1572 encoded as Atom: (1572 << 3) | 6 = 12582 = 0x3126
    int_slot = proc.base + 0x100
    proc.write_test_atom(int_slot, (1572 << 3) | 6)
    assert proc.read_value(int_slot, 'AVM2Number') == 1572

    # Negative int: -25 encoded as Int29
    neg_int_slot = proc.base + 0x104
    neg_atom = ((-25 << 3) | 6) & 0xFFFFFFFF
    proc.write_test_atom(neg_int_slot, neg_atom)
    assert proc.read_value(neg_int_slot, 'AVM2Number') == -25

    # 2. Test Boxed Double (tag 7)
    double_addr = proc.base + 0x200 # 8-byte aligned
    proc.write_test_double(double_addr, 8296.5)
    double_slot = proc.base + 0x108
    proc.write_test_atom(double_slot, double_addr | 7)
    assert proc.read_value(double_slot, 'AVM2Number') == 8296.5

    # Non-numeric tag should raise ValueError
    invalid_slot = proc.base + 0x10C
    proc.write_test_atom(invalid_slot, 0x04000200 | 1) # String tag 1
    with pytest.raises(ValueError, match="Not a numeric atom"):
        proc.read_value(invalid_slot, 'AVM2Number')


def test_provider_discovery_of_regenerating_mana(tmp_path):
    proc = MockAVM2Process(pid=10, start_time=500)
    provider = MemoryProvider(tmp_path, pid_resolver=lambda: 10, process_factory=lambda pid: proc, discovery_enabled=True)
    provider._connect()

    # Layout simulated AVM2 player state:
    # 1. Boxed double for current mana: starts at 500.0
    mana_double_addr = proc.base + 0x1000
    proc.write_test_double(mana_double_addr, 500.0)
    mana_slot = proc.base + 0x100
    proc.write_test_atom(mana_slot, mana_double_addr | 7)

    # 2. Boxed double for max mana: 8000.0
    max_double_addr = proc.base + 0x1008
    proc.write_test_double(max_double_addr, 8000.0)
    max_slot = proc.base + 0x104
    proc.write_test_atom(max_slot, max_double_addr | 7)

    # 3. Boxed double for coins: 1.5e138
    coin_double_addr = proc.base + 0x1010
    proc.write_test_double(coin_double_addr, 1.5e138)
    coin_slot = proc.base + 0x108
    proc.write_test_atom(coin_slot, coin_double_addr | 7)

    save_state = {
        'reincarnation': 24, 'gems': 1e70, 'coins': 1.5e138,
        'excavations': 1500, 'mana': 500.0, 'assistants': 20000
    }

    # Simulate mana regeneration by hook during discovery delay
    original_sleep = time.sleep
    def mock_sleep(seconds):
        # Update mana double to simulate +35/s regeneration
        proc.write_test_double(mana_double_addr, 500.0 + 35.0 * seconds)
        original_sleep(0.01)

    import src.memory.provider as prov_mod
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(prov_mod.time, 'sleep', mock_sleep)

    discovered = provider.discover_fields(save_state, sample_delay=0.1)
    monkeypatch.undo()

    assert 'mana_current' in discovered
    assert discovered['mana_current'].address == mana_slot
    assert discovered['mana_current'].confidence == 'VERIFIED'

    assert 'mana_max' in discovered
    assert discovered['mana_max'].address == max_slot

    assert 'coins' in discovered
    assert discovered['coins'].address == coin_slot

    # Verify that provider.sample() now reads live values from process memory
    obs, health = provider.sample(save_state)
    assert health['memory_provider_health'] == 'HEALTHY'
    assert 'mana_current' in obs
    assert obs['mana_current']['source'] == 'PROCESS_MEMORY'
    assert obs['mana_current']['confidence'] == 'VERIFIED'
    assert obs['mana_current']['value'] >= 500.0
    assert obs['coins']['value'] == 1.5e138


def test_session_invalidation_and_clean_reconnect(tmp_path):
    proc1 = MockAVM2Process(pid=10, start_time=500)
    provider = MemoryProvider(tmp_path, pid_resolver=lambda: 10 if proc1.alive else None, process_factory=lambda pid: proc1)
    provider._connect()

    ident1 = proc1.identity
    mapping = FieldMapping(
        field='mana_current', identity=ident1, address=proc1.base + 0x100,
        datatype='AVM2Number', confidence='VERIFIED',
        validation_source='test', minimum=0.0, maximum=10000.0
    )
    # Set up memory so register() succeeds
    d_addr = proc1.base + 0x200
    proc1.write_test_double(d_addr, 800.0)
    proc1.write_test_atom(proc1.base + 0x100, d_addr | 7)
    provider.register(mapping)

    save = {'reincarnation': 24, 'gems': 1e70, 'coins': 1e50}
    obs, health = provider.sample(save)
    assert health['process_connected'] is True
    assert 'mana_current' in obs

    # Game crashes / exits
    proc1.alive = False
    obs, health = provider.sample(save)
    assert health['process_connected'] is False
    assert health['memory_provider_health'] == 'DISCONNECTED'
    assert obs == {}

    # New game session starts with different PID and start_time
    proc2 = MockAVM2Process(pid=25, start_time=9999)
    provider.pid_resolver = lambda: 25
    provider.process_factory = lambda pid: proc2

    # Old mapping must be rejected because it belonged to proc1
    obs, health = provider.sample(save)
    assert health['process_connected'] is True
    assert 'mana_current' not in obs # Stale mapping from proc1 was invalidated
    assert health['memory_provider_health'] == 'CONNECTED_UNMAPPED'


def test_live_state_provider_fusion_with_process_memory(tmp_path):
    proc = MockAVM2Process(pid=10, start_time=500)
    provider = MemoryProvider(tmp_path, pid_resolver=lambda: 10, process_factory=lambda pid: proc)
    provider._connect()

    # Setup live mana and coins in memory
    mana_d = proc.base + 0x200
    proc.write_test_double(mana_d, 742.8)
    mana_s = proc.base + 0x100
    proc.write_test_atom(mana_s, mana_d | 7)

    coins_d = proc.base + 0x208
    proc.write_test_double(coins_d, 9.99e135)
    coins_s = proc.base + 0x104
    proc.write_test_atom(coins_s, coins_d | 7)

    ident = proc.identity
    provider.register(FieldMapping('mana_current', ident, mana_s, 'AVM2Number', 'VERIFIED', 'test', 0, 1e9))
    provider.register(FieldMapping('coins', ident, coins_s, 'AVM2Number', 'VERIFIED', 'test', 0, 1e308))

    save_data = {
        'reincarnation': 24, 'ascension': 0, 'gems': 1e70,
        'coins': 1.0e130, # Stale save coins
        'coins_this_game': 1.0e130,
        'mana': 200.0, # Stale save mana
        'save_timestamp': time.time(),
        'save_age_seconds': 0.5,
        'excavations': 1500, 'alignment': 1, 'faction': 0
    }

    live_provider = LiveStateProvider(save_reader=lambda: save_data, memory=provider, state_dir=tmp_path)
    state = live_provider.get()

    # Persistent fields come from save
    assert state['reincarnation'] == 24
    assert state['provenance']['reincarnation']['source'] == 'AIR_SHAREDOBJECT'

    # Volatile fields come from live process memory!
    assert state['mana_current'] == 742.8
    assert state['mana'] == 742.8 # Alias synced
    assert state['provenance']['mana_current']['source'] == 'PROCESS_MEMORY'
    assert state['provenance']['mana_current']['confidence'] == 'VERIFIED'

    assert state['coins'] == 9.99e135
    assert state['provenance']['coins']['source'] == 'PROCESS_MEMORY'
    assert state['provenance']['coins']['confidence'] == 'VERIFIED'

    # Telemetry health reflects process memory active
    assert state['telemetry']['memory_provider_health'] == 'HEALTHY'
    assert 'mana_current' in state['telemetry']['verified_fields']
    assert 'coins' in state['telemetry']['verified_fields']
