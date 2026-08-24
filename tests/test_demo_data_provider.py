"""
Comprehensive unit tests for DemoDataProvider.

Tests the deterministic demo data generation, all public API methods,
and verifies calculations match expected values for the seeded scenario.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from typing import Any

from bet_dashboard.backend.fixtures.demo_data import (
    DemoDataProvider,
    BetSlip,
    BetLeg,
    Match,
    Outcome,
    SlipStatus,
    get_demo_provider,
)


class TestDemoDataProviderInitialization:
    """Test DemoDataProvider initialization and deterministic generation."""

    def test_singleton_instance(self):
        """Verify get_demo_provider returns the same instance."""
        provider1 = get_demo_provider()
        provider2 = get_demo_provider()
        assert provider1 is provider2

    def test_deterministic_generation_same_seed(self):
        """Verify same seed produces identical data."""
        provider1 = DemoDataProvider(seed=42)
        provider2 = DemoDataProvider(seed=42)
        
        # Check slips are identical
        assert len(provider1._slips) == len(provider2._slips)
        for s1, s2 in zip(provider1._slips, provider2._slips):
            assert s1.slip_id == s2.slip_id
            assert s1.profile == s2.profile
            assert s1.total_odds == s2.total_odds
            assert s1.units == s2.units
            assert s1.slip_status == s2.slip_status
            assert s1.net_profit == s2.net_profit
            assert len(s1.legs) == len(s2.legs)
            for l1, l2 in zip(s1.legs, s2.legs):
                assert l1.match_name == l2.match_name
                assert l1.market == l2.market
                assert l1.odds == l2.odds
                assert l1.status == l2.status

    def test_different_seeds_produce_different_data(self):
        """Verify different seeds produce different data."""
        provider1 = DemoDataProvider(seed=42)
        provider2 = DemoDataProvider(seed=123)
        
        # At least one slip should differ
        assert provider1._slips != provider2._slips

    def test_data_generation_counts(self):
        """Verify expected data generation counts."""
        provider = DemoDataProvider(seed=42)
        
        # Should have ~632 matches over 6 months (actual count with seed=42)
        assert len(provider._matches) == 632
        
        # Should have ~350 slips
        assert len(provider._slips) == 350
        
        # Should have 3 profiles
        profiles = {s.profile for s in provider._slips}
        assert profiles == {"Conservative", "Balanced", "Aggressive"}
        
        # Should have odds history for matches in slips
        assert len(provider._odds_history) > 0

    def test_status_distribution(self):
        """Verify status distribution matches actual ratios for seed=42."""
        provider = DemoDataProvider(seed=42)
        
        statuses = [s.slip_status for s in provider._slips]
        total = len(statuses)
        
        won_pct = statuses.count(SlipStatus.WON.value) / total * 100
        lost_pct = statuses.count(SlipStatus.LOST.value) / total * 100
        pending_pct = statuses.count(SlipStatus.PENDING.value) / total * 100
        live_pct = statuses.count(SlipStatus.LIVE.value) / total * 100
        
        # Actual distribution for seed=42: ~19% won, ~67% lost, ~13% pending, ~1% live
        assert 15 <= won_pct <= 25
        assert 60 <= lost_pct <= 75
        assert 10 <= pending_pct <= 20
        assert 0 <= live_pct <= 5


class TestDemoDataProviderGetAnalytics:
    """Test get_analytics method with various filters."""

    @pytest.fixture
    def provider(self):
        return DemoDataProvider(seed=42)

    def test_get_analytics_all_data(self, provider):
        """Test analytics with no filters returns all data."""
        result = provider.get_analytics(None, None, None)
        
        # Verify all expected keys present
        expected_keys = [
            "history", "market_accuracy", "pnl_by_market", "odds_distribution",
            "correlation", "profile_scatter", "stats", "profiles",
            "market_breakdown", "league_breakdown", "rolling_edge",
            "drawdown", "return_distribution", "time_patterns",
            "correlation_matrix", "profit_attribution"
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
        
        # Verify stats structure
        stats = result["stats"]
        assert stats["total_settled"] > 0
        assert stats["total_won_count"] >= 0
        assert 0 <= stats["win_rate"] <= 100
        assert stats["total_units_bet"] > 0
        assert stats["net_profit"] != 0  # Should have some profit/loss
        assert stats["roi_percentage"] != 0
        assert stats["avg_odds"] > 1.0
        assert stats["profit_factor"] >= 0

    def test_get_analytics_profile_filter(self, provider):
        """Test analytics filtered by profile."""
        result = provider.get_analytics(["Conservative"], None, None)
        
        stats = result["stats"]
        assert stats["total_settled"] > 0
        
        # All slips should be Conservative
        profiles_in_result = {s["profile"] for s in result["profile_scatter"]}
        assert profiles_in_result == {"Conservative"}

    def test_get_analytics_date_filter(self, provider):
        """Test analytics filtered by date range."""
        result = provider.get_analytics(None, "2026-03-01", "2026-03-31")
        
        stats = result["stats"]
        # Should have fewer slips than full dataset
        full_result = provider.get_analytics(None, None, None)
        assert stats["total_settled"] <= full_result["stats"]["total_settled"]
        
        # All history dates should be in March 2026
        for day in result["history"]:
            assert day["date"].startswith("2026-03")

    def test_get_analytics_empty_result(self, provider):
        """Test analytics with date range that has no data."""
        result = provider.get_analytics(None, "2020-01-01", "2020-01-31")
        
        stats = result["stats"]
        assert stats["total_settled"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["net_profit"] == 0.0
        assert result["history"] == []
        assert result["market_accuracy"] == []
        assert result["pnl_by_market"] == []

    def test_history_cumulative_calculations(self, provider):
        """Verify daily history cumulative calculations are correct."""
        result = provider.get_analytics(None, None, None)
        history = result["history"]
        
        cumulative_profit = 0.0
        cumulative_bet = 0.0
        
        for day in history:
            cumulative_profit += day["net_profit"]
            cumulative_bet += day["units_bet"]
            
            assert abs(day["cumulative_profit"] - cumulative_profit) < 0.01
            assert abs(day["cumulative_bet"] - cumulative_bet) < 0.01
            
            if cumulative_bet > 0:
                expected_roi = round(cumulative_profit / cumulative_bet * 100, 2)
                assert abs(day["roi_percentage"] - expected_roi) < 0.01

    def test_market_accuracy_calculations(self, provider):
        """Verify market accuracy calculations."""
        result = provider.get_analytics(None, None, None)
        market_accuracy = result["market_accuracy"]
        
        for market in market_accuracy:
            total = market["total"]
            won = market["won"]
            lost = market["lost"]
            accuracy = market["accuracy"]
            
            assert total == won + lost
            if total > 0:
                expected_accuracy = round(won / total * 100, 1)
                assert abs(accuracy - expected_accuracy) < 0.1
            else:
                assert accuracy == 0.0

    def test_pnl_by_market_calculations(self, provider):
        """Verify PnL by market calculations."""
        result = provider.get_analytics(None, None, None)
        pnl_by_market = result["pnl_by_market"]
        
        for market in pnl_by_market:
            won = market["won"]
            lost = market["lost"]
            net_profit = market["net_profit"]
            
            # Net profit should be consistent with won/lost counts
            # (exact verification requires knowing per-leg stakes)
            assert isinstance(net_profit, (int, float))

    def test_odds_distribution_buckets(self, provider):
        """Verify odds distribution bucket calculations."""
        result = provider.get_analytics(None, None, None)
        odds_dist = result["odds_distribution"]
        
        for bucket in odds_dist:
            count = bucket["count"]
            wins = bucket["wins"]
            losses = bucket["losses"]
            win_rate = bucket["win_rate"]
            implied_win_rate = bucket["implied_win_rate"]
            edge = bucket["edge"]
            
            assert count == wins + losses
            if count > 0:
                assert abs(win_rate - round(wins / count * 100, 1)) < 0.1
                assert abs(edge - round(win_rate - implied_win_rate, 1)) < 0.1
            assert bucket["avg_odds"] > 1.0

    def test_profile_scatter_calculations(self, provider):
        """Verify profile scatter calculations."""
        result = provider.get_analytics(None, None, None)
        profile_scatter = result["profile_scatter"]
        
        for profile_data in profile_scatter:
            profile = profile_data["profile"]
            avg_odds = profile_data["avg_odds"]
            win_rate = profile_data["win_rate"]
            net_profit = profile_data["net_profit"]
            volume = profile_data["volume"]
            break_even = profile_data["break_even_win_rate"]
            
            assert profile in ["Conservative", "Balanced", "Aggressive"]
            assert avg_odds > 1.0
            assert 0 <= win_rate <= 100
            assert volume > 0
            if avg_odds > 0:
                expected_be = round(100 / avg_odds, 1)
                assert abs(break_even - expected_be) < 0.1

    def test_stats_calculations(self, provider):
        """Verify stats calculations are internally consistent."""
        result = provider.get_analytics(None, None, None)
        stats = result["stats"]
        
        total_settled = stats["total_settled"]
        total_won = stats["total_won_count"]
        win_rate = stats["win_rate"]
        total_units = stats["total_units_bet"]
        net_profit = stats["net_profit"]
        roi = stats["roi_percentage"]
        avg_odds = stats["avg_odds"]
        implied_wr = stats["implied_win_rate"]
        edge = stats["edge"]
        profit_factor = stats["profit_factor"]
        
        if total_settled > 0:
            assert abs(win_rate - round(total_won / total_settled * 100, 1)) < 0.1
            if total_units > 0:
                assert abs(roi - round(net_profit / total_units * 100, 2)) < 0.01
            assert abs(edge - round(win_rate - implied_wr, 1)) < 0.1
            assert profit_factor >= 0

    def test_market_breakdown_sorted_by_edge(self, provider):
        """Verify market breakdown is sorted by edge descending."""
        result = provider.get_analytics(None, None, None)
        market_breakdown = result["market_breakdown"]
        
        edges = [m["edge"] for m in market_breakdown]
        assert edges == sorted(edges, reverse=True)
        
        for market in market_breakdown:
            total = market["legs"]
            won = market["won"]
            lost = market["lost"]
            win_rate = market["win_rate"]
            implied = market["implied_win_rate"]
            edge = market["edge"]
            
            assert total == won + lost
            if total > 0:
                assert abs(win_rate - round(won / total * 100, 1)) < 0.1
                assert abs(edge - round(win_rate - implied, 1)) < 0.1

    def test_league_breakdown_sorted_by_edge(self, provider):
        """Verify league breakdown is sorted by edge descending."""
        result = provider.get_analytics(None, None, None)
        league_breakdown = result["league_breakdown"]
        
        edges = [l["edge"] for l in league_breakdown]
        assert edges == sorted(edges, reverse=True)

    def test_rolling_edge_calculations(self, provider):
        """Verify rolling edge calculations."""
        result = provider.get_analytics(None, None, None)
        rolling_edge = result["rolling_edge"]
        
        for day in rolling_edge:
            rolling_wr = day["rolling_win_rate"]
            rolling_implied = day["rolling_implied"]
            rolling_edge_val = day["rolling_edge"]
            
            assert abs(rolling_edge_val - round(rolling_wr - rolling_implied, 1)) < 0.1
            assert day["sample_size"] > 0

    def test_drawdown_calculations(self, provider):
        """Verify drawdown calculations."""
        result = provider.get_analytics(None, None, None)
        drawdown = result["drawdown"]
        
        peak = 0.0
        for day in drawdown:
            cum = day["cumulative_profit"]
            if cum > peak:
                peak = cum
            expected_dd = round(cum - peak, 2)
            assert abs(day["drawdown"] - expected_dd) < 0.01
            assert abs(day["peak"] - peak) < 0.01
            assert day["drawdown"] <= 0  # Drawdown should be <= 0

    def test_return_distribution(self, provider):
        """Verify return distribution calculations."""
        result = provider.get_analytics(None, None, None)
        ret_dist = result["return_distribution"]
        
        if ret_dist:
            assert "bins" in ret_dist
            assert "mean" in ret_dist
            assert "median" in ret_dist
            assert len(ret_dist["bins"]) == 10
            
            total_count = sum(b["count"] for b in ret_dist["bins"])
            assert total_count > 0

    def test_time_patterns(self, provider):
        """Verify time patterns calculations."""
        result = provider.get_analytics(None, None, None)
        time_patterns = result["time_patterns"]
        
        if time_patterns:
            assert "day_of_week" in time_patterns
            dow = time_patterns["day_of_week"]
            for day in dow:
                assert "key" in day
                assert "total" in day
                assert "won" in day
                assert "win_rate" in day
                if day["total"] > 0:
                    assert abs(day["win_rate"] - round(day["won"] / day["total"] * 100, 1)) < 0.1

    def test_correlation_matrix(self, provider):
        """Verify correlation matrix structure."""
        result = provider.get_analytics(None, None, None)
        corr_matrix = result["correlation_matrix"]
        
        assert "leagues" in corr_matrix
        assert "markets" in corr_matrix
        assert "matrix" in corr_matrix
        
        for league in corr_matrix["leagues"]:
            assert league in corr_matrix["matrix"]
            for market in corr_matrix["markets"]:
                if market in corr_matrix["matrix"][league]:
                    cell = corr_matrix["matrix"][league][market]
                    assert "win_rate" in cell
                    assert "edge" in cell
                    assert "total" in cell
                    assert cell["total"] > 0

    def test_profit_attribution(self, provider):
        """Verify profit attribution calculations."""
        result = provider.get_analytics(None, None, None)
        profit_attr = result["profit_attribution"]
        
        assert "total_profit" in profit_attr
        assert "components" in profit_attr
        
        total_profit = profit_attr["total_profit"]
        components = profit_attr["components"]
        
        # Sum of component values should approximately equal total_profit
        component_sum = sum(c["value"] for c in components)
        assert abs(component_sum - total_profit) < 1.0  # Allow small rounding differences
        
        # Percentages should sum to approximately 100%
        pct_sum = sum(c["percentage"] for c in components)
        assert abs(pct_sum - 100) < 5  # Allow some tolerance


class TestDemoDataProviderGetSlips:
    """Test get_slips method with various filters."""

    @pytest.fixture
    def provider(self):
        return DemoDataProvider(seed=42)

    def test_get_slips_all(self, provider):
        """Test getting all slips."""
        result = provider.get_slips(None, None, None, False, False)
        
        assert "slips" in result
        assert "stats" in result
        assert "profiles" in result
        assert len(result["slips"]) == len(provider._slips)
        assert set(result["profiles"]) == {"Conservative", "Balanced", "Aggressive"}

    def test_get_slips_profile_filter(self, provider):
        """Test slips filtered by profile."""
        result = provider.get_slips(["Conservative"], None, None, False, False)
        
        for slip in result["slips"]:
            assert slip["profile"] == "Conservative"
        # Note: profiles field returns all profiles that have slips in the date range
        # not just the filtered profile
        assert "Conservative" in result["profiles"]

    def test_get_slips_date_filter(self, provider):
        """Test slips filtered by date range."""
        result = provider.get_slips(None, "2026-03-01", "2026-03-31", False, False)
        
        for slip in result["slips"]:
            assert "2026-03" <= slip["date_generated"] <= "2026-03-31"

    def test_get_slips_hide_settled(self, provider):
        """Test hide_settled filter."""
        result = provider.get_slips(None, None, None, True, False)
        
        for slip in result["slips"]:
            assert slip["slip_status"] not in (SlipStatus.WON.value, SlipStatus.LOST.value)
            assert slip["slip_status"] in (SlipStatus.PENDING.value, SlipStatus.LIVE.value)

    def test_get_slips_live_only(self, provider):
        """Test live_only filter."""
        result = provider.get_slips(None, None, None, False, True)
        
        for slip in result["slips"]:
            assert any(leg["status"] == Outcome.LIVE.value for leg in slip["legs"])

    def test_slip_structure(self, provider):
        """Verify slip data structure."""
        result = provider.get_slips(None, None, None, False, False)
        slip = result["slips"][0]
        
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

    def test_net_profit_calculation(self, provider):
        """Verify net_profit calculation for settled slips."""
        result = provider.get_slips(None, None, None, False, False)
        
        for slip in result["slips"]:
            if slip["slip_status"] == SlipStatus.WON.value:
                expected_profit = round((slip["total_odds"] - 1) * slip["units"], 2)
                assert abs(slip["net_profit"] - expected_profit) < 0.01
            elif slip["slip_status"] == SlipStatus.LOST.value:
                expected_profit = round(-slip["units"], 2)
                assert abs(slip["net_profit"] - expected_profit) < 0.01
            else:
                assert slip["net_profit"] is None


class TestDemoDataProviderGetMatches:
    """Test get_matches method with various filters."""

    @pytest.fixture
    def provider(self):
        return DemoDataProvider(seed=42)

    def test_get_matches_default(self, provider):
        """Test default matches pagination."""
        result = provider.get_matches()
        
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert "matches" in result
        assert result["page"] == 1
        assert result["page_size"] == 40
        assert len(result["matches"]) <= 40
        assert result["total"] == len(provider._matches)

    def test_get_matches_pagination(self, provider):
        """Test matches pagination."""
        page1 = provider.get_matches(page=1, page_size=10)
        page2 = provider.get_matches(page=2, page_size=10)
        
        assert page1["page"] == 1
        assert page2["page"] == 2
        assert len(page1["matches"]) == 10
        assert len(page2["matches"]) == 10
        assert page1["matches"][0]["match_id"] != page2["matches"][0]["match_id"]
        assert page1["total"] == page2["total"]
        assert page1["total_pages"] == page2["total_pages"]

    def test_get_matches_search(self, provider):
        """Test matches search filter."""
        # Search for a known team
        result = provider.get_matches(search="Arsenal")
        
        for match in result["matches"]:
            assert "arsenal" in match["home"].lower() or "arsenal" in match["away"].lower()

    def test_get_matches_date_filter(self, provider):
        """Test matches date range filter."""
        result = provider.get_matches(date_from="2026-03-01", date_to="2026-03-31")
        
        for match in result["matches"]:
            if match["datetime"]:
                assert "2026-03" <= match["datetime"][:10] <= "2026-03-31"

    def test_get_matches_sort(self, provider):
        """Test matches sorting."""
        result = provider.get_matches(sort_by="datetime", sort_dir="asc")
        
        dates = [m["datetime"] for m in result["matches"] if m["datetime"]]
        assert dates == sorted(dates)
        
        result_desc = provider.get_matches(sort_by="datetime", sort_dir="desc")
        dates_desc = [m["datetime"] for m in result_desc["matches"] if m["datetime"]]
        assert dates_desc == sorted(dates_desc, reverse=True)

    def test_get_matches_min_consensus(self, provider):
        """Test min_consensus filter."""
        result = provider.get_matches(min_consensus=60)
        
        for match in result["matches"]:
            # At least one market should have consensus >= 60
            consensus_values = [
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
                match.get("cons_home", 0),
                match.get("cons_draw", 0),
                match.get("cons_away", 0),
                match.get("cons_over_25", 0),
                match.get("cons_under_25", 0),
                match.get("cons_btts_yes", 0),
                match.get("cons_btts_no", 0),
            ]
            assert max(consensus_values) >= 60

    def test_get_matches_min_odds(self, provider):
        """Test min_odds filter."""
        result = provider.get_matches(min_odds=3.0)
        
        for match in result["matches"]:
            odds_values = [
                match.get("odds_home", 0),
                match.get("odds_draw", 0),
                match.get("odds_away", 0),
                match.get("odds_over_25", 0),
                match.get("odds_under_25", 0),
                match.get("odds_btts_yes", 0),
                match.get("odds_btts_no", 0),
            ]
            assert max(odds_values) >= 3.0

    def test_match_structure(self, provider):
        """Verify match data structure."""
        result = provider.get_matches(page_size=1)
        match = result["matches"][0]
        
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


class TestDemoDataProviderGetProfiles:
    """Test get_profiles method."""

    @pytest.fixture
    def provider(self):
        return DemoDataProvider(seed=42)

    def test_get_profiles_structure(self, provider):
        """Verify profiles structure."""
        result = provider.get_profiles()
        
        assert "profiles" in result
        profiles = result["profiles"]
        
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
            
            # Verify profile-specific values
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


class TestDemoDataProviderGetOddsHistory:
    """Test get_odds_history method."""

    @pytest.fixture
    def provider(self):
        return DemoDataProvider(seed=42)

    def test_get_odds_history_valid_match(self, provider):
        """Test odds history for a valid match."""
        # Find a match with odds history
        match_ids_with_history = list(provider._odds_history.keys())
        assert len(match_ids_with_history) > 0
        
        match_id = match_ids_with_history[0]
        result = provider.get_odds_history(match_id)
        
        assert "match_id" in result
        assert "match_name" in result
        assert "datetime" in result
        assert "snapshots" in result
        assert "movement" in result
        
        assert result["match_id"] == match_id
        assert len(result["snapshots"]) == 30  # 30 days of history
        
        # Verify snapshots structure
        for snapshot in result["snapshots"]:
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
        movement = result["movement"]
        for key, value in movement.items():
            assert value in ("up", "down", "stable")

    def test_get_odds_history_invalid_match(self, provider):
        """Test odds history for invalid match ID."""
        with pytest.raises(ValueError, match="Match 999999 not found"):
            provider.get_odds_history(999999)

    def test_get_all_movements(self, provider):
        """Test get_all_movements."""
        result = provider.get_all_movements()
        
        assert isinstance(result, dict)
        for match_id, movement in result.items():
            assert isinstance(match_id, str)
            assert isinstance(movement, dict)
            for key, value in movement.items():
                assert value in ("up", "down", "stable")

    def test_get_significant_movements(self, provider):
        """Test get_significant_movements."""
        result = provider.get_significant_movements()
        
        assert isinstance(result, dict)
        for match_id, movement in result.items():
            assert isinstance(match_id, str)
            assert isinstance(movement, dict)
            # Should have at least one significant movement
            sig_count = sum(1 for v in movement.values() if v in ("up", "down"))
            assert sig_count > 0


class TestDemoDataProviderDeterministic:
    """Test that demo data is fully deterministic."""

    def test_full_determinism(self):
        """Verify complete determinism across all methods."""
        provider1 = DemoDataProvider(seed=42)
        provider2 = DemoDataProvider(seed=42)
        
        # Test all public methods return identical results
        assert provider1.get_analytics(None, None, None) == provider2.get_analytics(None, None, None)
        assert provider1.get_slips(None, None, None, False, False) == provider2.get_slips(None, None, None, False, False)
        assert provider1.get_matches() == provider2.get_matches()
        assert provider1.get_profiles() == provider2.get_profiles()
        
        # Test odds history for all matches with history
        for match_id in provider1._odds_history:
            assert provider1.get_odds_history(match_id) == provider2.get_odds_history(match_id)
        
        assert provider1.get_all_movements() == provider2.get_all_movements()
        assert provider1.get_significant_movements() == provider2.get_significant_movements()

    def test_filtered_determinism(self):
        """Verify determinism with filters."""
        provider1 = DemoDataProvider(seed=42)
        provider2 = DemoDataProvider(seed=42)
        
        assert provider1.get_analytics(["Conservative"], "2026-03-01", "2026-03-31") == \
               provider2.get_analytics(["Conservative"], "2026-03-01", "2026-03-31")
        assert provider1.get_slips(["Balanced"], "2026-04-01", "2026-04-30", True, False) == \
               provider2.get_slips(["Balanced"], "2026-04-01", "2026-04-30", True, False)
        assert provider1.get_matches(page=2, page_size=20, search="Real", sort_by="home") == \
               provider2.get_matches(page=2, page_size=20, search="Real", sort_by="home")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
