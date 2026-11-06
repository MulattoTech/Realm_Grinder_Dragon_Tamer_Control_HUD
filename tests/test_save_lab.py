import json
import base64
import struct
import zlib
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


@pytest.fixture
def binary_export(tmp_path, monkeypatch):
    schema = tmp_path / 'schema.json'
    schema.write_text(json.dumps([
        {'format': 'Uint16', 'key': 'saveVersion'},
        {'format': 'Uint16', 'key': 'reincarnation'},
        {'format': 'Float64', 'key': 'gems'},
    ]))
    monkeypatch.setattr(save_lab, 'SCHEMA_FILE', str(schema))
    raw = struct.pack('>HHd', 58, 24, 6.83e72) + b'opaque trailing data'
    raw += struct.pack('>I', zlib.crc32(raw))
    encrypted = bytes(v ^ save_lab.VIGENERE_KEY[i % len(save_lab.VIGENERE_KEY)] for i, v in enumerate(raw))
    return '$00s' + base64.b64encode(zlib.compress(encrypted)).decode() + '$e'


def test_fixture_patch_preserves_unknown_bytes_and_updates_crc(binary_export):
    export = save_lab.edit_export(binary_export, {'reincarnation': 48, 'gems': 1e100})
    encrypted = zlib.decompress(base64.b64decode(export[4:-2]))
    raw = bytes(v ^ save_lab.VIGENERE_KEY[i % len(save_lab.VIGENERE_KEY)] for i, v in enumerate(encrypted))
    assert struct.unpack('>HHd', raw[:12]) == (58, 48, 1e100)
    assert raw[12:-4] == b'opaque trailing data'
    assert struct.unpack('>I', raw[-4:])[0] == zlib.crc32(raw[:-4])


@pytest.mark.parametrize('changes', [{'saveVersion': 59}, {'gems': float('nan')},
                                    {'reincarnation': 48.5}, {'gems': True}, {'gems': -1}])
def test_fixture_patch_rejects_invalid_changes(binary_export, changes):
    with pytest.raises(ValueError):
        save_lab.edit_export(binary_export, changes)


def test_fixture_patch_rejects_bad_checksum(binary_export):
    encrypted = bytearray(zlib.decompress(base64.b64decode(binary_export[4:-2])))
    encrypted[-1] ^= 1
    bad = '$00s' + base64.b64encode(zlib.compress(encrypted)).decode() + '$e'
    with pytest.raises(ValueError, match='checksum'):
        save_lab.edit_export(bad, {'reincarnation': 48})
