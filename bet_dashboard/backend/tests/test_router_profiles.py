"""[P0] API tests for the profiles router (issue #58)."""

from __future__ import annotations

BASE = "/api/profiles"


class TestListProfiles:
    def test_list_returns_settings_profiles(self, client, fake_app):
        expected = {"safe": {"units": 1.0}, "bold": {"units": 2.0}}
        fake_app.settings.get.return_value = expected
        assert client.get(BASE).json() == {"profiles": expected}

    def test_list_empty_settings_returns_empty_dict(self, client, fake_app):
        fake_app.settings.get.return_value = None
        assert client.get(BASE).json() == {"profiles": {}}

    def test_list_uses_settings_key_profiles(self, client, fake_app):
        client.get(BASE)
        fake_app.settings.get.assert_called_once_with("profiles")


class TestSaveProfile:
    def _body(self, **overrides):
        body = {"name": "Safe Bet", "target_odds": 4.0, "units": 2.5, "run_daily_count": 3}
        body.update(overrides)
        return body

    def test_save_sanitizes_name_to_slug(self, client, fake_app):
        r = client.post(BASE, json=self._body(name="My Cool Profile!"))
        assert r.status_code == 200
        fake_app.settings.write.assert_called_once()
        args = fake_app.settings.write.call_args
        assert args[0][0] == "mycoolprofile"
        assert args[1] == {"subpath": "profiles"}

    def test_save_returns_name_and_data(self, client, fake_app):
        data = client.post(BASE, json=self._body()).json()
        assert data["name"] == "safebet"
        assert "data" in data
        assert data["data"]["units"] == 2.5
        assert data["data"]["run_daily_count"] == 3

    def test_save_name_with_underscores_and_dashes_preserved(self, client, fake_app):
        client.post(BASE, json=self._body(name="Pro_2-Go"))
        assert fake_app.settings.write.call_args[0][0] == "pro_2-go"

    def test_save_invalid_name_returns_400(self, client, fake_app):
        r = client.post(BASE, json=self._body(name="!!!"))
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid profile name"

    def test_save_empty_name_returns_400(self, client, fake_app):
        assert client.post(BASE, json=self._body(name="")).status_code == 400

    def test_save_missing_name_returns_422(self, client, fake_app):
        body = self._body()
        del body["name"]
        assert client.post(BASE, json=body).status_code == 422

    def test_save_defaults_applied(self, client, fake_app):
        client.post(BASE, json={"name": "d"})
        data = fake_app.settings.write.call_args[0][1]
        assert data["target_odds"] == 3.0
        assert data["target_legs"] == 3
        assert data["units"] == 1.0
        assert data["run_daily_count"] == 0
        assert data["balance_decay"] == "linear"


class TestDeleteProfile:
    def test_delete_delegates_to_settings(self, client, fake_app):
        r = client.delete(f"{BASE}/gone")
        assert r.status_code == 200
        assert r.json() == {"deleted": "gone"}
        fake_app.settings.delete.assert_called_once_with("gone", subpath="profiles")
