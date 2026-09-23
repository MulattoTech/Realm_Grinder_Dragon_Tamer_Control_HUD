"""Pure presentation helpers: never convert unknown measurements into accomplishments."""
import math
from src.action_verification import milestone_owned

def measured(value):
    if value is None or not isinstance(value,(int,float)) or not math.isfinite(value):
        return 'Unknown'
    return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.1f}'

def telemetry_banner(state,build):
    health=state.get('telemetry',{})
    origin=state.get('provenance',{}).get('mana_current',{}).get('source')
    source={'PROCESS_MEMORY':'MEM','AIR_SHAREDOBJECT':'SAVE','DERIVED':'DERIVED'}.get(origin,'UNKNOWN')
    count=len(health.get('verified_fields',[]))
    return (f"RAM {health.get('memory_provider_health','UNKNOWN')} | {count} verified fields | "
            f"Save {health.get('save_provider_health','UNKNOWN')} ({health.get('save_age_seconds',0):.0f}s old)\n"
            f"Mana {measured(state.get('mana_current'))} [{source}] / {measured(state.get('mana_max'))} max | "
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
