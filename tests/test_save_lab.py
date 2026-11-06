import json
from pathlib import Path

import pytest

from tools import save_lab


@pytest.fixture
def source(tmp_path, monkeypatch):
    live = tmp_path / 'live'
    live.mkdir()
    source = live / 'save.sol'
    source.write_bytes(b'original save bytes')
    monkeypatch.setattr(save_lab, '_extract_save_string', lambda data: data)
    monkeypatch.setattr(save_lab, 'decode_save', lambda data: {'saveVersion': 58, 'reincarnation': 24})
    return source


def test_snapshot_is_separate_and_source_unchanged(source, tmp_path):
    original = source.read_bytes()
    lab = save_lab.create_lab(source, tmp_path / 'labs')
    manifest = save_lab.verify_lab(lab)
    assert source.read_bytes() == original
    assert (lab / manifest['original']).read_bytes() == original
    assert manifest['runtime_isolation_verified'] is False
    assert save_lab.create_lab(source, tmp_path / 'labs') != lab


def test_refuses_live_directory_and_ancestor(source, tmp_path):
    for root in (source.parent, source.parent / 'tests', tmp_path):
        with pytest.raises(ValueError, match='separate'):
            save_lab.create_lab(source, root)


def test_corrupted_original_is_rejected(source, tmp_path):
    lab = save_lab.create_lab(source, tmp_path / 'labs')
    manifest = save_lab.verify_lab(lab)
    (lab / manifest['original']).write_bytes(b'corruption')
    with pytest.raises(ValueError, match='hash mismatch'):
        save_lab.verify_lab(lab)


def test_manifest_cannot_point_at_live_save(source, tmp_path):
    lab = save_lab.create_lab(source, tmp_path / 'labs')
    manifest = save_lab.verify_lab(lab)
    manifest['original'] = str(source)
    (lab / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='escapes'):
        save_lab.verify_lab(lab)
