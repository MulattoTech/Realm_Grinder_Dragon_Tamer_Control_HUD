from src.telemetry_presenter import dragon_goal_presentation
from unittest.mock import MagicMock, patch
from pathlib import Path
import re


def profile_state(**raw):
    return {
        'game_identity': {'supported': True, 'swf_sha256': 'current-hash', 'game_version': '4.3.22'},
        'raw_data': raw or {'trophies': {}},
    }


def plan(steps, target='Drakeling', complete=False):
    return {'steps': steps, 'next_action': {'target': target}, 'complete': complete}


def test_unknown_profile_and_missing_fields_remain_unknown():
    state = {'raw_data': {'trophies': {}}}
    p = plan([{'name': 'Drakeling', 'status': 'READY', 'owned': False,
               'conditions': [{'field': 'dragon_quest_counter', 'op': 'gte',
                               'value': 7200, 'actual': 7200, 'satisfied': True}]}])

    result = dragon_goal_presentation(state, p)

    assert result['profile_status'] == 'UNKNOWN'
    assert result['completion'] == 'UNKNOWN'
    assert result['milestones'][0]['status'] == 'UNKNOWN'
    assert result['blocker'] == 'Supported game identity: UNKNOWN'


def test_dragon_counter_unknown_is_not_called_elapsed_time_or_ready():
    state = profile_state(trophies={})
    p = plan([{'name': 'Drakeling', 'status': 'UNKNOWN', 'owned': False,
               'conditions': [{'field': 'dragon_quest_counter', 'op': 'gte',
                               'value': 7200, 'actual': None, 'satisfied': None}]}])

    result = dragon_goal_presentation(state, p)

    assert result['milestones'][0]['status'] == 'UNKNOWN'
    assert result['milestones'][0]['blockers'] == [
        'Dragon quest counter: UNKNOWN / 7,200; updater semantics UNKNOWN'
    ]
    assert 'elapsed' not in result['milestones'][0]['blockers'][0].lower()
    assert '43200' not in str(result)
    assert '7200' not in result['milestones'][0]['blockers'][0]


def test_counter_value_above_threshold_does_not_fabricate_purchase_readiness():
    state = profile_state(trophies={})
    p = plan([{'name': 'Hatch!', 'status': 'READY', 'owned': False,
               'conditions': [{'field': 'dragon_quest_counter', 'op': 'gte',
                               'value': 7200, 'actual': 8000, 'satisfied': True}]}])

    result = dragon_goal_presentation(state, p)

    assert result['milestones'][0]['status'] == 'UNKNOWN'
    assert 'updater semantics UNKNOWN' in result['milestones'][0]['blockers'][0]


def test_requirements_are_rendered_from_planner_conditions():
    state = profile_state(trophies={})
    p = plan([{'name': 'Dragon', 'status': 'LOCKED', 'owned': False,
               'conditions': [
                   {'field': 'reincarnation', 'op': 'gte', 'value': 46, 'actual': 44, 'satisfied': False},
                   {'field': 'faction', 'op': 'eq', 'value': 0, 'actual': 1, 'satisfied': False},
                   {'field': 'assistants_current', 'op': 'gte', 'value': 5000, 'actual': 3000, 'satisfied': False},
                   {'field': 'mana_max', 'op': 'gte', 'value': 60000, 'actual': 50000, 'satisfied': False},
               ]}])

    result = dragon_goal_presentation(state, p)

    assert result['milestones'][0]['status'] == 'BLOCKED'
    detail = ' | '.join(result['milestones'][0]['blockers'])
    assert '44 / 46' in detail
    assert 'Current faction' in detail
    assert '3,000 / 5,000' in detail
    assert 'Maximum mana' in detail and '50,000 / 60,000' in detail


