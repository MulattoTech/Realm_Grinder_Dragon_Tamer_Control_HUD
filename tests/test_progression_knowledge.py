import importlib
from pathlib import Path
import math
import pytest

ROOT=Path(__file__).resolve().parents[1]

def api(name):
    assert (ROOT/'src'/f'{name}.py').exists(), f'{name} not implemented'
    return importlib.import_module('src.'+name)


def test_knowledge_preserves_source_and_finds_requirements(tmp_path):
    k=api('source_knowledge').KnowledgeStore(tmp_path/'knowledge.sqlite3')
    k.ingest('Mercenary','http://musicfamily.org/realm/MercenaryFaction/',
        'Mercenary First Contract\nCost\n: 50 Spd (5e55)\nEffect\n: Unlocks Tier 1 Upgrades.',origin='musicfamily')
    rows=k.search('Mercenary First Contract')
    assert rows and rows[0]['source_url'].startswith('http://musicfamily.org/')
    assert '5e55' in rows[0]['text']
    assert k.stats()['documents']==1


def test_source_reimport_updates_without_duplicate_documents(tmp_path):
    k=api('source_knowledge').KnowledgeStore(tmp_path/'k.sqlite3')
    for text in ('First value','Updated value'):k.ingest('test','http://musicfamily.org/realm/Test/',text)
    assert k.stats()['documents']==1
    assert k.search('Updated')[0]['text']=='Updated value'


def test_archived_source_keeps_original_and_capture_date(tmp_path):
    k=api('source_knowledge').KnowledgeStore(tmp_path/'k.sqlite3')
    k.ingest('Mercenary','https://realm-grinder.fandom.com/wiki/Mercenary','Archived requirements',
        origin='fandom',resolved_url='http://web.archive.org/web/20260705/https://realm-grinder.fandom.com/wiki/Mercenary',captured_at='2026-07-05')
    row=k.search('Archived')[0]
    assert row['captured_at']=='2026-07-05' and 'web.archive.org' in row['resolved_url']


def test_templates_keep_spaces_apostrophes_and_continuation():
    records=api('source_knowledge').extract_templates("Build\nFR2,FR7,EL5,\nSP:Fairy Chanting,SP:God's Hand\nNote: test")
    assert records==["FR2,FR7,EL5,SP:Fairy Chanting,SP:God's Hand"]


def test_unknown_rule_is_not_false_or_automatically_satisfied():
    evaluate=api('strategy_rules').evaluate_condition
    assert evaluate({'op':'unknown_source_prose'}, {}) is None
    assert evaluate({'field':'mana_max','op':'gte','value':50000},{'mana_max':None}) is None
    assert evaluate({'field':'reincarnation','op':'gte','value':46},{'reincarnation':24}) is False


def test_three_valued_prerequisite_logic():
    e=api('strategy_rules').evaluate_condition
    unknown={'field':'missing','op':'gte','value':1}
    yes={'field':'r','op':'gte','value':24};no={'field':'r','op':'gte','value':46}
    assert e({'all':[yes,unknown]},{'r':24}) is None
    assert e({'all':[no,unknown]},{'r':24}) is False
    assert e({'any':[yes,unknown]},{'r':24}) is True
    assert e({'any':[no,unknown]},{'r':24}) is None


def sample(**changes):
    s={'reincarnation':24,'ascension':0,'gems':2.4e68,'coins':1e16,'faction':-1,'alignment':0,
       'raw_data':{'upgrades':{},'trophies':{'190':{}},'buildings':{},'mercSpell1':0,'mercSpell2':0}}
    s.update(changes);return s


def test_route_setup_starts_with_gem_power_not_repeated_buy_all():
    p=api('strategy_rules').RoutePlanner()
    result=p.next_step(sample(),'Neutral Mercenary',{})
    assert result['target']=='Gem Power' and result['action']=='purchase_named'


def test_owned_bootstrap_skips_to_alignment():
    p=api('strategy_rules').RoutePlanner()
    s=sample();s['raw_data']['upgrades']={'1':{'u1':True},'2':{'u1':True}}
    catalog={'Gem Power':{'id':1},'Stoic Resistance':{'id':2}}
    result=p.next_step(s,'Neutral Mercenary',catalog)
    assert result['target']=='Proof of Neutrality'


