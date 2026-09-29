# ============================================
# TOURNAMENT TESTS
# ============================================

import pytest
from datetime import date

from app.features.tournament.tournament_service import TournamentService
from app.features.tournament.tournament_repository import TournamentRepository
from app.features.tournament.tournament_schemas import (
    TournamentCreate,
    TournamentFilters,
    TournamentUpdate,
)
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


# ============================================
# GROUP LINK — the squad a tournament belongs to
# ============================================
# group_id is optional, and when it is set it — not from_date — decides the
# season. The two columns can therefore never disagree.

class TestTournamentGroupLink:

    def test_group_decides_the_season(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        season = create_season(company_id=company.id)
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TournamentService(db_session)
        tournament = service.create(TournamentCreate(
            company_id=company.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
            group_id=group.id,
        ))

        assert tournament.group_id == group.id
        assert tournament.season_id == group.season_id

    def test_group_of_the_academy_works_for_a_member_club(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        """The club has no season of its own — the academy owns it. The plain
        from_date lookup would raise here; going through the group resolves it
        against the academy instead."""
        academy = create_company(name="Academy", company_type="ACADEMY")
        club = create_company(name="Member Club", academy_id=academy.id)
        pool = create_company(name="Pool", company_type="POOL")
        season = create_season(company_id=academy.id)
        selection = create_selection(company_id=club.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TournamentService(db_session)
        tournament = service.create(TournamentCreate(
            company_id=club.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
            group_id=group.id,
        ))

        assert tournament.season_id == season.id

    def test_from_date_outside_the_groups_season_raises(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        season = create_season(company_id=company.id)  # 2026-01-01 .. 2026-12-31
        selection = create_selection(company_id=company.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TournamentService(db_session)
        with pytest.raises(BadRequestException, match="outside the group's season"):
            service.create(TournamentCreate(
                company_id=company.id,
                pool_id=pool.id,
                from_date=date(2027, 5, 1),
                to_date=date(2027, 5, 3),
                price=500,
                group_id=group.id,
            ))

    def test_group_from_another_academy_raises(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        other = create_company(name="Other Club")
        season = create_season(company_id=other.id)
        selection = create_selection(company_id=other.id)
        group = create_group(season_id=season.id, selection_id=selection.id)

        service = TournamentService(db_session)
        with pytest.raises(BadRequestException, match="same academy"):
            service.create(TournamentCreate(
                company_id=company.id,
                pool_id=pool.id,
                from_date=date(2026, 5, 1),
                to_date=date(2026, 5, 3),
                price=500,
                group_id=group.id,
            ))

    def test_moving_the_group_re_derives_the_season(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        old_season = create_season(company_id=company.id)
        new_season = create_season(
            company_id=company.id,
            name="2027 Season",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_current=False,
        )
        selection = create_selection(company_id=company.id)
        old_group = create_group(season_id=old_season.id, selection_id=selection.id)
        new_group = create_group(season_id=new_season.id, selection_id=selection.id)

        service = TournamentService(db_session)
        tournament = service.create(TournamentCreate(
            company_id=company.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
            group_id=old_group.id,
        ))
        assert tournament.season_id == old_season.id

        updated = service.update(tournament.id, TournamentUpdate(
            group_id=new_group.id, from_date=date(2027, 5, 1), to_date=date(2027, 5, 3)
        ))

        assert updated.group_id == new_group.id
        assert updated.season_id == new_season.id

    def test_filter_by_group_id(
        self, db_session, create_company, create_season, create_selection, create_group
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        season = create_season(company_id=company.id)
        u15 = create_selection(company_id=company.id, name="U15")
        u17 = create_selection(company_id=company.id, name="U17")
        u15_group = create_group(season_id=season.id, selection_id=u15.id)
        u17_group = create_group(season_id=season.id, selection_id=u17.id)

        service = TournamentService(db_session)

        def _make(group_id):
            return service.create(TournamentCreate(
                company_id=company.id,
                pool_id=pool.id,
                from_date=date(2026, 5, 1),
                to_date=date(2026, 5, 3),
                price=500,
                group_id=group_id,
            ))

        mine = _make(u15_group.id)
        _make(u17_group.id)
        open_entry = _make(None)

        repo = TournamentRepository(db_session)

        items, total = repo.get_list(filters=TournamentFilters(group_id=u15_group.id))
        assert total == 1
        assert items[0].id == mine.id
        # The squad's selection rides along on the list response.
        assert items[0].group.selection.name == "U15"

        items, _ = repo.get_list(filters=TournamentFilters(group_id__isnull=True))
        assert [i.id for i in items] == [open_entry.id]


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
