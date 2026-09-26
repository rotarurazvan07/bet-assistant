"""[P0] Unit tests for the matches router (issue #58).

Covers: pagination defaults/bounds, search, date filters, sort_by/sort_dir,
min_consensus, min_odds, only_significant_movement, excluded_sources,
empty-dataframe path, 422 validation, and frontend MatchesPage contract.
"""

from __future__ import annotations

import math

from conftest import FakeDashboardLogic, make_match_row, make_matches_df

BASE = "/api/matches"


class TestGetMatchesDefaults:
    """[P0] Default pagination and response envelope."""

    def test_get_matches_returns_default_page_and_size(self, client):
        r = client.get(BASE)
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["page_size"] == 40
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["matches"]) == 1

    def test_get_matches_response_matches_frontend_contract(self, client):
        """Response JSON keys must match frontend MatchesPage/Match types."""
        r = client.get(BASE)
        m = r.json()["matches"][0]
        for key in (
            "match_id",
            "datetime",
            "home",
            "away",
            "sources",
            "cons_home",
            "odds_home",
            "result_url",
            "league",
        ):
            assert key in m, f"missing contract key: {key}"
        # datetime serialized to ISO string
        assert isinstance(m["datetime"], str)

    def test_get_matches_serializes_scores_alias(self, client_factory):
        logic = FakeDashboardLogic(
            df=make_matches_df([make_match_row(_filtered_scores=[{"source": "s", "home": 1, "away": 0}])])
        )
        client, _ = client_factory(logic=logic)
        m = client.get(BASE).json()["matches"][0]
        assert m["scores"] == [{"source": "s", "home": 1, "away": 0}]

    def test_get_matches_sanitizes_nan_floats_to_none(self, client_factory):
        row = make_match_row(cons_home=float("nan"), league=float("nan"))
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df([row])))
        m = client.get(BASE).json()["matches"][0]
        assert m["cons_home"] is None


class TestGetMatchesPagination:
    """[P1] Pagination bounds and slicing."""

    def test_page_beyond_range_returns_empty_matches(self, client):
        r = client.get(BASE, params={"page": 5})
        assert r.status_code == 200
        assert r.json()["matches"] == []

    def test_page_size_slices_rows(self, client_factory):
        rows = [make_match_row(home=f"Team{i}", away=f"Opp{i}") for i in range(5)]
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(rows)))
        data = client.get(BASE, params={"page": 2, "page_size": 2}).json()
        assert data["total"] == 5
        assert data["total_pages"] == 3
        assert [m["home"] for m in data["matches"]] == ["Team2", "Team3"]

    def test_invalid_page_zero_returns_422(self, client):
        assert client.get(BASE, params={"page": 0}).status_code == 422

    def test_page_size_over_100_returns_422(self, client):
        assert client.get(BASE, params={"page_size": 101}).status_code == 422

    def test_page_size_zero_returns_422(self, client):
        assert client.get(BASE, params={"page_size": 0}).status_code == 422


class TestGetMatchesSearchAndDates:
    """[P1] Search passthrough and date params."""

    def test_search_forwards_to_filter_matches(self, client, fake_logic):
        client.get(BASE, params={"search": "madrid"})
        assert "filter_matches" in fake_logic.calls

    def test_search_no_hits_returns_zero_total(self, client):
        r = client.get(BASE, params={"search": "zzz"})
        data = r.json()
        assert data["total"] == 0
        assert data["matches"] == []
        assert data["total_pages"] == 1

    def test_date_from_and_to_forwarded(self, client, fake_logic):
        client.get(BASE, params={"date_from": "2030-01-01", "date_to": "2030-01-02"})
        assert "filter_matches" in fake_logic.calls


class TestGetMatchesSorting:
    """[P1] sort_by / sort_dir behavior."""

    def _three_rows(self):
        return [
            make_match_row(home="Alpha", away="Zed", sources=2),
            make_match_row(home="Mid", away="Yan", sources=9),
            make_match_row(home="Zulu", away="Xan", sources=5),
        ]

    def test_sort_by_home_desc(self, client_factory):
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(self._three_rows())))
        homes = [m["home"] for m in client.get(BASE, params={"sort_by": "home", "sort_dir": "desc"}).json()["matches"]]
        assert homes == ["Zulu", "Mid", "Alpha"]

    def test_sort_by_sources_asc(self, client_factory):
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(self._three_rows())))
        rows = client.get(BASE, params={"sort_by": "sources", "sort_dir": "asc"}).json()["matches"]
        assert [m["sources"] for m in rows] == [2, 5, 9]

    def test_invalid_sort_by_falls_back_to_datetime(self, client):
        r = client.get(BASE, params={"sort_by": "not_a_column"})
        assert r.status_code == 200

    def test_sort_by_consensus_column_allowed(self, client):
        r = client.get(BASE, params={"sort_by": "cons_home"})
        assert r.status_code == 200


