"""Pure presentation helpers: never convert unknown measurements into accomplishments."""
import math
from src.action_verification import milestone_owned

def measured(value):
    if value is None or not isinstance(value,(int,float)) or not math.isfinite(value):
        return 'Unknown'
    return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.1f}'

def mana_bar(state):
    """Return a dict ready for HUD mana bar display from live volatile state.

    Returns keys: current, maximum, regen, fill_pct, source_badge, is_live.
    fill_pct is None when either value is unknown.
    """
    current=state.get('mana_current')
    maximum=state.get('mana_max')
    regen=state.get('mana_regeneration')
    provenance=state.get('provenance',{}).get('mana_current',{})
    source=provenance.get('source','')
    is_live=(source=='PROCESS_MEMORY')
    source_badge='MEM' if is_live else ('SAVE' if source=='AIR_SHAREDOBJECT' else 'UNKNOWN')

    fill_pct=None
    if (current is not None and isinstance(current,(int,float)) and math.isfinite(current) and current>=0 and
            maximum is not None and isinstance(maximum,(int,float)) and math.isfinite(maximum) and maximum>0):
        fill_pct=min(100.0,max(0.0,current/maximum*100.0))

    return {
        'current':current,'maximum':maximum,'regen':regen,
        'fill_pct':fill_pct,'source_badge':source_badge,'is_live':is_live,
        'current_str':measured(current),'maximum_str':measured(maximum),
        'regen_str':(f'+{regen:,.1f}' if isinstance(regen,(int,float)) and math.isfinite(regen) else 'Unknown'),
    }

def telemetry_banner(state,build):
    health=state.get('telemetry',{})
    origin=state.get('provenance',{}).get('mana_current',{}).get('source')
    source={'PROCESS_MEMORY':'MEM','AIR_SHAREDOBJECT':'SAVE','DERIVED':'DERIVED'}.get(origin,'UNKNOWN')
    count=len(health.get('verified_fields',[]))
    bar=mana_bar(state)
    regen_str=bar['regen_str']
    return (f"RAM {health.get('memory_provider_health','UNKNOWN')} | {count} verified fields | "
            f"Save {health.get('save_provider_health','UNKNOWN')} ({health.get('save_age_seconds',0):.0f}s old)\n"
            f"Mana {bar['current_str']} [{source}] / {bar['maximum_str']} max | Regen {regen_str} mana/s | "
            f"Fairy assistants {measured(state.get('fairy_assistants'))} | "
            f"Build {'VERIFIED' if build.get('build_verified') else 'UNVERIFIED'}")

def dragon_stage_views(state,catalog):
    since=state.get('hellfire_since_hatch')
    detail={
        'hatch':'Egg found; incubation and ownership need verification.' if state.get('has_egg') else 'Spiky Rough Egg not acquired.',
        'drakeling':f"Hellfire since Hatch: {measured(since)} / 43,200 seconds; run/lifetime activity is different.",
        'dragon':f"Fairy assistants: {measured(state.get('fairy_assistants'))} / 3,750. Ownership must be observed.",
        'elder_dragon':f"Maximum mana: {measured(state.get('mana_max'))} / 50,000. Current mana is not maximum mana."}
    values={'hatch':None,'drakeling':since,'dragon':state.get('fairy_assistants'),'elder_dragon':state.get('mana_max')}
    targets={'hatch':None,'drakeling':43200,'dragon':3750,'elder_dragon':50000}
    result={}
    for index,name in enumerate(('hatch','drakeling','dragon','elder_dragon'),1):
        owned=milestone_owned(state,name,catalog);value,target=values[name],targets[name]
        progress=100 if owned is True else min(100,max(0,value/target*100)) if value is not None and target else 0
        result[index]={'name':name,'status':'OWNED' if owned is True else 'UNVERIFIED' if owned is None else 'WAITING',
                       'detail':detail[name],'progress':progress,'ready':False,
                       'can_check':owned is False,'ownership_verified':owned is True}
    return result