def test_insufficient_alignment_gold_generates_resource_step():
    p=api('strategy_rules').RoutePlanner();s=sample(coins=100)
    s['raw_data']['upgrades']={'1':{'u1':True},'2':{'u1':True}}
    result=p.next_step(s,'Neutral Mercenary',{'Gem Power':{'id':1},'Stoic Resistance':{'id':2}})
    assert result['action']=='collect_coins' and result['target_coins']==1e16


def test_neutral_alignment_leads_to_contract_not_other_faction():
    p=api('strategy_rules').RoutePlanner();s=sample(alignment=3,coins=1e60)
    s['raw_data']['upgrades']={'1':{'u1':True},'2':{'u1':True}}
    result=p.next_step(s,'Neutral Mercenary',{'Gem Power':{'id':1},'Stoic Resistance':{'id':2}})
    assert result['target']=='Mercenary First Contract'


def test_selecting_different_faction_never_blindly_resets():
    p=api('strategy_rules').RoutePlanner()
    result=p.next_step(sample(faction=5,alignment=2),'Neutral Mercenary',{})
    assert result['action']=='needs_abdication' and result['automatic_reset'] is False


def test_vanilla_path_has_correct_alignment_and_treaty():
    p=api('strategy_rules').RoutePlanner();s=sample(alignment=2,coins=1e30)
    s['raw_data']['upgrades']={'1':{'u1':True},'2':{'u1':True}}
    result=p.next_step(s,'Goblin',{'Gem Power':{'id':1},'Stoic Resistance':{'id':2}})
    assert result['target']=='Goblin Trade Treaty'


def test_modern_stage_not_silently_treated_as_a0():
    p=api('strategy_rules').RoutePlanner()
    result=p.next_step(sample(reincarnation=130,ascension=3),'Neutral Mercenary',{})
    assert result['action']=='unsupported_stage' and result['sources']


def test_default_eta_does_not_invent_twenty_minute_rs():
    from src.telemetry import ProgressionTracker
    tracker=ProgressionTracker();tracker.history=[]
    result=tracker.calculate_etas(24,2.4e68,1e16,{})
    assert result['current_r_eta_seconds'] is None
    assert result['total_eta_seconds'] is None and result['target_completion_date'] is None


def test_measured_log_progress_has_a_bounded_conditional_eta():
    e=api('measured_eta').estimate_target
    rows=[{'time':i*10,'value':10.0**(60+i),'run':'a'} for i in range(8)]
    result=e(rows,1e70,now=70)
    assert result['seconds'] is not None and 25<=result['seconds']<=35
    assert result['model']=='observed_log_growth' and result['conditional'] is True


def test_flat_reset_stale_and_insufficient_data_have_no_eta():
    e=api('measured_eta').estimate_target
    flat=[{'time':i*10,'value':1e60,'run':'a'} for i in range(8)]
    assert e(flat,1e70,now=70)['seconds'] is None
    rows=[{'time':i*10,'value':10.0**(60+i),'run':'a' if i<6 else 'b'} for i in range(8)]
    assert e(rows,1e70,now=70)['seconds'] is None
    assert e(flat,1e70,now=1000)['seconds'] is None


def test_paused_prediction_is_not_a_countdown():
    e=api('measured_eta').estimate_target
    rows=[{'time':i*10,'value':10.0**(60+i),'run':'a'} for i in range(8)]
    assert e(rows,1e70,now=70,paused=True)['status']=='PAUSED'


def test_source_urls_canonicalize_fragment_and_trailing_slash():
    from src import source_knowledge as k
    assert hasattr(k,'canonical_url')
    assert k.canonical_url('http://musicfamily.org/realm/MercBuilds#Notes')=='http://musicfamily.org/realm/MercBuilds/'
    assert k.canonical_url('https://realm-grinder.fandom.com/wiki/Mercenary#Tier')=='https://realm-grinder.fandom.com/wiki/Mercenary'


def test_html_templates_include_input_values():
    from src import source_knowledge as k
    assert hasattr(k,'html_text')
    result=k.html_text('<html><body><p>Assisted Advancement</p><input value="FR2,FR7,SP:Fairy Chanting"></body></html>')
    assert 'FR2,FR7,SP:Fairy Chanting' in result
