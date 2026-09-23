"""Save semantics and safe hybrid source selection regressions."""
import importlib
import json
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]

def normalizer():
    module = importlib.import_module('src.save_reader')
    assert hasattr(module, 'normalize_save_data'), 'Explicit save semantics are missing'
    return module.normalize_save_data

def sample():
    return {'reincarnation': 24, 'gems': 2.4e68, 'coins': 1e130, 'mana': 812.0,
            'alignment': 2, 'faction': 5, 'excavations': 1500,
            'stats': [{'stats': 1e140}] + [{}]*11 + [{'stats': 23590}],
            'buildings': {'9': {'q': 100}},
            'spells': {'3': {'t': -1, 'active0': 520},
                       '11': {'t': -1, 'active0': 280, 'active1': 1180, 'active2': 4172, 'a': False}},
            'trophies': {}, 'upgrades': {}}


def test_mana_current_is_not_maximum_or_regeneration():
    state = normalizer()(sample())
    assert state['mana_current'] == 812
    assert state['mana'] == 812  # Backward-compatible current-mana alias.
    assert state['mana_max'] is None
    assert state['mana_regeneration'] is None


def test_hellfire_uses_spell_11_active_time_not_call_to_arms_timer():
    state = normalizer()(sample())
    assert state['hellfire_time'] == 280
    assert state['hellfire_active_time_this_r'] == 1460
    assert state['hellfire_active_time_total'] == 5632
    assert state['hellfire_autocast'] is False
    assert state['hellfire_since_hatch'] is None


def test_ambiguous_stat_is_not_fairy_assistants():
    state = normalizer()(sample())
    assert state['fairy_assistants'] is None
    assert state['assistants_current'] is None
    assert state['assistants_total'] is None
    assert state['legacy_stat_12'] == 23590


def test_trophy_ownership_is_record_presence_not_upgrade_flag():
    data = sample()
    data['trophies']['211'] = {'id': 211, 'u1': False, 'u2': 0}
    assert normalizer()(data)['has_egg'] is True

@pytest.mark.parametrize('key,value', [('gems', float('nan')), ('gems', -1),
                                      ('reincarnation', -1), ('reincarnation', 24.5),
                                      ('coins', float('inf'))])
def test_corrupt_core_save_values_are_rejected(key, value):
    data = sample(); data[key] = value
    with pytest.raises(ValueError):
        normalizer()(data)


def test_normalizer_does_not_mutate_save():
    data = sample()
    before = json.dumps(data, sort_keys=True)
    normalizer()(data)
    assert json.dumps(data, sort_keys=True) == before


def test_legacy_json_decoder_branch_works():
    import base64, zlib
    from src.py_savecodec import decode_realm_grinder_save
    data = {'reincarnation': 24, 'gems': 1234}
    encoded = '$s' + base64.b64encode(zlib.compress(json.dumps(data).encode())).decode() + '$e'
    assert decode_realm_grinder_save(encoded) == data


def test_binary_decoder_has_no_concurrent_mutable_access(monkeypatch):
    import src.py_savecodec as codec
    from src.save_reader import extract_save_string_from_sol
    raw = extract_save_string_from_sol()
    active = 0
    maximum = 0
    lock = threading.Lock()
    original = codec.PythonSaveDecoder.decode_struct
    def instrumented(self, data):
        nonlocal active, maximum
        with lock:
            active += 1; maximum = max(maximum, active)
        try:
            time.sleep(0.002)
            return original(self, data)
        finally:
            with lock: active -= 1
    monkeypatch.setattr(codec.PythonSaveDecoder, 'decode_struct', instrumented)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(codec.decode_realm_grinder_save, [raw]*32))
    assert maximum == 1
    assert all(r['reincarnation'] == results[0]['reincarnation'] for r in results)


