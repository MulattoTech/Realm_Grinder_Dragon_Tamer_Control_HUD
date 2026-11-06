import threading

from src.idle_scheduler import IdleScheduler


def scheduler(tmp_path, clock, wait_fn):
    config = tmp_path / "bot_config.json"
    stop = tmp_path / "STOP"
    save = tmp_path / "realm-grinder.sol"
    config.write_text('{"paused": false}', encoding="utf-8")
    save.write_bytes(b"save-1")
    return IdleScheduler(
        config_path=config,
        stop_path=stop,
        save_path=save,
        clock=clock,
        wait_fn=wait_fn,
    ), config, stop, save


def test_unchanged_blocked_cycles_back_off_and_recover_on_progress(tmp_path):
    now = [0.0]
    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], lambda seconds: None)
    config = {"cycle_delay_sec": 2, "scheduler_floor_sec": 1, "scheduler_ceiling_sec": 12}
    blocked = {"status": "BLOCKED", "action": "WAITING", "message": "No new production"}

    assert idle.delay_after(blocked, config) == 2
    assert idle.delay_after(blocked, config) == 4
    assert idle.delay_after(blocked, config) == 8
    assert idle.delay_after(blocked, config) == 12
    assert idle.delay_after({"status": "VERIFIED", "action": "PURCHASED"}, config) == 2


def test_repeated_errors_are_bounded_by_safe_configured_ceiling(tmp_path):
    now = [0.0]
    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], lambda seconds: None)
    config = {"cycle_delay_sec": 3, "scheduler_floor_sec": 1, "scheduler_ceiling_sec": 10}
    error = {"kind": "error", "message": "temporary read failure"}

    delays = [idle.delay_after(error, config) for _ in range(8)]

    assert delays == [3, 6, 10, 10, 10, 10, 10, 10]


def test_repeated_observing_results_back_off(tmp_path):
    now = [0.0]
    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], lambda seconds: None)
    config = {"cycle_delay_sec": 2, "scheduler_ceiling_sec": 12}
    observing = {"status": "OBSERVING", "action": "WAITING", "message": "No safe action yet"}

    assert idle.delay_after(observing, config) == 2
    assert idle.delay_after(observing, config) == 4
    assert idle.delay_after(observing, config) == 8


def test_delay_settings_are_clamped_and_invalid_values_fall_back(tmp_path):
    now = [0.0]
    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], lambda seconds: None)

    assert idle.delay_after({"status": "VERIFIED"}, {"cycle_delay_sec": 0}) == 0.25
    assert idle.delay_after({"status": "VERIFIED"}, {"cycle_delay_sec": 900, "scheduler_ceiling_sec": 900}) == 300
    assert idle.delay_after({"status": "VERIFIED"}, {"cycle_delay_sec": "bad"}) == 3


def test_unchanged_long_wait_checks_cheaply_without_busy_loop(tmp_path):
    now = [0.0]
    waits = []

    def fake_wait(seconds):
        waits.append(seconds)
        now[0] += seconds

    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], fake_wait)
    watched = idle.snapshot()

    assert idle.wait_for_change(2.0, watched) is None
    assert now[0] == 2.0
    assert len(waits) == 8
    assert max(waits) <= 0.25


def test_config_save_and_stop_file_changes_interrupt_wait(tmp_path):
    for changed in ("config", "save", "stop"):
        case_dir = tmp_path / changed
        case_dir.mkdir()
        now = [0.0]
        writes = []
        idle, config, stop, save = scheduler(
            case_dir,
            lambda: now[0],
            lambda seconds: mutate_on_wait(seconds, changed, now, writes, config, stop, save),
        )
        watched = idle.snapshot()

        assert idle.wait_for_change(30, watched) == changed
        assert now[0] <= 0.25


def test_explicit_stop_event_interrupts_wait(tmp_path):
    now = [0.0]
    stop_event = threading.Event()

    def fake_wait(seconds):
        now[0] += seconds
        stop_event.set()

    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], fake_wait)

    assert idle.wait_for_change(30, idle.snapshot(), stop_event=stop_event) == "stop_event"
    assert now[0] <= 0.25


def test_file_stat_errors_do_not_disable_bounded_wait_or_escape(tmp_path):
    now = [0.0]
    idle, _, _, _ = scheduler(tmp_path, lambda: now[0], lambda seconds: now.__setitem__(0, now[0] + seconds))
    idle.config_path.unlink()
    watched = idle.snapshot()

    assert idle.wait_for_change(0.5, watched) is None
    assert now[0] == 0.5


def test_worker_persists_pause_once_then_resumes_through_existing_step(tmp_path, monkeypatch):
    import src.state_machine as worker

    paused = [False]
    event = threading.Event()
    writes = []
    steps = []
    wait_count = [0]

    class Lease:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Scheduler:
        def __init__(self, *args):
            pass

        def snapshot(self):
            return len(steps)

        def delay_after(self, outcome, config):
            return 1

        def wait_for_change(self, timeout, watched, *, stop_event=None):
            wait_count[0] += 1
            if wait_count[0] in (1, 2):
                paused[0] = True
            elif wait_count[0] == 3:
                paused[0] = False
            else:
                event.set()
            return None

    monkeypatch.setattr(worker, "WorkerLease", Lease)
    monkeypatch.setattr(worker, "IdleScheduler", Scheduler)
    monkeypatch.setattr(worker, "require_interactive_session", lambda: None)
    monkeypatch.setattr(worker, "load_config", lambda: {"paused": paused[0], "cycle_delay_sec": 1})
    monkeypatch.setattr(worker, "STOP_FILE", str(tmp_path / "STOP"))

    bot = worker.DragonBot.__new__(worker.DragonBot)
    bot.state = {"is_running": True, "next_expected_action": "Working", "retry_count": 0}
    bot.save_state = lambda: writes.append(dict(bot.state))

    def step():
        steps.append("dispatch")
        bot.state["is_running"] = True
        bot.state["next_expected_action"] = "Working"

    bot.step = step
    bot.run_loop(stop_event=event)

    pause_writes = [row for row in writes if not row["is_running"]]
    assert len(steps) == 2
    assert len(pause_writes) == 1
    assert "paused" in pause_writes[0]["next_expected_action"].lower()
    assert bot.state["is_running"] is True


def mutate_on_wait(seconds, changed, now, writes, config, stop, save):
    now[0] += seconds
    writes.append(seconds)
    if len(writes) == 1:
        if changed == "config":
            config.write_text('{"paused": true}', encoding="utf-8")
        elif changed == "save":
            save.write_bytes(b"save-2-changed")
        else:
            stop.write_text("paused", encoding="utf-8")
