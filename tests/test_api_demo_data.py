"""
Integration tests for API endpoints with demo data.

Tests the data_source=demo|live parameter routing for all 5 endpoints:
- /api/analytics
- /api/slips
- /api/matches
- /api/profiles
- /api/odds-history
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from bet_dashboard.backend.main import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


class TestAnalyticsEndpoint:
    """Test /api/analytics endpoint with data_source parameter."""

    def test_analytics_demo_data_source(self, client):
        """Test analytics endpoint with data_source=demo."""
        response = client.get("/api/analytics", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected keys present
        expected_keys = [
            "history", "market_accuracy", "pnl_by_market", "odds_distribution",
            "correlation", "profile_scatter", "stats", "profiles",
            "market_breakdown", "league_breakdown", "rolling_edge",
            "drawdown", "return_distribution", "time_patterns",
            "correlation_matrix", "profit_attribution"
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"
        
        # Verify stats structure
        stats = data["stats"]
        assert stats["total_settled"] > 0
        assert 0 <= stats["win_rate"] <= 100
        assert stats["total_units_bet"] > 0
        assert stats["avg_odds"] > 1.0
        assert stats["profit_factor"] >= 0

    def test_analytics_live_data_source(self, client):
        """Test analytics endpoint with data_source=live (default)."""
        response = client.get("/api/analytics", params={"data_source": "live"})
        assert response.status_code == 200
        data = response.json()
        
        # Should return live data structure (may be empty if no live data)
        expected_keys = [
            "history", "market_accuracy", "pnl_by_market", "odds_distribution",
            "correlation", "profile_scatter", "stats", "profiles",
            "market_breakdown", "league_breakdown", "rolling_edge",
            "drawdown", "return_distribution", "time_patterns",
            "correlation_matrix", "profit_attribution"
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_analytics_invalid_data_source(self, client):
        """Test analytics endpoint with invalid data_source."""
        response = client.get("/api/analytics", params={"data_source": "invalid"})
        assert response.status_code == 422  # Validation error

    def test_analytics_profile_filter_demo(self, client):
        """Test analytics with profile filter and demo data."""
        response = client.get("/api/analytics", params={
            "data_source": "demo",
            "profiles": ["Conservative"]
        })
        assert response.status_code == 200
        data = response.json()
        
        # All profile scatter data should be Conservative
        profiles_in_result = {s["profile"] for s in data["profile_scatter"]}
        assert profiles_in_result == {"Conservative"}

    def test_analytics_date_filter_demo(self, client):
        """Test analytics with date filter and demo data."""
        response = client.get("/api/analytics", params={
            "data_source": "demo",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        # All history dates should be in March 2026
        for day in data["history"]:
            assert day["date"].startswith("2026-03")


class TestSlipsEndpoint:
    """Test /api/slips endpoint with data_source parameter."""

    def test_slips_demo_data_source(self, client):
        """Test slips endpoint with data_source=demo."""
        response = client.get("/api/slips", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert "slips" in data
        assert "stats" in data
        assert "profiles" in data
        assert len(data["slips"]) > 0
        assert set(data["profiles"]) == {"Conservative", "Balanced", "Aggressive"}

    def test_slips_live_data_source(self, client):
        """Test slips endpoint with data_source=live."""
        response = client.get("/api/slips", params={"data_source": "live"})
        assert response.status_code == 200
        data = response.json()
        
        assert "slips" in data
        assert "stats" in data
        assert "profiles" in data

    def test_slips_invalid_data_source(self, client):
        """Test slips endpoint with invalid data_source."""
        response = client.get("/api/slips", params={"data_source": "invalid"})
        assert response.status_code == 422

    def test_slips_profile_filter_demo(self, client):
        """Test slips with profile filter and demo data."""
        response = client.get("/api/slips", params={
            "data_source": "demo",
            "profiles": ["Conservative"]
        })
        assert response.status_code == 200
        data = response.json()
        
        for slip in data["slips"]:
            assert slip["profile"] == "Conservative"
        assert data["profiles"] == ["Conservative"]

    def test_slips_hide_settled_demo(self, client):
        """Test slips hide_settled filter with demo data."""
        response = client.get("/api/slips", params={
            "data_source": "demo",
            "hide_settled": "true"
        })
        assert response.status_code == 200
        data = response.json()
        
        for slip in data["slips"]:
            assert slip["slip_status"] not in ("Won", "Lost")
            assert slip["slip_status"] in ("Pending", "Live")

    def test_slips_live_only_demo(self, client):
        """Test slips live_only filter with demo data."""
        response = client.get("/api/slips", params={
            "data_source": "demo",
            "live_only": "true"
        })
        assert response.status_code == 200
        data = response.json()
        
        for slip in data["slips"]:
            assert any(leg["status"] == "Live" for leg in slip["legs"])

    def test_slips_date_filter_demo(self, client):
        """Test slips with date filter and demo data."""
        response = client.get("/api/slips", params={
            "data_source": "demo",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        for slip in data["slips"]:
            assert "2026-03" <= slip["date_generated"] <= "2026-03-31"

    def test_slip_structure_demo(self, client):
        """Verify slip data structure with demo data."""
        response = client.get("/api/slips", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        slip = data["slips"][0]
        assert "slip_id" in slip
        assert "date_generated" in slip
        assert "profile" in slip
        assert "total_odds" in slip
        assert "units" in slip
        assert "slip_status" in slip
        assert "legs" in slip
        assert "net_profit" in slip
        
        assert isinstance(slip["legs"], list)
        assert len(slip["legs"]) > 0
        
        leg = slip["legs"][0]
        assert "match_name" in leg
        assert "datetime" in leg
        assert "market" in leg
        assert "market_type" in leg
        assert "odds" in leg
        assert "status" in leg
        assert "result_url" in leg
        assert "league" in leg

    def test_net_profit_calculation_demo(self, client):
        """Verify net_profit calculation for settled slips with demo data."""
        response = client.get("/api/slips", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        for slip in data["slips"]:
            if slip["slip_status"] == "Won":
                expected_profit = round((slip["total_odds"] - 1) * slip["units"], 2)
                assert abs(slip["net_profit"] - expected_profit) < 0.01
            elif slip["slip_status"] == "Lost":
                expected_profit = round(-slip["units"], 2)
                assert abs(slip["net_profit"] - expected_profit) < 0.01
            else:
                assert slip["net_profit"] is None


class TestMatchesEndpoint:
    """Test /api/matches endpoint with data_source parameter."""

    def test_matches_demo_data_source(self, client):
        """Test matches endpoint with data_source=demo."""
        response = client.get("/api/matches", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert "matches" in data
        assert data["page"] == 1
        assert data["page_size"] == 40
        assert len(data["matches"]) <= 40
        assert data["total"] > 0

    def test_matches_live_data_source(self, client):
        """Test matches endpoint with data_source=live."""
        response = client.get("/api/matches", params={"data_source": "live"})
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert "matches" in data

    def test_matches_invalid_data_source(self, client):
        """Test matches endpoint with invalid data_source."""
        response = client.get("/api/matches", params={"data_source": "invalid"})
        assert response.status_code == 422

    def test_matches_pagination_demo(self, client):
        """Test matches pagination with demo data."""
        page1 = client.get("/api/matches", params={"data_source": "demo", "page": 1, "page_size": 10})
        page2 = client.get("/api/matches", params={"data_source": "demo", "page": 2, "page_size": 10})
        
        assert page1.status_code == 200
        assert page2.status_code == 200
        assert page1.json()["page"] == 1
        assert page2.json()["page"] == 2
        assert len(page1.json()["matches"]) == 10
        assert len(page2.json()["matches"]) == 10
        assert page1.json()["matches"][0]["match_id"] != page2.json()["matches"][0]["match_id"]
        assert page1.json()["total"] == page2.json()["total"]
        assert page1.json()["total_pages"] == page2.json()["total_pages"]

    def test_matches_search_demo(self, client):
        """Test matches search filter with demo data."""
        response = client.get("/api/matches", params={
            "data_source": "demo",
            "search": "Arsenal"
        })
        assert response.status_code == 200
        data = response.json()
        
        for match in data["matches"]:
            assert "arsenal" in match["home"].lower() or "arsenal" in match["away"].lower()

    def test_matches_date_filter_demo(self, client):
        """Test matches date range filter with demo data."""
        response = client.get("/api/matches", params={
            "data_source": "demo",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        for match in data["matches"]:
            if match["datetime"]:
                assert "2026-03" <= match["datetime"][:10] <= "2026-03-31"

    def test_matches_sort_demo(self, client):
        """Test matches sorting with demo data."""
        response = client.get("/api/matches", params={
            "data_source": "demo",
            "sort_by": "datetime",
            "sort_dir": "asc"
        })
        assert response.status_code == 200
        data = response.json()
        
        dates = [m["datetime"] for m in data["matches"] if m["datetime"]]
        assert dates == sorted(dates)
        
        response_desc = client.get("/api/matches", params={
            "data_source": "demo",
            "sort_by": "datetime",
            "sort_dir": "desc"
        })
        assert response_desc.status_code == 200
        data_desc = response_desc.json()
        dates_desc = [m["datetime"] for m in data_desc["matches"] if m["datetime"]]
        assert dates_desc == sorted(dates_desc, reverse=True)

    def test_matches_min_consensus_demo(self, client):
        """Test matches min_consensus filter with demo data."""
        response = client.get("/api/matches", params={
            "data_source": "demo",
            "min_consensus": 60
        })
        assert response.status_code == 200
        data = response.json()
        
        for match in data["matches"]:
            consensus_values = [
                match.get("cons_home", 0),
                match.get("cons_draw", 0),
                match.get("cons_away", 0),
                match.get("cons_over_25", 0),
                match.get("cons_under_25", 0),
                match.get("cons_btts_yes", 0),
                match.get("cons_btts_no", 0),
                match.get("cons_over_05", 0),
                match.get("cons_under_05", 0),
                match.get("cons_over_15", 0),
                match.get("cons_under_15", 0),
                match.get("cons_over_35", 0),
                match.get("cons_under_35", 0),
                match.get("cons_over_45", 0),
                match.get("cons_under_45", 0),
                match.get("cons_dc_1x", 0),
                match.get("cons_dc_12", 0),
                match.get("cons_dc_x2", 0),
            ]
            assert max(consensus_values) >= 60

    def test_matches_min_odds_demo(self, client):
        """Test matches min_odds filter with demo data."""
        response = client.get("/api/matches", params={
            "data_source": "demo",
            "min_odds": 3.0
        })
        assert response.status_code == 200
        data = response.json()
        
        for match in data["matches"]:
            odds_values = [
                match.get("odds_home", 0),
                match.get("odds_draw", 0),
                match.get("odds_away", 0),
                match.get("odds_over_25", 0),
                match.get("odds_under_25", 0),
                match.get("odds_btts_yes", 0),
                match.get("odds_btts_no", 0),
                match.get("odds_over_05", 0),
                match.get("odds_under_05", 0),
                match.get("odds_over_15", 0),
                match.get("odds_under_15", 0),
                match.get("odds_over_35", 0),
                match.get("odds_under_35", 0),
                match.get("odds_over_45", 0),
                match.get("odds_under_45", 0),
                match.get("odds_dc_1x", 0),
                match.get("odds_dc_12", 0),
                match.get("odds_dc_x2", 0),
            ]
            assert max(odds_values) >= 3.0

    def test_match_structure_demo(self, client):
        """Verify match data structure with demo data."""
        response = client.get("/api/matches", params={"data_source": "demo", "page_size": 1})
        assert response.status_code == 200
        data = response.json()
        match = data["matches"][0]
        
        required_fields = [
            "match_id", "datetime", "home", "away", "sources",
            "cons_home", "cons_draw", "cons_away",
            "cons_over_25", "cons_under_25",
            "cons_btts_yes", "cons_btts_no",
            "odds_home", "odds_draw", "odds_away",
            "odds_over_25", "odds_under_25",
            "odds_btts_yes", "odds_btts_no",
            "result_url", "league"
        ]
        for field in required_fields:
            assert field in match, f"Missing field: {field}"
        
        assert match["sources"] >= 3
        assert match["odds_home"] > 1.0
        assert match["odds_draw"] > 1.0
        assert match["odds_away"] > 1.0


class TestProfilesEndpoint:
    """Test /api/profiles endpoint with data_source parameter."""

    def test_profiles_demo_data_source(self, client):
        """Test profiles endpoint with data_source=demo."""
        response = client.get("/api/profiles", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert "profiles" in data
        profiles = data["profiles"]
        
        assert set(profiles.keys()) == {"Conservative", "Balanced", "Aggressive"}
        
        for profile_name, config in profiles.items():
            required_fields = [
                "target_odds", "target_legs", "max_legs_overflow",
                "consensus_floor", "min_odds", "tolerance_factor",
                "stop_threshold", "min_legs_fill_ratio",
                "quality_vs_balance", "consensus_vs_sources",
                "included_markets", "included_leagues",
                "units", "target_payout", "run_daily_count"
            ]
            for field in required_fields:
                assert field in config, f"Missing field {field} in {profile_name}"
            
            if profile_name == "Conservative":
                assert config["target_odds"] == 2.0
                assert config["target_legs"] == 1
                assert config["units"] == 1.0
            elif profile_name == "Balanced":
                assert config["target_odds"] == 3.5
                assert config["target_legs"] == 2
                assert config["units"] == 1.5
            elif profile_name == "Aggressive":
                assert config["target_odds"] == 6.0
                assert config["target_legs"] == 3
                assert config["units"] == 2.0

    def test_profiles_live_data_source(self, client):
        """Test profiles endpoint with data_source=live."""
        response = client.get("/api/profiles", params={"data_source": "live"})
        assert response.status_code == 200
        data = response.json()
        
        assert "profiles" in data

    def test_profiles_invalid_data_source(self, client):
        """Test profiles endpoint with invalid data_source."""
        response = client.get("/api/profiles", params={"data_source": "invalid"})
        assert response.status_code == 422


class TestOddsHistoryEndpoint:
    """Test /api/odds-history endpoint with data_source parameter."""

    def test_odds_history_demo_data_source(self, client):
        """Test odds history endpoint with data_source=demo."""
        # First get a match ID that has odds history
        response = client.get("/api/matches", params={"data_source": "demo", "page_size": 1})
        assert response.status_code == 200
        matches = response.json()["matches"]
        assert len(matches) > 0
        match_id = matches[0]["match_id"]
        
        response = client.get(f"/api/odds-history/{match_id}", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert "match_id" in data
        assert "match_name" in data
        assert "datetime" in data
        assert "snapshots" in data
        assert "movement" in data
        
        assert data["match_id"] == match_id
        assert len(data["snapshots"]) == 30  # 30 days of history
        
        # Verify snapshots structure
        for snapshot in data["snapshots"]:
            assert "timestamp" in snapshot
            assert "odds" in snapshot
            odds = snapshot["odds"]
            assert "home" in odds
            assert "draw" in odds
            assert "away" in odds
            assert "over_25" in odds
            assert "under_25" in odds
            assert "btts_yes" in odds
            assert "btts_no" in odds
            for v in odds.values():
                assert v >= 1.01
        
        # Verify movement structure
        movement = data["movement"]
        for key, value in movement.items():
            assert value in ("up", "down", "stable")

    def test_odds_history_live_data_source(self, client):
        """Test odds history endpoint with data_source=live."""
        response = client.get("/api/odds-history/0", params={"data_source": "live"})
        # May return 404 if no live data, but should not error
        assert response.status_code in (200, 404)

    def test_odds_history_invalid_data_source(self, client):
        """Test odds history endpoint with invalid data_source."""
        response = client.get("/api/odds-history/0", params={"data_source": "invalid"})
        assert response.status_code == 422

    def test_odds_history_invalid_match(self, client):
        """Test odds history for invalid match ID."""
        response = client.get("/api/odds-history/999999", params={"data_source": "demo"})
        assert response.status_code == 404

    def test_all_movements_demo(self, client):
        """Test get_all_movements with demo data."""
        response = client.get("/api/odds-history/movements/all", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        for match_id, movement in data.items():
            assert isinstance(match_id, str)
            assert isinstance(movement, dict)
            for key, value in movement.items():
                assert value in ("up", "down", "stable")

    def test_significant_movements_demo(self, client):
        """Test get_significant_movements with demo data."""
        response = client.get("/api/odds-history/movements/significant", params={"data_source": "demo"})
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        for match_id, movement in data.items():
            assert isinstance(match_id, str)
            assert isinstance(movement, dict)
            # Should have at least one significant movement
            sig_count = sum(1 for v in movement.values() if v in ("up", "down"))
            assert sig_count > 0


class TestDataSourceRouting:
    """Test that data_source parameter correctly routes to demo or live provider."""

    def test_all_endpoints_accept_data_source(self, client):
        """Verify all 5 endpoints accept data_source parameter."""
        endpoints = [
            "/api/analytics",
            "/api/slips",
            "/api/matches",
            "/api/profiles",
            "/api/odds-history/movements/all",
        ]
        
        for endpoint in endpoints:
            # Test with demo
            response = client.get(endpoint, params={"data_source": "demo"})
            assert response.status_code == 200, f"Failed for {endpoint} with demo"
            
            # Test with live
            response = client.get(endpoint, params={"data_source": "live"})
            assert response.status_code == 200, f"Failed for {endpoint} with live"
            
            # Test default (should be live)
            response = client.get(endpoint)
            assert response.status_code == 200, f"Failed for {endpoint} with default"

    def test_demo_data_is_deterministic(self, client):
        """Verify demo data is deterministic across requests."""
        # Make two requests for the same endpoint with demo data
        response1 = client.get("/api/analytics", params={"data_source": "demo"})
        response2 = client.get("/api/analytics", params={"data_source": "demo"})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()
        
        # Test slips endpoint
        response1 = client.get("/api/slips", params={"data_source": "demo"})
        response2 = client.get("/api/slips", params={"data_source": "demo"})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()
        
        # Test matches endpoint
        response1 = client.get("/api/matches", params={"data_source": "demo"})
        response2 = client.get("/api/matches", params={"data_source": "demo"})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
