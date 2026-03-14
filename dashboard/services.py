"""
dashboard/service.py
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Callable


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


class PullerService:
    def __init__(self, pull_hour: int, on_pull: Callable):
        self.pull_hour = pull_hour
        self.on_pull   = on_pull
        self._thread   = _daemon(self._run, "puller")

    def _run(self):
        while True:
            print(f"[Puller] Next pull at {self.pull_hour:02d}:00")
            time.sleep(_seconds_until(self.pull_hour))
            try:
                self.on_pull()
                print(f"[Puller] Done at {datetime.now():%H:%M:%S}")
            except Exception as exc:
                print(f"[Puller] ERROR: {exc}")

    def is_alive(self) -> bool:
        return self._thread.is_alive()


class VerifierService:
    def __init__(self, on_tick: Callable, interval_seconds: int = 60):
        self.on_tick          = on_tick   # increments the store value
        self.interval_seconds = interval_seconds
        self._thread          = _daemon(self._run, "verifier")

    def _run(self):
        while True:
            time.sleep(self.interval_seconds)
            try:
                self.on_tick()
            except Exception as exc:
                print(f"[Verifier] ERROR: {exc}")

    def is_alive(self) -> bool:
        return self._thread.is_alive()


class GeneratorService:
    def __init__(self, generate_hour: int, on_tick: Callable):
        self.generate_hour = generate_hour
        self.on_tick       = on_tick
        self._thread       = _daemon(self._run, "generator")

    def _run(self):
        while True:
            print(f"[Generator] Next generation at {self.generate_hour:02d}:00")
            time.sleep(_seconds_until(self.generate_hour))
            try:
                self.on_tick()
            except Exception as exc:
                print(f"[Generator] ERROR: {exc}")

    def is_alive(self) -> bool:
        return self._thread.is_alive()


def init_services(
    pull_hour:     int,
    generate_hour: int,
    on_pull:       Callable,
    on_generate:   Callable,
    on_verify:     Callable,
) -> dict:
    return {
        "puller":    PullerService(pull_hour, on_pull),
        "generator": GeneratorService(generate_hour, on_generate),
        "verifier":  VerifierService(on_verify),
    }