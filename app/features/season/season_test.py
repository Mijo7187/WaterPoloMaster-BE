# ============================================
# SEASON TESTS
# ============================================

from unittest.mock import patch

import pytest

from app.features.season.season_model import Season


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestSeasonCompanyScope:
    """Non-SUPER_ADMIN users only see and manage seasons of their own company."""

    @pytest.fixture()
    def other_season(self, create_company, create_season):
        return create_season(company_id=create_company(name="Other Club").id)

    def test_own_company_season_visible(self, client, create_season, auth_headers):
        headers, _, company = auth_headers
        mine = create_season(company_id=company.id)

        response = _call(client, "get", f"/api/season/{mine.id}", headers)
        assert response.status_code == 200

    def test_list_excludes_other_company(self, client, create_season, other_season, auth_headers):
        headers, _, company = auth_headers
        mine = create_season(company_id=company.id)

        response = _call(client, "get", "/api/season/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert other_season.id not in ids

    def test_get_other_company_season_403(self, client, other_season, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/season/{other_season.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_season_403(self, client, other_season, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "put", f"/api/season/{other_season.id}", headers,
                         json={"name": "Hijacked"})
        assert response.status_code == 403

    def test_delete_other_company_season_403(self, client, db_session, other_season, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "delete", f"/api/season/{other_season.id}", headers)
        assert response.status_code == 403
        assert db_session.get(Season, other_season.id) is not None

    def test_create_season_in_other_company_403(self, client, create_company, auth_headers):
        headers, _, _ = auth_headers
        other = create_company(name="Other Club")
        response = _call(client, "post", "/api/season/", headers, json={
            "company_id": other.id,
            "name": "Sneaky Season",
            "start_date": "2027-01-01",
            "end_date": "2027-12-31",
        })
        assert response.status_code == 403

    def test_super_admin_sees_other_company_season(self, client, other_season, super_admin_headers):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/season/{other_season.id}", headers)
        assert response.status_code == 200
