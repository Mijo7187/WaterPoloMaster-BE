# ============================================
# TOURNAMENT TESTS
# ============================================

import pytest
from datetime import date

from app.features.tournament.tournament_service import TournamentService
from app.features.tournament.tournament_schemas import TournamentCreate
from app.features.quarter.quarter_model import QuarterType
from app.core.api.exceptions import BadRequestException


class TestTournamentServiceCreate:

    def test_create_resolves_quarter_from_from_date(
        self, db_session, create_company, create_quarter
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        # from_date May 2026 -> Q2 2026
        quarter = create_quarter(company_id=company.id, quarter_type=QuarterType.Q2, year=2026)
        service = TournamentService(db_session)
        tournament = service.create(TournamentCreate(
            company_id=company.id,
            pool_id=pool.id,
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 3),
            price=500,
        ))
        assert tournament.id is not None
        assert tournament.quarter_id == quarter.id
        assert tournament.quarter_type == QuarterType.Q2

    def test_create_without_quarter_raises(self, db_session, create_company):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        service = TournamentService(db_session)
        with pytest.raises(BadRequestException, match="You have to add Quarter for this date"):
            service.create(TournamentCreate(
                company_id=company.id,
                pool_id=pool.id,
                from_date=date(2026, 5, 1),
                to_date=date(2026, 5, 3),
                price=500,
            ))


class TestTournamentServiceGet:

    def test_get_by_id_exposes_quarter_type(
        self, db_session, create_company, create_quarter
    ):
        company = create_company()
        pool = create_company(name="Pool", company_type="POOL")
        create_quarter(company_id=company.id, quarter_type=QuarterType.Q3, year=2026)
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
