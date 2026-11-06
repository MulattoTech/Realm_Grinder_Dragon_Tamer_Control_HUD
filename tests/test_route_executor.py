import importlib
from pathlib import Path
import copy
import pytest

def api():
    assert Path('src/route_executor.py').exists(), 'Selected-route execution is not integrated'
    return importlib.import_module('src.route_executor')

def test_resolve_plural_installed_faction_labels():
    catalog={'Goblins Trade Treaty':{'id':216},'Fairies Trade Treaty':{'id':197}}
    assert api().catalog_entry(catalog,'Goblin Trade Treaty')['id']==216
    assert api().catalog_entry(catalog,'Fairy Trade Treaty')['id']==197

def test_already_owned_stoic_does_not_search_or_click(tmp_path):
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return {'raw_data':{'upgrades':{'552':{'u1':True}}}}
        def load(self,name):return {'Stoic Resistance':{'id':552}}
    result=api().RouteExecutor(Actions()).purchase_named({'target':'Stoic Resistance'})
    assert result['success'] and result['action']=='ALREADY_OWNED'


def test_goblin_template_dispatches_after_bank_even_without_research_facility(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import src.config as config

    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Automatic'})
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):
            return {'reincarnation':24,'faction':3,'alignment':2,'gems':1e72,
                    'game_identity':{'supported':True,'save_version':58,
                        'swf_sha256':'7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'},
                    'raw_data':{'saveVersion':58,'upgrades':{'412':{'u1':True}},'buildings':{}}}
        def load(self,_name):return {}
        def manifest(self,_recommendation):return {'verified':True,'required_upgrade_ids':[1],'merc_spells':[]}
        def deploy_template(self,_template):raise AssertionError('Mercenary template UI must not be used for Goblin')

    executor=api().RouteExecutor(Actions())
    executor.planner=SimpleNamespace(next_step=lambda *_args:{'action':'deploy_build','target':'Goblin build',
        'template':'S50,S105','recommendation':{'name':'Goblin build'}})
    executor.collect=lambda _step:pytest.fail('Research deployment must not be hidden as resource collection')
    executor.deploy_template=lambda template:{'success':False,'status':'BLOCKED',
        'action':'RESEARCH_UI_NOT_CALIBRATED','template':template}

    result=executor.run_once()

    assert result['status']=='BLOCKED'
    assert result['action']=='RESEARCH_UI_NOT_CALIBRATED'
    assert result['template']=='S50,S105'


