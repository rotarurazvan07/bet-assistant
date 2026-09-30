"""Integration tests for core/ticker_service.py (issue #60, cycle 4) — REAL threads.

Unlike cycle 3's FakeTicker (wiring inspection), this file exercises REAL
daemon threads and a REAL tick loop with short intervals (0.05s). Synchronization
is event/condition-based — never sleep-polling:
- positive waits use TickCounter.wait_at_least() (Condition.notify_all, bounded deadline)
- negative observations only where a tick is PROVABLY impossible
  (predicate False / enabled False / interval far beyond window)

Note: TickerService has no stop() API — teardown parks every thread via
set_enabled(False); parked daemons block on _wake_event and consume zero CPU.
Issue #60's "toggle_service()" maps to set_enabled on TickerService itself
(AppLogic.toggle_service is covered by the e2e integration suite).
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress

import pytest

from core.ticker_service import DEFAULT_POLLING_INTERVAL, TickerService


# ── Thread-safe tick counter ─────────────────────────────────────────────────


class TickCounter:
    """Callable on_tick substitute: counts ticks, optionally raises on the Nth."""

    def __init__(self, raise_on: int | None = None) -> None:
        self._cv = threading.Condition()
        self.count = 0
        self.raise_on = raise_on

    def __call__(self) -> None:
        with self._cv:
            self.count += 1
            current = self.count
            self._cv.notify_all()
        if self.raise_on is not None and current == self.raise_on:
            raise RuntimeError("boom on tick %d" % current)

    def wait_at_least(self, target: int, timeout: float) -> bool:
        """Block (Condition.wait) until count >= target or deadline. Bounded."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while self.count < target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cv.wait(remaining)
            return True


@pytest.fixture()
def tickers():
    """Registry so teardown parks every real thread created in the test."""
    created: list[TickerService] = []
    yield created
    for svc in created:
        with suppress(Exception):
            svc.set_enabled(False)  # park: thread blocks on _wake_event forever


def make_ticker(tickers, on_tick, interval=0.05, predicate=None, name="t"):
    svc = TickerService(name, on_tick, interval=interval, predicate=predicate)
    tickers.append(svc)
    return svc


# ── Lifecycle ────────────────────────────────────────────────────────────────


class TestTickerLifecycle:
    def test_starts_daemon_thread_in_init_and_is_alive(self, tickers):
        """[P0] Thread starts on construction, is daemon (dies with process), alive."""
        counter = TickCounter()
        svc = make_ticker(tickers, counter)
        assert svc.is_alive() is True
        assert svc._thread.daemon is True
        assert svc._thread.name == "t"

    def test_constructor_wiring_and_defaults(self, tickers):
        """[P1] Constructor stores name/on_tick/interval/predicate; enabled=True."""
        counter = TickCounter()

        def pred() -> bool:
            return True

        svc = make_ticker(tickers, counter, interval=3, predicate=pred, name="Custom")
        assert svc.name == "Custom"
        assert svc.on_tick is counter
        assert svc.interval == 3
        assert svc.predicate is pred
        assert svc.enabled is True

    def test_default_interval_constant(self, tickers):
        """[P2] Default polling interval is 60s (module constant)."""
        assert DEFAULT_POLLING_INTERVAL == 60
        svc = TickerService("t", TickCounter())  # no interval arg → constructor default
        tickers.append(svc)
        assert svc.interval == 60


# ── Tick execution ───────────────────────────────────────────────────────────


class TestTickExecution:
    def test_on_tick_executes_repeatedly_at_interval(self, tickers):
        """[P0] With no predicate, on_tick fires repeatedly every interval."""
        counter = TickCounter()
        make_ticker(tickers, counter, interval=0.05)
        assert counter.wait_at_least(3, timeout=2.0), "expected >=3 ticks in 2s window"

    def test_on_tick_receives_no_arguments(self, tickers):
        """[P2] The loop calls on_tick() with no args (callback contract)."""
        counter = TickCounter()
        make_ticker(tickers, counter, interval=0.05)
        assert counter.wait_at_least(1, timeout=2.0)


# ── Predicate gating ─────────────────────────────────────────────────────────


class FlagPredicate:
    """Mutable predicate holder — flips without lambdas (test-file convention)."""

    def __init__(self, initial: bool = False) -> None:
        self.value = initial

    def __call__(self) -> bool:
        return self.value


class TestPredicateGating:
    def test_predicate_true_allows_ticks(self, tickers):
        """[P1] predicate=True behaves like no predicate."""
        counter = TickCounter()
        make_ticker(tickers, counter, interval=0.05, predicate=FlagPredicate(True))
        assert counter.wait_at_least(2, timeout=2.0)

    def test_predicate_false_blocks_then_true_resumes(self, tickers):
        """[P0] Callback skipped while predicate=False; resumes when flipped True.

        Provability: at 0.05s interval the loop attempts ~6 gate checks inside the
        0.3s blocked window, so zero ticks proves gating (not a dead thread); the
        subsequent flip proves the loop was alive and gated only by the predicate.
        """
        counter = TickCounter()
        flag = FlagPredicate(False)
        make_ticker(tickers, counter, interval=0.05, predicate=flag)
        time.sleep(0.3)  # bounded negative window: ~6 would-be attempts, none pass
        assert counter.count == 0, "tick fired while predicate was False"
        flag.value = True
        assert counter.wait_at_least(2, timeout=2.0), "ticks did not resume after predicate flip"

    def test_predicate_false_only_never_ticks(self, tickers):
        """[P1] Permanently-False predicate never ticks (observation window)."""
        counter = TickCounter()
        make_ticker(tickers, counter, interval=0.05, predicate=FlagPredicate(False))
        time.sleep(0.3)
        assert counter.count == 0


