import threading
from collections.abc import Callable
from datetime import datetime, timedelta


def _seconds_until(hour: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _daemon(fn, name: str) -> threading.Thread:
    t = threading.Thread(target=fn, name=name, daemon=True)
    t.start()
    return t


class TickerService:
    def __init__(self, name: str, on_tick: Callable, interval: int = None, hour: int = None) -> None:
        self.name = name
        self.on_tick = on_tick
        self.interval = interval
        self.hour = hour
        self.enabled = True

        self._wake_event = threading.Event()
        self._force_run = False
        self._thread = _daemon(self._run, name.lower())

    def update_config(self, hour: int, trigger_now: bool = False) -> None:
        self.hour = hour
        if trigger_now:
            self._force_run = True
        self._wake_event.set()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._wake_event.set()

    def _run(self) -> None:
        while True:
            if not self.enabled:
                self._wake_event.wait()
                self._wake_event.clear()
                continue

            if self.hour is not None:
                wait = _seconds_until(self.hour)
                if not self._force_run:
                    print(f"[{self.name.capitalize()}] Sleeping for {wait:.1f}s until {self.hour:02d}:00")
            else:
                wait = self.interval or 60

            # Wait for either the timeout, or an interrupt (settings save / toggle)
            interrupted = self._wake_event.wait(wait)
            self._wake_event.clear()

            if not self.enabled:
                continue

            # If interrupted but NOT forced to run now, it just loops to recalculate wait time
            if interrupted and not self._force_run:
                continue

            try:
                self.on_tick()
                if self.hour is not None and not self._force_run:
                    print(f"[{self.name.capitalize()}] Done at {datetime.now():%H:%M:%S}")
                elif self._force_run:
                    print(f"[{self.name.capitalize()}] Forced manual run complete.")
            except Exception as exc:
                print(f"[{self.name.capitalize()}] ERROR: {exc}")
            finally:
                self._force_run = False

    def is_alive(self) -> bool:
        return self._thread.is_alive()
