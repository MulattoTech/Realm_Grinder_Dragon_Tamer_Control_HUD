"""Evidence check for controlled normal-spell mana observations."""
import math

def validate_mana_trace(rows,cast_times,cost):
    result={'verified':False,'cycles':[],'reason':'Need two observed cast/regeneration cycles'}
    if len(cast_times)<2 or len(rows)<6:return result
    if any(not math.isfinite(t) or not math.isfinite(v) or v<0 for t,v in rows):return result
    for index,cast in enumerate(cast_times):
        next_cast=cast_times[index+1] if index+1<len(cast_times) else rows[-1][0]+0.01
        before=[(t,v) for t,v in rows if t<cast]
        after=[(t,v) for t,v in rows if cast<=t<min(cast+0.7,next_cast)]
        later=[(t,v) for t,v in rows if cast+0.7<=t<next_cast]
        if not before or not after or not later:return result
        base=before[-1][1];low=min(after,key=lambda point:point[1])
        drop=base-low[1];recovered=later[-1][1]-low[1]
        rate=recovered/max(0.001,later[-1][0]-low[0])
        valid=cost*0.8<=drop<=cost*1.15 and recovered>0 and rate>0
        result['cycles'].append({'drop':drop,'regeneration_per_second':rate,'valid':valid})
    result['verified']=all(c['valid'] for c in result['cycles'])
    result['reason']='Two cost-matched drops and recoveries observed' if result['verified'] else 'Trace does not match both spell cost and regeneration'
    return result
