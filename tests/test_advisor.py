from src.ai_engine import ProgressionAdvisor


def test_unknown_game_does_not_recommend_a_dragon_purchase():
    result = ProgressionAdvisor().evaluate({'reincarnation': 48, 'has_egg': True}, {})
    assert result['action_type'] == 'WAIT_FOR_EVIDENCE'
    assert result['payload']['plan']['next_action']['status'] == 'UNSUPPORTED_GAME_VERSION'


def test_legacy_mode_setting_has_no_effect_on_advice():
    state = {'reincarnation': 24, 'gems': 1e30, 'coins': 0}
    advisor = ProgressionAdvisor()
    result = advisor.evaluate(state, {'ultron_burst': True})
    assert 'ultron' not in result['reasoning'].lower()
    assert 'ultron_burst' not in result['payload']
