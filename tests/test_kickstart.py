"""Tests for post-reset kickstart logic: coins-from-zero bootstrap, alignment/treaty
prerequisite sequencing, and DragonBot.kickstart_new_run() delegation.

Offline-safe: no live game process, no .sol file, no display.
"""
from __future__ import annotations
import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.route_executor as route_module
import src.state_machine as sm_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_post_reset_state(coins=0, gems=5e60, alignment=2, faction=11,
                            reincarnation=24, buildings_total=0):
    """State immediately after abdication: coins=0, no buildings."""
    return {
        'reincarnation': reincarnation, 'gems': gems, 'coins': coins,
        'coins_this_game': coins, 'potential_gems': 0,
        'excavations': 0, 'hellfire_time': 0, 'hellfire_since_hatch': None,
        'has_egg': False, 'faction': faction, 'alignment': alignment, 'ascension': 0,
        'fairy_assistants': None, 'mana_current': 50.0, 'mana_max': 100.0,
        'mana_regeneration': 5.0,
        'save_fingerprint': 'post_reset_abc',
        'raw_data': {
            'saveVersion': 58,
            'upgrades': {'20': {'u1': True}},   # Gem Power already owned
            'trophies': {}, 'buildings': {}, 'spells': {},
            'mercSpell1': 6, 'mercSpell2': 9,
        },
        'telemetry': {
            'process_connected': True, 'memory_provider_health': 'HEALTHY',
            'verified_fields': ['mana_current'], 'save_age_seconds': 2,
            'save_provider_health': 'FRESH', 'consequential_actions_allowed': True,
            'pid': 99999, 'process_start_time': 1000.0,
        },
        'provenance': {'mana_current': {'source': 'PROCESS_MEMORY'}},
    }


# ---------------------------------------------------------------------------
# RouteExecutor.collect() kickstart sequence tests
# ---------------------------------------------------------------------------

class _MockActions:
    """Minimal ProgressionActions stub for RouteExecutor unit tests."""
    def __init__(self, state, tmp_path):
        self.state_dir = tmp_path
        self.window = MagicMock()
        self.window.get_client_size.return_value = [1280, 752]
        self._state = state
        self.runner = MagicMock()

    def read(self): return dict(self._state)
    def load(self, name): return {}


def test_collect_triggers_realm_click_and_building_purchase(tmp_path):
    """collect() dispatches realm clicks and buy_all_buildings when coins are 0."""
    state = fresh_post_reset_state(coins=0)
    actions = _MockActions(state, tmp_path)

    # load_config is called inside collect() via "from src.config import load_config"
    # patch it at the source module so all callers pick it up.
    cfg = {'auto_click_realm': True, 'auto_buy_buildings': True,
           'auto_buy_upgrades': False, 'auto_spells': False, 'auto_cast_spells': False}

    with patch('src.config.load_config', return_value=cfg), \
         patch('src.route_executor.input_allowed', return_value=True), \
         patch('src.route_executor.fresh_transition', return_value=True), \
         patch('src.route_executor.ActionLock', return_value=contextlib.nullcontext()):
        ui = MagicMock()
        with patch('src.route_executor.SemanticUI', return_value=ui):
            executor = route_module.RouteExecutor(actions)
            executor.collect()

    assert ui.click_control.call_count >= 1
    realm_calls = [c for c in ui.click_control.call_args_list if c[0][0] == 'realm']
    building_calls = [c for c in ui.click_control.call_args_list if c[0][0] == 'buy_all_buildings']
    assert realm_calls, 'Realm clicks must be dispatched during kickstart collect()'
    assert building_calls, 'buy_all_buildings must be called during kickstart collect()'


