from types import SimpleNamespace

from src.progression_actions import ProgressionActions


def action_fixture(tmp_path, step):
    actions = ProgressionActions.__new__(ProgressionActions)
    actions.state_dir = tmp_path
    actions.read = lambda: {}
    actions._knowledge = SimpleNamespace(plan_target=lambda target, state: {
        'complete': False, 'goal': target, 'next_action': step})
    return actions


def test_goal_dispatch_preserves_required_reincarnation(tmp_path):
    actions = action_fixture(tmp_path, {'action': 'reach_reincarnation', 'target_r': 48})
    seen = []
    actions.advance_reincarnation = lambda **kw: seen.append(kw) or {'success': False}
    actions.execute_named_goal('Dragon Tamer')
    assert seen == [{'target_r': 48}]


def test_unimplemented_resource_strategy_is_an_explicit_blocker(tmp_path):
    actions = action_fixture(tmp_path, {'action': 'collect_resource', 'field': 'mana_max',
                                       'target': 'Elder Dragon', 'amount': 60000})
    calls = []
    actions.route = SimpleNamespace(collect=lambda: calls.append('click'))
    result = actions.execute_named_goal('Dragon Tamer')
    assert result['status'] == 'BLOCKED' and 'mana_max' in result['message']
    assert calls == []


def test_build_only_never_takes_the_reset_route(monkeypatch):
    monkeypatch.setattr('src.config.load_config', lambda: {'selected_goal': 'Build only'})
    actions = ProgressionActions.__new__(ProgressionActions)
    actions.setup_build = lambda: {'action': 'SETUP_ONLY'}
    assert actions.auto_clear()['action'] == 'SETUP_ONLY'


def test_dragon_goal_uses_executable_dependency_graph(monkeypatch):
    monkeypatch.setattr('src.config.load_config', lambda: {'selected_goal': 'Dragon Tamer'})
    actions = ProgressionActions.__new__(ProgressionActions)
    actions.execute_named_goal = lambda target: {'goal': target}
    assert actions.auto_clear() == {'goal': 'Dragon Tamer'}
