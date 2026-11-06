"""Regression tests for state-proven actions, build truth and runtime safety."""
import importlib
import copy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

def api():
    assert (ROOT/'src/action_verification.py').exists(), 'Transactional verification is missing'
    return importlib.import_module('src.action_verification')

def state(r=24, gems=100, faction=5, token='before'):
    return {'reincarnation':r, 'gems':gems, 'faction':faction, 'alignment':2,
            'coins':10000, 'coins_this_game':100000, 'potential_gems':200,
            'save_fingerprint':token, 'save_timestamp':1000,
            'raw_data':{'saveVersion':58,'upgrades':{},'trophies':{},'buildings':{'9':{'q':100}},
                        'spells':{},'mercSpell1':0,'mercSpell2':0},
            'telemetry':{'consequential_actions_allowed':True,'pid':17,'process_start_time':123}}

class Clock:
    def __init__(self): self.t=0
    def now(self): return self.t
    def sleep(self, value): self.t+=value

class Feed:
    def __init__(self, *states): self.states=list(states); self.last=states[-1]
    def __call__(self):
        if self.states: self.last=self.states.pop(0)
        return copy.deepcopy(self.last)


def runner(tmp_path, feed, cancelled=lambda:False, backup=None):
    a=api(); clock=Clock()
    return a.TransactionRunner(feed, state_dir=tmp_path,
        cancelled=cancelled, backup=backup or (lambda:'test-backup.sol'),
        clock=clock.now, sleep=clock.sleep, timeout=1.0, poll_interval=0.1)


def test_reincarnation_requires_exactly_one_increment_and_fresh_save():
    a=api(); before=state()
    assert not a.reincarnation_verified(before,state(r=24,token='new'))
    assert not a.reincarnation_verified(before,state(r=26,token='new'))
    assert not a.reincarnation_verified(before,state(r=25))
    assert a.reincarnation_verified(before,state(r=25,gems=0,token='new'))


def test_abdication_requires_reset_not_only_more_gems():
    a=api(); before=state()
    after=state(gems=200,token='new')
    assert not a.abdication_verified(before,after)
    after['faction']=-1; after['alignment']=0; after['coins_this_game']=0
    assert a.abdication_verified(before,after)
    after['reincarnation']=25
    assert not a.abdication_verified(before,after)


def test_no_gain_build_reset_requires_explicit_no_gain_permission():
    a=api(); before=state(); after=state(faction=-1,token='new')
    after['alignment']=0; after['coins_this_game']=0
    assert not a.abdication_verified(before,after)
    assert a.abdication_verified(before,after,allow_no_gain=True)


def test_upgrade_ownership_is_not_record_presence():
    a=api(); s=state();s['raw_data']['upgrades']['194']={'u1':False}
    assert not a.upgrade_owned(s,194)
    s['raw_data']['upgrades']['194']['u1']=True
    assert a.upgrade_owned(s,194)
    s['raw_data']['trophies']['211']={'u1':False}
    assert a.trophy_owned(s,211)


def test_transaction_success_is_after_proof_and_one_dispatch(tmp_path):
    a=api(); before=state();after=state(r=25,gems=0,token='after'); calls=[]
    tx=runner(tmp_path,Feed(before,before,after))
    result=tx.run('REINCARNATED',lambda s:True,lambda:calls.append('input'),a.reincarnation_verified)
    assert result['success'] and result['status']=='VERIFIED'
    assert calls==['input']
    assert result['after']['reincarnation']==25


def test_unchanged_state_never_reports_success_or_retries_input(tmp_path):
    a=api();calls=[];tx=runner(tmp_path,Feed(state()))
    result=tx.run('REINCARNATED',lambda s:True,lambda:calls.append('input'),a.reincarnation_verified)
    assert not result['success'] and result['status']=='UNCERTAIN'
    assert calls==['input']
    again=tx.run('REINCARNATED',lambda s:True,lambda:calls.append('input'),a.reincarnation_verified)
    assert not again['success'] and calls==['input']


def test_cancelled_transaction_sends_no_input(tmp_path):
    a=api(); calls=[];tx=runner(tmp_path,Feed(state()),cancelled=lambda:True)
    result=tx.run('TEST',lambda s:True,lambda:calls.append('input'),a.reincarnation_verified)
    assert not result['success'] and calls==[]


def test_stale_state_cannot_authorize_input(tmp_path):
    a=api();s=state();s['telemetry']['consequential_actions_allowed']=False;calls=[]
    result=runner(tmp_path,Feed(s)).run('TEST',lambda s:True,lambda:calls.append(1),a.reincarnation_verified)
    assert not result['success'] and calls==[]


