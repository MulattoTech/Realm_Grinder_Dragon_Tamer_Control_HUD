import time
import pytest

from src.action_verification import ui_action_verified
from src.live_state import LiveStateProvider


class NoMemory:
    def sample(self, saved):
        return {}, {'process_connected': True}


def test_ordinary_telemetry_does_not_start_heap_discovery(tmp_path, monkeypatch):
    import src.live_state as live
    discovery = []
    def memory_factory(folder, discovery_enabled):
        discovery.append(discovery_enabled)
        return NoMemory()
    monkeypatch.setattr(live, 'MemoryProvider', memory_factory)
    LiveStateProvider(lambda: {}, state_dir=tmp_path)
    assert discovery == [False]


def test_observation_carries_current_binary_identity(tmp_path):
    identity = {'supported': True, 'swf_sha256': 'a'*64, 'game_version': '4.3.22', 'save_version': 58}
    saved = {'reincarnation': 24, 'save_timestamp': time.time(),
             'save_fingerprint': 'snapshot', 'raw_data': {'saveVersion': 58}}
    provider = LiveStateProvider(lambda: saved, NoMemory(), tmp_path,
                                 identity_reader=lambda: dict(identity))
    assert provider.get()['game_identity'] == identity
    identity.update(supported=False, swf_sha256='b'*64)
    assert provider.get()['game_identity'] == identity


def test_ui_calibration_is_bound_to_installed_binary():
    profile = {'save_version': 58, 'swf_sha256': 'a'*64,
               'verified_actions': ['reincarnation'], 'actions': {'reincarnation': [[10, 10]]}}
    state = {'raw_data': {'saveVersion': 58},
             'game_identity': {'supported': True, 'swf_sha256': 'b'*64}}
    assert not ui_action_verified(profile, 'reincarnation', state)
    state['game_identity']['swf_sha256'] = 'a'*64
    assert ui_action_verified(profile, 'reincarnation', state)
    state['game_identity']['supported'] = False
    assert not ui_action_verified(profile, 'reincarnation', state)
    state.pop('game_identity')
    assert not ui_action_verified(profile, 'reincarnation', state)


@pytest.mark.parametrize('supported,schema', [(False, 58), (True, 59), (True, None)])
def test_unknown_binary_or_save_schema_blocks_actions(tmp_path, supported, schema):
    identity = {'supported': supported, 'swf_sha256': 'a'*64, 'save_version': schema}
    saved = {'reincarnation': 24, 'save_timestamp': time.time(),
             'save_fingerprint': 'snapshot', 'raw_data': {'saveVersion': 58}}
    provider = LiveStateProvider(lambda: saved, NoMemory(), tmp_path,
                                 identity_reader=lambda: identity)
    assert provider.get()['telemetry']['consequential_actions_allowed'] is False


@pytest.mark.parametrize('digest,record,expected', [
    ('7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b',
     {'stats': 120, 'statsReset': 6000, 'statsRei': 2000}, 8120),
    ('a'*64, {'stats': 99999, 'statsReset': 0, 'statsRei': 0}, None),
    ('7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b',
     {'stats': 99999}, None),
    ('7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b',
     {'stats': float('nan'), 'statsReset': 0, 'statsRei': 0}, None),
])
def test_dragon_counter_reads_exact_installed_condition(tmp_path, digest, record, expected):
    identity = {'supported': True, 'swf_sha256': digest, 'save_version': 58}
    saved = {'reincarnation': 24, 'save_timestamp': time.time(),
             'save_fingerprint': 'snapshot', 'raw_data': {'saveVersion': 58, 'stats': [{}]*81+[record]}}
    result = LiveStateProvider(lambda: saved, NoMemory(), tmp_path,
                               identity_reader=lambda: identity).get()
    assert result.get('dragon_quest_counter') == expected
    if expected is not None:
        assert result['provenance']['dragon_quest_counter']['validation_source'] == 'installed_getFullStat_81'