def test_invalid_configuration_fails_paused(monkeypatch, tmp_path):
    import src.config as config
    path = tmp_path/'bot_config.json'; path.write_text('{broken')
    monkeypatch.setattr(config, 'CONFIG_FILE', str(path))
    assert config.load_config()['paused'] is True


def live_api():
    assert (ROOT/'src/live_state.py').exists(), 'Hybrid provider is missing'
    return importlib.import_module('src.live_state')

class FakeMemory:
    def __init__(self, fields=None, connected=True):
        self.fields = fields or {}
        self.health = {'process_connected': connected, 'memory_handle_open': connected,
                       'pid': 17 if connected else None, 'verified_fields': list(self.fields)}
    def sample(self, save_state):
        return self.fields, self.health
    def close(self):
        pass


def snapshot():
    state = normalizer()(sample())
    state['save_timestamp'] = time.time()
    state['save_age_seconds'] = 0
    return state


def observation(value, confidence='VERIFIED', age=0):
    return {'value': value, 'source': 'PROCESS_MEMORY', 'timestamp': time.time()-age,
            'confidence': confidence, 'validation_source': 'two_cast_regeneration_cycles'}


def test_fusion_memory_only_overrides_validated_volatile_fields(tmp_path):
    api = live_api()
    fields = {'mana_current': observation(900.5), 'gems': observation(999),
              'reincarnation': observation(999)}
    state = api.LiveStateProvider(save_reader=snapshot, memory=FakeMemory(fields), state_dir=tmp_path).get()
    assert state['mana_current'] == state['mana'] == 900.5
    assert state['reincarnation'] == 24 and state['gems'] == 2.4e68
    assert state['provenance']['mana_current']['source'] == 'PROCESS_MEMORY'
    assert state['provenance']['gems']['source'] == 'AIR_SHAREDOBJECT'
    assert state['mana_max'] is None
    assert state['telemetry']['process_connected']

@pytest.mark.parametrize('field', [observation(900, 'LOW'), observation(900, age=20),
                                  observation(float('nan')), observation(-1)])
def test_untrusted_stale_or_invalid_memory_falls_back(tmp_path, field):
    api = live_api()
    state = api.LiveStateProvider(save_reader=snapshot,
        memory=FakeMemory({'mana_current': field}), state_dir=tmp_path).get()
    assert state['mana_current'] == 812
    assert state['provenance']['mana_current']['source'] == 'AIR_SHAREDOBJECT'


def test_disconnected_memory_preserves_save_with_blocked_actions(tmp_path):
    api = live_api()
    provider = api.LiveStateProvider(save_reader=snapshot, memory=FakeMemory(connected=False), state_dir=tmp_path)
    state = provider.get()
    assert state['reincarnation'] == 24
    assert state['telemetry']['consequential_actions_allowed'] is False
    assert (tmp_path/'telemetry_health.json').exists()


def test_last_good_save_is_explicitly_stale_after_decoder_failure(tmp_path):
    api = live_api()
    calls = 0
    def read():
        nonlocal calls
        calls += 1
        if calls > 1: raise ValueError('Partial save')
        return snapshot()
    provider = api.LiveStateProvider(save_reader=read, memory=FakeMemory(), state_dir=tmp_path)
    provider.get()
    state = provider.get()
    assert state['telemetry']['save_provider_health'] == 'STALE_ERROR'
    assert state['telemetry']['consequential_actions_allowed'] is False
    assert 'Partial save' in state['telemetry']['save_error']


def test_stale_save_never_becomes_fresh_by_reading_it_again(tmp_path):
    api = live_api()
    def read():
        state = snapshot(); state['save_timestamp'] = time.time()-600
        state['save_age_seconds'] = 600
        return state
    provider = api.LiveStateProvider(save_reader=read, memory=FakeMemory(), state_dir=tmp_path)
    state = provider.get()
    assert state['provenance']['gems']['age_ms'] >= 590000
    assert state['telemetry']['consequential_actions_allowed'] is False


