"""Stage 5: validate_slips tests (issue #68).

Pins: pure delegation to BetAssistant.validate_slips(), summary log line,
live/settled item lines, Won/Lost icon branches, error propagation.
FT/LIVE/PENDING outcome handling is covered at the framework level (root
suite); the pipeline integration file covers FT/LIVE/PENDING flow end-to-end
with mocked result pages.
"""

from unittest.mock import MagicMock

import pytest

import bet_crawler.crawl_core.validate_slips as vs_mod
from bet_crawler.crawl_core.validate_slips import validate_slips

from bet_framework.core.Slip import LegOutcomeInfo, ValidationReport
from bet_framework.core.type_defs import MarketLabel


def make_leg(outcome="Won", name="A vs B", score="2:1", minute=""):
    return LegOutcomeInfo(
        leg_id=1,
        match_name=name,
        market=MarketLabel.HOME,
        score=score,
        minute=minute,
        outcome=outcome,
    )


def make_report(settled=None, live=None, errors=0, checked=5):
    return ValidationReport(
        checked=checked,
        settled=settled or [],
        live=live or [],
        errors=errors,
    )


def run_stage(monkeypatch, report):
    inst = MagicMock()
    inst.validate_slips.return_value = report
    fake_cls = MagicMock(return_value=inst)
    monkeypatch.setattr(vs_mod, "BetAssistant", fake_cls)
    validate_slips("slips.db")
    return inst, fake_cls


class TestValidateSlipsP0:
    def test_delegates_to_bet_assistant_and_closes(self, monkeypatch):
        inst, fake_cls = run_stage(monkeypatch, make_report())
        fake_cls.assert_called_once_with("slips.db")
        inst.validate_slips.assert_called_once_with()
        inst.close.assert_called_once()

    def test_summary_log_reports_counts(self, monkeypatch, caplog):
        report = make_report(
            settled=[make_leg()],
            live=[make_leg(outcome="Live")],
            errors=2,
            checked=7,
        )
        with caplog.at_level("INFO", logger="bet_crawler.crawl_core.validate_slips"):
            run_stage(monkeypatch, report)
        summary = [r.getMessage() for r in caplog.records if "Checked" in r.getMessage()]
        assert summary
        assert "Checked 7" in summary[0]
        assert "Settled 1" in summary[0]
        assert "Live 1" in summary[0]
        assert "Errors 2" in summary[0]

    def test_live_items_logged_with_score_and_minute(self, monkeypatch, caplog):
        leg = make_leg(
            outcome="Live",
            name="Live FC vs Hot FC",
            score="1:0",
            minute="63m",
        )
        with caplog.at_level("INFO", logger="bet_crawler.crawl_core.validate_slips"):
            run_stage(monkeypatch, make_report(live=[leg], checked=1))
        live_lines = [r.getMessage() for r in caplog.records if "63m" in r.getMessage()]
        assert live_lines
        assert "Live FC vs Hot FC" in live_lines[0]
        assert "1:0" in live_lines[0]

    def test_won_and_lost_settled_lines_logged(self, monkeypatch, caplog):
        won = make_leg(outcome="Won", name="Win FC")
        lost = make_leg(outcome="Lost", name="Lose FC")
        with caplog.at_level("INFO", logger="bet_crawler.crawl_core.validate_slips"):
            run_stage(monkeypatch, make_report(settled=[won, lost], checked=2))
        msgs = [r.getMessage() for r in caplog.records]
        assert any("Win FC" in m and "Won" in m for m in msgs)
        assert any("Lose FC" in m and "Lost" in m for m in msgs)


class TestValidateSlipsP1:
    def test_empty_report_logs_zero_counts(self, monkeypatch, caplog):
        with caplog.at_level("INFO", logger="bet_crawler.crawl_core.validate_slips"):
            run_stage(monkeypatch, make_report(settled=[], live=[], errors=0, checked=0))
        summary = [r.getMessage() for r in caplog.records if "Checked" in r.getMessage()]
        assert summary
        assert "Checked 0" in summary[0]
        assert "Settled 0" in summary[0]
        assert "Live 0" in summary[0]

    def test_validate_error_propagates_to_caller(self, monkeypatch):
        """No silent swallow: a failing BetAssistant must raise to the CLI caller."""
        inst = MagicMock()
        inst.validate_slips.side_effect = RuntimeError("boom")
        fake_cls = MagicMock(return_value=inst)
        monkeypatch.setattr(vs_mod, "BetAssistant", fake_cls)
        with pytest.raises(RuntimeError, match="boom"):
            validate_slips("slips.db")
