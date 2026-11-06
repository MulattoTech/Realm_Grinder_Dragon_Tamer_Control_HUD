import hashlib
import json
from pathlib import Path

from src import game_identity


def test_identity_reads_only_supported_version_metadata_and_caches_by_file_stat(tmp_path,monkeypatch):
    game=tmp_path/'game';game.mkdir()
    binary=game/'RealmGrinderDesktop.swf';binary.write_bytes(b'installed swf bytes')
    digest=hashlib.sha256(binary.read_bytes()).hexdigest()
    catalog=tmp_path/'supported.json'
    catalog.write_text(json.dumps({'schema_version':1,'versions':[{
        'game_version':'4.3.22','save_version':58,'swf_sha256':digest,'definitions':[]}]}))
    monkeypatch.setattr(game_identity,'VERSION_CATALOG_PATH',catalog)

    result=game_identity.get_game_identity(game)
    assert result=={'game_version':'4.3.22','swf_sha256':digest,'save_version':58,
                    'supported':True,'support_status':'MATCHED_SUPPORTED_VERSION'}
    binary.write_bytes(b'new unknown swf bytes')
    updated=game_identity.get_game_identity(game)
    assert updated['support_status']=='UNRECOGNIZED_BINARY'
    assert updated['swf_sha256']==hashlib.sha256(binary.read_bytes()).hexdigest()


def test_identity_missing_binary_returns_fail_closed_status(tmp_path,monkeypatch):
    catalog=tmp_path/'supported.json'
    catalog.write_text(json.dumps({'schema_version':1,'versions':[]}))
    monkeypatch.setattr(game_identity,'VERSION_CATALOG_PATH',catalog)
    result=game_identity.get_game_identity(tmp_path/'missing')
    assert result=={'game_version':None,'swf_sha256':None,'save_version':None,
                    'supported':False,'support_status':'NOT_AVAILABLE'}
