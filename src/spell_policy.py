"""Base-cost spell budget and slot layout; observations, not button order guesses.

Reference costs: musicfamily.org/realm/Spells/. Actual costs may be reduced by
upgrades, so these are conservative base costs rather than claimed live values.
The save timer is used only as an active/inactive indicator, not remaining time.
"""
import math
FACTION_SPELL={0:6,1:14,2:9,3:8,4:15,5:11,6:13,7:10,8:2}
COSTS={18:200,3:400,12:900,1:600,7:1000,6:1000,14:700,9:900,8:800,
       15:1000,11:1000,13:600,10:1000,2:600,17:2500}
PRIORITY=(6,9,8,13,10,2,15,11,14,7,1,12,3,17)


def spell_slots(state):
    raw=state.get('raw_data',{});slots={18:'1',3:'2'}
    alignment=state.get('alignment',0);faction=state.get('faction',-1)
    if alignment in (1,2,3):slots[{1:12,2:1,3:7}[alignment]]='3'
    next_slot=4
    if faction==11:
        for field in ('mercSpell1','mercSpell2'):
            identifier=raw.get(field,0)
            if identifier:slots[identifier]=str(next_slot);next_slot+=1
    elif faction in FACTION_SPELL:
        slots[FACTION_SPELL[faction]]='4';next_slot=5
    if state.get('reincarnation',0)>=14:slots[17]=str(next_slot)
    return slots


def plan_spells(state):
    """Plan spells with volatile mana saturation detection.

    Uses live memory fields (mana_current, mana_max, mana_regeneration) to
    detect saturation and aggressively schedule Tax Collection bursts when
    mana_current >= mana_max - 50 or mana_current / mana_max >= 0.95.
    """
    mana=state.get('mana_current');slots=spell_slots(state);raw=state.get('raw_data',{}).get('spells',{})
    mana_max=state.get('mana_max')
    # mana_regeneration is available from the AVM2 volatile memory engine but not
    # yet used for burst size estimation beyond basic saturation detection.
    result={'casts':[],'mana_committed':0,'source':'http://musicfamily.org/realm/Spells/',
            'cost_model':'conservative base costs; upgrades may reduce actual costs',
            'mana_saturation_pct':None,'headroom':None,'saturating':False}
    if mana is None or not isinstance(mana,(float,int)) or not math.isfinite(mana) or mana<0:return result

    # --- Saturation detection using live volatile mana fields ---
    saturating=False
    headroom=None
    if isinstance(mana_max,(float,int)) and math.isfinite(mana_max) and mana_max>0:
        headroom=mana_max-mana
        sat_pct=mana/mana_max
        result['headroom']=headroom
        result['mana_saturation_pct']=round(sat_pct*100,1)
        # Saturating: within 5% of max OR within 50 raw mana of max
        saturating=(headroom<=50.0 or sat_pct>=0.95)
        result['saturating']=saturating

    # --- Priority spell casting (descending priority order) ---
    inactive=[]
    for identifier in PRIORITY:
        if identifier not in slots:continue
        record=raw.get(str(identifier))
        if record is None:continue
        if record.get('t',-1)>=0:continue
        inactive.append(identifier);cost=COSTS[identifier]
        if cost<=mana-result['mana_committed']:
            result['casts'].append({'spell_id':identifier,'key':slots[identifier],'budget_cost':cost})
            result['mana_committed']+=cost

    # --- Saturating mana dump: burst Tax Collections to drain wasted regen ---
    # When saturating, fill available headroom; otherwise only use spare mana.
    if not inactive or saturating:
        available_for_tax=mana-result['mana_committed']
        if saturating and headroom is not None:
            # Aggressively dump: cast enough Tax Collections to consume saturated mana
            cap=max(1,int(headroom//COSTS[18])+1)
        else:
            # Normal fallback: spare mana above 500 floor, max 3 casts
            cap=min(3,max(0,int((available_for_tax-500)//COSTS[18])))
        for _ in range(cap):
            if COSTS[18]<=mana-result['mana_committed']:
                result['casts'].append({'spell_id':18,'key':'1','budget_cost':COSTS[18]})
                result['mana_committed']+=COSTS[18]
    return result
