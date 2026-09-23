"""Integration regressions for measured forecasts and the actual production path."""
from types import SimpleNamespace
from pathlib import Path
import pytest


def test_eta_uses_explicit_in_memory_history_not_unrelated_disk_history(monkeypatch):
    from src.telemetry import ProgressionTracker
    tracker=ProgressionTracker();tracker.history=[]
    monkeypatch.setattr(tracker,'load_history',lambda:[{'time':1,'r':24,'run':[24,1,11],'potential_gems':1e100}])
    result=tracker.calculate_etas(24,1,100,{})
    assert result['current_r_eta_seconds'] is None


def test_eta_filters_old_permanent_gem_run(monkeypatch):
    import src.config as config
    from src.telemetry import ProgressionTracker
    import time
    now=time.time()
    tracker=ProgressionTracker()
    tracker.history=[{'time':now-70+i*10,'r':24,'gems':100,'run':[24,100,11],
                      'potential_gems':10.0**(93+i),'paused':False} for i in range(8)]
    monkeypatch.setattr(config,'load_config',lambda:{'paused':False})
    assert tracker.calculate_etas(24,200,1e100,{})['current_r_eta_seconds'] is None


def test_eta_observation_does_not_bridge_pause(monkeypatch):
    import src.telemetry as telemetry
    from src.measured_eta import estimate_target
    monkeypatch.setattr(telemetry.ProgressionTracker,'save_history',lambda self:None)
    tracker=telemetry.ProgressionTracker();tracker.history=[]
    for i in range(8):
        tracker.observe_state({'reincarnation':24,'gems':100,'faction':11,'alignment':3,
            'coins_this_game':1e100,'potential_gems':10.0**(50+i),
            'save_fingerprint':str(i),'save_timestamp':i*10},paused=i==5)
    points=[{'time':row['time'],'value':row['potential_gems'],'run':row['run']} for row in tracker.history]
    assert estimate_target(points,1e70,now=70)['seconds'] is None


@pytest.mark.parametrize('changes',[
    {'time':-1,'value':1e60,'run':'a'},
    {'time':200,'value':1e60,'run':'a'},
])
def test_eta_rejects_inconsistent_sample_times(changes):
    from src.measured_eta import estimate_target
    rows=[{'time':i*10,'value':10.0**(60+i),'run':'a'} for i in range(8)]
    rows.append(changes)
    assert estimate_target(rows,1e70,now=70)['seconds'] is None


def test_increasing_log_series_is_conditional_with_bounded_uncertainty():
    from src.measured_eta import estimate_target
    rows=[{'time':i*10,'value':10.0**(60+i),'run':'a'} for i in range(8)]
    result=estimate_target(rows,1e70,now=70)
    assert 29<=result['seconds']<=31
    assert result['lower_seconds']<=result['seconds']<=result['upper_seconds']<=7*86400


def test_normal_production_calls_the_working_route_executor():
    from src.progression_actions import ProgressionActions
    actions=ProgressionActions.__new__(ProgressionActions)
    calls=[]
    actions.route=SimpleNamespace(collect=lambda: calls.append('collect') or
        {'success':False,'action':'COLLECT_RESOURCES','status':'OBSERVING','message':'bounded production'})
    actions.read=lambda:{'coins_this_game':100,'reincarnation':24,'gems':100,'potential_gems':200}
    actions.diagnose_build=lambda state:{'build_verified':True}
    result=actions.maintain_production()
    assert calls==['collect'] and result['action']=='COLLECT_RESOURCES'


def test_complete_build_route_advances_to_production(tmp_path,monkeypatch):
    import src.config as config
    from src.route_executor import RouteExecutor
    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Neutral Mercenary'})
    state={'reincarnation':24,'gems':2.4e68,'faction':11,'alignment':3,
           'raw_data':{'upgrades':{'1':{'u1':True}},'mercSpell1':6,'mercSpell2':9}}
    manifest={'verified':True,'required_upgrade_ids':[1],'merc_spells':[6,9]}
    actions=SimpleNamespace(state_dir=tmp_path,read=lambda:state,
        load=lambda name:{'builds':{'test':manifest}} if name=='build_manifests.json' else {},
        manifest=lambda rec:manifest)
    executor=RouteExecutor(actions)
    executor.planner=SimpleNamespace(next_step=lambda *args:{'action':'deploy_build','target':'test',
        'recommendation':{'name':'test'},'template':'FR2','sources':[]})
    result=executor.plan()
    assert result['action']=='maintain_faction'


def test_spell_budget_respects_auto_cast_spells_switch_in_production_source():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'src/route_executor.py').read_text(encoding='utf-8')
    assert 'auto_cast_spells' in text



def test_named_goal_dispatches_only_a_ready_reviewed_purchase(tmp_path):
    from types import SimpleNamespace
    from src.progression_actions import ProgressionActions
    actions=ProgressionActions.__new__(ProgressionActions);actions.state_dir=tmp_path
    actions.read=lambda:{'ascension':0,'gems':1,'coins':10,'raw_data':{'upgrades':{}}}
    calls=[]
    actions.route=SimpleNamespace(purchase_named=lambda step:calls.append(step) or {'success':False,'status':'OBSERVING','message':'observed'})
    assert hasattr(actions,'execute_named_goal'), 'Named goal dispatch is not integrated'
    actions.execute_named_goal('Gem Power')
    assert calls[0]['target']=='Gem Power'


def test_unreviewed_named_goal_sends_no_input(tmp_path):
    from types import SimpleNamespace
    from src.progression_actions import ProgressionActions
    actions=ProgressionActions.__new__(ProgressionActions);actions.state_dir=tmp_path
    actions.read=lambda:{'raw_data':{'upgrades':{}}}
    calls=[];actions.route=SimpleNamespace(purchase_named=lambda step:calls.append(step))
    assert hasattr(actions,'execute_named_goal'), 'Named goal dispatch is not integrated'
    result=actions.execute_named_goal('Imaginary technique')
    assert not result['success'] and calls==[]


def test_owned_named_goal_is_verified_without_input(tmp_path):
    from src.progression_actions import ProgressionActions
    actions=ProgressionActions.__new__(ProgressionActions);actions.state_dir=tmp_path
    actions.read=lambda:{'ascension':0,'raw_data':{'upgrades':{'20':{'u1':True}}}}
    assert hasattr(actions,'execute_named_goal'), 'Named goal dispatch is not integrated'
    result=actions.execute_named_goal('Gem Power')
    assert result['success'] and result['action']=='NAMED_GOAL_OWNED'


def test_large_current_mana_cannot_create_a_dragon_tamer_directive():
    from src.ai_engine import SkynetOptimizationCore
    s={'reincarnation':46,'gems':1e90,'coins':1e200,'mana':999999,'mana_max':None,'has_egg':True,'raw_data':{'trophies':{}}}
    result=SkynetOptimizationCore().evaluate(s,{})
    assert result['decision']!='CLAIM_DRAGON_TAMER'


def test_resume_button_uses_the_same_pending_action_admission_as_start():
    import ast
    tree=ast.parse(Path('src/monitor_window.py').read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='action_toggle_pause')
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='start_selected_path' for n in ast.walk(node))

def test_launcher_prepares_a_fresh_checkout_before_opening_hud():
    import ast
    tree=ast.parse(Path('launcher.py').read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='main')
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='initialize' for n in ast.walk(node))
