"""Bounded worker-cycle backoff with inexpensive file-change wakeups.

This module deliberately does not inspect game state or capture screenshots. It
only checks file metadata while the action owner is waiting for its next cycle.
"""

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional


_MAX_WAIT_SLICE_SEC = 0.25
_DEFAULT_CYCLE_SEC = 3.0
_HARD_FLOOR_SEC = 0.25
_HARD_CEILING_SEC = 300.0


class IdleScheduler:
    """Schedule one existing worker with bounded backoff and responsive wakes."""

    def __init__(
        self,
        config_path: os.PathLike,
        stop_path: os.PathLike,
        save_path: os.PathLike,
        *,
        clock: Callable[[], float] = time.monotonic,
        wait_fn: Callable[[float], Any] = time.sleep,
        check_interval_sec: float = _MAX_WAIT_SLICE_SEC,
    ) -> None:
        self.config_path = Path(config_path)
        self.stop_path = Path(stop_path)
        self.save_path = Path(save_path)
        self.clock = clock
        self.wait_fn = wait_fn
        self.check_interval_sec = min(_MAX_WAIT_SLICE_SEC, max(0.01, float(check_interval_sec)))
        self._previous_signature: Optional[tuple] = None
        self._repeat_count = 0

    @staticmethod
    def _safe_number(value: Any, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return fallback
        if number != number or number in (float("inf"), float("-inf")):
            return fallback
        return number

    def delay_after(self, outcome: Mapping[str, Any], config: Mapping[str, Any]) -> float:
        """Return the next delay, backing off only for repeated blocked/errors."""
        hard_floor = _HARD_FLOOR_SEC
        hard_ceiling = _HARD_CEILING_SEC
        floor = min(hard_ceiling, max(hard_floor, self._safe_number(config.get("scheduler_floor_sec", hard_floor), hard_floor)))
        ceiling = min(hard_ceiling, max(floor, self._safe_number(config.get("scheduler_ceiling_sec", 60.0), 60.0)))
        base = self._safe_number(config.get("cycle_delay_sec", _DEFAULT_CYCLE_SEC), _DEFAULT_CYCLE_SEC)
        base = min(ceiling, max(floor, base))

        kind = str(outcome.get("kind", "")).lower()
        status = str(outcome.get("status", "")).upper()
        backoff = kind in {"error", "blocked", "waiting"} or status in {
            "BLOCKED", "UNCERTAIN", "WAITING", "OBSERVING"
        }
        signature = (kind, status, outcome.get("action"), outcome.get("message"))
        if backoff and signature == self._previous_signature:
            self._repeat_count += 1
        elif backoff:
            self._repeat_count = 0
        else:
            self._repeat_count = 0
        self._previous_signature = signature if backoff else None
        return min(ceiling, base * (2 ** min(self._repeat_count, 20)))

    @staticmethod
    def _stat(path: Path) -> tuple:
        try:
            info = path.stat()
        except OSError:
            return (False,)
        return (True, getattr(info, "st_dev", None), getattr(info, "st_ino", None), info.st_size, info.st_mtime_ns)

    def snapshot(self) -> tuple:
        """Capture cheap metadata for config, STOP and save change detection."""
        return (
            self._stat(self.config_path),
            self._stat(self.stop_path),
            self._stat(self.save_path),
        )

    def wait_for_change(
        self,
        timeout_sec: float,
        watched: Optional[tuple] = None,
        *,
        stop_event: Optional[threading.Event] = None,
    ) -> Optional[str]:
        """Wait in <=250ms slices; return the changed input or None on timeout."""
        baseline = self.snapshot() if watched is None else watched
        timeout = max(0.0, self._safe_number(timeout_sec, 0.0))
        deadline = self.clock() + timeout
        while True:
            if stop_event is not None and stop_event.is_set():
                return "stop_event"
            current = self.snapshot()
            if current[0] != baseline[0]:
                return "config"
            if current[1] != baseline[1]:
                return "stop"
            if current[2] != baseline[2]:
                return "save"
            remaining = deadline - self.clock()
            if remaining <= 0:
                return None
            self.wait_fn(min(self.check_interval_sec, remaining))
