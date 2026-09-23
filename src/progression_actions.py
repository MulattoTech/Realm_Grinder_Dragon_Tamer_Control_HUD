"""Shared semantic action adapter; the existing native input plane remains unchanged."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
from src.action_verification import (ActionLock,TransactionRunner,abdication_verified,
    reincarnation_verified,fresh_transition,upgrade_owned,milestone_owned,verify_build,ui_action_verified)
from src.atomic_store import write_json
from src.live_state import get_live_game_state
from src.runtime_safety import input_allowed
from src.save_reader import SOL_PATH
from src.wiki_data import get_recommended_build,get_reincarnation_gem_requirement
from src.strategy_rules import selected_route
from src.route_executor import RouteExecutor

ROOT=Path(__file__).resolve().parents[1]

def blocked(message,action='BLOCKED'):
    return {'success':False,'action':action,'status':'BLOCKED','message':message}

def actual_dragon_stage(state,catalog):
    if state['reincarnation'] < 46: return 'REACH_R46'
    if not state['has_egg']: return 'ACQUIRE_EGG'
    if milestone_owned(state,'dragon_tamer',catalog) is True: return 'COMPLETED'
    for name,stage in [('hatch','STAGE1_HATCH'),('drakeling','STAGE2_DRAKELING'),
                       ('dragon','STAGE3_DRAGON'),('elder_dragon','STAGE4_ELDER_DRAGON')]:
        if milestone_owned(state,name,catalog) is not True: return stage
    return 'VERIFY_TROPHY'

class ProgressionActions:
    def __init__(self,window,state_reader=get_live_game_state,state_dir=None):
        self.window=window;self.read=state_reader
        self.state_dir=Path(state_dir or ROOT/'state')
        self.runner=TransactionRunner(self.read,self.state_dir,
            cancelled=lambda:not input_allowed(self.window),backup=self.backup)
        self.route=RouteExecutor(self)
        self._metric=None;self._last_improvement=time.monotonic()

    def load(self,name):
        path=self.state_dir/name
        if not path.exists(): return {}
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict): raise ValueError(f'Expected a JSON object: {name}')
        return data

    def catalog(self): return self.load('milestone_catalog.json').get('milestones',{})

    def manifest(self,recommendation):
        return self.load('build_manifests.json').get('builds',{}).get(recommendation['name'],{})

    def diagnose_build(self,state=None):
        from src.config import load_config
        state=state or self.read()
        selection,rec=selected_route(state,load_config().get('selected_path','Automatic'))
        result=verify_build(state,rec,self.manifest(rec))
        result.update(reincarnation=state['reincarnation'],gems=state['gems'],selected_path=selection,
                      observed_at=time.time(),save_fingerprint=state.get('save_fingerprint'))
        write_json(self.state_dir/'build_verification.json',result)
        return result

    def backup(self):
        source=Path(SOL_PATH);before=source.stat();data=source.read_bytes();after=source.stat()
        if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
            raise OSError('Game save changed during backup; no action sent')
        digest=hashlib.sha256(data).hexdigest()
        path=ROOT/'backups'/f'transaction-{digest[:20]}.sol'
        if not path.exists(): path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise OSError('Backup verification failed')
        return str(path)

    def _dispatch(self,sequence,template=None):
        if len(sequence)>128: raise ValueError('Semantic action exceeds the step budget')
        for step in sequence:
            if not input_allowed(self.window): raise RuntimeError('Input cancelled by pause/session/window guard')
            if isinstance(step,list) and len(step)==2:
                x,y=step
                if not (0<=x<=1280 and 0<=y<=752): raise ValueError('Point is outside the design canvas')
                self.window.click(x,y,delay_after=0.15)
            elif isinstance(step,dict) and set(step)<= {'key','repeat'} and 'key' in step:
                repeat=int(step.get('repeat',1))
                if not 1<=repeat<=512: raise ValueError('Key repetition exceeds budget')
                for _ in range(repeat):
                    if not input_allowed(self.window): raise RuntimeError('Input cancelled')
                    self.window.press_key(step['key'],delay_after=0)
            elif step=={'text':'$TEMPLATE'} and template is not None:
                if len(template)>4096 or any(ord(ch)<32 for ch in template):
                    raise ValueError('Unsupported template text')
                for ch in template:
                    if not input_allowed(self.window): raise RuntimeError('Template entry cancelled')
                    self.window.type_text(ch,delay_between=0.003)
            else:
                raise ValueError('Unrecognized semantic input step')

    def _transaction(self,name,operation,condition,proof,template=None):
        holder={}
        def precondition(state):
            profile=self.load('ui_actions.json')
            if not ui_action_verified(profile,operation,state): return False
            if profile.get('client_size') != list(self.window.get_client_size()): return False
            holder['sequence']=profile['actions'][operation]
            return bool(condition(state))
        result=self.runner.run(name,precondition,lambda:self._dispatch(holder['sequence'],template),proof)
        if result['status']=='UNCERTAIN':
            # Do not repeatedly fire a possibly successful reset after the save has lagged.
            (self.state_dir/'STOP').write_text('Unresolved action: '+result['message'],encoding='utf-8')
        return result

    def abdicate(self,allow_no_gain=False):
        return self._transaction('ABDICATED','abdication',
            lambda s:s.get('faction',-1)!=-1 and (allow_no_gain or s.get('potential_gems',0)>s['gems']),
            lambda before,after:abdication_verified(before,after,allow_no_gain))

    def reincarnate(self):
        def ready(state):
            audit=self.load('permanent_milestone_audit.json')
            checks=audit.get('checks',[])
            return (state['gems']>=get_reincarnation_gem_requirement(state['reincarnation']) and
                    audit.get('reincarnation')==state['reincarnation'] and audit.get('verified') is True and
                    bool(checks) and all(check.get('complete') is True for check in checks))
        return self._transaction('REINCARNATED','reincarnation',ready,reincarnation_verified)

    def deploy_template(self,template=None):
        from src.config import load_config
        state=self.read();_,rec=selected_route(state,load_config().get('selected_path','Automatic'))
        return self.route.deploy_template(template if template is not None else rec.get('template',''))

    def setup_build(self):
        return self.route.run_once()

    def purchase_all(self,kind):
        if kind not in ('upgrades','buildings'): raise ValueError('Unknown purchase category')
        def quantity(state):
            raw=state.get('raw_data',{})
            if kind=='buildings': return sum(item.get('q',0) for item in raw.get('buildings',{}).values())
            return sum(bool(item.get('u1')) for item in raw.get('upgrades',{}).values())
        return self._transaction('PURCHASED_'+kind.upper(),'buy_all_'+kind,lambda s:True,
            lambda before,after:fresh_transition(before,after) and quantity(after)>quantity(before))

    def excavate(self,target=1500):
        state=self.read()
        if state['has_egg']:
            return {'success':True,'status':'VERIFIED','action':'EGG_OBTAINED','message':'Spiky Rough Egg is present in the decoded save'}
        if state['reincarnation']<46: return blocked('Dragon egg excavation requires the Dragon unlock stage','REQUIRES_R46')
        result=self._transaction('EXCAVATED','excavate',lambda s:s['reincarnation']>=46,
            lambda before,after:fresh_transition(before,after) and
            (after['has_egg'] or after['excavations']>before['excavations']))
        if result['success'] and self.read()['has_egg']: result['action']='EGG_OBTAINED'
        return result

    def purchase_milestone(self,name):
        catalog=self.catalog();state=self.read();owned=milestone_owned(state,name,catalog)
        if owned is None: return blocked(f'{name}: current-version upgrade/trophy identifier is not verified','CATALOG_UNVERIFIED')
        if owned:
            return {'success':True,'status':'VERIFIED','action':name.upper()+'_OWNED',
                    'message':name+' ownership is present in the save; this does not assert Steam achievement status'}
        previous={'hatch':None,'drakeling':'hatch','dragon':'drakeling','elder_dragon':'dragon'}
        if name not in previous: return blocked('Unsupported milestone purchase')
        def ready(s):
            if not s['has_egg'] or s['reincarnation']<46: return False
            prerequisite=previous[name]
            if prerequisite and milestone_owned(s,prerequisite,catalog) is not True: return False
            if name=='dragon' and (s.get('fairy_assistants') is None or s['fairy_assistants']<3750): return False
            if name=='elder_dragon' and (s.get('mana_max') is None or s['mana_max']<50000): return False
            return True
        return self._transaction(name.upper()+'_PURCHASED','buy_all_upgrades',ready,
            lambda before,after:fresh_transition(before,after) and milestone_owned(after,name,catalog) is True)

    def maintain_production(self):
        # The same executor that starts a run also maintains it; do not revive the
        # obsolete fixed-profile purchase loop or indiscriminate spell spam.
        state=self.read()
        build=self.diagnose_build(state)
        if not build['build_verified']:return blocked('; '.join(build.get('missing',[])),'BUILD_UNVERIFIED')
        return self.route.collect()

    def advance_reincarnation(self,decision=None):
        state=self.read()
        if state['reincarnation']>=46:
            return {'success':True,'status':'VERIFIED','action':'R46_REACHED','message':'R46 or later is present in the save'}
        from src.config import load_config
        cfg=load_config()
        if state['gems']>=get_reincarnation_gem_requirement(state['reincarnation']) and cfg.get('auto_reincarnate',True):
            return self.reincarnate()
        if cfg.get('auto_abdicate',True) and (decision in ('ABDICATE_FOR_REINCARNATION','OPTIMAL_ABDICATION') or
                                            state['potential_gems']>=state['gems']*2):
            return self.abdicate()
        if not self.diagnose_build(state)['build_verified'] and cfg.get('auto_apply_build',True):
            return self.setup_build()
        return self.maintain_production()

    def auto_clear(self,decision=None):
        stage=actual_dragon_stage(self.read(),self.catalog())
        if stage=='REACH_R46': return self.advance_reincarnation(decision)
        if stage=='ACQUIRE_EGG': return self.excavate()
        names={'STAGE1_HATCH':'hatch','STAGE2_DRAKELING':'drakeling','STAGE3_DRAGON':'dragon','STAGE4_ELDER_DRAGON':'elder_dragon'}
        if stage in names: return self.purchase_milestone(names[stage])
        if stage=='COMPLETED':
            return {'success':True,'status':'VERIFIED','action':'DRAGON_TAMER_OWNED',
                    'message':'Dragon Tamer trophy is present in the save; Steam achievement is not independently verified'}
        return blocked('Elder ownership and Dragon Tamer trophy must be verified separately','VERIFY_TROPHY')