class TestGetMatchesFilters:
    """[P0] Market-cell filters: consensus, odds, significant movement."""

    @staticmethod
    def _only(cons_home=None, odds_home=None, home="Row"):
        """Row where only cons_home/odds_home can pass filters; all other markets set to fail."""
        from conftest import make_match_row

        row = make_match_row(home=home)
        cons_keys = [k for k in row if k.startswith("cons_") and k != "cons_home"]
        odds_keys = [k for k in row if k.startswith("odds_") and k != "odds_home"]
        for k in cons_keys:
            row[k] = 0.0
        for k in odds_keys:
            row[k] = 1.01
        if cons_home is not None:
            row["cons_home"] = cons_home
        if odds_home is not None:
            row["odds_home"] = odds_home
        return row

    def test_min_consensus_filters_rows(self, client_factory):
        rows = [self._only(cons_home=80.0, home="High"), self._only(cons_home=20.0, home="Low")]
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(rows)))
        homes = [m["home"] for m in client.get(BASE, params={"min_consensus": 50}).json()["matches"]]
        assert homes == ["High"]

    def test_min_consensus_zero_keeps_all(self, client):
        data = client.get(BASE, params={"min_consensus": 0}).json()
        assert data["total"] == 1

    def test_min_odds_filters_rows(self, client_factory):
        rows = [self._only(odds_home=2.5, home="Expensive"), self._only(odds_home=1.2, home="Cheap")]
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(rows)))
        homes = [m["home"] for m in client.get(BASE, params={"min_odds": 2.0}).json()["matches"]]
        assert homes == ["Expensive"]

    def test_min_odds_one_keeps_all(self, client):
        data = client.get(BASE, params={"min_odds": 1.0}).json()
        assert data["total"] == 1

    def test_only_significant_movement_keeps_significant_rows(self, client_factory):
        rows = [make_match_row(home="Sig", result_url="https://x.com/1"), make_match_row(home="Plain", result_url="https://x.com/2")]
        logic = FakeDashboardLogic(df=make_matches_df(rows))
        # Only match 0 (index) has a significant movement registered
        logic._movement_strength = {}

        def strength(idx):
            if idx == 0:
                return {"home": {"direction": "up", "change_pct": 9.0, "significant": True}}
            return {}

        logic.get_odds_movement_with_strength = strength
        client, _ = client_factory(logic=logic)
        homes = [m["home"] for m in client.get(BASE, params={"only_significant_movement": True}).json()["matches"]]
        assert homes == ["Sig"]

    def test_combined_consensus_and_odds_filter(self, client_factory):
        both = self._only(cons_home=80.0, odds_home=2.5, home="Both")
        other_market = self._only(home="OtherMarket")
        other_market["cons_over_25"] = 80.0
        other_market["odds_over_25"] = 2.5
        neither = self._only(cons_home=20.0, odds_home=1.2, home="Neither")
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df([both, other_market, neither])))
        homes = [m["home"] for m in client.get(BASE, params={"min_consensus": 50, "min_odds": 2.0}).json()["matches"]]
        # OR over markets: home market passes for Both, over_25 market passes for OtherMarket
        assert homes == ["Both", "OtherMarket"]

    def test_min_consensus_out_of_range_returns_422(self, client):
        assert client.get(BASE, params={"min_consensus": 101}).status_code == 422
        assert client.get(BASE, params={"min_consensus": -1}).status_code == 422

    def test_min_odds_out_of_range_returns_422(self, client):
        assert client.get(BASE, params={"min_odds": 0.5}).status_code == 422
        assert client.get(BASE, params={"min_odds": 51.0}).status_code == 422


class TestGetMatchesExcludedSources:
    """[P2] excluded_sources parsing."""

    def test_excluded_sources_csv_forwarded_as_list(self, client, fake_logic):
        captured = {}
        orig = fake_logic.filter_matches

        def spy(search_text=None, date_from=None, date_to=None, excluded_sources=None):
            captured["excluded"] = excluded_sources
            return orig(search_text, date_from, date_to, excluded_sources)

        fake_logic.filter_matches = spy
        client.get(BASE, params={"excluded_sources": "forebet,xgscore"})
        assert captured["excluded"] == ["forebet", "xgscore"]

    def test_no_excluded_sources_defaults_to_empty_list(self, client, fake_logic):
        captured = {}
        orig = fake_logic.filter_matches

        def spy(search_text=None, date_from=None, date_to=None, excluded_sources=None):
            captured["excluded"] = excluded_sources
            return orig(search_text, date_from, date_to, excluded_sources)

        fake_logic.filter_matches = spy
        client.get(BASE)
        assert captured["excluded"] == []


class TestGetMatchesEmpty:
    """[P1] Empty dataframe short-circuit."""

    def test_empty_df_returns_zero_envelope(self, empty_client):
        data = empty_client.get(BASE).json()
        assert data == {"total": 0, "page": 1, "page_size": 40, "total_pages": 1, "matches": []}

    def test_empty_df_with_filters_returns_zero_envelope(self, empty_client):
        data = empty_client.get(BASE, params={"min_consensus": 50, "min_odds": 2.0}).json()
        assert data["total"] == 0

    def test_filter_removing_all_rows_returns_zero_envelope(self, empty_client):
        data = empty_client.get(BASE, params={"search": "anything"}).json()
        assert data["total"] == 0


class TestRowToDictUnit:
    """[P2] Unit coverage of the _row_to_dict/_clean helpers."""

    def test_clean_passes_non_nan_through(self):
        from routers.matches import _clean

        assert _clean(1.5) == 1.5
        assert _clean("text") == "text"
        assert _clean(None) is None

    def test_row_to_dict_isoformat_serialization(self):
        from routers.matches import _row_to_dict

        row = make_match_row()
        out = _row_to_dict(row)
        assert isinstance(out["datetime"], str)

    def test_row_to_dict_float_nan_becomes_none(self):
        from routers.matches import _row_to_dict

        out = _row_to_dict(make_match_row(odds_home=float("nan")))
        assert out["odds_home"] is None


class TestTotalPagesMath:
    """[P3] total_pages ceiling math."""

    def test_total_pages_ceil(self, client_factory):
        rows = [make_match_row(home=f"T{i}") for i in range(41)]
        client, _ = client_factory(logic=FakeDashboardLogic(df=make_matches_df(rows)))
        data = client.get(BASE).json()
        assert data["total"] == 41
        assert data["total_pages"] == math.ceil(41 / 40)

    def test_single_row_total_pages_is_one(self, client):
        assert client.get(BASE).json()["total_pages"] == 1
