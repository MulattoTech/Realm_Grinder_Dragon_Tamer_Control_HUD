"""Read-only evaluation of a reviewed, version-scoped permanent milestone checklist."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import time

ROOT=Path(__file__).resolve().parents[1]
REVIEW_REGISTRY_PATH=ROOT/'data'/'permanent_milestone_reviews.json'


def _finite_number(value):
    return (not isinstance(value,bool) and isinstance(value,(int,float)) and
            (isinstance(value,int) or math.isfinite(value)))


def _digest(value):
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                       allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_identity(state):
    fingerprint=state.get('save_fingerprint')
    timestamp=state.get('save_timestamp')
    reincarnation=state.get('reincarnation')
    save_version=state.get('raw_data',{}).get('saveVersion')
    if (not isinstance(fingerprint,str) or not fingerprint.strip() or
            not _finite_number(timestamp) or timestamp<=0 or
            isinstance(reincarnation,bool) or not isinstance(reincarnation,int) or reincarnation<0 or
            isinstance(save_version,bool) or not isinstance(save_version,int) or save_version<=0):
        return None
    return {'snapshot_fingerprint':fingerprint,'snapshot_timestamp':timestamp,
            'reincarnation':reincarnation,'save_version':save_version}


def _game_identity(value,save_version):
    if not isinstance(value,dict): return None
    digest=value.get('swf_sha256');version=value.get('game_version');stored_save_version=value.get('save_version')
    if (value.get('supported') is not True or not isinstance(digest,str) or
            re.fullmatch(r'[0-9a-f]{64}',digest) is None or
            not isinstance(version,str) or not version.strip() or
            isinstance(stored_save_version,bool) or not isinstance(stored_save_version,int) or
            stored_save_version!=save_version):
        return None
    return {'swf_sha256':digest,'game_version':version,'save_version':stored_save_version,'supported':True}


def _load_review_registry():
    try:
        value=json.loads(REVIEW_REGISTRY_PATH.read_text(encoding='utf-8'))
    except (OSError,ValueError,TypeError):
        return None
    return value if isinstance(value,dict) else None


def _coverage(checklist):
    checks=checklist.get('checks')
    if not isinstance(checks,list) or not checks: return None
    coverage=[];ids=[]
    for check in checks:
        if not isinstance(check,dict) or not isinstance(check.get('id'),str) or not check['id'].strip():
            return None
        if check['id'] in ids: return None
        if 'condition' not in check: return None
        ids.append(check['id'])
        coverage.append({'id':check['id'],'condition':check['condition']})
    return ids,coverage


def _approved_review(registry,checklist_digest,coverage_digest,check_ids,game_identity):
    if (not isinstance(registry,dict) or type(registry.get('schema_version')) is not int or
            registry.get('schema_version')!=1):
        return False
    entries=registry.get('approved_reviews')
    if not isinstance(entries,list): return False
    matches=[]
    for entry in entries:
        if not isinstance(entry,dict): continue
        pinned_game=_game_identity(entry.get('game_identity'),game_identity['save_version'])
        if (entry.get('checklist_digest')==checklist_digest and
                entry.get('coverage_digest')==coverage_digest and
                entry.get('check_ids')==check_ids and pinned_game==game_identity):
            matches.append(entry)
    return len(matches)==1


def _lookup(state,path):
    if not isinstance(path,str) or not path:
        return False,None
    value=state
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:
            return False,None
        value=value[part]
    return True,value


def _evaluate_condition(condition,state):
    if not isinstance(condition,dict) or set(condition)-{'field','op','value'}:
        return 'UNKNOWN'
    field=condition.get('field');op=condition.get('op')
    found,value=_lookup(state,field)
    if op=='exists':
        expected=condition.get('value',True)
        if not isinstance(expected,bool): return 'UNKNOWN'
        return 'PASS' if found is expected else 'FAIL'
    if not found:
        return 'UNKNOWN'
    if op=='is_true':
        return 'PASS' if value is True else 'FAIL' if value is False else 'UNKNOWN'
    if op=='is_false':
        return 'PASS' if value is False else 'FAIL' if value is True else 'UNKNOWN'
    if op in ('eq','neq'):
        if 'value' not in condition: return 'UNKNOWN'
        expected=condition.get('value')
        equal=type(value) is type(expected) and value==expected
        return 'PASS' if (equal if op=='eq' else not equal) else 'FAIL'
    if op in ('gt','gte','lt','lte'):
        if 'value' not in condition: return 'UNKNOWN'
        expected=condition.get('value')
        if not _finite_number(value) or not _finite_number(expected):
            return 'UNKNOWN'
        passed={'gt':value>expected,'gte':value>=expected,
                'lt':value<expected,'lte':value<=expected}[op]
        return 'PASS' if passed else 'FAIL'
    return 'UNKNOWN'


def evaluate_milestone_audit(checklist,state,review_registry=None,now=None):
    """Evaluate only explicitly reviewed checks and bind results to this save snapshot.

    No checklist requirements are implied. Missing, malformed, unsupported, or
    out-of-scope evidence yields a blocked report.
    """
    now=time.time() if now is None else now
    identity=_snapshot_identity(state if isinstance(state,dict) else {})
    result={'schema_version':1,'status':'BLOCKED','verified':False,'checks':[],
            'evaluated_at':now}
    if identity:
        result.update(identity)
    else:
        result['reason']='A current save fingerprint, timestamp, save version, and reincarnation are required'
        return result
    game_identity=_game_identity(state.get('game_identity'),identity['save_version'])
    if not game_identity:
        result['reason']='A supported game hash, game version, and matching save version are required'
        return result
    result['game_identity']=game_identity
    result['game_identity_digest']=_digest(game_identity)
    if not isinstance(checklist,dict):
        result['reason']='Reviewed permanent milestone checklist is missing'
        return result
    try:
        digest=_digest(checklist)
    except (TypeError,ValueError):
        result['reason']='Checklist is not valid finite JSON data'
        return result
    result.update(checklist_id=checklist.get('checklist_id'),checklist_digest=digest)
    if (type(checklist.get('schema_version')) is not int or checklist.get('schema_version')!=1 or
            checklist.get('reviewed') is not True or
            not isinstance(checklist.get('checklist_id'),str) or not checklist['checklist_id'].strip()):
        result['reason']='Checklist schema, review status, or checklist identity is not verified'
        return result
    versions=checklist.get('save_versions');reincarnations=checklist.get('reincarnations')
    if (not isinstance(versions,list) or any(isinstance(item,bool) or not isinstance(item,int) for item in versions) or
            identity['save_version'] not in versions or not isinstance(reincarnations,list) or
            any(isinstance(item,bool) or not isinstance(item,int) for item in reincarnations) or
            identity['reincarnation'] not in reincarnations):
        result['reason']='Checklist is not scoped to this save version and reincarnation'
        return result
    checks=checklist.get('checks')
    if not isinstance(checks,list) or not checks:
        result['reason']='Checklist has no reviewed checks'
        return result
    coverage_result=_coverage(checklist)
    if coverage_result is None:
        result['reason']='Checklist check coverage is invalid or incomplete'
        return result
    check_ids,coverage=coverage_result
    try:
        coverage_digest=_digest(coverage)
    except (TypeError,ValueError):
        result['reason']='Checklist coverage is not valid finite JSON data'
        return result
    result.update(check_ids=check_ids,coverage_digest=coverage_digest)
    seen=set()
    for check in checks:
        if not isinstance(check,dict) or not isinstance(check.get('id'),str) or not check['id'].strip() or check['id'] in seen:
            result['reason']='Checklist contains an invalid or duplicate check identity'
            return result
        seen.add(check['id'])
        status=_evaluate_condition(check.get('condition'),state)
        result['checks'].append({'id':check['id'],'status':status})
    if not all(item['status']=='PASS' for item in result['checks']):
        result['reason']='One or more reviewed checks failed or could not be evaluated'
        return result
    registry=_load_review_registry() if review_registry is None else review_registry
    if not _approved_review(registry,digest,coverage_digest,check_ids,game_identity):
        result['reason']='No canonical review authorizes this exact checklist coverage and game identity'
        return result
    result.update(status='VERIFIED',verified=True)
    return result


def audit_matches_current(audit,state,checklist,review_registry=None,now=None,max_age_seconds=300):
    """Confirm a stored report still describes the exact current inputs."""
    now=time.time() if now is None else now
    if not isinstance(audit,dict) or audit.get('verified') is not True:
        return False
    try:
        evaluated_at=audit.get('evaluated_at')
        if not _finite_number(evaluated_at):
            return False
        age=now-evaluated_at
    except (TypeError,ValueError):
        return False
    current=evaluate_milestone_audit(checklist,state,review_registry=review_registry,now=now)
    return (current.get('verified') is True and audit.get('status')=='VERIFIED' and
            audit.get('schema_version')==1 and
            all(audit.get(key)==current.get(key) for key in
                ('checklist_digest','coverage_digest','check_ids','game_identity_digest',
                 'snapshot_fingerprint','snapshot_timestamp','save_version','reincarnation')) and
            isinstance(age,(int,float)) and 0<=age<=max_age_seconds)
