"""Single serial background reader for noncritical HUD observations.

Readers never run on the Tk thread. Snapshot publication is one atomic
reference assignment; UI callbacks only inspect the latest immutable-by-
convention result and never wait for an in-flight game observation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import threading
import time
from typing import Callable, Optional


@dataclass(frozen=True)
class ObservationSnapshot:
    state: Optional[dict] = None
    observed_at: Optional[float] = None
    reading: bool = False
    error: Optional[str] = None
    generation: int = 0

    @property
    def age_seconds(self) -> Optional[float]:
        if self.observed_at is None:
            return None
        return max(0.0, time.monotonic() - self.observed_at)


class ObservationCache:
    """Poll one reader serially and expose its last completed observation."""

    def __init__(self, reader: Callable[[], dict], poll_interval: float = 2.5,
                 stale_after: float = 7.5):
        self.reader = reader
        self.poll_interval = max(0.05, float(poll_interval))
        self.stale_after = max(0.05, float(stale_after))
        self._snapshot = ObservationSnapshot()
        self._stop = threading.Event()
        self._refresh = threading.Event()
        self._start_lock = threading.Lock()
        self._thread = None

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run, name='hud-observation-cache', daemon=True
            )
            self._thread.start()

    def snapshot(self) -> ObservationSnapshot:
        """Return the most recently published snapshot without acquiring a lock."""
        return self._snapshot

    def request_refresh(self) -> None:
        """Ask the serial reader to sample again after its current call finishes."""
        if not self._stop.is_set():
            self._refresh.set()

    def close(self) -> None:
        """Signal shutdown without joining or waiting for a slow reader."""
        self._stop.set()
        self._refresh.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._refresh.clear()
            if self._stop.is_set():
                return
            current = self._snapshot
            self._snapshot = replace(current, reading=True, error=None)
            try:
                state = self.reader()
                if not isinstance(state, dict):
                    raise ValueError('observation reader returned no state object')
            except Exception as exc:
                if self._stop.is_set():
                    return
                current = self._snapshot
                self._snapshot = replace(
                    current, reading=False,
                    error=f'{type(exc).__name__}: observation read failed'
                )
            else:
                if self._stop.is_set():
                    return
                self._snapshot = ObservationSnapshot(
                    state=state,
                    observed_at=time.monotonic(),
                    reading=False,
                    generation=current.generation + 1,
                )
            self._refresh.wait(self.poll_interval)
