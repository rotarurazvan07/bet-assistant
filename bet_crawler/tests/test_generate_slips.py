"""Stage 4: generate_slips tests (issue #68).

Pins: profile loading gate (SystemExit on empty), matches db → slip persistence
in slips.db, units handling, BetSlipConfig field flow, no-eligible-matches path.
Note: crawl_core.generate_slips does NOT read run_daily_count (CLI invokes one
explicit profile; daily gating lives in backend AppLogic) — documented divergence.
"""

from datetime import datetime

import pytest

from bet_crawler.crawl_core.generate_slips import generate_slips
from bet_framework.BetAssistant import BetAssistant
from bet_framework.MatchesManager import MatchesManager

from .conftest import make_match


def _seed_matches_db(db_path, matches):
    mm = MatchesManager(db_path, similarity_config=None)
    for m in matches:
        mm.add_match(m)
    mm.flush()
    mm.close()


def _slips_rows(slips_db):
    ba = BetAssistant(slips_db)
    try:
        return ba.fetch_rows("SELECT slip_id, profile, total_odds, units FROM slips")
    finally:
        ba.close()


DT = datetime(2026, 9, 25, 15, 0, 0)


def _consensus_match(home="United FC", away="Rival FC", url="https://r.com/1"):
    from bet_framework.core.Match import Odds, Score

    return make_match(
        home=home,
        away=away,
        dt=DT,
        preds=[Score(source=f"s{i}", home=3, away=1) for i in range(3)],
        odds=Odds(home=1.9, draw=3.4, away=4.2),
        url=url,
    )


PROFILE = {
    "target_odds": 2.0,
    "target_legs": 1,
    "tolerance_factor": 0.30,
    "stop_threshold": 0.50,
    "consensus_floor": 40.0,
    "min_odds": 1.01,
    "odds_movement_weight": None,
}


class TestGenerateSlipsP0:
    def test_empty_profile_data_raises_system_exit(self, tmp_path):
        matches_db = str(tmp_path / "matches.db")
        _seed_matches_db(matches_db, [_consensus_match()])
        slips_db = str(tmp_path / "slips.db")
        with pytest.raises(SystemExit) as exc:
            generate_slips(matches_db, slips_db, "ghost", {})
        assert exc.value.code == 1

    def test_slip_saved_with_units(self, tmp_path):
        matches_db = str(tmp_path / "matches.db")
        _seed_matches_db(matches_db, [_consensus_match()])
        slips_db = str(tmp_path / "slips.db")
        profile = dict(PROFILE, units=2.5)
        generate_slips(matches_db, slips_db, "aggressive", profile)
        rows = _slips_rows(slips_db)
        assert len(rows) == 1
        assert rows[0]["profile"] == "aggressive"
        assert rows[0]["units"] == 2.5
        assert abs(rows[0]["total_odds"] - 1.9) < 1e-9

    def test_units_defaults_to_1_when_missing(self, tmp_path):
        matches_db = str(tmp_path / "matches.db")
        _seed_matches_db(matches_db, [_consensus_match()])
        slips_db = str(tmp_path / "slips.db")
        generate_slips(matches_db, slips_db, "plain", dict(PROFILE))
        rows = _slips_rows(slips_db)
        assert rows[0]["units"] == 1.0

    def test_no_matches_db_yields_no_slip(self, tmp_path):
        matches_db = str(tmp_path / "matches.db")
        _seed_matches_db(matches_db, [])
        slips_db = str(tmp_path / "slips.db")
        generate_slips(matches_db, slips_db, "plain", dict(PROFILE))
        assert _slips_rows(slips_db) == []

    def test_no_eligible_matches_yields_no_slip(self, tmp_path):
        """Matches present but consensus floor unreachable → build returns no legs."""
        matches_db = str(tmp_path / "matches.db")
        _seed_matches_db(matches_db, [_consensus_match()])
        slips_db = str(tmp_path / "slips.db")
        profile = dict(PROFILE, min_odds=99.0)  # odds 1.9 < 99 → no candidate passes the gate
        generate_slips(matches_db, slips_db, "picky", profile)
        assert _slips_rows(slips_db) == []
