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


def test_supported_binary_rebuilds_catalogs_and_discards_old_verified_rows(tmp_path,monkeypatch):
    import hashlib
    import src.bootstrap as bootstrap
    import src.installed_catalog as installed
    game=tmp_path/'game';game.mkdir()
    binary=game/'RealmGrinderDesktop.swf';binary.write_bytes(b'supported 4.3.22')
    digest=hashlib.sha256(binary.read_bytes()).hexdigest()
    support=tmp_path/'supported.json'
    support.write_text(json.dumps({'schema_version':1,'versions':[{
        'game_version':'4.3.22','save_version':None,'swf_sha256':digest,
        'definitions':[{'id':211,'name':'Spiky Rough Egg','kind':'trophy','icon_candidates':['EggIcon']},
                       {'id':613,'name':'Dragon Tamer','kind':'upgrade','icon_candidates':['TamerIcon']}]}]}))
    monkeypatch.setattr(bootstrap,'VERSION_CATALOG_PATH',support,raising=False)
    monkeypatch.setattr(installed,'inspect_definitions',lambda path:{'swf_sha256':digest,'source_path':str(path),
        'definitions':[{'id':211,'name':'Spiky Rough Egg','kind':'trophy','icon_candidates':['EggIcon'],
                        'constructor':9,'class':'EggDef'},
                       {'id':613,'name':'Dragon Tamer','kind':'upgrade','icon_candidates':['TamerIcon'],
                        'constructor':12,'class':'TamerDef'}]})
    project=tmp_path/'project';state=project/'state';state.mkdir(parents=True)
    config={'paused':False,'auto_abdicate':True,'auto_reincarnate':True,'selected_path':'Druid'}
    profile={'calibrated_client_size':[123,456],'verified_actions':['abdicate']}
    (state/'bot_config.json').write_text(json.dumps(config))
    (state/'STOP').write_text('do not clear')
    (state/'ui_actions.json').write_text(json.dumps(profile))
    (state/'upgrade_catalog.json').write_text(json.dumps({
        'Old verified upgrade':{'id':552,'verification':'installed_definition','source_sha256':'old'}}))
    (state/'milestone_catalog.json').write_text(json.dumps({'schema_version':2,'milestones':{
        'dragon_tamer':{'id':210,'verified':True,'swf_sha256':'old'}}}))
    (project/'assets/templates').mkdir(parents=True)
    (project/'assets/templates/registry.json').write_text(json.dumps({'Old icon':{'file':'old.png',
        'source_page':'INSTALLED_GAME old','sha256':'old'}}))
    report=bootstrap.initialize(project,game_dir=game)
    upgrades=json.loads((state/'upgrade_catalog.json').read_text())
    milestones=json.loads((state/'milestone_catalog.json').read_text())['milestones']
    registry=json.loads((project/'assets/templates/registry.json').read_text())
    assert report['game_metadata']=='MATCHED_SUPPORTED_VERSION'
    assert json.loads((state/'bot_config.json').read_text())==config
    assert (state/'STOP').read_text()=='do not clear'
    assert json.loads((state/'ui_actions.json').read_text())==profile
    assert upgrades['Dragon Tamer']['id']==613
    assert upgrades['Dragon Tamer']['source_sha256']==digest
    assert 'Old verified upgrade' not in upgrades
    assert milestones['spiky_rough_egg']['id']==211 and milestones['spiky_rough_egg']['verified']
    assert 'dragon_tamer' not in milestones
    assert not any(row.get('source_page')=='INSTALLED_GAME old' for row in registry.values())


@pytest.mark.parametrize('binary_bytes,expected_status',[(b'unknown','UNRECOGNIZED_BINARY'),
                                                         (None,'NOT_AVAILABLE')],
                         ids=['unknown-binary','missing-binary'])
def test_unsupported_binary_invalidates_verified_catalogs_and_keeps_pause_controls(
        tmp_path,monkeypatch,binary_bytes,expected_status):
    import src.bootstrap as bootstrap
    support=tmp_path/'supported.json'
    support.write_text(json.dumps({'schema_version':1,'versions':[]}))
    monkeypatch.setattr(bootstrap,'VERSION_CATALOG_PATH',support,raising=False)
    game=tmp_path/'game';game.mkdir()
    if binary_bytes is not None:(game/'RealmGrinderDesktop.swf').write_bytes(binary_bytes)
    project=tmp_path/'project';state=project/'state';state.mkdir(parents=True)
    config={'paused':False,'auto_abdicate':True,'auto_reincarnate':True,'selected_path':'Druid'}
    (state/'bot_config.json').write_text(json.dumps(config))
    (state/'STOP').write_text('existing stop')
    (state/'upgrade_catalog.json').write_text(json.dumps({'Old verified':{
        'id':210,'verification':'installed_definition','source_sha256':'old'}}))
    (state/'milestone_catalog.json').write_text(json.dumps({'schema_version':2,'milestones':{
        'dragon_tamer':{'id':210,'verified':True,'swf_sha256':'old'}}}))
    (project/'assets/templates').mkdir(parents=True)
    (project/'assets/templates/registry.json').write_text(json.dumps({'Old icon':{
        'file':'old.png','source_page':'INSTALLED_GAME old'}}))
    report=bootstrap.initialize(project,game_dir=game)
    assert report['game_metadata']==expected_status
    assert json.loads((state/'bot_config.json').read_text())==config
    assert (state/'STOP').read_text()=='existing stop'
    assert json.loads((state/'upgrade_catalog.json').read_text())=={}
    assert json.loads((state/'milestone_catalog.json').read_text())['milestones']=={}
    assert json.loads((project/'assets/templates/registry.json').read_text())=={}


def test_supported_catalog_data_contains_literal_ids_without_calibration_claims():
    data=json.loads((Path(__file__).resolve().parents[1]/'data/supported_game_versions.json').read_text())
    current=next(item for item in data['versions'] if item['game_version']=='4.3.22')
    pairs={(row['name'],row['kind']):row['id'] for row in current['definitions']}
    assert current['swf_sha256']=='7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'
    assert current['save_version']==58
    assert current['save_version_provenance']=='current save decode + installed manifest/hash, 2026-11-06'
    assert pairs[('Spiky Rough Egg','trophy')]==211
    assert pairs[('Dragon Tamer','upgrade')]==613
    assert pairs[('Dragon Tamer','trophy')]==210
    assert not any(key in current for key in ('reset_calibration','mechanics','ui_actions'))