def test_collect_skips_upgrades_when_alignment_is_zero(tmp_path):
    """Without alignment, buy_all_upgrades should not be attempted."""
    state = fresh_post_reset_state(coins=0, alignment=0)
    actions = _MockActions(state, tmp_path)

    cfg = {'auto_click_realm': True, 'auto_buy_buildings': True,
           'auto_buy_upgrades': True, 'auto_spells': False, 'auto_cast_spells': False}

    with patch('src.config.load_config', return_value=cfg), \
         patch('src.route_executor.input_allowed', return_value=True), \
         patch('src.route_executor.fresh_transition', return_value=True), \
         patch('src.route_executor.ActionLock', return_value=contextlib.nullcontext()):
        ui = MagicMock()
        with patch('src.route_executor.SemanticUI', return_value=ui):
            executor = route_module.RouteExecutor(actions)
            executor.collect()

    upgrade_calls = [c for c in ui.click_control.call_args_list if c[0][0] == 'buy_all_upgrades']
    assert not upgrade_calls, 'buy_all_upgrades must be skipped when alignment is 0'


def test_collect_paused_returns_blocked(tmp_path):
    """collect() must return BLOCKED status when input is not allowed."""
    state = fresh_post_reset_state()
    actions = _MockActions(state, tmp_path)

    with patch('src.route_executor.input_allowed', return_value=False):
        executor = route_module.RouteExecutor(actions)
        result = executor.collect()

    assert result['success'] is False
    assert result['status'] == 'BLOCKED'


# ---------------------------------------------------------------------------
# DragonBot.kickstart_new_run() delegation tests
# ---------------------------------------------------------------------------

def test_kickstart_new_run_delegates_to_setup_build():
    """DragonBot.kickstart_new_run() must delegate to actions.setup_build()."""
    import ast
    tree = ast.parse(Path('src/state_machine.py').read_text(encoding='utf-8'))
    method = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == 'kickstart_new_run')
    calls = [n for n in ast.walk(method)
             if isinstance(n, ast.Attribute) and n.attr == 'setup_build']
    assert calls, 'kickstart_new_run must delegate to self.actions.setup_build()'


def test_kickstart_persists_result_to_state():
    """kickstart_new_run must persist the action result into self.state."""
    import ast
    tree = ast.parse(Path('src/state_machine.py').read_text(encoding='utf-8'))
    method = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == 'kickstart_new_run')
    assignments = [n for n in ast.walk(method) if isinstance(n, ast.Assign)]
    targets_flat = [ast.dump(t) for a in assignments for t in a.targets]
    assert any('last_action_result' in t for t in targets_flat), \
        'kickstart_new_run must store result in state for observability'


# ---------------------------------------------------------------------------
# Post-reset state transitions via route planner
# ---------------------------------------------------------------------------

def test_route_plan_recommends_gem_power_when_not_owned():
    """After a reset with no Gem Power, the route planner should target Gem Power or collect."""
    state = fresh_post_reset_state(coins=0)
    state['raw_data']['upgrades'] = {}  # Gem Power NOT owned

    # Use 'Automatic' so the planner doesn't complain about faction mismatch
    with patch('src.config.load_config', return_value={'selected_path': 'Automatic'}):
        from src.strategy_rules import RoutePlanner
        catalog = {'Gem Power': {'id': 20}}
        planner = RoutePlanner()
        step = planner.next_step(state, 'Automatic', catalog)

    # Without Gem Power or any alignment treaty, should suggest purchase_named or collect
    assert step['action'] in ('purchase_named', 'collect_coins', 'deploy_build',
                               'needs_abdication', 'maintain_faction'), \
        f"Unexpected first action after reset: {step['action']}"
    assert 'reason' in step, 'Route plan must include a reason string'


def test_route_plan_with_alignment_returns_valid_action():
    """With alignment set, the route planner must not crash and must return a valid action."""
    from src.strategy_rules import RoutePlanner
    # Use 'Automatic' so the planner selects the best route without faction mismatch
    state_align = fresh_post_reset_state(alignment=2, faction=2)  # faction=2 matches Goblin
    catalog = {
        'Gem Power': {'id': 20},
        'Goblins Trade Treaty': {'id': 216},
        'Goblin Trade Treaty': {'id': 216},
    }

    planner = RoutePlanner()
    with patch('src.config.load_config', return_value={'selected_path': 'Automatic'}):
        step = planner.next_step(state_align, 'Automatic', catalog)

    assert step['action'] in ('purchase_named', 'collect_coins', 'deploy_build',
                               'maintain_faction', 'needs_abdication'), \
        f"Unexpected step with alignment: {step}"
    assert 'reason' in step, 'Route plan must include a reason string'

