from types import SimpleNamespace

import pytest

from tools import probe_live_memory as probe


def test_missing_game_probe_never_launches_it(monkeypatch):
    monkeypatch.setattr(probe, 'RealmGrinderWindow', lambda: SimpleNamespace(find_window=lambda: False))
    monkeypatch.setattr('subprocess.Popen', lambda *_a, **_k: pytest.fail('Read-only probe launched a process'))
    with pytest.raises(RuntimeError, match='already running'):
        probe.ensure_game_running()


def test_minimized_probe_preserves_window_and_closes_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(probe, 'RealmGrinderWindow', lambda: SimpleNamespace(
        find_window=lambda: True, pid=123, hwnd=456, is_minimized=lambda: True))
    monkeypatch.setattr('win32gui.ShowWindow', lambda *_: pytest.fail('Read-only probe changed window state'))
    monkeypatch.setattr(probe, 'get_current_game_state', lambda: {'gems': 1., 'coins': 1.})
    closed=[]
    class Provider:
        def __init__(self, *_a, **_k):
            self.reader=SimpleNamespace(identity=None, query_regions=lambda: [SimpleNamespace(readable=True,size=400*1024*1024)])
        def _connect(self): pass
        def discover_fields(self, *_a, **_k): return {}
        def sample(self, *_): return {}, {'memory_provider_health': 'CONNECTED_UNMAPPED'}
        def close(self): closed.append(True)
    monkeypatch.setattr(probe, 'MemoryProvider', Provider)
    result=probe.probe_memory()
    assert result['pid']==123 and closed==[True]
