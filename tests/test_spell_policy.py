from pathlib import Path
import importlib

def api():
    assert Path('src/spell_policy.py').exists(), 'State-aware spell policy missing'
    return importlib.import_module('src.spell_policy')

def state():
    return {'faction':11,'alignment':3,'reincarnation':24,'mana_current':5000,
            'raw_data':{'mercSpell1':6,'mercSpell2':9,'spells':{str(i):{'t':-1} for i in (18,3,7,6,9,17)}}}

def test_mercenary_second_spell_moves_spiritual_surge_to_six():
    result=api().spell_slots(state())
    assert result[6]=='4' and result[9]=='5' and result[17]=='6'
    s=state();s['raw_data']['mercSpell2']=0
    assert api().spell_slots(s)[17]=='5'

def test_spell_budget_prioritizes_buffs_without_overcommitting_mana():
    plan=api().plan_spells(state())
    assert plan['mana_committed']<=5000
    assert plan['casts'][0]['spell_id']==6
    assert all(c['spell_id']!=18 for c in plan['casts'])

def test_active_spells_are_not_recast_from_a_stale_recommendation():
    s=state();s['raw_data']['spells']['6']['t']=100
    plan=api().plan_spells(s)
    assert 6 not in [c['spell_id'] for c in plan['casts']]

def test_unknown_current_mana_disables_spending_prediction():
    s=state();s['mana_current']=None
    assert api().plan_spells(s)['casts']==[]

def test_tax_collection_uses_only_spare_mana_after_buffs_active():
    s=state()
    for value in s['raw_data']['spells'].values():value['t']=100
    plan=api().plan_spells(s)
    assert plan['casts'] and all(c['spell_id']==18 for c in plan['casts'])
    assert len(plan['casts'])<=3
