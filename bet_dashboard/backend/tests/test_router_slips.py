"""[P0] API tests for the slips router (issue #58).

Covers: POST /api/slips validation + 400/422, GET filters
(profiles, profiles[] alias, dates, hide_settled, live_only),
POST /validate_manual, DELETE /{id}, POST /validate, POST /generate.
"""

from __future__ import annotations

from types import SimpleNamespace

from conftest import FakeDashboardLogic, make_leg, make_slip

BASE = "/api/slips"


def _valid_leg(**overrides) -> dict:
    leg = {
        "match_name": "Real Madrid - Barcelona",
        "market": "1",
        "market_type": "result",
        "odds": 1.9,
        "result_url": "https://example.com/match/1",
        "datetime": "2030-01-01T20:00:00",
        "consensus": 55.0,
        "sources": 4,
    }
    leg.update(overrides)
    return leg


class TestAddSlip:
    """[P0] POST /api/slips"""

    def test_add_slip_valid_returns_slip_id(self, client, fake_app):
        fake_app.save_slip_and_broadcast.return_value = 42
        r = client.post(BASE, json={"legs": [_valid_leg()], "units": 2.0})
        assert r.status_code == 200
        assert r.json() == {"slip_id": 42}
        fake_app.save_slip_and_broadcast.assert_called_once()
        args = fake_app.save_slip_and_broadcast.call_args[0]
        assert args[0] == "manual"
        assert args[2] == 2.0

    def test_add_slip_explicit_profile_used(self, client, fake_app):
        fake_app.save_slip_and_broadcast.return_value = 1
        r = client.post(BASE, json={"profile": "safe", "legs": [_valid_leg()]})
        assert r.status_code == 200
        assert fake_app.save_slip_and_broadcast.call_args[0][0] == "safe"

    def test_add_slip_match_not_found_returns_400(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(match_name="Nowhere United")]})
        assert r.status_code == 400
        assert "Match not found" in r.json()["detail"]

    def test_add_slip_invalid_market_returns_400(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(market="Bogus Market")]})
        assert r.status_code == 400
        assert "Invalid market" in r.json()["detail"]

    def test_add_slip_zero_odds_returns_400(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(odds=0)]})
        assert r.status_code == 400
        assert "Invalid odds" in r.json()["detail"]

    def test_add_slip_invalid_result_url_returns_400(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(result_url="none")]})
        assert r.status_code == 400
        assert "Invalid result_url" in r.json()["detail"]

    def test_add_slip_out_of_range_consensus_returns_400_not_500(self, client):
        """Guards the ValueError→400 fix in add_slip."""
        r = client.post(BASE, json={"legs": [_valid_leg(consensus=150.0)]})
        assert r.status_code == 400
        assert "consensus" in r.json()["detail"]

    def test_add_slip_negative_sources_returns_400_not_500(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(sources=-2)]})
        assert r.status_code == 400
        assert "sources" in r.json()["detail"]

    def test_add_slip_invalid_market_type_returns_400_not_500(self, client):
        r = client.post(BASE, json={"legs": [_valid_leg(market_type="nope")]})
        assert r.status_code == 400
        assert "market_type" in r.json()["detail"]

    def test_add_slip_missing_legs_returns_422(self, client):
        assert client.post(BASE, json={}).status_code == 422

    def test_add_slip_leg_missing_required_field_returns_422(self, client):
        bad = _valid_leg()
        del bad["consensus"]
        assert client.post(BASE, json={"legs": [bad]}).status_code == 422


