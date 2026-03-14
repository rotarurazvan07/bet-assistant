"""
dashboard/service.py
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Any


def _seconds_until(hour: int) -> float:
    now    = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _daemon(fn, name: str) -> threading.Thread:
    t = threading.Thread(target=fn, name=name, daemon=True)
    t.start()
    return t


class TickerService:
    def __init__(self, name: str, on_tick: Callable, interval: int = None, hour: int = None):
        self.name     = name
        self.on_tick  = on_tick
        self.interval = interval
        self.hour     = hour
        self._thread  = _daemon(self._run, name.lower())

    def _run(self):
        while True:
            if self.hour is not None:
                print(f"[{self.name.capitalize()}] Next run at {self.hour:02d}:00")
                wait = _seconds_until(self.hour)
            else:
                wait = self.interval or 60

            if wait > 0:
                time.sleep(wait)

            try:
                self.on_tick()
                if self.hour is not None:
                    print(f"[{self.name.capitalize()}] Done at {datetime.now():%H:%M:%S}")
            except Exception as exc:
                print(f"[{self.name.capitalize()}] ERROR: {exc}")

    def is_alive(self) -> bool:
        return self._thread.is_alive()
