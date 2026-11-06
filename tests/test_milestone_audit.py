import copy
import hashlib
import json


def checklist():
    return {'schema_version':1,'checklist_id':'reviewed-test-v1','reviewed':True,
        'save_versions':[58],'reincarnations':[24],
        'checks':[{'id':'has-current-r','condition':{'field':'reincarnation','op':'eq','value':24}},
                  {'id':'known-ascension','condition':{'field':'ascension','op':'eq','value':0}}]}


def snapshot():
    return {'reincarnation':24,'ascension':0,'save_fingerprint':'save-abc','save_timestamp':100.0,
        'raw_data':{'saveVersion':58},'game_identity':game_identity()}


def game_identity():
    return {'swf_sha256':'a'*64,'game_version':'4.3.11','save_version':58,'supported':True}


def manifest_for(source,state=None):
    state=state or snapshot()
    canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                                      allow_nan=False).encode('utf-8')
    checks=source['checks']
    coverage=[{'id':check['id'],'condition':check['condition']} for check in checks]
    entry={'checklist_digest':hashlib.sha256(canonical(source)).hexdigest(),
        'coverage_digest':hashlib.sha256(canonical(coverage)).hexdigest(),
        'check_ids':[check['id'] for check in checks],'game_identity':state['game_identity']}
    return {'schema_version':1,'approved_reviews':[entry]}


def test_missing_or_unreviewed_checklist_fails_closed():
    from src.milestone_audit import evaluate_milestone_audit
    state=snapshot()
    for source in (None,{**checklist(),'reviewed':False}):
        result=evaluate_milestone_audit(source,state,now=101.0)
        assert result['verified'] is False
        assert result['status']=='BLOCKED'


def test_reviewed_checklist_evaluation_binds_to_exact_save_and_r():
    from src.milestone_audit import evaluate_milestone_audit,audit_matches_current
    state=snapshot()
    source=checklist();registry=manifest_for(source,state)
    report=evaluate_milestone_audit(source,state,review_registry=registry,now=101.0)
    assert report['verified'] is True and report['status']=='VERIFIED'
    assert report['snapshot_fingerprint']=='save-abc'
    assert report['snapshot_timestamp']==100.0
    assert report['save_version']==58 and report['reincarnation']==24
    assert audit_matches_current(report,state,source,registry,now=102.0)


def test_mutable_reviewed_flag_is_not_authority_without_canonical_manifest():
    from src.milestone_audit import evaluate_milestone_audit
    report=evaluate_milestone_audit(checklist(),snapshot(),review_registry={'schema_version':1,'approved_reviews':[]},now=101.0)
    assert report['verified'] is False and report['status']=='BLOCKED'


def test_committed_registry_truthfully_starts_with_no_approved_reviews():
    from src.milestone_audit import REVIEW_REGISTRY_PATH,evaluate_milestone_audit
    registry=json.loads(REVIEW_REGISTRY_PATH.read_text(encoding='utf-8'))
    assert registry['approved_reviews']==[]
    assert 'No permanent-milestone checklist is currently approved' in registry['policy']
    assert evaluate_milestone_audit(checklist(),snapshot(),now=101.0)['verified'] is False


def test_omitted_or_changed_conditions_do_not_match_pinned_coverage():
    from src.milestone_audit import evaluate_milestone_audit
    source=checklist();state=snapshot();registry=manifest_for(source,state)
    omitted=copy.deepcopy(source);omitted['checks'].pop()
    changed=copy.deepcopy(source);changed['checks'][0]['condition']['value']=25
    for candidate in (omitted,changed):
        result=evaluate_milestone_audit(candidate,state,review_registry=registry,now=101.0)
        assert result['verified'] is False and result['status']=='BLOCKED'


def test_game_hash_version_and_save_version_must_match_approved_manifest():
    from src.milestone_audit import evaluate_milestone_audit
    source=checklist();state=snapshot();registry=manifest_for(source,state)
    for key,value in [('swf_sha256','b'*64),('game_version','4.3.12'),('save_version',59)]:
        changed=copy.deepcopy(state)
        changed['game_identity'][key]=value
        report=evaluate_milestone_audit(source,changed,review_registry=registry,now=101.0)
        assert report['verified'] is False


def test_unknown_check_and_missing_field_block_whole_audit():
    from src.milestone_audit import evaluate_milestone_audit
    source=checklist()
    source['checks'].append({'id':'unknown-mechanic','condition':{'field':'ascension','op':'magic'}})
    result=evaluate_milestone_audit(source,snapshot(),now=101.0)
    assert result['verified'] is False and result['status']=='BLOCKED'
    assert result['checks'][-1]['status']=='UNKNOWN'
    source=checklist()
    source['checks'][0]['condition']['field']='not_measured'
    result=evaluate_milestone_audit(source,snapshot(),now=101.0)
    assert result['verified'] is False
    assert result['checks'][0]['status']=='UNKNOWN'
    source=checklist()
    source['checks'][0]['condition'].pop('value')
    result=evaluate_milestone_audit(source,snapshot(),now=101.0)
    assert result['verified'] is False
    assert result['checks'][0]['status']=='UNKNOWN'


def test_checklist_version_and_reincarnation_scope_must_match_snapshot():
    from src.milestone_audit import evaluate_milestone_audit
    state=snapshot()
    source=checklist();source['save_versions']=[57]
    assert evaluate_milestone_audit(source,state,now=101.0)['verified'] is False
    source=checklist();source['reincarnations']=[23]
    assert evaluate_milestone_audit(source,state,now=101.0)['verified'] is False


def test_audit_report_is_rejected_for_stale_or_changed_evidence():
    from src.milestone_audit import evaluate_milestone_audit,audit_matches_current
    state=snapshot();source=checklist()
    registry=manifest_for(source,state)
    report=evaluate_milestone_audit(source,state,review_registry=registry,now=101.0)
    assert report['verified'] is True
    changed=copy.deepcopy(state);changed['save_fingerprint']='save-new'
    assert not audit_matches_current(report,changed,source,registry,now=102.0)
    changed=copy.deepcopy(state);changed['reincarnation']=25
    assert not audit_matches_current(report,changed,source,registry,now=102.0)
    assert not audit_matches_current(report,state,source,registry,now=101.0+301)