# ── enable/disable (toggle semantics) ──────────────────────────────────────


class TestSetEnabled:
    def test_set_enabled_false_parks_thread_true_resumes(self, tickers):
        """[P0] set_enabled(False) stops ticking (thread parks on _wake_event);
        set_enabled(True) resumes ticking."""
        counter = TickCounter()
        make_ticker(tickers, counter, interval=0.05)
        assert counter.wait_at_least(1, timeout=2.0), "ticker never started ticking"
        svc = tickers[-1]
        svc.set_enabled(False)
        frozen = counter.count
        time.sleep(0.3)  # bounded window: ~6 would-be attempts while parked
        assert counter.count == frozen, "tick fired while service disabled"
        svc.set_enabled(True)
        assert counter.wait_at_least(frozen + 2, timeout=2.0), "ticking did not resume"

    def test_enabled_attribute_flips_via_set_enabled(self, tickers):
        """[P2] set_enabled stores the flag (external-call contract from issue #60)."""
        counter = TickCounter()
        svc = make_ticker(tickers, counter, interval=0.05)
        assert svc.enabled is True
        svc.set_enabled(False)
        assert svc.enabled is False
        svc.set_enabled(True)
        assert svc.enabled is True

    def test_disable_during_wait_hits_final_enabled_check(self, tickers):
        """[P1] Covers the wait-timeout enabled re-check (lines 74-75).

        Sequence: first tick proves the loop; the thread then sits inside
        _wake_event.wait(0.6) with enabled still True. Setting enabled=False
        directly (NO wake) means the wait runs to timeout with interrupted=False;
        line 70 is skipped and line 74 must catch the disable, park the thread
        and suppress the second tick. Re-enabling via set_enabled (wake) proves
        the thread survived. Margin analysis: flip lands ~microseconds after tick
        #1; the 0.6s timeout wake needs a 0.6s main-thread deschedule to miss —
        impossible in this single-process suite.
        """
        counter = TickCounter()
        svc = make_ticker(tickers, counter, interval=0.6)
        assert counter.wait_at_least(1, timeout=2.0), "first tick never fired"
        time.sleep(0.15)  # settle: thread re-entered wait(0.6) microseconds after tick #1
        svc.enabled = False  # direct attribute: no wake — targets the timeout path
        time.sleep(0.8)  # > one full 0.6s wait cycle: second tick would have landed
        assert counter.count == 1, "second tick fired despite mid-wait disable"
        svc.set_enabled(True)  # wake the parked thread
        assert counter.wait_at_least(2, timeout=2.0), "thread died after mid-wait disable"


# ── update_config ─────────────────────────────────────────────────────────────


class TestUpdateConfig:
    def test_interval_change_applies_immediately_via_wake(self, tickers):
        """[P1] update_config(interval) interrupts the current wait and adopts
        the new rhythm. Old rhythm (1.5s) provably cannot tick inside 0.2s; after
        switching to 0.05s, ticks must flow."""
        counter = TickCounter()
        svc = make_ticker(tickers, counter, interval=1.5)
        time.sleep(0.2)  # provable no-tick: 0.2s << 1.5s first-tick bound
        assert counter.count == 0
        svc.update_config(interval=0.05)
        assert counter.wait_at_least(2, timeout=2.0), "new interval never took effect"
        assert svc.interval == 0.05

    def test_trigger_now_forces_immediate_tick_bypassing_predicate(self, tickers):
        """[P0] update_config(trigger_now=True) forces an immediate run even while
        a False predicate would block it (manual-run semantics)."""
        counter = TickCounter()
        flag = FlagPredicate(False)
        svc = make_ticker(tickers, counter, interval=30, predicate=flag)
        svc.update_config(trigger_now=True)
        assert counter.wait_at_least(1, timeout=2.0), "forced run did not fire"
        assert flag.value is False  # predicate was never consulted for the forced run

    def test_update_config_without_args_wakes_but_does_not_tick(self, tickers):
        """[P2] Pure wake: interrupt path only (continue), no forced tick."""
        counter = TickCounter()
        svc = make_ticker(tickers, counter, interval=30)
        time.sleep(0.2)
        svc.update_config()  # neither interval nor trigger_now
        time.sleep(0.3)  # still inside the 30s rhythm on both sides of the wake
        assert counter.count == 0
        assert svc.interval == 30


# ── Error resilience ──────────────────────────────────────────────────────────


class TestTickErrorHandling:
    def test_on_tick_exception_is_caught_and_thread_survives(self, tickers):
        """[P1] A raising callback is caught; the very next tick still runs."""
        counter = TickCounter(raise_on=1)
        make_ticker(tickers, counter, interval=0.05)
        assert counter.wait_at_least(2, timeout=2.0), "thread died after first-tick exception"
