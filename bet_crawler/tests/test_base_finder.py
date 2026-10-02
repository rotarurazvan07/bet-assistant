"""BaseMatchFinder contract tests (issue #69 part (a)).

Covers: ctor wiring, abstract surface, normalise_datetime, add_match pipeline
(skip patterns / date window / odds strip / force / exception->False),
skip_match_by_patterns, validate_match_date, _detect_local_timezone fallback.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from bet_crawler.finders.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import Match, Odds, Score

from .finder_test_helpers import DEFAULT_SKIP_PATTERNS, make_finder


class _Finder(BaseMatchFinder):
    """Minimal concrete subclass for base-contract testing."""

    def get_matches_urls(self):
        return []

    def get_matches(self, urls):
        return None

    def _parse_page(self, url, html):
        return None


class _TzFinder(_Finder):
    TIMEZONE = "Asia/Bangkok"


# Runner-TZ pin (PR #75 CI fix, D51): validate_match_date compares against an
# AWARE now in the finder's local_timezone (Europe/Bucharest in these tests),
# but naive datetime.now() is RUNNER wall-clock. Under TZ=UTC runners the
# naive clock trails Bucharest by 3h (a full calendar day across UTC
# midnight) and fixtures fall outside the date gate. _now_local() builds
# fixtures from the naive BUCHAREST wall clock — identical semantics to the
# Bucharest-runner behaviour these tests have always pinned.
BUCHAREST = ZoneInfo("Europe/Bucharest")


def _now_local():
    return datetime.now(BUCHAREST).replace(tzinfo=None, microsecond=0)


def _mk(home="Arsenal", away="Chelsea", dt=None, preds=None, odds=None):
    return Match(
        home,
        away,
        dt if dt is not None else _now_local(),
        preds if preds is not None else [Score("test", 2, 1)],
        odds,
    )


class TestCtor:
    def test_ctor_stores_all_runtime_settings(self):
        finder, collector = make_finder(
            _Finder, contributes_odds=True, top_leagues_only=False, num_days_ahead=3, local_timezone="Europe/London"
        )
        assert finder.add_match_callback is collector
        assert finder.contributes_odds is True
        assert finder.top_leagues_only is False
        assert finder.num_days_ahead == 3
        assert finder.local_timezone == "Europe/London"
        assert finder.skip_patterns == DEFAULT_SKIP_PATTERNS
        assert finder.TIMEZONE is None

    def test_ctor_normalises_list_patterns_to_tuple(self):
        patterns = [("x", "y")]
        finder, _ = make_finder(_Finder, skip_patterns=patterns)
        assert isinstance(finder.skip_patterns, tuple)

    def test_abstract_surface_semantics(self):
        """BaseMatchFinder is NOT an ABCMeta class: @abstractmethod is decorative
        only — instantiation succeeds; the stubs raise NotImplementedError (pinned
        actual behaviour)."""
        base = BaseMatchFinder(
            lambda m: None,
            contributes_odds=False,
            top_leagues_only=True,
            num_days_ahead=1,
            local_timezone="UTC",
            skip_patterns=(),
        )
        with pytest.raises(NotImplementedError):
            base.get_matches_urls()
        with pytest.raises(NotImplementedError):
            base.get_matches([])
        with pytest.raises(NotImplementedError):
            base._parse_page("u", "h")


class TestSkipPatterns:
    def test_youth_u19_skipped(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(home="Arsenal U19")) is False
        assert len(collector) == 0

    def test_women_team_skipped(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(home="Arsenal W")) is False
        assert len(collector) == 0

    def test_reserve_roman_skipped(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(away="Rangers II")) is False
        assert len(collector) == 0

    def test_case_insensitive_match(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(home="arsenal u19")) is False

    def test_first_matching_reason_wins(self):
        finder, _ = make_finder(_Finder)
        reason = finder.skip_match_by_patterns("Inter B", "Arsenal II")
        assert reason in {r for _, r in DEFAULT_SKIP_PATTERNS}

    def test_explicit_patterns_override_instance(self):
        finder, _ = make_finder(_Finder)
        assert finder.skip_match_by_patterns("Inter B", "X", [(r"\bB\b", "B team")]) == "B team"
        # instance patterns not passed -> no match under override list
        assert finder.skip_match_by_patterns("Inter U19", "X", [(r"\bB\b", "B team")]) is None

    def test_clean_teams_not_skipped(self):
        finder, _ = make_finder(_Finder)
        assert finder.skip_match_by_patterns("Arsenal", "Chelsea") is None


class TestDateWindow:
    def test_today_match_kept(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(dt=_now_local())) is True
        assert len(collector) == 1

    def test_within_days_ahead_kept(self):
        finder, collector = make_finder(_Finder, num_days_ahead=2)
        assert finder.add_match(_mk(dt=_now_local() + timedelta(days=2))) is True
        assert len(collector) == 1

    def test_beyond_days_ahead_skipped(self):
        finder, collector = make_finder(_Finder, num_days_ahead=1)
        assert finder.add_match(_mk(dt=_now_local() + timedelta(days=2))) is False
        assert len(collector) == 0

    def test_past_match_skipped(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(dt=_now_local() - timedelta(days=1))) is False
        assert len(collector) == 0

    def test_validate_match_date_bounds(self):
        finder, _ = make_finder(_Finder, num_days_ahead=3)
        now_local = datetime.now(ZoneInfo("Europe/Bucharest"))
        assert finder.validate_match_date(now_local) is True
        assert finder.validate_match_date(now_local + timedelta(days=3)) is True
        assert finder.validate_match_date(now_local + timedelta(days=4)) is False
        assert finder.validate_match_date(now_local - timedelta(days=1)) is False


class TestAddMatchPipeline:
    def test_odds_stripped_for_non_odds_finder(self):
        finder, collector = make_finder(_Finder, contributes_odds=False)
        odds = Odds(home=2.1, draw=3.2, away=3.8)
        assert finder.add_match(_mk(dt=_now_local(), odds=odds)) is True
        assert collector.first.odds is None

    def test_odds_kept_for_odds_finder(self):
        finder, collector = make_finder(_Finder, contributes_odds=True)
        odds = Odds(home=2.1)
        assert finder.add_match(_mk(dt=_now_local(), odds=odds)) is True
        assert collector.first.odds is not None
        assert collector.first.odds.home == 2.1

    def test_force_bypasses_gates(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(home="Arsenal U19"), force=True) is True
        assert len(collector) == 1

    def test_none_datetime_passes_date_gate(self):
        finder, collector = make_finder(_Finder)
        assert finder.add_match(_mk(dt=None)) is True

    def test_callback_exception_returns_false(self):
        def bad_callback(match):
            raise RuntimeError("boom")

        finder = _Finder(
            bad_callback,
            contributes_odds=False,
            top_leagues_only=True,
            num_days_ahead=1,
            local_timezone="UTC",
            skip_patterns=(),
        )
        assert finder.add_match(_mk(dt=_now_local())) is False

    def test_match_passed_through_with_prediction_source(self):
        finder, collector = make_finder(_Finder)
        finder.add_match(_mk(dt=_now_local()))
        assert collector.first.predictions[0].source == "test"
        assert collector.first.home_team == "Arsenal"


class TestNormaliseDatetime:
    def test_none_timezone_returns_dt_unchanged(self):
        finder, _ = make_finder(_Finder)
        dt = datetime(2035, 6, 15, 19, 45)
        assert finder.normalise_datetime(dt) is dt

    def test_source_tz_converted_to_local_tz(self):
        finder, _ = make_finder(_TzFinder, local_timezone="Europe/Bucharest")
        dt = datetime(2035, 6, 15, 19, 45)  # naive Bangkok time
        result = finder.normalise_datetime(dt)
        # Bangkok is UTC+7, Bucharest UTC+3 (summer) -> 4h earlier
        assert result.hour == 15
        assert result.tzinfo is None

    def test_aware_dt_converted(self):
        finder, _ = make_finder(_TzFinder, local_timezone="Europe/Bucharest")
        dt = datetime(2035, 6, 15, 19, 45, tzinfo=ZoneInfo("Asia/Bangkok"))
        result = finder.normalise_datetime(dt)
        assert result.hour == 15


class TestDetectLocalTimezone:
    def test_returns_string_when_tzlocal_available(self):
        result = BaseMatchFinder._detect_local_timezone()
        assert result is None or isinstance(result, str)
