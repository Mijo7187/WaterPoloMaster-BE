# ============================================
# TOURNAMENT TESTS
# ============================================

import pytest
from datetime import date

from app.features.tournament.tournament_service import TournamentService
from app.features.tournament.tournament_schemas import TournamentCreate
from app.utils.dateUtils import QuarterType
from app.core.api.exceptions import BadRequestException


class TestTournamentServiceCreate:

    def test_create_resolves_season_from_from_date(
        self, db_session, create_company, create_season
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        season = create_season(company_id=company.id)
        service = TournamentService(db_session)
        tournament = service.create(TournamentCreate(
            company_id=company.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
        ))
        assert tournament.id is not None
        assert tournament.season_id == season.id
        # quarter_type is derived from the date now, not stored: May -> Q2
        assert tournament.quarter_type == QuarterType.Q2

    def test_create_without_season_raises(self, db_session, create_company):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        service = TournamentService(db_session)
        with pytest.raises(BadRequestException, match="You have to add a Season covering this date"):
            service.create(TournamentCreate(
                company_id=company.id,
                pool_id=pool.id,
                from_date=date(2026, 5, 1),
                to_date=date(2026, 5, 3),
                price=500,
            ))


class TestTournamentServiceGet:

    def test_get_by_id_exposes_quarter_type(
        self, db_session, create_company, create_season
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        create_season(company_id=company.id)
        service = TournamentService(db_session)
        created = service.create(TournamentCreate(
            company_id=company.id,
            pool_id=pool.id,
            from_date=date(2026, 8, 1),  # August -> Q3
            to_date=date(2026, 8, 2),
            price=700,
        ))
        found = service.get_by_id(created.id)
        assert found.quarter_type == QuarterType.Q3


def _call(client, method, url, headers, **kwargs):
    from unittest.mock import patch
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


class TestTournamentCompanyScope:
    """Non-SUPER_ADMIN users only see and manage tournaments of their own company."""

    @pytest.fixture()
    def other_tournament(self, db_session, create_company, create_season):
        other = create_company(name="Other Club")
        pool = create_company(name="Other Pool", company_type="POOL")
        create_season(company_id=other.id)
        return TournamentService(db_session).create(TournamentCreate(
            company_id=other.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
        ))

    def test_list_excludes_other_company(self, client, other_tournament, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", "/api/tournament/", headers)
        assert response.status_code == 200
        ids = {i["id"] for i in response.json()["data"]["items"]}
        assert other_tournament.id not in ids

    def test_get_other_company_tournament_403(self, client, other_tournament, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "get", f"/api/tournament/{other_tournament.id}", headers)
        assert response.status_code == 403

    def test_update_other_company_tournament_403(self, client, other_tournament, auth_headers):
        headers, _, _ = auth_headers
        response = _call(client, "put", f"/api/tournament/{other_tournament.id}", headers,
                         json={"price": 1})
        assert response.status_code == 403

    def test_delete_other_company_tournament_403(
        self, client, db_session, other_tournament, auth_headers
    ):
        from app.features.tournament.tournament_model import Tournament

        headers, _, _ = auth_headers
        response = _call(client, "delete", f"/api/tournament/{other_tournament.id}", headers)
        assert response.status_code == 403
        assert db_session.get(Tournament, other_tournament.id) is not None

    def test_super_admin_sees_other_company_tournament(
        self, client, other_tournament, super_admin_headers
    ):
        headers, _ = super_admin_headers
        response = _call(client, "get", f"/api/tournament/{other_tournament.id}", headers)
        assert response.status_code == 200
