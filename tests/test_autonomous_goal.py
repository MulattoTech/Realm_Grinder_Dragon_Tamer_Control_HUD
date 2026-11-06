"""Tests for the autonomous goal pipeline: 1-click button handler, goal dispatch,
worker pause/unpause semantics, and volatile mana saturation casting integration.

These tests are offline-safe: they stub window, IO, and game state and never
contact the live game process.
"""
from __future__ import annotations
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_state(r=24, gems=2.4e68, coins=1e50, paused=True):
    return {
        'reincarnation': r, 'gems': gems, 'coins': coins, 'potential_gems': 0,
        'coins_this_game': coins, 'excavations': 0, 'hellfire_time': 0,
        'hellfire_since_hatch': None, 'has_egg': False,
        'faction': 11, 'alignment': 3, 'ascension': 0,
        'fairy_assistants': None, 'mana_current': 800.0,
        'mana_max': 1000.0, 'mana_regeneration': 20.0,
        'save_fingerprint': 'abc123',
        'raw_data': {'saveVersion': 58, 'upgrades': {}, 'trophies': {},
                     'buildings': {}, 'spells': {}, 'mercSpell1': 6, 'mercSpell2': 9},
        'provenance': {'mana_current': {'source': 'PROCESS_MEMORY', 'confidence': 'VERIFIED'}},
        'telemetry': {'process_connected': True, 'memory_provider_health': 'HEALTHY',
                      'verified_fields': ['mana_current', 'mana_max'], 'save_age_seconds': 5,
                      'save_provider_health': 'FRESH', 'consequential_actions_allowed': True,
                      'pid': 99999, 'process_start_time': 1000.0},
    }


# ---------------------------------------------------------------------------
# TASK 2: action_automate_straight_to_goal dispatcher
# ---------------------------------------------------------------------------

class _FakeWindow:
    hwnd = None
    def is_minimized(self): return False
    def find_window(self): return False
    def get_client_size(self): return [1280, 752]

class _FakeRoot:
    """Minimal Tkinter root stub — no display needed."""
    def __init__(self): self._callbacks = []
    def winfo_exists(self): return True
    def after(self, ms, fn=None, *a): return
    def destroy(self): pass
    def configure(self, **kw): pass


