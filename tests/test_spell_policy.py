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

# --- Saturation autocasting tests ---

def test_mana_saturation_detected_when_within_50_of_max():
    """Within 50 mana of max triggers saturating=True."""
    s=state();s['mana_current']=1060.0;s['mana_max']=1100.0
    plan=api().plan_spells(s)
    assert plan['saturating'] is True
    assert plan['headroom'] is not None and plan['headroom']<=50.0

def test_mana_saturation_detected_when_above_95_pct():
    """>=95% of max triggers saturating=True even if headroom>50."""
    s=state();s['mana_current']=960.0;s['mana_max']=1000.0
    plan=api().plan_spells(s)
    assert plan['saturating'] is True
    assert plan['mana_saturation_pct']>=95.0

def test_saturation_dumps_mana_via_tax_collection():
    """When saturating, at least one Tax Collection (spell 18) is scheduled."""
    s=state()
    # Make all priority spells inactive (already active so not recast)
    for v in s['raw_data']['spells'].values():v['t']=100
    s['mana_current']=990.0;s['mana_max']=1000.0  # 99% full => saturating
    plan=api().plan_spells(s)
    assert plan['saturating'] is True
    tax_casts=[c for c in plan['casts'] if c['spell_id']==18]
    assert len(tax_casts)>=1,'Saturating mana must schedule Tax Collection bursts'

def test_saturation_budget_does_not_exceed_current_mana():
    """Budget never exceeds available mana even during saturation dump."""
    s=state()
    for v in s['raw_data']['spells'].values():v['t']=100
    s['mana_current']=1095.0;s['mana_max']=1100.0
    plan=api().plan_spells(s)
    assert plan['mana_committed']<=s['mana_current']

def test_headroom_is_none_when_mana_max_unknown():
    """headroom and mana_saturation_pct stay None when mana_max is not available."""
    s=state();s['mana_current']=5000.0;s.pop('mana_max',None)
    plan=api().plan_spells(s)
    assert plan['headroom'] is None
    assert plan['mana_saturation_pct'] is None
    assert plan['saturating'] is False

def test_not_saturating_below_threshold():
    """mana well below max should NOT trigger saturation."""
    s=state();s['mana_current']=500.0;s['mana_max']=1000.0
    plan=api().plan_spells(s)
    assert plan['saturating'] is False
    assert plan['mana_saturation_pct']==50.0

def test_plan_spells_returns_expected_result_keys():
    """plan_spells result always contains the new saturation keys."""
    plan=api().plan_spells(state())
    for key in ('casts','mana_committed','saturating','headroom','mana_saturation_pct'):
        assert key in plan, f'Missing key: {key}'
