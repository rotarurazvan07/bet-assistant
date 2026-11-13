"""[P0] API tests for the analytics router endpoint.

Validates the full GET /api/analytics structure, profile/date filter passthrough,
and the all-numeric-fields-finite guarantee (no NaN/Inf in JSON).
"""

import math

from conftest import FakeDashboardLogic, make_leg, make_slip

BASE = "/api/analytics"

EXPECTED_KEYS = {
    "history",
    "market_accuracy",
    "pnl_by_market",
    "correlation",
    "profile_scatter",
    "stats",
    "profiles",
    "rolling_edge",
    "drawdown",
    "market_breakdown",
    "league_breakdown",
    "correlation_matrix",
    "source_breakdown",
    "source_market_correlation",
}


def _assert_finite(node, path="root") -> None:
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

    def test_analytics_full_structure(self, client) -> None:
        r = client.get(BASE)
        assert r.status_code == 200
        data = r.json()
        assert set(data) >= EXPECTED_KEYS

    def test_all_numeric_fields_finite(self, client) -> None:
        """response must contain no NaN/Inf anywhere."""
        _assert_finite(client.get(BASE).json())

    def test_analytics_with_rich_slips_stays_finite(self, client_factory) -> None:
        slips = [
            make_slip(slip_id=1, slip_status="Won", profile="safe"),
            make_slip(
                slip_id=2,
                slip_status="Lost",
                profile="bold",
                legs=[
                    make_leg(
                        status="Won",
                        market="Over 2.5",
                        market_type="over_under_25",
                        final_score="3:1",
                        predictions=[{"source": "forebet", "home": 2, "away": 1}],
                    ),
                    make_leg(
                        status="Lost",
                        market="2",
                        market_type="result",
                        final_score="1:1",
                        predictions=[{"source": "xgscore", "home": 0, "away": 0}],
                    ),
                ],
            ),
        ]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))
        _assert_finite(client.get(BASE).json())

    def test_paper_slips_keep_accuracy_without_financial_impact(self, client_factory) -> None:
        slips = [
            make_slip(
                slip_id=1,
                slip_status="Won",
                units=None,
                legs=[
                    make_leg(
                        result_url="https://example.com/match/1",
                        predictions=[{"source": "forebet", "home": 2, "away": 1}],
                    )
                ],
            ),
            make_slip(
                slip_id=2,
                slip_status="Lost",
                units=0.0,
                legs=[
                    make_leg(
                        status="Lost",
                        result_url="https://example.com/match/2",
                        predictions=[{"source": "forebet", "home": 0, "away": 2}],
                    )
                ],
            ),
        ]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))

        response = client.get(BASE)

        assert response.status_code == 200
        data = response.json()
        _assert_finite(data)
        assert data["history"][0]["slips_count"] == 2
        assert data["history"][0]["units_bet"] == 0.0
        assert data["market_accuracy"][0]["total"] == 2
        assert data["source_breakdown"][0]["total_predictions"] == 2
        assert data["source_breakdown"][0]["accuracy"] == 50.0
        assert data["profile_scatter"][0]["volume"] == 2
        assert data["profile_scatter"][0]["net_profit"] == 0.0

    def test_source_breakdown_trust_fields_in_response(self, client_factory) -> None:
        slips = [
            make_slip(
                slip_id=1,
                slip_status="Won",
                date_generated="2030-01-01T10:00:00",
                legs=[
                    make_leg(
                        market="Over 2.5",
                        market_type="over_under_25",
                        final_score="2:1",
                        predictions=[{"source": "forebet", "home": 2, "away": 1}],
                    )
                ],
            ),
        ]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))
        data = client.get(BASE).json()
        src = data["source_breakdown"][0]
        # trust fields present and JSON-serializable
        assert isinstance(src["trust_score"], float)
        assert 0.0 <= src["trust_score"] <= 1.0
        assert src["recency_weight"] in (0.2, 0.5, 0.8, 1.0)
        assert src["latest_prediction_date"] == "2030-01-01"
        _assert_finite(data)

    def test_profiles_filter_forwarded(self, client, fake_logic) -> None:
        client.get(BASE, params={"profiles": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_profiles_bracket_alias_forwarded(self, client, fake_logic) -> None:
        client.get(BASE, params={"profiles[]": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_date_filters_forwarded(self, client, fake_logic) -> None:
        client.get(BASE, params={"date_from": "2030-01-01", "date_to": "2030-01-31"})
        assert "get_slips" in fake_logic.calls

    def test_stats_echoed_from_logic(self, client) -> None:
        assert client.get(BASE).json()["stats"]["win_rate"] == 100.0

    def test_profiles_union_from_all_slips(self, client_factory) -> None:
        slips = [make_slip(profile="zeta"), make_slip(profile="alpha", slip_id=2)]
        client, _ = client_factory(logic=FakeDashboardLogic(slips=slips))
        assert client.get(BASE).json()["profiles"] == ["alpha", "zeta"]

    def test_empty_slips_finite_and_well_formed(self, client_factory) -> None:
        client, _ = client_factory(logic=FakeDashboardLogic(slips=[]))
        data = client.get(BASE).json()
        _assert_finite(data)
        assert data["pnl_by_market"] == []
        assert data["profile_scatter"] == []
        assert data["source_breakdown"] == []
        assert data["profiles"] == []
