import threading
import time
from unittest.mock import MagicMock, patch

from src.observation_cache import ObservationCache, ObservationSnapshot
from src.monitor_window import ModernDragonTrackerApp


class _Root:
    def __init__(self):
        self.callbacks = []

    def winfo_exists(self):
        return True

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))


def _mana_app(cache):
    app = object.__new__(ModernDragonTrackerApp)
    app.root = _Root()
    app.observation_cache = cache
    app._closing = False
    app.c_muted = '#muted'
    app.c_cyan = '#cyan'
    app.mem_badge = MagicMock()
    app.mana_label = MagicMock()
    app.mana_bar_prog = MagicMock()
    app.mem_source_lbl = MagicMock()
    return app


def test_slow_observation_does_not_block_mana_hud_callback():
    entered = threading.Event()
    release = threading.Event()

    def slow_reader():
        entered.set()
        release.wait(2)
        return {'mana_current': 950, 'mana_max': 1000, 'mana_regeneration': 2,
                'telemetry': {'memory_provider_health': 'HEALTHY'},
                'provenance': {'mana_current': {'source': 'PROCESS_MEMORY'}}}

    cache = ObservationCache(slow_reader, poll_interval=0.01)
    cache.start()
    try:
        assert entered.wait(1)
        app = _mana_app(cache)
        with patch('src.monitor_window.get_live_game_state', side_effect=AssertionError('UI callback called the provider')):
            started = time.perf_counter()
            ModernDragonTrackerApp.update_mana_bar(app)
            elapsed = time.perf_counter() - started
        assert elapsed < 0.05
        assert app.mem_badge.configure.call_args.kwargs['text'] == '[WAIT]'
        assert app.mana_label.configure.call_args.kwargs['text'] == 'Mana: Unknown / Unknown | Regen: Unknown/s'
        assert app.root.callbacks and app.root.callbacks[-1][0] == 250
    finally:
        cache.close()
        release.set()


def test_stale_cached_mana_is_labeled_and_not_claimed_live():
    state = {'mana_current': 900, 'mana_max': 1000, 'mana_regeneration': 2,
             'telemetry': {'memory_provider_health': 'HEALTHY'},
             'provenance': {'mana_current': {'source': 'PROCESS_MEMORY'}}}
    cache = ObservationCache(lambda: state)
    cache._snapshot = ObservationSnapshot(state=state, observed_at=time.monotonic() - 30, reading=False)
    app = _mana_app(cache)

    ModernDragonTrackerApp.update_mana_bar(app)

    assert app.mem_badge.configure.call_args.kwargs['text'] == '[STALE]'
    assert 'stale' in app.mem_source_lbl.configure.call_args.kwargs['text'].lower()
    assert app.mana_label.configure.call_args.kwargs['fg'] == app.c_muted


def test_cache_close_signals_without_waiting_for_slow_reader():
    entered = threading.Event()
    release = threading.Event()

    def slow_reader():
        entered.set()
        release.wait(2)
        return {'reincarnation': 1}

    cache = ObservationCache(slow_reader)
    cache.start()
    try:
        assert entered.wait(1)
        started = time.perf_counter()
        cache.close()
        assert time.perf_counter() - started < 0.05
    finally:
        release.set()


def test_app_close_signals_cache_before_destroy_without_waiting(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    def slow_reader():
        entered.set()
        release.wait(2)
        return {'reincarnation': 1}

    cache = ObservationCache(slow_reader)
    cache.start()
    try:
        assert entered.wait(1)
        app = object.__new__(ModernDragonTrackerApp)
        app._closing = False
        app.observation_cache = cache
        app.root = MagicMock()
        with patch('src.monitor_window.os._exit') as exit_process:
            started = time.perf_counter()
            ModernDragonTrackerApp.on_close(app)
            assert time.perf_counter() - started < 0.05
        assert app._closing is True
        app.root.destroy.assert_called_once_with()
        exit_process.assert_called_once_with(0)
    finally:
        cache.close()
        release.set()


def test_mana_callback_does_not_schedule_again_after_close():
    app = _mana_app(ObservationCache(lambda: None))
    app._closing = True
    ModernDragonTrackerApp.update_mana_bar(app)
    assert not app.root.callbacks


def test_pause_callback_does_not_wait_for_observation_reader(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    def slow_reader():
        entered.set()
        release.wait(2)
        return {'reincarnation': 1}

    cache = ObservationCache(slow_reader)
    cache.start()
    try:
        assert entered.wait(1)
        app = MagicMock()
        app.observation_cache = cache
        cache.snapshot = MagicMock(side_effect=AssertionError('pause callback read cache'))
        app.c_amber = '#amber'
        stop_path = tmp_path / 'STOP'
        with patch('src.monitor_window.load_config', return_value={'paused': False}), \
             patch('src.monitor_window.save_config'), \
             patch('src.monitor_window.STOP_FILE', str(stop_path)):
            started = time.perf_counter()
            ModernDragonTrackerApp.action_toggle_pause(app)
            elapsed = time.perf_counter() - started
        assert elapsed < 0.05
        assert stop_path.exists()
        cache.snapshot.assert_not_called()
    finally:
        cache.close()
        release.set()


def test_cache_never_overlaps_reader_calls():
    guard = threading.Lock()
    active = 0
    peak = 0
    calls = 0
    completed = threading.Event()

    def reader():
        nonlocal active, peak, calls
        with guard:
            active += 1
            peak = max(peak, active)
            calls += 1
        time.sleep(0.02)
        with guard:
            active -= 1
            if calls >= 3:
                completed.set()
        return {'reincarnation': calls}

    cache = ObservationCache(reader, poll_interval=0.005)
    cache.start()
    try:
        assert completed.wait(1)
        assert peak == 1
    finally:
        cache.close()


def test_update_state_uses_cached_snapshot_not_provider_on_tk_thread():
    app = object.__new__(ModernDragonTrackerApp)
    app._closing = False
    app.observation_cache = ObservationCache(lambda: None)
    app.observation_cache._snapshot = ObservationSnapshot()

    with patch('src.monitor_window.get_live_game_state', side_effect=AssertionError('UI callback called the provider')):
        assert ModernDragonTrackerApp.update_state(app) is None
