import base64
import hashlib
import json
import os
import zlib

from src.save_reader import get_current_game_state


def test_same_size_same_mtime_replacement_changes_decoded_fingerprint(monkeypatch, tmp_path):
    import src.save_reader as reader

    path = tmp_path/'synthetic.sol'
    def encoded(gems):
        data = {'reincarnation': 24, 'gems': gems, 'coins': 5678}
        body = base64.b64encode(zlib.compress(json.dumps(data).encode())).decode('ascii')
        return ('save$s' + body + '$e').encode('ascii')

    first, second = encoded(1234), encoded(9876)
    assert len(first) == len(second)
    path.write_bytes(first)
    monkeypatch.setattr(reader, 'SOL_PATH', str(path))
    before = path.stat()
    state_before = reader.get_current_game_state()

    path.write_bytes(second)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)

    state_after = reader.get_current_game_state()
    assert state_before['gems'] == 1234
    assert state_after['gems'] == 9876
    assert state_before['save_fingerprint'] != state_after['save_fingerprint']
    assert state_after['save_fingerprint'].endswith(hashlib.sha256(second).hexdigest())

def test_reader():
    st = get_current_game_state()
    print("Reincarnation:", st["reincarnation"])
    print("Excavations:", st["excavations"])
    print("Gems:", f"{st['gems']:.4e}")
    print("Has Spiky Rough Egg:", st["has_egg"])
    print("Hellfire active time:", st["hellfire_time"])

if __name__ == "__main__":
    test_reader()
