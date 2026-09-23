"""Conditional projections from observed same-run progress; never default run durations."""
import math
import statistics
import time

def estimate_target(samples,target,now=None,paused=False,min_span=30,max_age=90):
    now=time.time() if now is None else now
    result={'seconds':None,'lower_seconds':None,'upper_seconds':None,'conditional':True,
            'model':'observed_log_growth','status':'MEASURING','sample_count':0}
    if paused:result['status']='PAUSED';return result
    if not samples or not math.isfinite(target) or target<=0:return result
    run=samples[-1].get('run');points=[]
    for item in reversed(samples):
        if item.get('run')!=run:break
        value=item.get('value');stamp=item.get('time')
        if not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:continue
        if not isinstance(stamp,(float,int)) or not math.isfinite(stamp):continue
        points.append((stamp,math.log10(value)))
    points=sorted(set(points));result['sample_count']=len(points)
    if not points or now-points[-1][0]>max_age:result['status']='STALE';return result
    if points[-1][1]>=math.log10(target):result.update(seconds=0,lower_seconds=0,upper_seconds=0,status='TARGET_REACHED');return result
    if len(points)<6 or points[-1][0]-points[0][0]<min_span:return result
    slopes=[(b[1]-a[1])/(b[0]-a[0]) for a,b in zip(points,points[1:]) if b[0]>a[0]]
    positive=[v for v in slopes if v>1e-10]
    if len(positive)<len(slopes)*0.7:result['status']='STALLED_OR_NONSTATIONARY';return result
    speed=statistics.median(positive);spread=statistics.median(abs(v-speed) for v in slopes)
    if spread>speed*0.75:result['status']='NONSTATIONARY';return result
    remaining=math.log10(target)-points[-1][1]
    seconds=remaining/speed
    if seconds>7*86400:result['status']='BEYOND_RELIABLE_HORIZON';return result
    result.update(seconds=seconds,lower_seconds=remaining/(speed+2*spread) if spread else seconds,
                  upper_seconds=remaining/max(speed*0.1,speed-2*spread),status='CONDITIONAL_ESTIMATE',
                  observed_log10_per_second=speed,observed_span_seconds=points[-1][0]-points[0][0])
    return result