def test_completion_requires_observed_trophy_210_even_if_plan_says_complete():
    p = plan([{'name': 'Dragon Tamer', 'status': 'OWNED', 'owned': True}],
             target=None, complete=True)

    no_trophy = dragon_goal_presentation(profile_state(trophies={}), p)
    trophy_missing = dragon_goal_presentation({'game_identity': {'supported': True}}, p)
    actual_trophy = dragon_goal_presentation(profile_state(trophies={'210': {}}), p)

    assert no_trophy['completion'] == 'IN_PROGRESS'
    assert no_trophy['blocker'] == 'Trophy 210 not observed in the save'
    assert trophy_missing['completion'] == 'UNKNOWN'
    assert actual_trophy['completion'] == 'COMPLETE'
    assert actual_trophy['trophy_210_owned'] is True


def test_unsupported_profile_is_not_reported_as_progress_ready():
    state = {'game_identity': {'supported': False}, 'raw_data': {'trophies': {}}}
    p = plan([{'name': 'Hatch!', 'status': 'READY', 'owned': False, 'conditions': []}])

    result = dragon_goal_presentation(state, p)

    assert result['profile_status'] == 'UNSUPPORTED'
    assert result['milestones'][0]['status'] == 'UNKNOWN'
    assert result['milestones'][0]['blockers'] == ['Game identity is not a supported profile']


def test_start_keeps_stop_when_consequential_telemetry_is_not_authorized(tmp_path):
    from src.monitor_window import ModernDragonTrackerApp
    app = MagicMock()
    app.save_selected_path = MagicMock()
    app.c_red = '#red'
    app.c_amber = '#amber'
    stop = tmp_path / 'STOP'
    stop.write_text('paused')
    game_state = {'telemetry': {'process_connected': True,
                                'consequential_actions_allowed': False}}

    with patch('src.monitor_window.require_interactive_session'), \
         patch('src.monitor_window.get_live_game_state', return_value=game_state), \
         patch('src.monitor_window.load_config', return_value={'paused': True}), \
         patch('src.monitor_window.save_config') as save, \
         patch('src.monitor_window.STOP_FILE', str(stop)):
        result = ModernDragonTrackerApp.start_selected_path(app)

    assert result is False
    assert stop.exists()
    save.assert_not_called()


def test_stop_controls_write_only_existing_stop_and_pause_state(tmp_path):
    from src.monitor_window import ModernDragonTrackerApp
    stop = tmp_path / 'STOP'
    config = {'paused': False}
    app = MagicMock()
    app.c_amber = '#amber'
    app.c_red = '#red'
    app.config = config
    app._stop_worker = lambda emergency=False: ModernDragonTrackerApp._stop_worker(app, emergency)

    with patch('src.monitor_window.STOP_FILE', str(stop)), \
         patch('src.monitor_window.load_config', return_value=config.copy()), \
         patch('src.monitor_window.save_config') as save, \
         patch('src.monitor_window.os._exit') as exit_process:
        result = ModernDragonTrackerApp.action_emergency_stop(app)

    assert result is True
    assert stop.read_text() == 'Emergency STOP'
    assert save.call_args.args[0]['paused'] is True
    exit_process.assert_not_called()


def test_hud_does_not_claim_old_stage_facts_or_window_restoration():
    source = Path('src/monitor_window.py').read_text(encoding='utf-8')
    presenter = Path('src/telemetry_presenter.py').read_text(encoding='utf-8')
    for text in (source, presenter):
        assert '43200' not in text
        assert '43,200' not in text
        assert '3750' not in text
        assert '3,750' not in text
        assert '50000' not in text
        assert '50,000' not in text
    assert 'SW_SHOWNOACTIVATE' not in source
    assert 'force fast-track' not in source.lower()


def test_controls_use_plain_language_without_always_on_claims():
    source = Path('src/monitor_window.py').read_text(encoding='utf-8')
    visible_literals = [match.group(2) for match in re.finditer(
        r'\b(?:text|title)\s*=\s*([\'\"])(.*?)\1', source, re.DOTALL
    )]
    visible_text = '\n'.join(visible_literals).casefold()

    assert '24/7' not in visible_text
    assert 'autopilot' not in visible_text
    assert 'skynet' not in visible_text
    assert 'ultron' not in visible_text
    assert 'turbo' not in visible_text
