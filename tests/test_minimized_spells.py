import copy
from types import SimpleNamespace

import pytest

from src.action_verification import TransactionRunner
from src.route_executor import RouteExecutor, SUPPORTED_4322_SWF


def make_executor(tmp_path, monkeypatch, change=True):
    import src.config
    import src.route_executor
    config = {'auto_spells': True, 'auto_cast_spells': True}
    monkeypatch.setattr(src.config, 'load_config', lambda: config)
    monkeypatch.setattr(src.route_executor, 'input_allowed', lambda _: True)
    state = {'reincarnation': 24, 'faction': 3, 'alignment': 2,
             'mana_current': 1000, 'save_fingerprint': 'before',
             'game_identity': {'supported': True, 'swf_sha256': SUPPORTED_4322_SWF, 'save_version': 58},
             'telemetry': {'consequential_actions_allowed': True, 'pid': 4, 'process_start_time': 5},
             'raw_data': {'saveVersion': 58, 'spells': {'3': {'c': 13, 't': -1, 'a': False}}}}
    sent = []
    after = copy.deepcopy(state)
    after['save_fingerprint'] = 'after'
    after['raw_data']['spells']['3'].update(c=14 if change else 13, t=10 if change else -1)
    def read():
        return after if sent else state
    def send(key, **_):
        sent.append(key)
    elapsed = [0]
    window = SimpleNamespace(is_minimized=lambda: True, press_key=send)
    actions = SimpleNamespace(window=window, state_dir=tmp_path, read=read)
    actions.runner = TransactionRunner(read, tmp_path, lambda: False, lambda: 'test-backup',
        clock=lambda: elapsed[0], sleep=lambda s: elapsed.__setitem__(0, elapsed[0]+s), timeout=1)
    return RouteExecutor(actions), state, after, sent, config


def test_minimized_collection_sends_only_one_verified_spell(tmp_path, monkeypatch):
    executor, _, _, sent, _ = make_executor(tmp_path, monkeypatch)
    monkeypatch.setattr('src.route_executor.SemanticUI', lambda *_: pytest.fail('No minimized visual input'))
    result = executor.collect()
    assert sent == ['2']
    assert result['status'] == 'VERIFIED'
    assert result['proof']['before_casts'] == 13
    assert result['proof']['after_casts'] == 14


@pytest.mark.parametrize('fault', ['active', 'autocast', 'mana', 'version', 'missing_count', 'disabled'])
def test_minimized_spell_preconditions_send_nothing(tmp_path, monkeypatch, fault):
    executor, state, _, sent, config = make_executor(tmp_path, monkeypatch)
    record = state['raw_data']['spells']['3']
    if fault == 'active': record['t'] = 10
    if fault == 'autocast': record['a'] = True
    if fault == 'mana': state['mana_current'] = 399
    if fault == 'version': state['game_identity']['swf_sha256'] = 'unknown'
    if fault == 'missing_count': record.pop('c')
    if fault == 'disabled': config['auto_cast_spells'] = False
    result = executor.collect()
    assert not sent and result['status'] == 'BLOCKED'


def test_passive_coins_do_not_verify_minimized_spell_and_stop_retry(tmp_path, monkeypatch):
    executor, _, after, sent, _ = make_executor(tmp_path, monkeypatch, change=False)
    after['coins_this_game'] = 1e100
    result = executor.collect()
    assert sent == ['2'] and result['status'] == 'NO_EFFECT'
    assert (tmp_path/'STOP').exists()


def test_changed_process_cannot_verify_spell(tmp_path, monkeypatch):
    executor, _, after, sent, _ = make_executor(tmp_path, monkeypatch)
    after['telemetry']['pid'] = 9
    result = executor.collect()
    assert sent == ['2'] and result['status'] == 'UNCERTAIN'
    assert (tmp_path/'STOP').exists()


@pytest.mark.parametrize('fault', ['inactive_timer', 'stale_save', 'multiple_casts'])
def test_ambiguous_spell_transition_is_not_verified(tmp_path, monkeypatch, fault):
    executor, _, after, sent, _ = make_executor(tmp_path, monkeypatch)
    if fault == 'inactive_timer': after['raw_data']['spells']['3']['t'] = -1
    if fault == 'stale_save': after['save_fingerprint'] = 'before'
    if fault == 'multiple_casts': after['raw_data']['spells']['3']['c'] = 15
    result = executor.collect()
    assert sent == ['2'] and result['status'] in ('NO_EFFECT', 'UNCERTAIN')
    assert (tmp_path/'STOP').exists()
