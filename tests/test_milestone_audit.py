import copy


def checklist():
    return {'schema_version':1,'checklist_id':'reviewed-test-v1','reviewed':True,
        'save_versions':[58],'reincarnations':[24],
        'checks':[{'id':'has-current-r','condition':{'field':'reincarnation','op':'eq','value':24}},
                  {'id':'known-ascension','condition':{'field':'ascension','op':'eq','value':0}}]}


def snapshot():
    return {'reincarnation':24,'ascension':0,'save_fingerprint':'save-abc','save_timestamp':100.0,
        'raw_data':{'saveVersion':58}}


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
    report=evaluate_milestone_audit(checklist(),state,now=101.0)
    assert report['verified'] is True and report['status']=='VERIFIED'
    assert report['snapshot_fingerprint']=='save-abc'
    assert report['snapshot_timestamp']==100.0
    assert report['save_version']==58 and report['reincarnation']==24
    assert audit_matches_current(report,state,checklist(),now=102.0)


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
    report=evaluate_milestone_audit(source,state,now=101.0)
    changed=copy.deepcopy(state);changed['save_fingerprint']='save-new'
    assert not audit_matches_current(report,changed,source,now=102.0)
    changed=copy.deepcopy(state);changed['reincarnation']=25
    assert not audit_matches_current(report,changed,source,now=102.0)
    assert not audit_matches_current(report,state,source,now=101.0+301)
