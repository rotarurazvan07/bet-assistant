import threading
from collections.abc import Callable

# Default polling interval (1 minute)
DEFAULT_POLLING_INTERVAL = 60


def _daemon(fn, name: str) -> threading.Thread:
    t = threading.Thread(target=fn, name=name, daemon=True)
    t.start()
    return t


class TickerService:
    """
    A generic polling service that runs a task based on an interval and an optional predicate.

    Attributes:
        name: Name of the service.
        on_tick: Callback to execute when conditions are met.
        interval: Polling interval in seconds.
        predicate: Optional function returning bool; task only runs if True.
    """

    def __init__(
        self,
        name: str,
        on_tick: Callable,
        interval: int = DEFAULT_POLLING_INTERVAL,
        predicate: Callable[[], bool] | None = None,
    ) -> None:
        self.name = name
        self.on_tick = on_tick
        self.interval = interval
        self.predicate = predicate
        self.enabled = True

        self._wake_event = threading.Event()
        self._force_run = False
        self._thread = _daemon(self._run, name.lower())

    def update_config(self, interval: int | None = None, trigger_now: bool = False) -> None:
        """Update service rhythm."""
        if interval is not None:
            self.interval = interval

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

            wait = self.interval

            # Wait for either the timeout, or an interrupt (settings save / toggle)
            interrupted = self._wake_event.wait(wait)
            self._wake_event.clear()

            # If interrupted but NOT forced to run now, it just loops to recalculate wait
            if interrupted and not self._force_run:
                continue

            # Final check to ensure service hasn't been disabled during wait period
            if not self.enabled:
                continue

            # Check predicate (unless forced)
            if self.predicate and not self._force_run:
                if not self.predicate():
                    continue

            try:
                # If we reached here, it's time to run!
                self.on_tick()

                if self._force_run:
                    print(f"[{self.name.capitalize()}] Forced manual run complete.")
            except Exception as exc:
                print(f"[{self.name.capitalize()}] ERROR: {exc}")
            finally:
                self._force_run = False

    def is_alive(self) -> bool:
        return self._thread.is_alive()
