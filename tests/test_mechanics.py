"""Source mechanics are interpreted as data, never executed as wiki code."""
import importlib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

def api():
    assert (ROOT/'src/mechanics.py').exists(), 'Mechanic prerequisite engine is missing'
    return importlib.import_module('src.mechanics')


def rule(name,dependencies=(),conditions=(),costs=(),**kwargs):
    result={'name':name,'dependencies':list(dependencies),'conditions':list(conditions),'costs':list(costs),
            'reviewed':True,'sources':[{'url':'http://musicfamily.org/realm/Upgrades/'}],
            'action':{'action':'purchase_named','target':name},'ownership':{'kind':'upgrade','id':len(name)}}
    result.update(kwargs);return result


def test_dependency_graph_orders_bootstrap_before_alignment():
    a=api()
    rules=[rule('Gem Power'),rule('Stoic Resistance',['Gem Power']),rule('Proof of Neutrality',['Stoic Resistance'],
            costs=[{'field':'coins','amount':1e16}])]
    book=a.RuleBook(rules)
    state={'coins':1e16,'raw_data':{'upgrades':{}}}
    plan=book.plan('Proof of Neutrality',state)
    assert plan['next_action']['target']=='Gem Power'
    assert [step['name'] for step in plan['steps']]==['Gem Power','Stoic Resistance','Proof of Neutrality']


def test_owned_dependencies_are_skipped_but_costs_are_not():
    a=api();book=a.RuleBook([rule('Gem Power'),rule('Proof of Neutrality',['Gem Power'],costs=[{'field':'coins','amount':1e16}])])
    state={'coins':100,'raw_data':{'upgrades':{'9':{'u1':True}}}}
    result=book.plan('Proof of Neutrality',state)
    assert result['next_action']['action']=='collect_coins'
    assert result['next_action']['target_coins']==1e16


def test_faction_coin_costs_check_each_currency_not_combined_sum():
    a=api();r=rule('Test',costs=[{'field':'raw_data.factionCoins.0.factionCoins','amount':100},
                               {'field':'raw_data.factionCoins.1.factionCoins','amount':100}])
    result=a.RuleBook([r]).plan('Test',{'raw_data':{'upgrades':{},'factionCoins':[{'factionCoins':10000},{'factionCoins':2}]}})
    step=result['steps'][-1]
    assert step['status']=='NEEDS_RESOURCES'
    assert step['costs'][1]['deficit']==98


def test_unknown_measurement_is_unknown_not_zero_or_passed():
    a=api();r=rule('Elder Dragon',conditions=[{'field':'mana_max','op':'gte','value':50000}])
    result=a.RuleBook([r]).plan('Elder Dragon',{'mana':999999,'mana_max':None,'raw_data':{'upgrades':{}}})
    assert result['next_action']['action']=='needs_measurement'
    assert result['steps'][-1]['status']=='UNKNOWN'


def test_unrecognized_requirement_never_disappears():
    a=api();r=rule('Other',conditions=[{'op':'unparsed','text':'Complete the special challenge'}])
    result=a.RuleBook([r]).plan('Other',{'raw_data':{'upgrades':{}}})
    assert result['steps'][-1]['status']=='UNKNOWN'


def test_unreviewed_or_unsourced_rules_never_authorize_purchase():
    a=api()
    for update in ({'reviewed':False},{'sources':[]}):
        r=rule('Test',**update);result=a.RuleBook([r]).plan('Test',{'raw_data':{'upgrades':{}}})
        assert result['next_action']['action']=='reference_only'


def test_stage_mismatch_is_reported_not_reinterpreted():
    a=api();r=rule('Test',scope={'ascensions':[0,1],'min_r':3})
    result=a.RuleBook([r]).plan('Test',{'reincarnation':130,'ascension':2,'raw_data':{'upgrades':{}}})
    assert result['steps'][-1]['status']=='UNSUPPORTED_STAGE'


def test_cycle_is_rejected_and_missing_dependency_has_a_named_blocker():
    a=api()
    with pytest.raises(ValueError,match='cycle'):
        a.RuleBook([rule('a',['b']),rule('b',['a'])]).plan('a',{})
    result=a.RuleBook([rule('a',['missing'])]).plan('a',{})
    assert result['next_action']['target']=='missing'
    assert result['next_action']['action']=='reference_only'


def test_owned_trophy_does_not_need_upgrade_u1():
    a=api();r=rule('Trophy',ownership={'kind':'trophy','id':210})
    result=a.RuleBook([r]).plan('Trophy',{'raw_data':{'trophies':{'210':{'u1':False}}}})
    assert result['complete'] is True and result['next_action'] is None


def test_missing_ownership_collection_is_unknown():
    a=api();result=a.RuleBook([rule('Test')]).plan('Test',{})
    assert result['steps'][-1]['status']=='UNKNOWN'


def test_explicit_faction_and_building_paths_are_resolved():
    a=api()
    assert a.read_field({'raw_data':{'buildings':{'9':{'q':100}}}},'raw_data.buildings.9.q')==100
    assert a.read_field({'items':[1,2]},'items.1')==2
    assert a.read_field({'items':[1,2]},'items.5') is None


def test_ascension_free_cost_does_not_erase_faction_coin_cost():
    a=api();r=rule('Test',costs=[{'field':'coins','amount':1e16,'free_from_ascension':1},
                               {'field':'raw_data.factionCoins.0.factionCoins','amount':20}])
    result=a.RuleBook([r]).plan('Test',{'ascension':1,'coins':0,'raw_data':{'upgrades':{},'factionCoins':[{'factionCoins':20}]}})
    assert result['steps'][-1]['status']=='READY'


def test_safe_formula_supports_wiki_arithmetic_without_eval():
    a=api()
    assert a.calculate_formula('(x + 1) * x / 2',{'x':24})==300
    assert a.calculate_formula('floor(sqrt(x)^2 + max(y, 2))',{'x':100,'y':3})==103


@pytest.mark.parametrize('expression',[
    '__import__("os").system("x")','x.__class__','[x for x in range(1000)]',
    '(lambda: 1)()','x[0]','10 ** 1000000','2 ** (2 ** 100)','1/0','sqrt(-1)'])
def test_unsafe_or_unbounded_formula_is_rejected(expression):
    a=api()
    with pytest.raises(ValueError):a.calculate_formula(expression,{'x':1})


def test_formula_missing_variable_stays_unknown():
    a=api()
    with pytest.raises(ValueError,match='Unknown variable'):a.calculate_formula('x+y',{'x':1})


def test_planning_never_mutates_state():
    a=api();state={'coins':100,'raw_data':{'upgrades':{}}}
    import copy
    before=copy.deepcopy(state);a.RuleBook([rule('Test')]).plan('Test',state)
    assert state==before
