"""Cached, read-only identity for the installed Realm Grinder executable.

Identity is tied to the SWF SHA-256 and file stat signature. This module never
reads a save, inspects a running process, launches the game, or writes game data.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_CATALOG_PATH = ROOT / 'data' / 'supported_game_versions.json'


def _stat_signature(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=16)
def _identity_for_signature(binary_path, binary_signature, catalog_path, catalog_signature):
    if binary_signature is None:
        return {'game_version': None, 'swf_sha256': None, 'save_version': None,
                'supported': False, 'support_status': 'NOT_AVAILABLE'}
    try:
        digest = hashlib.sha256(Path(binary_path).read_bytes()).hexdigest()
        catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    except OSError:
        return {'game_version': None, 'swf_sha256': None, 'save_version': None,
                'supported': False, 'support_status': 'NOT_AVAILABLE'}
    match = next((item for item in catalog.get('versions', [])
                  if item.get('swf_sha256') == digest), None)
    if match is None:
        return {'game_version': None, 'swf_sha256': digest, 'save_version': None,
                'supported': False, 'support_status': 'UNRECOGNIZED_BINARY'}
    return {'game_version': match.get('game_version'), 'swf_sha256': digest,
            'save_version': match.get('save_version'), 'supported': True,
            'support_status': 'MATCHED_SUPPORTED_VERSION'}


def get_game_identity(game_dir=None):
    """Return supported-version metadata without reading game state or saves."""
    if game_dir is None:
        from src.bootstrap import find_game_directory
        game_dir = find_game_directory()
    binary = Path(game_dir) / 'RealmGrinderDesktop.swf'
    binary_signature = _stat_signature(binary)
    catalog_signature = _stat_signature(VERSION_CATALOG_PATH)
    result = _identity_for_signature(str(binary), binary_signature,
                                     str(VERSION_CATALOG_PATH), catalog_signature)
    return dict(result)


def clear_identity_cache():
    """Clear the process-local identity cache (primarily for controlled reloads)."""
    _identity_for_signature.cache_clear()
