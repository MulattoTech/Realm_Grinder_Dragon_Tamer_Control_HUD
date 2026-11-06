"""Template syntax, numeric ownership IDs and actual faction verification."""
import importlib
from pathlib import Path
import pytest

def api():
    assert Path('src/build_catalog.py').exists(), 'Source-backed build compiler is missing'
    return importlib.import_module('src.build_catalog')


def test_current_merc_template_compiles_twelve_upgrades_and_two_spells():
    from src.wiki_data import BUILDS_DATABASE
    catalog=api().load_reference_ids()
    template=BUILDS_DATABASE['R24_MERC_NEUTRAL']['template']
    result=api().compile_template(template,catalog,save_version=58,game_identity=identity())
    assert result['verified'] and len(result['required_upgrade_ids'])==12
    assert result['merc_spells']==[6,9]
    assert 203 in result['required_upgrade_ids']
    assert len(result['sources'])>=1


def test_unknown_template_tokens_never_pass_validation():
    result=api().compile_template('FR2,NOPE999,SP:Invented Spell',api().load_reference_ids(),58)
    assert not result['verified'] and result['unresolved_tokens']==['FR2','NOPE999','SP:Invented Spell']


def test_research_template_uses_branch_value_ids_not_plain_number():
    result=api().compile_template('S50,C105,D55,E80,A10,W25',api().load_reference_ids(),58,identity())
    assert result['verified'] and len(result['required_upgrade_ids'])==6
    assert result['required_upgrade_ids'][0]==300
    assert 130002 not in result['required_upgrade_ids']


def identity():
    import json
    support=json.loads((Path(__file__).resolve().parents[1]/'data/supported_game_versions.json').read_text())
    item=next(v for v in support['versions'] if v['game_version']=='4.3.22')
    return {'supported':True,'swf_sha256':item['swf_sha256'],'save_version':item['save_version']}


def test_template_manifest_fails_closed_for_wrong_game_hash():
    result=api().compile_template('S50',api().load_reference_ids(),58,{**identity(),'swf_sha256':'0'*64})
    assert not result['verified']
    assert result['unresolved_tokens']==['S50']


def test_neutral_mercenary_name_is_a_valid_affiliation_label():
    from src.action_verification import verify_build
    state={'faction':11,'alignment':3,'game_identity':identity(),
           'raw_data':{'saveVersion':58,'upgrades':{'203':{'u1':True}}}}
    rec={'name':'test','faction':'Neutral Mercenary','bloodline':None,'template':'FR2'}
    manifest={'verified':True,'template':'FR2','save_version':58,'swf_sha256':identity()['swf_sha256'],
              'required_upgrade_ids':[203],'alignment':3}
    assert verify_build(state,rec,manifest)['build_verified']


def test_visible_input_requires_an_explicit_configuration_mode(monkeypatch):
    import src.runtime_safety as safety
    class FakePath:
        def __truediv__(self,x):return self
        def exists(self):return False
    class Window:
        pid=4
        def find_window(self):return True
        def is_minimized(self):return False
    monkeypatch.setattr(safety,'STATE_DIR',FakePath())
    monkeypatch.setattr(safety,'session_id',lambda pid=None:1)
    monkeypatch.setattr(safety,'load_config',lambda:{'paused':False,'require_minimized':True})
    assert not safety.input_allowed(Window())
    monkeypatch.setattr(safety,'load_config',lambda:{'paused':False,'require_minimized':False})
    assert safety.input_allowed(Window())