class TestGetSlips:
    """[P0] GET /api/slips filters and envelope."""

    def test_get_slips_envelope_shape(self, client):
        data = client.get(BASE).json()
        assert set(data) == {"slips", "stats", "profiles"}
        assert data["profiles"] == ["manual"]
        slip = data["slips"][0]
        for key in ("slip_id", "date_generated", "profile", "total_odds", "units", "slip_status", "legs"):
            assert key in slip
        leg_keys = (
            "match_name", "datetime", "market", "market_type", "odds",
            "status", "result_url", "league", "predictions",
        )
        for key in leg_keys:
            assert key in slip["legs"][0]

    def test_get_slips_enum_status_serialized_to_string(self, client_factory):
        from bet_framework.core.type_defs import Outcome

        logic = FakeDashboardLogic(slips=[make_slip(slip_status=Outcome.WON)])
        client, _ = client_factory(logic=logic)
        data = client.get(BASE).json()
        assert data["slips"][0]["slip_status"] == "Won"

    def test_hide_settled_filters_won_and_lost(self, client_factory):
        logic = FakeDashboardLogic(
            slips=[
                make_slip(slip_id=1, slip_status="Won"),
                make_slip(slip_id=2, slip_status="Lost"),
                make_slip(slip_id=3, slip_status="Pending"),
            ]
        )
        client, _ = client_factory(logic=logic)
        data = client.get(BASE, params={"hide_settled": "true"}).json()
        assert [s["slip_id"] for s in data["slips"]] == [3]

    def test_hide_settled_accepts_truthy_coercions(self, client_factory):
        logic = FakeDashboardLogic(slips=[make_slip(slip_status="Won"), make_slip(slip_id=2, slip_status="Pending")])
        client, _ = client_factory(logic=logic)
        for val in ("1", "yes", "on", "TRUE"):
            data = client.get(BASE, params={"hide_settled": val}).json()
            assert [s["slip_id"] for s in data["slips"]] == [2]

    def test_hide_settled_false_keeps_all(self, client_factory):
        logic = FakeDashboardLogic(slips=[make_slip(slip_status="Won"), make_slip(slip_id=2, slip_status="Pending")])
        client, _ = client_factory(logic=logic)
        assert len(client.get(BASE, params={"hide_settled": "false"}).json()["slips"]) == 2

    def test_live_only_keeps_slips_with_live_legs(self, client_factory):
        live = make_slip(slip_id=1, legs=[make_leg(status="Live")])
        settled = make_slip(slip_id=2)
        client, _ = client_factory(logic=FakeDashboardLogic(slips=[live, settled]))
        data = client.get(BASE, params={"live_only": "true"}).json()
        assert [s["slip_id"] for s in data["slips"]] == [1]

    def test_live_only_no_live_legs_returns_empty(self, client):
        data = client.get(BASE, params={"live_only": "true"}).json()
        assert data["slips"] == []

    def test_profiles_query_param_forwarded(self, client, fake_logic):
        client.get(BASE, params={"profiles": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_profiles_bracket_alias_handled(self, client, fake_logic):
        client.get(BASE, params={"profiles[]": "safe"})
        assert "get_slips" in fake_logic.calls

    def test_date_filters_forwarded(self, client, fake_logic):
        client.get(BASE, params={"date_from": "2030-01-01", "date_to": "2030-01-31"})
        assert "get_slips" in fake_logic.calls

    def test_nan_floats_sanitized_to_none(self, client_factory):
        slip = make_slip(total_odds=float("nan"))
        client, _ = client_factory(logic=FakeDashboardLogic(slips=[slip]))
        assert client.get(BASE).json()["slips"][0]["total_odds"] is None

    def test_stats_included_in_response(self, client):
        data = client.get(BASE).json()
        assert data["stats"]["win_rate"] == 100.0

    def test_profiles_with_slips_union_sorted(self, client_factory):
        logic = FakeDashboardLogic(
            slips=[make_slip(profile="zeta"), make_slip(profile="alpha", slip_id=2)]
        )
        client, _ = client_factory(logic=logic)
        assert client.get(BASE).json()["profiles"] == ["alpha", "zeta"]


class TestValidateManual:
    """[P1] POST /api/slips/validate_manual"""

    def test_all_valid_legs(self, client):
        r = client.post(f"{BASE}/validate_manual", json=[_valid_leg(), _valid_leg(match_name="Real Madrid vs Barcelona")])
        assert r.status_code == 200
        data = r.json()
        assert data["all_valid"] is True
        assert all(leg["valid"] for leg in data["legs"])

    def test_mixed_validity_reports_all_valid_false(self, client):
        r = client.post(f"{BASE}/validate_manual", json=[_valid_leg(), _valid_leg(match_name="Nope")])
        data = r.json()
        assert data["all_valid"] is False
        assert data["legs"][0]["valid"] is True
        assert data["legs"][1]["valid"] is False
        assert "Match not found" in data["legs"][1]["error"]

    def test_empty_list_all_valid_true(self, client):
        r = client.post(f"{BASE}/validate_manual", json=[])
        assert r.json() == {"legs": [], "all_valid": True}

    def test_invalid_body_returns_422(self, client):
        assert client.post(f"{BASE}/validate_manual", json={"not": "a list"}).status_code == 422


class TestDeleteSlip:
    """[P1] DELETE /api/slips/{id}"""

    def test_delete_returns_deleted_id(self, client, fake_app):
        r = client.delete(f"{BASE}/7")
        assert r.status_code == 200
        assert r.json() == {"deleted": 7}
        fake_app.delete_slip_and_broadcast.assert_called_once_with(7)

    def test_delete_non_numeric_id_returns_422(self, client):
        assert client.delete(f"{BASE}/abc").status_code == 422


class TestValidateSlips:
    """[P1] POST /api/slips/validate"""

    def test_validate_response_shape(self, client, fake_app):
        fake_app.validate_and_broadcast.return_value = SimpleNamespace(
            checked=5,
            settled=["s1", "s2"],
            live=[SimpleNamespace(match_name="A - B", score="1:0", minute=33)],
            errors=["e1"],
        )
        r = client.post(f"{BASE}/validate")
        assert r.status_code == 200
        assert r.json() == {
            "checked": 5,
            "settled": 2,
            "live": 1,
            "errors": ["e1"],
            "live_data": [{"match_name": "A - B", "score": "1:0", "minute": 33}],
        }

    def test_validate_empty_live(self, client, fake_app):
        fake_app.validate_and_broadcast.return_value = SimpleNamespace(checked=0, settled=[], live=[], errors=[])
        data = client.post(f"{BASE}/validate").json()
        assert data == {"checked": 0, "settled": 0, "live": 0, "errors": [], "live_data": []}


class TestGenerateSlips:
    """[P1] POST /api/slips/generate"""

    def test_generate_sums_by_profile(self, client, fake_app):
        fake_app.generate_and_broadcast.return_value = {"safe": ["s1", "s2"], "balanced": ["s3"]}
        r = client.post(f"{BASE}/generate")
        assert r.status_code == 200
        assert r.json() == {"generated": 3, "by_profile": {"safe": 2, "balanced": 1}}

    def test_generate_empty_result(self, client, fake_app):
        fake_app.generate_and_broadcast.return_value = {}
        assert client.post(f"{BASE}/generate").json() == {"generated": 0, "by_profile": {}}