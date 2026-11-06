"""Read-only evaluation of a reviewed, version-scoped permanent milestone checklist."""
from __future__ import annotations

import hashlib
import json
import math
import time


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


def evaluate_milestone_audit(checklist,state,now=None):
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
    if not isinstance(checklist,dict):
        result['reason']='Reviewed permanent milestone checklist is missing'
        return result
    try:
        digest=_digest(checklist)
    except (TypeError,ValueError):
        result['reason']='Checklist is not valid finite JSON data'
        return result
    result.update(checklist_id=checklist.get('checklist_id'),checklist_digest=digest)
    if (checklist.get('schema_version')!=1 or checklist.get('reviewed') is not True or
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
    seen=set()
    for check in checks:
        if not isinstance(check,dict) or not isinstance(check.get('id'),str) or not check['id'].strip() or check['id'] in seen:
            result['reason']='Checklist contains an invalid or duplicate check identity'
            return result
        seen.add(check['id'])
        status=_evaluate_condition(check.get('condition'),state)
        result['checks'].append({'id':check['id'],'status':status})
    if all(item['status']=='PASS' for item in result['checks']):
        result.update(status='VERIFIED',verified=True)
    else:
        result['reason']='One or more reviewed checks failed or could not be evaluated'
    return result


def audit_matches_current(audit,state,checklist,now=None,max_age_seconds=300):
    """Confirm a stored report still describes the exact current inputs."""
    now=time.time() if now is None else now
    identity=_snapshot_identity(state if isinstance(state,dict) else {})
    if not identity or not isinstance(audit,dict) or audit.get('verified') is not True:
        return False
    try:
        digest=_digest(checklist)
        evaluated_at=audit.get('evaluated_at')
        if not _finite_number(evaluated_at):
            return False
        age=now-evaluated_at
    except (TypeError,ValueError):
        return False
    return (audit.get('status')=='VERIFIED' and audit.get('schema_version')==1 and
            audit.get('checklist_digest')==digest and
            all(audit.get(key)==value for key,value in identity.items()) and
            isinstance(age,(int,float)) and 0<=age<=max_age_seconds)
