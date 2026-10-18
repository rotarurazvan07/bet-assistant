"""[P0] API tests for the profiles router (issue #58)."""

BASE = "/api/profiles"


class TestSaveProfileSchedulePreservation:
    """[P0] F1: a builder save must not wipe Services-configured scheduling."""

    def test_omitted_scheduling_keys_keep_persisted_values(self, client, fake_app) -> None:
        """[P0] Order/schedule/auto_generate/run_daily_count survive an omit."""
        fake_app.settings.get.return_value = {
            "safebet": {
                "order": 4,
                "auto_generate": True,
                "generate_hour": 7,
                "generate_minute": 15,
                "run_daily_count": 2,
            }
        }
        r = client.post(BASE, json={"name": "Safe Bet", "target_odds": 4.0})
        assert r.status_code == 200
        written = fake_app.settings.write.call_args[0][1]
        assert written["order"] == 4
        assert written["auto_generate"] is True
        assert written["generate_hour"] == 7
        assert written["generate_minute"] == 15
        assert written["run_daily_count"] == 2

    def test_provided_scheduling_keys_are_persisted(self, client, fake_app) -> None:
        """[P0] Explicitly sent scheduling fields are written through."""
        fake_app.settings.get.return_value = None
        r = client.post(
            BASE,
            json={
                "name": "Safe Bet",
                "target_odds": 4.0,
                "order": 1,
                "auto_generate": True,
                "generate_hour": 6,
                "generate_minute": 30,
            },
        )
        assert r.status_code == 200
        written = fake_app.settings.write.call_args[0][1]
        assert written["order"] == 1
        assert written["auto_generate"] is True
        assert written["generate_hour"] == 6
        assert written["generate_minute"] == 30

    def test_omitted_run_daily_count_keeps_legacy_value(self, client, fake_app) -> None:
        """[P0] The frontend no longer sends run_daily_count; legacy survives."""
        fake_app.settings.get.return_value = {"safebet": {"run_daily_count": 3}}
        client.post(BASE, json={"name": "Safe Bet", "target_odds": 4.0})
        written = fake_app.settings.write.call_args[0][1]
        assert written["run_daily_count"] == 3


class TestListProfiles:
    def test_list_returns_settings_profiles(self, client, fake_app) -> None:
        expected = {"safe": {"units": 1.0}, "bold": {"units": 2.0}}
        fake_app.settings.get.return_value = expected
        assert client.get(BASE).json() == {"profiles": expected}

    def test_list_empty_settings_returns_empty_dict(self, client, fake_app) -> None:
        fake_app.settings.get.return_value = None
        assert client.get(BASE).json() == {"profiles": {}}

    def test_list_uses_settings_key_profiles(self, client, fake_app) -> None:
        client.get(BASE)
        fake_app.settings.get.assert_called_once_with("profiles")


class TestSaveProfile:
    def _body(self, **overrides):
        body = {
            "name": "Safe Bet",
            "target_odds": 4.0,
            "units": 2.5,
            "run_daily_count": 3,
        }
        body.update(overrides)
        return body

    def test_save_sanitizes_name_to_slug(self, client, fake_app) -> None:
        r = client.post(BASE, json=self._body(name="My Cool Profile!"))
        assert r.status_code == 200
        fake_app.settings.write.assert_called_once()
        args = fake_app.settings.write.call_args
        assert args[0][0] == "mycoolprofile"
        assert args[1] == {"subpath": "profiles"}

    def test_save_returns_name_and_data(self, client, fake_app) -> None:
        data = client.post(BASE, json=self._body()).json()
        assert data["name"] == "safebet"
        assert "data" in data
        assert data["data"]["units"] == 2.5
        assert data["data"]["run_daily_count"] == 3

    def test_save_name_with_underscores_and_dashes_preserved(self, client, fake_app) -> None:
        client.post(BASE, json=self._body(name="Pro_2-Go"))
        assert fake_app.settings.write.call_args[0][0] == "pro_2-go"

    def test_save_invalid_name_returns_400(self, client, fake_app) -> None:
        r = client.post(BASE, json=self._body(name="!!!"))
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid profile name"

    def test_save_empty_name_returns_400(self, client, fake_app) -> None:
        assert client.post(BASE, json=self._body(name="")).status_code == 400

    def test_save_missing_name_returns_422(self, client, fake_app) -> None:
        body = self._body()
        del body["name"]
        assert client.post(BASE, json=body).status_code == 422

    def test_save_defaults_applied(self, client, fake_app) -> None:
        client.post(BASE, json={"name": "d"})
        written = fake_app.settings.write.call_args[0][1]
        assert written["target_odds"] == 3.0
        assert written["target_legs"] == 3
        assert written["units"] == 1.0
        # F1: run_daily_count is opt-in — omitted it is not written as 0, so a
        # legacy auto-generation profile keeps its schedule across a builder save.
        assert "run_daily_count" not in written
        assert written["balance_decay"] == "linear"


class TestDeleteProfile:
    def test_delete_delegates_to_settings(self, client, fake_app) -> None:
        r = client.delete(f"{BASE}/gone")
        assert r.status_code == 200
        assert r.json() == {"deleted": "gone"}
        fake_app.settings.delete.assert_called_once_with("gone", subpath="profiles")
