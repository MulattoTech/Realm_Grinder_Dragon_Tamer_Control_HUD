"""Create and verify private save fixtures without writing the game's save.

This prepares files only. It does not isolate a running game, import a save,
change Steam state, or claim that edited fixtures were earned in gameplay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.save_reader import SOL_PATH, _extract_save_string, decode_save


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
    parser.add_argument('--source', type=Path, default=Path(SOL_PATH))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'state/test-lab')
    args = parser.parse_args()
    lab = args.verify or create_lab(args.source, args.root)
    print(json.dumps({'lab': str(lab), 'verification': verify_lab(lab)}, indent=2))


if __name__ == '__main__':
    main()
