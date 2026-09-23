"""Persist observed quest transitions and conservative timing bounds across restarts."""
import copy
import json
import math
from pathlib import Path
import time
from src.action_verification import milestone_owned
from src.atomic_store import write_json

class QuestObserver:
    def __init__(self,path,catalog):
        self.path=Path(path);self.catalog=catalog

    def observe(self,state,now=None):
        now=time.time() if now is None else now
        result=dict(state)
        try:record=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        except (OSError,ValueError):record={}
        previous=record.get('previous',{})
        events=record.setdefault('events',{})
        token=state.get('save_fingerprint');stamp=state.get('save_timestamp')
        health='HEALTHY'
        valid=(isinstance(stamp,(int,float)) and math.isfinite(stamp) and stamp<=now+1 and
               stamp>=previous.get('timestamp',-math.inf))
        current={name:milestone_owned(state,name,self.catalog) for name in self.catalog}
        if not valid:health='CLOCK_OR_SAVE_DISCONTINUITY'
        elif token!=previous.get('token'):
            for name,owned in current.items():
                old=previous.get('owned',{}).get(name)
                if owned is True and old is False and name not in events:
                    events[name]={'earliest':previous['timestamp'],'latest':stamp,
                                  'evidence':'FALSE_TO_TRUE_OWNERSHIP_TRANSITION','token':token}
                    if name=='hatch':events[name]['hellfire_baseline']=state.get('hellfire_active_time_total')
                elif owned is False and old is True and name in events:
                    health='OWNERSHIP_REGRESSION';events[name]['invalidated']=True
            record['previous']={'token':token,'timestamp':stamp,'owned':current}
            record['schema_version']=1
            try:write_json(self.path,record)
            except OSError as exc:health='PERSISTENCE_ERROR: '+str(exc)
        quest={'events':copy.deepcopy(events),'observer_health':health,'timing_status':{}}
        for name,field in [('spiky_rough_egg','egg_elapsed_seconds'),('drakeling','drakeling_elapsed_seconds'),
                           ('dragon','dragon_elapsed_seconds')]:
            event=events.get(name,{})
            trustworthy=valid and 'latest' in event and not event.get('invalidated') and now>=event['latest']
            quest[field]=now-event['latest'] if trustworthy else None
            quest['timing_status'][name]=('OBSERVED_ELAPSED_LOWER_BOUND' if trustworthy else
                'PREEXISTING_TIME_UNKNOWN' if current.get(name) is True else 'NOT_OBSERVED')
        baseline=events.get('hatch',{}).get('hellfire_baseline')
        total=state.get('hellfire_active_time_total')
        valid_counter=(valid and isinstance(baseline,(int,float)) and isinstance(total,(int,float)) and
                       math.isfinite(total) and total>=baseline and not events.get('hatch',{}).get('invalidated'))
        result['hellfire_since_hatch']=total-baseline if valid_counter else None
        result['quest']=quest
        result['quest_evidence_policy']='Timing is a conservative bound from observed transitions, not an invented acquisition timestamp.'
        return result
