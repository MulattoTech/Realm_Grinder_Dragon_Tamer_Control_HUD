"""Dragon timing follows observed transitions, not a guessed local start time."""
import importlib
from pathlib import Path
import pytest

def api():
    assert Path('src/quest_observer.py').exists(), 'Persisted milestone observations are missing'
    return importlib.import_module('src.quest_observer')

def state(token,stamp,egg=False,hatch=False,hellfire=0):
    return {'reincarnation':46,'save_fingerprint':token,'save_timestamp':stamp,
            'hellfire_active_time_total':hellfire,'raw_data':{'upgrades':{'604':{'u1':True}} if hatch else {},
            'trophies':{'211':{'u1':False}} if egg else {}}}
CATALOG={'spiky_rough_egg':{'id':211,'kind':'trophy','verified':True},
         'hatch':{'id':604,'kind':'upgrade','verified':True}}


def test_preexisting_egg_does_not_get_a_fabricated_earned_time(tmp_path):
    observer=api().QuestObserver(tmp_path/'quest.json',CATALOG)
    result=observer.observe(state('a',100,egg=True),now=200)
    assert result['quest']['egg_elapsed_seconds'] is None
    assert result['quest']['timing_status']['spiky_rough_egg']=='PREEXISTING_TIME_UNKNOWN'


def test_observed_transition_provides_conservative_elapsed_bound(tmp_path):
    observer=api().QuestObserver(tmp_path/'quest.json',CATALOG)
    observer.observe(state('a',100),now=100)
    result=observer.observe(state('b',105,egg=True),now=205)
    assert result['quest']['egg_elapsed_seconds']==100
    assert result['quest']['events']['spiky_rough_egg']['earliest']==100
    assert result['quest']['events']['spiky_rough_egg']['latest']==105


def test_restarting_observer_preserves_event_time(tmp_path):
    path=tmp_path/'quest.json';observer=api().QuestObserver(path,CATALOG)
    observer.observe(state('a',100),now=100);observer.observe(state('b',105,egg=True),now=105)
    result=api().QuestObserver(path,CATALOG).observe(state('c',110,egg=True),now=205)
    assert result['quest']['egg_elapsed_seconds']==100


def test_hellfire_counter_starts_at_observed_hatch_not_lifetime(tmp_path):
    observer=api().QuestObserver(tmp_path/'quest.json',CATALOG)
    observer.observe(state('a',100,egg=True,hellfire=100000),now=100)
    observer.observe(state('b',105,egg=True,hatch=True,hellfire=100100),now=105)
    result=observer.observe(state('c',110,egg=True,hatch=True,hellfire=100500),now=110)
    assert result['hellfire_since_hatch']==400


def test_counter_regression_is_unknown_not_zero_or_completion(tmp_path):
    observer=api().QuestObserver(tmp_path/'quest.json',CATALOG)
    observer.observe(state('a',100,egg=True,hellfire=100000),now=100)
    observer.observe(state('b',105,egg=True,hatch=True,hellfire=100100),now=105)
    result=observer.observe(state('c',110,egg=True,hatch=True,hellfire=1),now=110)
    assert result['hellfire_since_hatch'] is None


def test_future_or_out_of_order_save_cannot_create_event(tmp_path):
    observer=api().QuestObserver(tmp_path/'quest.json',CATALOG)
    observer.observe(state('a',100),now=100)
    result=observer.observe(state('b',90,egg=True),now=110)
    assert result['quest']['egg_elapsed_seconds'] is None
    assert result['quest']['observer_health']=='CLOCK_OR_SAVE_DISCONTINUITY'


def test_owned_condition_predicates_distinguish_missing_and_false():
    from src.mechanics import condition_value
    assert condition_value({'op':'owned_trophy','id':190},{}) is None
    assert condition_value({'op':'owned_trophy','id':190},{'raw_data':{'trophies':{}}}) is False
    assert condition_value({'op':'owned_trophy','id':190},{'raw_data':{'trophies':{'190':{'u1':False}}}}) is True


def test_knowledge_service_evaluates_reviewed_target_not_raw_text(tmp_path):
    assert Path('src/knowledge_service.py').exists(), 'Knowledge service integration is missing'
    from src.knowledge_service import KnowledgeService
    service=KnowledgeService(state_dir=tmp_path)
    result=service.plan_target('Gem Power',{'ascension':0,'gems':2,'coins':10,'raw_data':{'upgrades':{}}})
    assert result['next_action']['action']=='purchase_named'
    assert service.plan_target('Unrecognized game mechanic',{})['next_action']['action']=='reference_only'


def test_prior_excavations_do_not_bypass_the_r46_egg_requirement(tmp_path):
    from src.knowledge_service import KnowledgeService
    state={'reincarnation':24,'ascension':0,'excavations':1500,'raw_data':{'upgrades':{},'trophies':{}}}
    plan=KnowledgeService(state_dir=tmp_path).plan_target('Dragon Tamer',state)
    assert plan['next_action']['action']=='reach_reincarnation'
    assert plan['next_action']['target_r']==46

@pytest.mark.parametrize(('target','owned_upgrades'),[
    ('Hatch!',{'604':{'u1':False}}),
    ('Drakeling',{'604':{'u1':True},'605':{'u1':False}}),
    ('Dragon',{'604':{'u1':True},'605':{'u1':True},'606':{'u1':False}}),
    ('Elder Dragon',{'604':{'u1':True},'605':{'u1':True},'606':{'u1':True},'607':{'u1':False}}),
])
def test_r46_dragon_stages_are_available_in_pre_ascension_save(tmp_path,target,owned_upgrades):
    from src.knowledge_service import KnowledgeService
    state={'reincarnation':46,'ascension':0,'excavations':1500,'has_egg':True,
        'coins':1e100,'mana_max':50000,'fairy_assistants':3750,
        'hellfire_since_hatch':43200,
        'quest':{'egg_elapsed_seconds':43200,'drakeling_elapsed_seconds':43200,'dragon_elapsed_seconds':43200},
        'raw_data':{'saveVersion':58,'upgrades':owned_upgrades,
            'trophies':{'211':{}},'factionCoins':[{'factionCoins':1e12} for _ in range(11)]}}
    plan=KnowledgeService(state_dir=tmp_path).plan_target(target,state)
    stage=next(step for step in plan['steps'] if step['name']==target)
    assert stage['status']!='UNSUPPORTED_STAGE'
