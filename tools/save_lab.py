"""Create and verify private save fixtures without writing the game's save.

This prepares files only. It does not isolate a running game, import a save,
change Steam state, or claim that edited fixtures were earned in gameplay.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import uuid
import struct
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.save_reader import SOL_PATH, _extract_save_string, decode_save
from src.py_savecodec import PythonSaveDecoder, SCHEMA_FILE, TYPE_MAP, VIGENERE_KEY


def edit_export(export: str, changes: dict):
    """Patch selected scalar fields, retaining unknown bytes and array contents.

    Wire format reference: dox4242/RG-tools lib/savecodec2.js (MIT).
    Independent implementation using Python's standard CRC32 and zlib APIs.
    Returns an import string only; it never accesses the live save location.
    """
    allowed = {'reincarnation', 'gems', 'coins', 'mana', 'excavations'}
    if not changes or not set(changes) <= allowed:
        raise ValueError('Only explicit supported fixture scalar fields may be changed')
    if not export.startswith('$00s') or not export.endswith('$e'):
        raise ValueError('Only format-00 binary exports are supported')
    compressed = base64.b64decode(export[4:-2], validate=True)
    encrypted = zlib.decompress(compressed)
    raw = bytearray(v ^ VIGENERE_KEY[i % len(VIGENERE_KEY)] for i, v in enumerate(encrypted))
    if len(raw) < 6 or struct.unpack_from('>I', raw, len(raw)-4)[0] != zlib.crc32(raw[:-4]):
        raise ValueError('Input save checksum is invalid')

    class Offsets(PythonSaveDecoder):
        def __init__(self):
            super().__init__(SCHEMA_FILE)
            self.offsets = {}

        def _parse_item(self, parent, item):
            start = self.position
            super()._parse_item(parent, item)
            key, fmt = item.get('key'), item.get('format')
            if parent is self.save and isinstance(key, str) and key in allowed and fmt in TYPE_MAP:
                if self.position-start == TYPE_MAP[fmt][1]:
                    self.offsets[key] = (start, TYPE_MAP[fmt][0])

    reader = Offsets()
    before = reader.decode_struct(bytes(raw))
    if before.get('saveVersion') != 58:
        raise ValueError('Fixture editing requires reviewed save schema 58')
    for key, value in changes.items():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError('Fixture values must be finite nonnegative numbers')
        if key not in reader.offsets:
            raise ValueError(f'No verified scalar offset for {key}')
        offset, fmt = reader.offsets[key]
        if fmt != '>d' and (not isinstance(value, int)):
            raise ValueError(f'{key} requires an integer')
        struct.pack_into(fmt, raw, offset, value)
    struct.pack_into('>I', raw, len(raw)-4, zlib.crc32(raw[:-4]))
    expected = dict(before, **changes)
    if Offsets().decode_struct(bytes(raw)) != expected:
        raise ValueError('Edited save changed fields outside the requested patch')
    encrypted = bytes(v ^ VIGENERE_KEY[i % len(VIGENERE_KEY)] for i, v in enumerate(raw))
    return '$00s' + base64.b64encode(zlib.compress(encrypted)).decode('ascii') + '$e'


def create_fixture(lab: Path, changes: dict):
    manifest = verify_lab(lab)
    baseline = (lab / manifest['baseline']).read_bytes()
    export = edit_export(_extract_save_string(baseline), changes)
    output = lab / 'test-saves' / ('fixture-' + uuid.uuid4().hex)
    output = output.resolve()
    if lab.resolve() not in output.parents:
        raise ValueError('Fixture output escapes the lab')
    output.mkdir(exist_ok=False)
    (output / 'import.txt').write_text(export, encoding='ascii')
    receipt = {'kind': 'MODIFIED_TEST_SAVE', 'changes': changes,
               'baseline_sha256': manifest['sha256'], 'export_sha256': digest(export.encode('ascii')),
               'imported_into_game': False, 'earned_progression': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    verify_lab(lab)
    return output


def digest(data):
    return hashlib.sha256(data).hexdigest()


def create_lab(source: Path, root: Path):
    source, root = source.resolve(strict=True), root.resolve()
    if root == source.parent or source.parent in root.parents or root in source.parents:
        raise ValueError('Test storage must be separate from the live save directory')
    before = source.stat()
    data = source.read_bytes()
    after = source.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size) or source.read_bytes() != data:
        raise RuntimeError('Save changed while being captured; retry a fresh observation')
    decoded = decode_save(_extract_save_string(data))
    lab = root / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:8])
    original = lab / 'protected-original' / 'realm-grinder.sol'
    baseline = lab / 'test-saves' / 'baseline.sol'
    original.parent.mkdir(parents=True, exist_ok=False)
    baseline.parent.mkdir()
    for path in (original, baseline):
        with path.open('xb') as stream:
            stream.write(data)
        if path.read_bytes() != data:
            raise OSError('Save copy failed byte verification')
    manifest = {
        'schema': 1, 'created_at': time.time(), 'source': str(source),
        'original': str(original.relative_to(lab)),
        'baseline': str(baseline.relative_to(lab)), 'sha256': digest(data),
        'bytes': len(data), 'save_version': decoded.get('saveVersion'),
        'reincarnation': decoded.get('reincarnation'),
        'isolation': 'FILES_ONLY', 'runtime_isolation_verified': False,
        'live_save_written': False,
    }
    (lab / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    verify_lab(lab)
    return lab


def verify_lab(lab: Path):
    lab = lab.resolve(strict=True)
    manifest = json.loads((lab / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1:
        raise ValueError('Unknown save lab manifest schema')
    for key in ('original', 'baseline'):
        path = (lab / manifest[key]).resolve(strict=True)
        if lab not in path.parents:
            raise ValueError('Save fixture escapes the lab directory')
        data = path.read_bytes()
        if len(data) != manifest['bytes'] or digest(data) != manifest['sha256']:
            raise ValueError(f'{key} hash mismatch; do not use this lab')
        decoded = decode_save(_extract_save_string(data))
        if decoded.get('saveVersion') != manifest['save_version']:
            raise ValueError('Save schema does not match the manifest')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--fixture-from', type=Path)
    parser.add_argument('--set', action='append', default=[], metavar='FIELD=NUMBER')
    parser.add_argument('--source', type=Path, default=Path(SOL_PATH))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'state/test-lab')
    args = parser.parse_args()
    if args.fixture_from:
        changes = dict(item.split('=', 1) for item in args.set)
        print(create_fixture(args.fixture_from, {key: json.loads(value) for key, value in changes.items()}))
        return
    if args.set:
        parser.error('--set requires --fixture-from')
    lab = args.verify or create_lab(args.source, args.root)
    print(json.dumps({'lab': str(lab), 'verification': verify_lab(lab)}, indent=2))


if __name__ == '__main__':
    main()
