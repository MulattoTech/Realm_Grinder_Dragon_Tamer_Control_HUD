"""
Save extractor and decoder for Realm Grinder.
Uses dox4242/RG-tools savecodec and fennovj/py-rgtools decrypt logic.
Operates READ-ONLY on .sol SharedObject and exported strings.
"""

import os
import re
import json
import base64
import hashlib
import threading
from typing import Optional, Dict, Any

SOL_PATH = os.path.expandvars(
    r"%APPDATA%\com.kongregate.mobile.realmgrinder.air\Local Store\#SharedObjects\RealmGrinderDesktop.swf\realm-grinder.sol"
)


def extract_save_string_from_sol(sol_path: str = SOL_PATH) -> str:
    """Reads the latest raw save string from the local SharedObject file."""
    if not os.path.exists(sol_path):
        raise FileNotFoundError(f"SharedObject file not found at: {sol_path}")
    with open(sol_path, "rb") as f:
        return _extract_save_string(f.read())


def _extract_save_string(d: bytes) -> str:
    """Extract a save string from one already-read SharedObject snapshot."""
    end = d.rfind(b"$e")
    if end == -1:
        raise ValueError("Could not locate '$e' terminator in .sol file.")
    end += 2

    save_key = d.find(b"save")
    if save_key != -1:
        start = d.find(b"$", save_key)
    else:
        start = d.find(b"$0")
        if start == -1:
            start = d.find(b"$")

    if start == -1 or end <= start:
        raise ValueError("Could not locate valid save string boundaries in .sol file.")
    save_str = d[start:end].decode("latin1").strip().rstrip("\x00")
    return save_str


from src.py_savecodec import decode_realm_grinder_save


def decode_save(save_string: str) -> Dict[str, Any]:
    """
    Decodes a save string via 100% pure Python in-memory decoder in ~4ms.
    Zero subprocesses, zero console allocations, zero terminal windows.
    """
    return decode_realm_grinder_save(save_string)


def normalize_save_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve raw save data and distinguish measured fields from unknown quantities.

    Field IDs/semantics: dox4242/RG-tools lib/util.js and edit/edit.js.
    Spell 11 is Hellfire Blast; 3 is Call to Arms. active0/1/2 are
    this-run/previous-runs/previous-reincarnations activity; t is duration.
    Trophy presence proves ownership; its u1 flag is NOT upgrade ownership.
    """
    import math
    for key in ('reincarnation', 'gems', 'coins'):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid core save field: {key}={value!r}')
    if int(data['reincarnation']) != data['reincarnation']:
        raise ValueError('Reincarnation must be an integer')
    stats = data.get('stats', [])
    def stat(index, default=0):
        return stats[index].get('stats', default) if isinstance(stats, list) and len(stats)>index and isinstance(stats[index], dict) else default
    coins_this_game = stat(0, data['coins'])
    if not isinstance(coins_this_game, (int, float)) or not math.isfinite(coins_this_game) or coins_this_game < 0:
        raise ValueError('Invalid coins produced this run')
    potential = math.floor((math.sqrt(1.0+8.0*(coins_this_game/1e12))-1.0)/2.0) if coins_this_game else 0
    hellfire = data.get('spells', {}).get('11', {})
    active = [max(0.0, float(hellfire.get(f'active{i}', 0))) for i in range(3)]
    if not all(math.isfinite(value) for value in active):
        raise ValueError('Invalid spell activity counter')
    mana = data.get('mana')
    if mana is not None and (not isinstance(mana, (int, float)) or not math.isfinite(mana) or mana < 0):
        raise ValueError('Invalid current mana')
    legacy = stat(12)
    return {
        'reincarnation': int(data['reincarnation']), 'ascension': data.get('ascension', 0),
        'gems': data['gems'], 'coins': data['coins'],
        'coins_this_game': coins_this_game, 'coins_this_abdication': coins_this_game,
        'potential_gems': potential, 'gems_gain': max(0.0, potential-data['gems']),
        'assistants': legacy,  # Deprecated legacy compatibility field, NOT assistants evidence.
        'legacy_stat_12': legacy, 'assistants_total': None,
        'assistants_current': None, 'fairy_assistants': None,
        'excavations': data.get('excavations', 0), 'alignment': data.get('alignment', 0),
        'faction': data.get('faction', -1), 'prestige_faction': data.get('prestigeFaction', -1),
        'has_egg': '211' in data.get('trophies', {}),
        'hellfire_time': active[0], 'hellfire_active_time_this_run': active[0],
        'hellfire_active_time_this_r': sum(active[:2]), 'hellfire_active_time_total': sum(active),
        'hellfire_since_hatch': None, 'hellfire_autocast': bool(hellfire.get('a', False)),
        'hellfire_remaining_raw': hellfire.get('t'),
        'mana': mana, 'mana_current': mana, 'mana_max': None, 'mana_regeneration': None,
        'raw_data': data,
    }


def get_current_game_state() -> Dict[str, Any]:
    """Read a stable on-disk snapshot; retain its actual age, not the read time."""
    import time
    last_error = None
    for _ in range(3):
        try:
            before = os.stat(SOL_PATH)
            with open(SOL_PATH, "rb") as stream:
                snapshot = stream.read()
            data = decode_save(_extract_save_string(snapshot))
            after = os.stat(SOL_PATH)
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                raise OSError('Save changed during decoding')
            result = normalize_save_data(data)
            result.update(save_timestamp=after.st_mtime,
                          save_age_seconds=max(0, time.time()-after.st_mtime),
                          save_fingerprint=(f'{after.st_mtime_ns}:{after.st_size}:'
                                            f'{hashlib.sha256(snapshot).hexdigest()}'),
                          save_decoded_at=time.time())
            return result
        except (OSError, ValueError, EOFError) as exc:
            last_error = exc
            time.sleep(0.02)
    raise last_error