def test_goblin_route_collects_until_bank_is_owned(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import src.config as config

    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Automatic'})
    before={'reincarnation':24,'faction':3,'alignment':2,'gems':1e72,
        'game_identity':{'supported':True,'save_version':58,
            'swf_sha256':'7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'},
        'raw_data':{'saveVersion':58,'upgrades':{},'buildings':{}},
        'save_fingerprint':'before','telemetry':{'pid':11,'process_start_time':22,
            'consequential_actions_allowed':True}}
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return before
        def load(self,_name):return {}
        def manifest(self,_recommendation):return {'verified':True,'required_upgrade_ids':[1],'merc_spells':[]}
    executor=api().RouteExecutor(Actions())
    executor.planner=SimpleNamespace(next_step=lambda *_args:{'action':'deploy_build','target':'Goblin build',
        'template':'S50,S105','recommendation':{'name':'Goblin build'}})
    executor.collect=lambda step:{'success':False,'status':'OBSERVING','action':'COLLECT_RESOURCES','step':step}
    executor.deploy_template=lambda _template:pytest.fail('Do not attempt research before Goblin Bank 412 is owned')

    result=executor.run_once()

    assert result['action']=='PREPARE_GOBLIN_BANK'
    assert result['status']=='OBSERVING'
    assert result['step']['target']=='Goblin build'


def test_goblin_bank_purchase_requires_fresh_same_process_save(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import src.config as config

    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Automatic'})
    identity={'pid':11,'process_start_time':22,'consequential_actions_allowed':True}
    base={'reincarnation':24,'faction':3,'alignment':2,'gems':1e72,
        'game_identity':{'supported':True,'save_version':58,
            'swf_sha256':'7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'},
        'raw_data':{'saveVersion':58,'upgrades':{},'buildings':{}},
        'save_fingerprint':'before','telemetry':identity}
    after={**base,'save_fingerprint':'after','raw_data':{'saveVersion':58,
        'upgrades':{'412':{'u1':True}},'buildings':{}}}
    states=iter((base,base,after))
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return next(states)
        def load(self,_name):return {}
        def manifest(self,_recommendation):return {'verified':True,'required_upgrade_ids':[1],'merc_spells':[]}
    executor=api().RouteExecutor(Actions())
    executor.planner=SimpleNamespace(next_step=lambda *_args:{'action':'deploy_build','target':'Goblin build',
        'template':'S50,S105','recommendation':{'name':'Goblin build'}})
    executor.collect=lambda _step:{'success':False,'status':'OBSERVING','action':'COLLECT_RESOURCES'}
    executor.deploy_template=lambda _template:pytest.fail('Facility purchase must be proven before research dispatch')

    result=executor.run_once()

    assert result['success'] and result['status']=='VERIFIED'
    assert result['action']=='GOBLIN_BANK_PURCHASED'
    assert result['upgrade_id']==412


def test_goblin_bank_transition_without_process_identity_stops_uncertain(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import src.config as config

    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Automatic'})
    base={'reincarnation':24,'faction':3,'alignment':2,'gems':1e72,
        'game_identity':{'supported':True,'save_version':58,
            'swf_sha256':'7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'},
        'raw_data':{'saveVersion':58,'upgrades':{},'buildings':{}},
        'save_fingerprint':'before','telemetry':{'consequential_actions_allowed':True}}
    after={**base,'save_fingerprint':'after','raw_data':{'saveVersion':58,
        'upgrades':{'412':{'u1':True}},'buildings':{}}}
    states=iter((base,base,after))
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return next(states)
        def load(self,_name):return {}
        def manifest(self,_recommendation):return {'verified':True,'required_upgrade_ids':[1],'merc_spells':[]}
    executor=api().RouteExecutor(Actions())
    executor.planner=SimpleNamespace(next_step=lambda *_args:{'action':'deploy_build','target':'Goblin build',
        'template':'S50,S105','recommendation':{'name':'Goblin build'}})
    executor.collect=lambda _step:{'success':False,'status':'OBSERVING','action':'COLLECT_RESOURCES'}

    result=executor.run_once()

    assert not result['success'] and result['status']=='UNCERTAIN'
    assert result['action']=='GOBLIN_BANK_OWNERSHIP_UNCERTAIN'
    assert (tmp_path/'STOP').exists()


def test_unverified_faction_template_stays_fail_closed(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import src.config as config

    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Automatic'})
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return {'reincarnation':24,'faction':None,'alignment':None,'gems':1e72,
                              'raw_data':{'saveVersion':58,'upgrades':{}}}
        def load(self,_name):return {}
        def manifest(self,_recommendation):return {'verified':True,'required_upgrade_ids':[1],'merc_spells':[]}
        def deploy_template(self,_template):raise AssertionError('No template input for an unknown faction')

    executor=api().RouteExecutor(Actions())
    executor.planner=SimpleNamespace(next_step=lambda *_args:{'action':'deploy_build','target':'unknown build',
        'template':'S50','recommendation':{'name':'unknown build'}})
    executor.collect=lambda _step:pytest.fail('Unknown faction must not collect or click')

    result=executor.run_once()

    assert result['status']=='BLOCKED' and result['action']=='FACTION_UNVERIFIED'


def test_collect_waits_for_delayed_fresh_save_with_coin_growth(tmp_path,monkeypatch):
    import src.config as config
    import src.route_executor as module

    monkeypatch.setattr(config,'load_config',lambda:{'auto_click_realm':False,
        'auto_buy_buildings':True,'auto_buy_upgrades':False,'auto_spells':False})
    monkeypatch.setattr(module,'input_allowed',lambda _window:True)
    clicks=[]
    class UI:
        def __init__(self,*_args):pass
        def click_control(self,name):clicks.append(name)
    monkeypatch.setattr(module,'SemanticUI',UI)
    monkeypatch.setattr('src.spell_policy.plan_spells',lambda _state:{'casts':[]})

    before={'coins_this_game':100,'reincarnation':24,'save_fingerprint':'before',
        'telemetry':{'consequential_actions_allowed':True,'pid':8,'process_start_time':99}}
    after={**before,'coins_this_game':150,'save_fingerprint':'after'}
    elapsed=[0.0]
    reads=[0]
    class Actions:
        state_dir=tmp_path
        window=object()
        def read(self):
            reads[0]+=1
            return after if elapsed[0]>=1 else before

    executor=module.RouteExecutor(Actions())
    monkeypatch.setattr(module.time,'monotonic',lambda:elapsed[0])
    monkeypatch.setattr(module.time,'sleep',lambda seconds:elapsed.__setitem__(0,elapsed[0]+seconds))

    result=executor.collect()

    assert result['success'] and result['status']=='VERIFIED'
    assert result['before']['coins_this_game']==100
    assert result['after']['coins_this_game']==150
    assert reads[0]>=3 and clicks==['buy_all_buildings']

def test_progression_setup_delegates_to_selected_route():
    import ast
    tree=ast.parse(Path('src/progression_actions.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='setup_build')
    assert any(isinstance(n,ast.Attribute) and n.attr=='run_once' for n in ast.walk(method))

def test_route_plan_uses_user_selection_not_only_recommended_build(tmp_path,monkeypatch):
    import src.config as config
    monkeypatch.setattr(config,'load_config',lambda:{'selected_path':'Goblin'})
    class Actions:
        state_dir=tmp_path
        window=None
        def read(self):return {'reincarnation':24,'gems':1e68,'coins':1e68,'alignment':2,'faction':-1,'ascension':0,
                    'raw_data':{'trophies':{},'upgrades':{'20':{'u1':True}}}}
        def load(self,name):return {'Gem Power':{'id':20},'Goblins Trade Treaty':{'id':216}}
    result=api().RouteExecutor(Actions()).plan()
    assert result['target']=='Goblin Trade Treaty' and result['selected_path']=='Goblin'

def test_transaction_can_report_proven_no_effect_for_purchase_only(tmp_path):
    from src.action_verification import TransactionRunner
    before={'reincarnation':24,'save_fingerprint':'a','telemetry':{'consequential_actions_allowed':True,'pid':1,'process_start_time':1}}
    after=dict(before,save_fingerprint='b')
    clock=[0];calls=[0]
    def read():calls[0]+=1;return copy.deepcopy(before if calls[0]==1 else after)
    def sleep(dt):clock[0]+=dt
    runner=TransactionRunner(read,tmp_path,lambda:False,lambda:'backup',clock=lambda:clock[0],sleep=sleep,timeout=.3,poll_interval=.1)
    result=runner.run('PURCHASE',lambda s:True,lambda:None,lambda a,b:False,allow_no_effect=True)
    assert not result['success'] and result['status']=='NO_EFFECT'


def test_partial_template_changes_are_not_full_build_success():
    import src.route_executor as module
    assert hasattr(module,'template_progress')
    manifest={'required_upgrade_ids':[1,2,3],'merc_spells':[6,9]}
    before={'raw_data':{'upgrades':{},'mercSpell1':0,'mercSpell2':0}}
    after={'raw_data':{'upgrades':{'1':{'u1':True}},'mercSpell1':6,'mercSpell2':0}}
    result=module.template_progress(before,after,manifest)
    assert result['progressed'] and not result['complete']
    assert result['upgrades_owned']==1 and result['spells_selected']==1
