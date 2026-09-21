# ============================================
# SELECTION (sifarnik) TESTS
# ============================================

from unittest.mock import patch

import pytest

from app.features.sifarnici.selection.selection_model import Selection


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


@pytest.fixture()
def create_selection(db_session):
    def _create(company_id, name="U15", **kwargs):
        selection = Selection(company_id=company_id, name=name, **kwargs)
        db_session.add(selection)
        db_session.commit()
        db_session.refresh(selection)
        return selection
    return _create


class TestSelectionCompanyScope:
    """Selections are per company — a non-SUPER_ADMIN only sees their own."""

    @pytest.fixture()
    def other_selection(self, create_company, create_selection):
        return create_selection(company_id=create_company(name="Other Club").id, name="U17")

    def test_list_excludes_other_company(
        self, client, create_selection, other_selection, auth_headers
    ):
        headers, _, company = auth_headers
        mine = create_selection(company_id=company.id)

        response = _call(client, "get", "/api/selection/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert mine.id in ids
        assert other_selection.id not in ids

    def test_get_other_company_selection_403(self, client, other_selection, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/selection/{other_selection.id}", headers)
        assert response.status_code == 403

    def test_own_company_selection_visible(self, client, create_selection, auth_headers):
        headers, _, company = auth_headers
        mine = create_selection(company_id=company.id)

        response = _call(client, "get", f"/api/selection/{mine.id}", headers)
        assert response.status_code == 200

    def test_super_admin_sees_other_company_selection(
        self, client, other_selection, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/selection/{other_selection.id}", headers)
        assert response.status_code == 200