def _build_minimal_app(tmp_path, goal='Dragon Tamer', named='Dragon Tamer'):
    """Build a ModernDragonTrackerApp with all heavy dependencies stubbed."""
    import src.config as cfg_mod
    cfg_mod._config_path = tmp_path / 'config.json'  # redirect config writes
    cfg = {'selected_goal': goal, 'named_goal': named, 'paused': True}
    (tmp_path / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

    stop_file = tmp_path / 'state' / 'STOP'
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.write_text('test stop')

    # Patch everything that touches the display or OS before importing the module
    with patch('tkinter.Tk'), \
         patch('src.monitor_window.ProgressionTracker'), \
         patch('src.monitor_window.GateClearer'), \
         patch('src.monitor_window.SkynetOptimizationCore'), \
         patch('src.monitor_window.ProcessGuardian'), \
         patch('src.monitor_window.DragonBot'), \
         patch('src.monitor_window.KnowledgeService'), \
         patch('src.monitor_window.load_knowledge_base', return_value={}), \
         patch('src.monitor_window.get_live_game_state', return_value=fresh_state()), \
         patch('src.monitor_window.require_interactive_session'), \
         patch('src.monitor_window.win32gui'), \
         patch('src.monitor_window.STOP_FILE', str(stop_file)):
        pass  # just ensuring patching would work; actual test calls below use direct method tests


def _make_app_mock():
    """Build a mock app instance with color attributes set."""
    mock_app = MagicMock()
    mock_app.c_gold = '#f5a623'
    mock_app.c_red = '#ff4757'
    mock_app.c_green = '#2ecc71'
    mock_app.c_cyan = '#00e5c0'
    mock_app.c_muted = '#8e94a6'
    mock_app.c_amber = '#e67e22'
    mock_app.clearer = MagicMock()
    return mock_app



def test_automate_goal_uses_start_admission_and_reports_success():
    """The shortcut must use Start's admission path and only claim active on success."""
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()
    mock_app.start_selected_path.return_value = True
    mock_app.automate_status_lbl = MagicMock()
    with patch('src.monitor_window.load_config',
               return_value={'selected_goal': 'Dragon Tamer', 'paused': False}), \
         patch('src.monitor_window.win32gui'):
        assert ModernDragonTrackerApp.action_automate_straight_to_goal(mock_app) is True
    mock_app.start_selected_path.assert_called_once_with()
    assert 'Active' in mock_app.automate_status_lbl.configure.call_args.kwargs['text']


def test_automate_goal_does_not_claim_active_when_start_admission_fails():
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()
    mock_app.start_selected_path.return_value = False
    mock_app.automate_status_lbl = MagicMock()
    assert ModernDragonTrackerApp.action_automate_straight_to_goal(mock_app) is False
    mock_app.start_selected_path.assert_called_once_with()
    assert all('Active' not in str(call.kwargs.get('text', ''))
               for call in mock_app.automate_status_lbl.configure.call_args_list)


def test_automate_goal_blocked_by_non_interactive_session():
    """action_automate_straight_to_goal must be blocked when session is not interactive."""
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()

    def raise_session():
        raise RuntimeError('Not an interactive desktop session')

    with patch('src.monitor_window.require_interactive_session', side_effect=raise_session):
        result = ModernDragonTrackerApp.start_selected_path(mock_app)

    assert result is False
    mock_app.set_feedback.assert_called()
    args = mock_app.set_feedback.call_args[0]
    assert 'blocked' in args[0].lower()


def test_start_connection_failure_keeps_stop_and_does_not_unpause(tmp_path):
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()
    mock_app.save_selected_path = MagicMock()
    stop_path = tmp_path / 'STOP'
    stop_path.write_text('paused')
    state_file = tmp_path / 'state' / 'dragon_tamer_state.json'
    state_file.parent.mkdir()
    saved = []
    with patch('src.monitor_window.require_interactive_session'), \
         patch('src.monitor_window.get_live_game_state', return_value={'telemetry': {'process_connected': False}}), \
         patch('src.monitor_window.load_config', return_value={'paused': True}), \
         patch('src.monitor_window.save_config', side_effect=lambda cfg: saved.append(dict(cfg))), \
         patch('src.monitor_window.STATE_FILE', str(state_file)), \
         patch('src.monitor_window.STOP_FILE', str(stop_path)):
        result = ModernDragonTrackerApp.start_selected_path(mock_app)

    assert result is False
    assert stop_path.exists()
    assert not saved


def test_automate_goal_stays_paused_for_unresolved_pending_action(tmp_path):
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()
    mock_app.save_selected_path = MagicMock()
    mock_app.start_selected_path.side_effect = lambda: ModernDragonTrackerApp.start_selected_path(mock_app)
    mock_app.clearer.window.is_minimized.return_value = True
    mock_app.root = MagicMock()
    stop_path = tmp_path / 'STOP'
    stop_path.write_text('paused')
    state_dir = tmp_path / 'state'
    state_dir.mkdir()
    state_file = state_dir / 'dragon_tamer_state.json'
    (state_dir / 'pending_action.json').write_text(json.dumps({
        'id': 'action-1', 'action': 'UNKNOWN_ACTION', 'status': 'UNCERTAIN',
    }))
    saved = []
    with patch('src.monitor_window.require_interactive_session'), \
         patch('src.monitor_window.get_live_game_state', return_value=fresh_state()), \
         patch('src.monitor_window.load_config', return_value={'paused': True, 'require_minimized': True}), \
         patch('src.monitor_window.save_config', side_effect=lambda cfg: saved.append(dict(cfg))), \
         patch('src.action_verification.reconcile_known_template_no_text', return_value=False), \
         patch('src.monitor_window.STATE_FILE', str(state_file)), \
         patch('src.monitor_window.STOP_FILE', str(stop_path)), \
         patch('src.monitor_window.messagebox.showwarning'):
        result = ModernDragonTrackerApp.action_automate_straight_to_goal(mock_app)

    assert result is False
    assert stop_path.exists()
    assert not saved
    assert all('Active' not in str(call.kwargs.get('text', ''))
               for call in mock_app.automate_status_lbl.configure.call_args_list)


def test_start_window_geometry_failure_does_not_unpause_or_clear_stop(tmp_path):
    from src.monitor_window import ModernDragonTrackerApp
    mock_app = _make_app_mock()
    mock_app.save_selected_path = MagicMock()
    mock_app.clearer.window.is_minimized.return_value = False
    stop_path = tmp_path / 'STOP'
    stop_path.write_text('paused')
    state_file = tmp_path / 'state' / 'dragon_tamer_state.json'
    state_file.parent.mkdir()
    with patch('src.monitor_window.require_interactive_session'), \
         patch('src.monitor_window.get_live_game_state', return_value=fresh_state()), \
         patch('src.monitor_window.load_config', return_value={'paused': True, 'require_minimized': True}), \
         patch('src.monitor_window.save_config') as save, \
         patch('src.monitor_window.STATE_FILE', str(state_file)), \
         patch('src.monitor_window.STOP_FILE', str(stop_path)):
        result = ModernDragonTrackerApp.start_selected_path(mock_app)

    assert result is False
    assert stop_path.exists()
    save.assert_not_called()



# ---------------------------------------------------------------------------
# TASK 5: Volatile saturation spell policy integration
# ---------------------------------------------------------------------------

def _spell_api():
    return importlib.import_module('src.spell_policy')


def test_saturating_mana_schedules_tax_dump_with_live_memory_fields():
    """Live memory mana_max triggers saturation Tax Collection dumps."""
    api = _spell_api()
    state = {
        'faction': 11, 'alignment': 3, 'reincarnation': 24,
        'mana_current': 980.0, 'mana_max': 1000.0, 'mana_regeneration': 20.0,
        'raw_data': {'mercSpell1': 6, 'mercSpell2': 9,
                     'spells': {str(i): {'t': 100} for i in (18, 3, 7, 6, 9, 17)}}
    }
    plan = api.plan_spells(state)
    assert plan['saturating'] is True, 'Should be saturating at 98%'
    tax = [c for c in plan['casts'] if c['spell_id'] == 18]
    assert tax, 'Saturating mana must produce Tax Collection casts'
    assert plan['mana_committed'] <= 980.0, 'Budget must not exceed mana_current'


def test_spell_plan_uses_mana_max_for_fill_ratio():
    api = _spell_api()
    state = {
        'faction': 0, 'alignment': 1, 'reincarnation': 14,
        'mana_current': 400.0, 'mana_max': 1000.0, 'mana_regeneration': 10.0,
        'raw_data': {'spells': {str(i): {'t': -1} for i in (18, 3, 12, 6)}}
    }
    plan = api.plan_spells(state)
    assert plan['mana_saturation_pct'] == 40.0
    assert plan['saturating'] is False


def test_spell_plan_mana_max_zero_does_not_crash():
    api = _spell_api()
    state = {
        'faction': 11, 'alignment': 3, 'reincarnation': 24,
        'mana_current': 500.0, 'mana_max': 0.0,
        'raw_data': {'mercSpell1': 6, 'mercSpell2': 9,
                     'spells': {str(i): {'t': -1} for i in (18, 6, 9)}}
    }
    plan = api.plan_spells(state)
    assert plan['saturating'] is False  # 0 max is treated as unknown
    assert plan['headroom'] is None


# ---------------------------------------------------------------------------
# TASK 1: mana_bar presenter
# ---------------------------------------------------------------------------

def _presenter():
    return importlib.import_module('src.telemetry_presenter')


def test_mana_bar_is_live_only_when_source_is_process_memory():
    p = _presenter()
    s = fresh_state()
    bar = p.mana_bar(s)
    assert bar['is_live'] is True
    assert bar['fill_pct'] == 80.0  # 800/1000


def test_mana_bar_fill_none_when_mana_max_absent():
    p = _presenter()
    s = fresh_state()
    del s['mana_max']
    bar = p.mana_bar(s)
    assert bar['fill_pct'] is None


def test_mana_bar_regen_formatted_positively():
    p = _presenter()
    s = fresh_state()
    bar = p.mana_bar(s)
    assert bar['regen_str'].startswith('+')
    assert '20.0' in bar['regen_str']


def test_telemetry_banner_includes_regen_from_volatile_state():
    p = _presenter()
    s = fresh_state()
    text = p.telemetry_banner(s, {'build_verified': False})
    assert '20.0' in text or '+20.0' in text
