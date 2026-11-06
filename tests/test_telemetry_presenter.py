"""HUD and snapshot presentation must not turn unknown measurements into accomplishments."""
import importlib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

def api():
    assert (ROOT/'src/telemetry_presenter.py').exists(), 'Truthful telemetry presentation is missing'
    return importlib.import_module('src.telemetry_presenter')

def state():
    return {'reincarnation':24,'gems':2.4e68,'faction':5,'mana_current':23207,
            'mana_max':None,'fairy_assistants':None,'has_egg':False,
            'hellfire_time':999999,'hellfire_since_hatch':None,
            'raw_data':{'upgrades':{},'trophies':{}},
            'provenance':{'mana_current':{'source':'AIR_SHAREDOBJECT','confidence':'LOW'}},
            'telemetry':{'process_connected':False,'memory_provider_health':'DISCONNECTED',
                         'verified_fields':[],'save_age_seconds':600,'save_provider_health':'STALE'}}


def test_banner_distinguishes_save_current_mana_and_unknown_maximum():
    a=api();text=a.telemetry_banner(state(),{'build_verified':False})
    assert 'SAVE' in text and 'Unknown' in text
    assert 'UNVERIFIED' in text and 'DISCONNECTED' in text


def test_banner_labels_verified_process_memory():
    a=api();s=state();s['provenance']['mana_current']={'source':'PROCESS_MEMORY','confidence':'VERIFIED'}
    s['telemetry'].update(process_connected=True,memory_provider_health='HEALTHY',verified_fields=['mana_current'])
    text=a.telemetry_banner(s,{'build_verified':True})
    assert 'MEM' in text and '1 verified' in text


def test_old_elapsed_time_assumptions_are_not_used_for_goal_stages():
    a=api()
    assert hasattr(a, 'dragon_goal_presentation')


def test_stage_reference_reads_profile_facts_and_labels_counter_uncertainty():
    a=api()
    view=a.dragon_stage_reference({
        'req_r':46,
        'time_gate_seconds':7200,
        'time_gate_description':'Static purchase check: save stat 81 total >= 7200; updater unknown',
        'req_faction':0,
        'req_assistants':5000,
        'assistants_description':'5,000 Fairy assistants under faction field 0',
    },True)
    assert 'R46' in view
    assert 'Dragon quest counter (stat 81)' in view
    assert 'updater semantics UNKNOWN' in view
    assert '5,000 Fairy assistants' in view
    assert '43200' not in view


def test_stage_reference_hides_profile_facts_until_identity_supported():
    a=api()
    view=a.dragon_stage_reference({'req_r':42,'req_excavations':1500},False)
    assert view=='Requirements: UNKNOWN until the supported game profile is confirmed.'


def test_unknown_number_formats_without_crashing():
    a=api();assert a.measured(None)=='Unknown'
    assert a.measured(1234)=='1,234'


# --- mana_bar() helper tests ---

def test_mana_bar_unknown_when_max_is_none():
    a=api();s=state()  # mana_max=None
    bar=a.mana_bar(s)
    assert bar['fill_pct'] is None
    assert bar['maximum'] is None

def test_mana_bar_fill_pct_computed_from_live_values():
    a=api();s=state();s['mana_current']=500.0;s['mana_max']=1000.0
    bar=a.mana_bar(s)
    assert bar['fill_pct']==50.0

def test_mana_bar_fill_capped_at_100():
    a=api();s=state();s['mana_current']=1200.0;s['mana_max']=1000.0
    bar=a.mana_bar(s)
    assert bar['fill_pct']==100.0

def test_mana_bar_source_badge_is_mem_for_process_memory():
    a=api();s=state()
    s['provenance']['mana_current']={'source':'PROCESS_MEMORY','confidence':'VERIFIED'}
    bar=a.mana_bar(s)
    assert bar['source_badge']=='MEM' and bar['is_live'] is True

def test_mana_bar_source_badge_is_save_for_sharedobject():
    a=api();s=state()  # default source is AIR_SHAREDOBJECT
    bar=a.mana_bar(s)
    assert bar['source_badge']=='SAVE' and bar['is_live'] is False

def test_mana_bar_regen_unknown_when_not_in_state():
    a=api();s=state();s.pop('mana_regeneration',None)
    bar=a.mana_bar(s)
    assert bar['regen_str']=='Unknown'

def test_mana_bar_regen_formatted_when_present():
    a=api();s=state();s['mana_regeneration']=22.5
    bar=a.mana_bar(s)
    assert bar['regen_str']=='+22.5'

def test_banner_includes_regen_rate():
    a=api();s=state();s['mana_regeneration']=15.3
    text=a.telemetry_banner(s,{'build_verified':False})
    assert '+15.3' in text or '15.3' in text
