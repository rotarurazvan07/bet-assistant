from datetime import datetime
from threading import Event, Thread
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from bet_framework.BetAssistant import BetAssistant, _parse_match_result_html
from bet_framework.core.Slip import CandidateLeg
from bet_framework.markets.enums import MarketKey, MarketType, MatchStatus, Outcome

# ── Mock Data ────────────────────────────────────────────────────────────────

SCORE_DIV = '<div class="text-base font-bold min-sm:text-xl text-center">2:1</div>'
STATUS_FINISHED = '<div id="status-container">FT</div>'
STATUS_LIVE = '<div id="status-container">LIVE 65\'</div>'
PARENT_DIV = '<div><div class="text-base font-bold min-sm:text-xl text-center">1:1</div><div>65\'</div></div>'


@pytest.fixture
def ba(tmp_path):
    assistant = BetAssistant(str(tmp_path / "validate.db"), tz=ZoneInfo("UTC"))
    yield assistant
    assistant.close()


# ── Tests for _parse_match_result_html ──────────────────────────────────────


def test_parse_normal_finished() -> None:
    """Verify FT result parsing with downloaded HTML."""
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.FT
    assert res.score == "2:1"


def test_parse_future_match_ignores_stats() -> None:
    """Verify that a future match (no status) ignores random X:Y patterns on the page."""
    html = '<html><body><span class="random-stat">4:3</span><div class="footer">Kickoff 20:00</div></body></html>'
    res = _parse_match_result_html(html, "http://test.future")
    assert res.status == MatchStatus.PENDING
    assert res.score == ""  # Should NOT pick up the 4:3


def test_parse_fuzzy_fallback() -> None:
    """Verify that score is found via fuzzy regex if class structure changes."""
    html = '<html><body><span class="random-new-class">3:2</span><div id="status-container">FT</div></body></html>'
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.FT
    assert res.score == "3:2"


def test_parse_live() -> None:
    """Verify LIVE result parsing."""
    html = f"<html><body>{SCORE_DIV}{STATUS_LIVE}</body></html>"
    res = _parse_match_result_html(html, "http://test.url")
    assert res.status == MatchStatus.LIVE
    assert res.score == "2:1"


# ── Tests for validate_slips ───────────────────────────────────────────────


def test_validate_slips_integration(ba) -> None:
    """Full integration test for the validation loop."""
    # 1. Setup DB with a pending slip
    legs = [
        CandidateLeg(
            match_name="A vs B",
            datetime=datetime.now(),
            market=MarketKey.HOME,
            market_type=MarketType.RESULT,
            odds=1.5,
            result_url="http://match1",
            consensus=80.0,
            sources=3,
        )
    ]
    ba.save_slip("test_profile", legs)

    # 2. Fake the shared fetcher while exercising the validation callback.
    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"

    progress = []
    with (
        patch("bet_framework.BetAssistant.fetch", return_value=html),
        patch("bet_framework.BetAssistant.is_blocked", return_value=False),
    ):
        report = ba.validate_slips(
            progress_callback=lambda checked, total, current: progress.append((checked, total, current)),
        )

        assert report.checked == 1
        assert len(report.settled) == 1
        assert report.settled[0].outcome == Outcome.WON
        assert progress[0] == (0, 1, "")
        assert progress[-1] == (1, 1, "A vs B")

        # Verify DB updated
        rows = ba.fetch_rows("SELECT status FROM legs")
        assert rows[0]["status"] == Outcome.WON


def test_validate_slips_skips_processed(ba) -> None:
    """Verify validate_slips only touches Pending/Live legs."""
    legs = [
        CandidateLeg(
            match_name="A vs B",
            datetime=datetime.now(),
            market=MarketKey.HOME,
            market_type=MarketType.RESULT,
            odds=1.5,
            result_url="http://match1",
            consensus=80.0,
            sources=3,
        )
    ]
    # We have to manually insert to force status 'Won' for testing purposes or use update_leg
    ba.save_slip("test", legs)
    rows = ba.fetch_rows("SELECT leg_id FROM legs")
    ba.update_leg(rows[0]["leg_id"], Outcome.WON)

    report = ba.validate_slips()
    assert report.checked == 0
    assert report.cancelled is False