def test_failed_precondition_cannot_authorize_input(tmp_path):
    a=api();calls=[]
    result=runner(tmp_path,Feed(state())).run('TEST',lambda s:False,lambda:calls.append(1),a.reincarnation_verified)
    assert not result['success'] and calls==[]


def test_backup_failure_prevents_input(tmp_path):
    a=api();calls=[]
    def broken(): raise OSError('backup disk denied')
    result=runner(tmp_path,Feed(state()),backup=broken).run('TEST',lambda s:True,lambda:calls.append(1),a.reincarnation_verified)
    assert not result['success'] and calls==[]

def test_known_template_failure_before_text_can_be_reconciled_without_retry(tmp_path):
    a=api();path=tmp_path/'pending_action.json'
    before=state(faction=11,token='before')
    pending={'id':'abc123','action':'MERCENARY_TEMPLATE','status':'UNCERTAIN',
             'error':'Template Import dialog was not verified; no text was sent',
             'backup':'transaction.sol','before':a.state_summary(before)}
    a.write_json(path,pending)
    observed=state(faction=0,token='later')
    resolved=a.reconcile_known_template_no_text(path,observed,now=lambda:1234)
    saved=__import__('json').loads(path.read_text())
    assert resolved and saved['status']=='RECONCILED_NO_TEMPLATE_TEXT'
    assert saved['backup']=='transaction.sol' and saved['id']=='abc123'
    assert saved['reconciliation']['observed_after']['save_fingerprint']=='later'

@pytest.mark.parametrize('action,error',[
    ('REINCARNATE','Template Import dialog was not verified; no text was sent'),
    ('MERCENARY_TEMPLATE','No verified state transition before the observation timeout'),
])
def test_other_uncertain_transactions_are_never_auto_reconciled(tmp_path,action,error):
    a=api();path=tmp_path/'pending_action.json'
    a.write_json(path,{'id':'not-safe','action':action,'status':'UNCERTAIN','error':error,
                       'before':a.state_summary(state(faction=11))})
    assert not a.reconcile_known_template_no_text(path,state(token='later'))
    assert __import__('json').loads(path.read_text())['status']=='UNCERTAIN'

def test_known_template_reconciliation_requires_fresh_healthy_same_r_save(tmp_path):
    a=api();path=tmp_path/'pending_action.json';before=state(faction=11,token='before')
    a.write_json(path,{'id':'same-r','action':'MERCENARY_TEMPLATE','status':'UNCERTAIN',
        'error':'Template Import dialog was not verified; no text was sent','before':a.state_summary(before)})
    stale=state(token='later');stale['telemetry']['consequential_actions_allowed']=False
    assert not a.reconcile_known_template_no_text(path,stale)
    stale=state(r=25,token='later')
    assert not a.reconcile_known_template_no_text(path,stale)
    assert __import__('json').loads(path.read_text())['status']=='UNCERTAIN'


def test_process_restart_during_transaction_is_uncertain(tmp_path):
    a=api(); after=state(r=25,token='new'); after['telemetry']['process_start_time']=124
    result=runner(tmp_path,Feed(state(),after)).run('TEST',lambda s:True,lambda:None,a.reincarnation_verified)
    assert not result['success'] and result['status']=='UNCERTAIN'


def test_build_recommendation_does_not_prove_active_mercenary_build():
    a=api();result=a.verify_build(state(),{'name':'Neutral Mercenary','faction':'Mercenary','bloodline':'Fairy','template':'FR2'})
    assert not result['build_verified']
    assert any('faction' in problem.lower() for problem in result['missing'])
    assert any('bloodline' in problem.lower() for problem in result['missing'])


def test_empty_or_unvalidated_build_manifest_is_not_proof():
    a=api();s=state(faction=11);s['raw_data']['upgrades']['194']={'u1':True}
    rec={'name':'Merc','faction':'Mercenary','bloodline':'Fairy','template':'FR2'}
    result=a.verify_build(s,rec,manifest={'verified':True,'required_upgrade_ids':[]})
    assert not result['build_verified']


def test_complete_manifest_checks_all_owned_upgrades_and_spells():
    a=api();s=state(faction=11);s['alignment']=3
    s['raw_data']['upgrades']={'194':{'u1':True},'101':{'u1':True},'102':{'u1':True}}
    s['raw_data']['mercSpell1']=6;s['raw_data']['mercSpell2']=9
    rec={'name':'Merc','faction':'Mercenary','bloodline':'Fairy','template':'TEST'}
    manifest={'verified':True,'template':'TEST','save_version':58,'alignment':3,
              'required_upgrade_ids':[101,102],'merc_spells':[6,9]}
    assert a.verify_build(s,rec,manifest)['build_verified']
    s['raw_data']['upgrades']['102']['u1']=False
    assert not a.verify_build(s,rec,manifest)['build_verified']


