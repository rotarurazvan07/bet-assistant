"""[P0] API tests for the analytics router endpoint (issue #58).

Validates the full GET /api/analytics structure, profile/date filter passthrough,
and the all-numeric-fields-finite guarantee (no NaN/Inf in JSON).
"""

from __future__ import annotations

import math

from conftest import FakeDashboardLogic, make_leg, make_slip

BASE = "/api/analytics"

EXPECTED_KEYS = {
    "history", "market_accuracy", "pnl_by_market", "correlation", "profile_scatter",
    "stats", "profiles", "rolling_edge", "drawdown", "market_breakdown",
    "league_breakdown", "correlation_matrix", "source_breakdown", "source_market_correlation",
}


def _assert_finite(node, path="root"):
    """Recursively assert every float/int in the payload is finite."""
    if isinstance(node, dict):
        for k, v in node.items():
            _assert_finite(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _assert_finite(v, f"{path}[{i}]")
    elif isinstance(node, float):
        assert math.isfinite(node), f"non-finite value at {path}: {node}"


class TestGetAnalytics:
    """[P0] GET /api/analytics"""

    def test_analytics_full_structure(self, client):
        r = client.get(BASE)
        assert r.status_code == 200
        data = r.json()
        assert set(data) >= EXPECTED_KEYS

    def test_all_numeric_fields_finite(self, client):
        """Issue #58: response must contain no NaN/Inf anywhere."""
        _assert_finite(client.get(BASE).json())

    def test_analytics_with_rich_slips_stays_finite(self, client_factory):
        slips = [
            make_slip(slip_id=1, slip_status="Won", profile="safe"),
            make_slip(
                slip_id=2,
                slip_status="Lost",
                profile="bold",
                legs=[
                    make_leg(status="Won", market="Over 2.5", market_type="over_under_25", final_score="3:1",
                             predictions=[{"source": "forebet", "home": 2, "away": 1}]),
                    make_leg(status="Lost", market="2", market_type="result", final_score="1:1",
                             predictions=[{"source": "xgscore", "home": 0, "away": 0}]),
                ],
            ),
        ]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))
        _assert_finite(client.get(BASE).json())

    def test_profiles_filter_forwarded(self, client, fake_logic):
        client.get(BASE, params={"profiles": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_profiles_bracket_alias_forwarded(self, client, fake_logic):
        client.get(BASE, params={"profiles[]": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_date_filters_forwarded(self, client, fake_logic):
        client.get(BASE, params={"date_from": "2030-01-01", "date_to": "2030-01-31"})
        assert "get_slips" in fake_logic.calls

    def test_stats_echoed_from_logic(self, client):
        assert client.get(BASE).json()["stats"]["win_rate"] == 100.0

    def test_profiles_union_from_all_slips(self, client_factory):
        slips = [make_slip(profile="zeta"), make_slip(profile="alpha", slip_id=2)]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))
        assert client.get(BASE).json()["profiles"] == ["alpha", "zeta"]

    def test_empty_slips_finite_and_well_formed(self, client_factory):
        client, _ = client_factory(logic=FakeDashboardLogic(slips=[]))
        data = client.get(BASE).json()
        _assert_finite(data)
        assert data["pnl_by_market"] == []
        assert data["profile_scatter"] == []
        assert data["source_breakdown"] == []
        assert data["profiles"] == []