def test_validate_slips_checks_unique_urls_only_for_active_slips(ba) -> None:
    """Check each active match URL once and skip pending legs in already-lost slips."""
    active_leg = CandidateLeg(
        match_name="A vs B",
        datetime=datetime.now(),
        market=MarketKey.HOME,
        market_type=MarketType.RESULT,
        odds=1.5,
        result_url="http://active-match",
        consensus=80.0,
        sources=3,
    )
    ba.save_slip("active-one", [active_leg])
    ba.save_slip("active-two", [active_leg])
    settled_pending_leg = CandidateLeg(
        match_name="C vs D",
        datetime=datetime.now(),
        market=MarketKey.HOME,
        market_type=MarketType.RESULT,
        odds=1.5,
        result_url="http://active-match",
        consensus=80.0,
        sources=3,
    )
    settled_lost_leg = CandidateLeg(
        match_name="E vs F",
        datetime=datetime.now(),
        market=MarketKey.HOME,
        market_type=MarketType.RESULT,
        odds=1.5,
        result_url="http://finished-match",
        consensus=80.0,
        sources=3,
    )
    ba.save_slip("already-lost", [settled_pending_leg, settled_lost_leg])
    ba.update_leg(
        ba.fetch_rows("SELECT leg_id FROM legs WHERE match_name = 'E vs F'")[0]["leg_id"],
        Outcome.LOST,
    )

    html = f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
    progress = []
    with (
        patch("bet_framework.BetAssistant.fetch", return_value=html) as mock_fetch,
        patch("bet_framework.BetAssistant.is_blocked", return_value=False),
    ):
        report = ba.validate_slips(
            progress_callback=lambda checked, total, current: progress.append((checked, total, current)),
        )

    assert report.checked == 1
    assert len(report.settled) == 2
    mock_fetch.assert_called_once_with("http://active-match", stealthy_headers=False)
    assert progress[-1] == (1, 1, "A vs B")

    rows = ba.fetch_rows("SELECT match_name, status FROM legs ORDER BY match_name")
    statuses = {row["match_name"]: row["status"] for row in rows}
    assert statuses["A vs B"] == Outcome.WON
    assert statuses["C vs D"] == Outcome.PENDING
    assert statuses["E vs F"] == Outcome.LOST


def test_validate_slips_reports_progress_and_honors_cancel(ba) -> None:
    legs = [
        CandidateLeg(
            match_name="A vs B",
            datetime=datetime.now(),
            market=MarketKey.HOME,
            market_type=MarketType.RESULT,
            odds=1.5,
            result_url="http://match1",
            consensus=80.0,
            sources=3,
        )
    ]
    ba.save_slip("test", legs)
    progress = []
    cancel_event = Event()
    cancel_event.set()

    with patch("bet_framework.BetAssistant.fetch") as mock_fetch:
        report = ba.validate_slips(
            progress_callback=lambda checked, total, current: progress.append((checked, total, current)),
            cancel_event=cancel_event,
        )
        mock_fetch.assert_not_called()

    assert report.cancelled is True
    assert progress[0] == (0, 1, "")
    assert ba.fetch_rows("SELECT status FROM legs")[0]["status"] == Outcome.PENDING


def test_validate_slips_returns_promptly_when_cancelled_during_fetch(ba) -> None:
    leg = CandidateLeg(
        match_name="A vs B",
        datetime=datetime.now(),
        market=MarketKey.HOME,
        market_type=MarketType.RESULT,
        odds=1.5,
        result_url="http://match1",
        consensus=80.0,
        sources=3,
    )
    ba.save_slip("test", [leg])
    fetch_started = Event()
    release_fetch = Event()
    fetch_finished = Event()
    cancel_event = Event()
    reports = []

    def slow_fetch(*args, **kwargs) -> str:
        fetch_started.set()
        try:
            release_fetch.wait(timeout=3)
            return f"<html><body>{SCORE_DIV}{STATUS_FINISHED}</body></html>"
        finally:
            fetch_finished.set()

    with (
        patch("bet_framework.BetAssistant.fetch", side_effect=slow_fetch),
        patch("bet_framework.BetAssistant.is_blocked", return_value=False),
    ):
        worker = Thread(
            target=lambda: reports.append(ba.validate_slips(cancel_event=cancel_event)),
        )
        worker.start()
        assert fetch_started.wait(timeout=2)
        cancel_event.set()
        worker.join(timeout=1)
        release_fetch.set()
        worker.join(timeout=2)
        assert fetch_finished.wait(timeout=2)

    assert not worker.is_alive()
    assert reports[0].cancelled is True
    assert reports[0].settled == []