def test_no_save_is_not_reported_as_a_new_r0_game(tmp_path):
    api = live_api()
    def broken(): raise FileNotFoundError('No save')
    provider = api.LiveStateProvider(save_reader=broken, memory=FakeMemory(), state_dir=tmp_path)
    with pytest.raises(FileNotFoundError): provider.get()


def memory_api():
    assert (ROOT/'src/memory/provider.py').exists(), 'Session-mapping provider is missing'
    return importlib.import_module('src.memory.provider')


def test_mapping_is_bound_to_creation_time_and_confidence():
    api = memory_api()
    from src.memory.process import ProcessIdentity
    identity = ProcessIdentity(17, 123, 'RealmGrinderDesktop.exe', 8)
    mapping = api.FieldMapping('mana_current', identity, 4096, 'Float64', 'VERIFIED',
                               'two_cast_regeneration_cycles', 0, 1e9)
    assert mapping.valid_for(identity)
    assert not mapping.valid_for(ProcessIdentity(17, 124, 'RealmGrinderDesktop.exe', 8))
    mapping.confidence = 'LOW'
    assert not mapping.valid_for(identity)


def test_mapping_range_nan_and_expired_process_rejected():
    api = memory_api()
    from src.memory.process import ProcessIdentity
    identity = ProcessIdentity(17, 123, 'RealmGrinderDesktop.exe', 8)
    mapping = api.FieldMapping('mana_current', identity, 4096, 'Float64', 'VERIFIED', 'test', 0, 1000)
    assert mapping.accepts(812)
    assert not mapping.accepts(-1)
    assert not mapping.accepts(1001)
    assert not mapping.accepts(float('nan'))
    assert not mapping.valid_for(None)


def test_process_discovery_uses_existing_windows_dependencies(monkeypatch):
    import sys
    from src.memory.provider import game_pid
    monkeypatch.setitem(sys.modules, 'psutil', None)
    pid = game_pid()
    assert pid is None or isinstance(pid, int)


def test_memory_provider_reuses_existing_window_discovery(monkeypatch):
    import src.window as window_module
    from src.memory.provider import game_pid
    class Window:
        pid = 424242
        def find_window(self): return True
    monkeypatch.setattr(window_module, 'RealmGrinderWindow', Window)
    assert game_pid() == 424242



def test_passive_save_anchor_matches_do_not_claim_live_mana_verification(tmp_path):
    from src.memory.provider import MemoryProvider
    from src.memory.process import ProcessIdentity
    from src.memory.scanner import Candidate,ScanResult
    class Reader:
        identity=ProcessIdentity(17,123,'RealmGrinderDesktop.exe',4)
        value=100.0
        def read_double(self,address): return self.value
        def read_value(self,address,datatype): return self.value
    reader=Reader()
    provider=MemoryProvider(tmp_path,discovery_enabled=True)
    provider.reader=reader
    provider._tracking={'identity':reader.identity,
       'result':ScanResult(reader.identity,[Candidate(4096,100.0,'Float64')]),
       'fingerprint':'0','anchor':100.0,'changes':0}
    for index,value in enumerate((101.0,102.0),1):
        reader.value=value
        provider._rediscover_mana({'mana_current':value,'save_timestamp':time.time(),
                                  'save_fingerprint':str(index),'reincarnation':24,'gems':100,'faction':5,'alignment':2})
    assert provider.mappings=={}, 'Monotonic full-mana/max-mana coincidences are not cast/regeneration proof'


def test_windows_utf8_bom_configuration_preserves_options(monkeypatch,tmp_path):
    import src.config as config
    path=tmp_path/'bot_config.json'
    path.write_text('{"paused":true,"cycle_delay_sec":17}',encoding='utf-8-sig')
    monkeypatch.setattr(config,'CONFIG_FILE',str(path))
    loaded=config.load_config()
    assert loaded['paused'] is True and loaded['cycle_delay_sec']==17
