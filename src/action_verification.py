"""State proofs shared by the worker, GateClearer and HUD; no game-memory writes."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid
from src.atomic_store import write_json

FACTION_IDS={'Fairy':0,'Elf':1,'Angel':2,'Goblin':3,'Undead':4,'Demon':5,
             'Titan':6,'Druid':7,'Faceless':8,'Mercenary':11}
BLOODLINE_IDS={'Fairy':194,'Druid':136}  # Verified RG-tools factual identifiers.

def upgrade_owned(state, identifier):
    return bool(state.get('raw_data',{}).get('upgrades',{}).get(str(identifier),{}).get('u1',False))

def trophy_owned(state, identifier):
    return str(identifier) in state.get('raw_data',{}).get('trophies',{})

def fresh_transition(before, after):
    return bool(after.get('save_fingerprint') and
                after.get('save_fingerprint') != before.get('save_fingerprint') and
                after.get('telemetry',{}).get('consequential_actions_allowed'))

def reincarnation_verified(before, after):
    return fresh_transition(before,after) and after.get('reincarnation') == before.get('reincarnation',-2)+1

def abdication_verified(before, after, allow_no_gain=False):
    reset = (before.get('faction',-1) != -1 and after.get('faction') == -1 and
             after.get('alignment') == 0 and
             after.get('coins_this_game',math.inf) < before.get('coins_this_game',0))
    gems_ok = after.get('gems',-1) >= before.get('gems',0) if allow_no_gain else after.get('gems',-1) > before.get('gems',0)
    return bool(fresh_transition(before,after) and after.get('reincarnation') == before.get('reincarnation') and reset and gems_ok)

def milestone_owned(state, name, catalog):
    entry=catalog.get(name,{})
    if entry.get('verified') is not True or not isinstance(entry.get('id'),int):
        return None
    if entry.get('kind') == 'upgrade':
        return upgrade_owned(state,entry['id'])
    if entry.get('kind') == 'trophy':
        return trophy_owned(state,entry['id'])
    return None

def verify_build(state, recommendation, manifest=None):
    manifest=manifest or {}
    raw=state.get('raw_data',{})
    missing=[]; checks=[]
    faction_name=recommendation.get('faction','')
    base_name='Mercenary' if 'Mercenary' in faction_name else {'Elven':'Elf','Fairy/Dwarf':'Fairy','Goblin/Drow':'Goblin'}.get(faction_name,faction_name)
    faction=FACTION_IDS.get(base_name)
    faction_ok=faction is not None and state.get('faction') == faction
    checks.append(faction_ok)
    if not faction_ok: missing.append(f'Faction: expected {faction_name}; actual ID {state.get("faction")}')
    bloodline=recommendation.get('bloodline')
    if bloodline and str(bloodline).lower() not in ('none','n/a','-'):
        identifier=BLOODLINE_IDS.get(bloodline)
        bloodline_ok=identifier is not None and upgrade_owned(state,identifier)
        checks.append(bloodline_ok)
        if not bloodline_ok: missing.append(f'Bloodline {bloodline}: ownership not verified')
    required=manifest.get('required_upgrade_ids',[])
    manifest_ok=(manifest.get('verified') is True and bool(required) and
                 manifest.get('template') == recommendation.get('template') and
                 manifest.get('save_version') == raw.get('saveVersion'))
    checks.append(manifest_ok)
    if not manifest_ok:
        missing.append('Complete current-version template ownership manifest is not verified')
    else:
        for identifier in required:
            owned=upgrade_owned(state,identifier); checks.append(owned)
            if not owned: missing.append(f'Required upgrade/research ID {identifier} is not purchased')
        if 'alignment' in manifest:
            correct=state.get('alignment') == manifest['alignment']; checks.append(correct)
            if not correct: missing.append('Alignment does not match the intended build')
        if manifest.get('merc_spells'):
            correct=sorted([raw.get('mercSpell1'),raw.get('mercSpell2')]) == sorted(manifest['merc_spells'])
            checks.append(correct)
            if not correct: missing.append('Mercenary spell selections do not match the template')
    return {'build_verified':all(checks),'build_completeness':round(sum(checks)/len(checks),3),
            'recommended_build':recommendation.get('name'),'actual_faction_id':state.get('faction'),
            'missing':missing,'ownership_manifest_verified':manifest_ok}

def ui_action_verified(profile, operation, state):
    sequence=profile.get('actions',{}).get(operation)
    return bool(profile.get('save_version') == state.get('raw_data',{}).get('saveVersion') and
                operation in profile.get('verified_actions',[]) and isinstance(sequence,list) and sequence)

class ActionLock:
    """One writer across threads and processes, automatically released on process exit."""
    _thread_lock=threading.Lock()
    def __init__(self,state_dir):
        self.path=Path(state_dir)/'action.lock'; self.stream=None
    def __enter__(self):
        if not self._thread_lock.acquire(blocking=False):
            raise RuntimeError('Another action is already in progress')
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self.stream=self.path.open('a+b')
            self.stream.seek(0,2)
            if self.stream.tell()==0: self.stream.write(b'0');self.stream.flush()
            self.stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return self
        except BaseException:
            if self.stream: self.stream.close()
            self._thread_lock.release()
            raise RuntimeError('Another action owns the writer lock')
    def __exit__(self,*exc):
        try:
            if self.stream:
                self.stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.stream,fcntl.LOCK_UN)
                self.stream.close()
        finally:
            self._thread_lock.release()


def state_summary(state):
    return {key:state.get(key) for key in ('reincarnation','gems','faction','alignment',
             'coins_this_game','save_fingerprint','save_timestamp','telemetry')}

def reconcile_known_template_no_text(pending_path,observed_state,now=time.time):
    """Reconcile one precisely identified template failure that occurs before typing.

    The exception is raised after trying to open the template dialog but before the
    input click or character loop. It is therefore safe to release the transaction
    lock while retaining an auditable record. No game input is sent here.
    """
    path=Path(pending_path)
    try:
        with ActionLock(path.parent):
            pending=json.loads(path.read_text(encoding='utf-8'))
            before=pending.get('before') or {}
            before_fingerprint=before.get('save_fingerprint')
            after_fingerprint=observed_state.get('save_fingerprint')
            telemetry=observed_state.get('telemetry') or {}
            if not (pending.get('action')=='MERCENARY_TEMPLATE' and
                    pending.get('status')=='UNCERTAIN' and
                    pending.get('error')=='Template Import dialog was not verified; no text was sent' and
                    before.get('reincarnation')==observed_state.get('reincarnation') and
                    isinstance(before_fingerprint,str) and before_fingerprint and
                    isinstance(after_fingerprint,str) and after_fingerprint!=before_fingerprint and
                    telemetry.get('consequential_actions_allowed') is True):
                return False
            pending.update(status='RECONCILED_NO_TEMPLATE_TEXT',reconciled_at=now(),
                reconciliation={'kind':'known_pretyping_template_failure',
                    'proof':'The import dialog check raises before clicking its input field or typing any template characters.',
                    'observed_after':state_summary(observed_state)})
            write_json(path,pending)
            return True
    except (OSError,ValueError,RuntimeError):
        return False

class TransactionRunner:
    def __init__(self,state_reader,state_dir,cancelled,backup,clock=time.monotonic,
                 sleep=time.sleep,timeout=45.0,poll_interval=0.25):
        self.read=state_reader;self.state_dir=Path(state_dir);self.cancelled=cancelled;self.backup=backup
        self.clock=clock;self.sleep=sleep;self.timeout=timeout;self.poll_interval=poll_interval
        self.pending_path=self.state_dir/'pending_action.json'

    def run(self,name,precondition,dispatch,verify,allow_no_effect=False):
        started=self.clock();dispatched=False;before=None;after=None;record={}
        result={'success':False,'action':name,'status':'BLOCKED','message':''}
        try:
            with ActionLock(self.state_dir):
                if self.cancelled():
                    result['message']='Paused, cancelled, or not on the game desktop';return result
                if self.pending_path.exists():
                    prior=json.loads(self.pending_path.read_text(encoding='utf-8'))
                    if prior.get('status') in ('DISPATCHED','UNCERTAIN'):
                        result['message']='Previous action is unresolved; no duplicate input was sent';return result
                before=self.read()
                if not before.get('telemetry',{}).get('consequential_actions_allowed'):
                    result['message']='A connected process and fresh, healthy save are required';return result
                if not precondition(before):
                    result['message']='Required game state or calibrated semantic action is not verified';return result
                backup_path=self.backup()
                if not backup_path:
                    raise OSError('Save backup was not confirmed')
                if self.cancelled():
                    result['message']='Cancelled after backup, before input';return result
                record={'id':uuid.uuid4().hex,'action':name,'status':'DISPATCHED',
                        'timestamp':time.time(),'backup':str(backup_path),'before':state_summary(before)}
                write_json(self.pending_path,record)
                dispatched=True
                dispatch()
                identity=tuple(before['telemetry'].get(k) for k in ('pid','process_start_time'))
                while self.clock()-started <= self.timeout:
                    if self.cancelled():
                        raise RuntimeError('Action cancelled after input; outcome needs reconciliation')
                    try:
                        after=self.read()
                    except (OSError,ValueError):
                        self.sleep(self.poll_interval);continue
                    if tuple(after.get('telemetry',{}).get(k) for k in ('pid','process_start_time')) != identity:
                        raise RuntimeError('Game process changed during the transaction')
                    if verify(before,after):
                        record.update(status='VERIFIED',after=state_summary(after),verified_at=time.time())
                        write_json(self.pending_path,record)
                        result.update(success=True,status='VERIFIED',after=state_summary(after),
                                      message=f'{name}: fresh game-state transition verified')
                        return result
                    self.sleep(self.poll_interval)
                if allow_no_effect and after is not None and fresh_transition(before,after):
                    record.update(status='NO_EFFECT',after=state_summary(after))
                    write_json(self.pending_path,record)
                    result.update(status='NO_EFFECT',message='Fresh save observed without the requested purchase; no progress claimed')
                    return result
                raise TimeoutError('No verified state transition before the observation timeout')
        except (OSError,ValueError,RuntimeError) as exc:
            result.update(status='UNCERTAIN' if dispatched else 'BLOCKED',message=str(exc))
            if dispatched:
                record.update(status='UNCERTAIN',error=str(exc))
                try: write_json(self.pending_path,record)
                except OSError: pass
        finally:
            result['elapsed_seconds']=round(self.clock()-started,3)
            try: write_json(self.state_dir/'last_action_result.json',result)
            except OSError: pass
        return result