def test_unknown_dragon_ids_cannot_prove_completion():
    a=api();s=state(r=46);s['mana']=999999;s['coins']=1e300
    assert a.milestone_owned(s,'elder_dragon',{}) is None
    assert a.milestone_owned(s,'dragon_tamer',{}) is None


def test_milestone_requires_verified_catalog_and_actual_ownership():
    a=api();s=state(r=46); catalog={'hatch':{'id':1234,'kind':'upgrade','verified':True}}
    assert a.milestone_owned(s,'hatch',catalog) is False
    s['raw_data']['upgrades']['1234']={'u1':True}
    assert a.milestone_owned(s,'hatch',catalog) is True
    catalog['hatch']['verified']=False
    assert a.milestone_owned(s,'hatch',catalog) is None


def test_ui_profile_requires_verified_action_and_matching_game_version():
    a=api();s=state()
    s['game_identity']={'supported':True,'swf_sha256':'a'*64}
    profile={'save_version':58,'swf_sha256':'a'*64,'verified_actions':[],'actions':{'abdication':[[200,25],[572,460]]}}
    assert not a.ui_action_verified(profile,'abdication',s)
    profile['verified_actions']=['abdication']
    assert a.ui_action_verified(profile,'abdication',s)
    s['raw_data']['saveVersion']=59
    assert not a.ui_action_verified(profile,'abdication',s)


def test_shared_lock_prevents_two_action_owners(tmp_path):
    a=api()
    with a.ActionLock(tmp_path):
        with pytest.raises(RuntimeError,match='action'):
            with a.ActionLock(tmp_path): pass


def test_safe_launcher_does_not_resume_just_by_opening_hud():
    import ast
    text=(ROOT/'launcher.py').read_text(encoding='utf-8')
    tree=ast.parse(text)
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    assert not [n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='unpause_bot']


def test_start_script_does_not_remove_stop_before_checks():
    text=(ROOT/'start.ps1').read_text(encoding='utf-8')
    assert 'param(' in text and '[switch]$Resume' in text
    assert 'SessionId' in text


@pytest.mark.parametrize('filename', ['src/state_machine.py','src/gate_clearer.py','src/monitor_window.py','src/state_capture.py'])
def test_high_value_consumers_use_hybrid_state(filename):
    text=(ROOT/filename).read_text(encoding='utf-8')
    assert 'from src.live_state import get_live_game_state' in text
    assert 'get_current_game_state()' not in text


def test_gate_reset_uses_shared_transaction_adapter():
    import ast
    tree=ast.parse((ROOT/'src/gate_clearer.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='clear_reincarnation_gate')
    calls=[n.func.attr for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
    assert 'advance_reincarnation' in calls
    assert 'send_hover_click' not in calls


def test_worker_has_one_decision_owner_and_no_pretend_steam_success():
    text=(ROOT/'src/state_machine.py').read_text(encoding='utf-8')
    assert 'fast_track_res = self.fast_track_gate()' not in text
    assert 'STEAM ACHIEVEMENT LEGITIMATELY ACHIEVED' not in text
    assert 'WorkerLease' in text


def test_gui_refresh_does_not_launch_game_or_run_guardian_actions():
    import ast
    tree=ast.parse((ROOT/'src/monitor_window.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_state')
    calls=[n.func.attr for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
    assert 'pulse_check' not in calls


def test_session_zero_cannot_launch_or_control_game(monkeypatch):
    import src.runtime_safety as safety
    monkeypatch.setattr(safety,'session_id',lambda pid=None:0)
    with pytest.raises(RuntimeError,match='desktop'):
        safety.require_interactive_session()


def test_minimized_placeholder_is_marked_synthetic():
    from src.window import RealmGrinderWindow
    window=RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.base_width=1280;window.base_height=752
    window.is_valid=lambda:True;window.is_minimized=lambda:True
    image=window.capture()
    assert image.info.get('capture_kind')=='SYNTHETIC_STATUS'
    assert image.info.get('is_live_ui_evidence') is False


def test_stop_script_only_targets_this_project():
    text=(ROOT/'stop.ps1').read_text(encoding='utf-8')
    assert '[regex]::Escape($PSScriptRoot)' in text
    assert 'paused' in text
