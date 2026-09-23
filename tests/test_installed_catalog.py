from pathlib import Path
import importlib
import pytest

def api():
    assert Path('src/installed_catalog.py').exists(), 'Installed data catalog missing'
    return importlib.import_module('src.installed_catalog')

@pytest.fixture(scope='module')
def catalog():
    from src.bootstrap import find_game_directory
    return api().inspect_definitions(find_game_directory()/'RealmGrinderDesktop.swf')

def test_installed_upgrade_and_trophy_names_are_distinct(catalog):
    upgrades=[r for r in catalog['definitions'] if r['name']=='Stoic Resistance' and r['kind']=='upgrade']
    trophies=[r for r in catalog['definitions'] if r['name']=='Stoic Resistance' and r['kind']=='trophy']
    assert len(upgrades)==len(trophies)==1
    assert upgrades[0]['id']==552 and trophies[0]['id']==190

def test_installed_gem_power_matches_live_purchase_evidence(catalog):
    rows=[r for r in catalog['definitions'] if r['name']=='Gem Power' and r['kind']=='upgrade']
    assert len(rows)==1 and rows[0]['id']==20

def test_metadata_is_hash_scoped_and_not_an_executed_formula(catalog):
    assert len(catalog['swf_sha256'])==64
    assert catalog['execution_policy']=='DEFINITIONS_ONLY_NO_GAME_CODE_EXECUTION'
    assert len(catalog['definitions'])>500

def test_parse_declarative_constant_assignment_does_not_accept_computed_value():
    ops=[{'op':'pushshort','args':[552],'resolved':None},
         {'op':'0x5e','args':[1],'resolved':':id'},
         {'op':'0x2b','args':[],'resolved':None},
         {'op':'setproperty','args':[1],'resolved':':id'}]
    assert api().literal_assignment(ops,':id')==552
    ops.insert(1,{'op':'callproperty','args':[5,0],'resolved':':unknown'})
    assert api().literal_assignment(ops,':id') is None

def test_installed_sprite_preserves_transparency_and_dimensions(tmp_path):
    from PIL import Image
    atlas=Image.new('RGBA',(20,20),(1,2,3,255))
    item={'name':'test','x':'2','y':'3','width':'4','height':'5','frameX':'-1','frameY':'-2','frameWidth':'8','frameHeight':'9'}
    image=api().sprite_image(atlas,item)
    assert image.size==(8,9)
    assert image.getpixel((0,0))[3]==0 and image.getpixel((1,2))==(1,2,3,255)
