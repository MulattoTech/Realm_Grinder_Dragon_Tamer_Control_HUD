"""A clean checkout must bootstrap locally without importing private game state."""
import importlib
import json
from pathlib import Path
import pytest

def api():
    assert Path('src/bootstrap.py').exists(), 'Checkout bootstrap is missing'
    return importlib.import_module('src.bootstrap')


def test_bootstrap_creates_paused_configuration_without_game_or_network(tmp_path):
    report=api().initialize(tmp_path,game_dir=tmp_path/'missing-game')
    cfg=json.loads((tmp_path/'state/bot_config.json').read_text())
    assert cfg['paused'] is True and (tmp_path/'state/STOP').exists()
    assert cfg['auto_abdicate'] is False and cfg['auto_reincarnate'] is False
    assert report['game_metadata']=='NOT_AVAILABLE'
    assert (tmp_path/'state/build_manifests.json').exists()
    assert report['network_requests']==0 and report['game_input_sent'] is False


def test_bootstrap_preserves_existing_configuration_and_never_resumes(tmp_path):
    folder=tmp_path/'state';folder.mkdir()
    (folder/'bot_config.json').write_text('{"paused":true,"selected_path":"Druid","cycle_delay_sec":7}')
    (folder/'STOP').write_text('User stop')
    api().initialize(tmp_path,game_dir=tmp_path/'missing-game')
    cfg=json.loads((folder/'bot_config.json').read_text())
    assert cfg=={'paused':True,'selected_path':'Druid','cycle_delay_sec':7}
    assert (folder/'STOP').read_text()=='User stop'


def test_bootstrap_never_writes_to_game_directory(tmp_path):
    game=tmp_path/'game';game.mkdir();(game/'unrelated.bin').write_bytes(b'original')
    api().initialize(tmp_path/'project',game_dir=game)
    assert list(game.iterdir())==[game/'unrelated.bin']
    assert (game/'unrelated.bin').read_bytes()==b'original'


def test_cached_literal_identifiers_are_not_verified_against_a_different_binary(tmp_path):
    game=tmp_path/'game';game.mkdir();(game/'RealmGrinderDesktop.swf').write_bytes(b'not the supported version')
    report=api().initialize(tmp_path/'project',game_dir=game)
    assert report['game_metadata']=='UNRECOGNIZED_BINARY'
    catalog=json.loads((tmp_path/'project/state/milestone_catalog.json').read_text())
    assert not any(row.get('verified') for row in catalog['milestones'].values())


def test_missing_game_version_does_not_make_ui_action_profiles_verified(tmp_path):
    api().initialize(tmp_path,game_dir=tmp_path/'game')
    profile=tmp_path/'state/ui_actions.json'
    assert not profile.exists() or not json.loads(profile.read_text()).get('verified_actions')


def test_portable_reference_identifiers_do_not_require_scratch_directory():
    from src.build_catalog import load_reference_ids
    identifiers=load_reference_ids()
    assert identifiers['codes']['FR2']==195
    assert identifiers['spells']["God's Hand"]==9


def test_manifest_refresh_preserves_stronger_installed_identifier_metadata(tmp_path,monkeypatch):
    import src.build_catalog as catalog
    monkeypatch.setattr(catalog,'ROOT',tmp_path)
    source=Path(__file__).resolve().parents[1]/'data/reference_identifiers.json'
    (tmp_path/'data').mkdir();(tmp_path/'data/reference_identifiers.json').write_bytes(source.read_bytes())
    (tmp_path/'state').mkdir()
    original={'Fairy Bloodline':{'id':194,'verification':'installed_definition','source_sha256':'known'}}
    (tmp_path/'state/upgrade_catalog.json').write_text(json.dumps(original))
    catalog.rebuild_manifests(58)
    after=json.loads((tmp_path/'state/upgrade_catalog.json').read_text())
    assert after['Fairy Bloodline']==original['Fairy Bloodline']
