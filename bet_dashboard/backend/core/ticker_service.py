import threading
from collections.abc import Callable
from datetime import datetime

# Default polling interval for hour-based services (5 minutes)
HOUR_POLL_INTERVAL = 5 * 60


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
        # Track last run date to avoid multiple runs in same hour
        self._last_run_date: str | None = None
        self._thread = _daemon(self._run, name.lower())

    def update_config(self, hour: int, trigger_now: bool = False) -> None:
        self.hour = hour
        if trigger_now:
            self._force_run = True
        self._wake_event.set()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._wake_event.set()

    def _should_run_hour_based(self) -> bool:
        """Check if hour-based service should run now (polling approach)."""
        now = datetime.now()
        current_hour = now.hour
        today_key = now.strftime("%Y-%m-%d-%H")
        
        # Check if current hour matches target and we haven't run this hour yet
        if current_hour == self.hour and self._last_run_date != today_key:
            self._last_run_date = today_key
            return True
        return False

    def _run(self) -> None:
        while True:
            if not self.enabled:
                self._wake_event.wait()
                self._wake_event.clear()
                continue

            if self.hour is not None:
                # Polling approach: check every HOUR_POLL_INTERVAL
                wait = HOUR_POLL_INTERVAL
            else:
                wait = self.interval or 60

            # Wait for either the timeout, or an interrupt (settings save / toggle)
            interrupted = self._wake_event.wait(wait)
            self._wake_event.clear()

            # If interrupted but NOT forced to run now, it just loops
            if interrupted and not self._force_run:
                continue

            # Final check to ensure service hasn't been disabled during wait period
            if not self.enabled:
                continue

            # For hour-based services, check if it's time to run
            if self.hour is not None and not self._force_run:
                if not self._should_run_hour_based():
                    continue
                print(f"[{self.name.capitalize()}] Target hour {self.hour:02d}:00 reached, running...")

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
