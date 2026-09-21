# ============================================
# SEASON SERVICE - Business Logic
# ============================================

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.features.season.season_model import Season
from app.features.season.season_repository import SeasonRepository
from app.features.users.users_models import User, UserRole


def resolve_season_id(db, company_id: int, d: date) -> int:
    """
    Resolve the season a training/tournament belongs to from its date.

    Looks up the company's season whose date range contains `d`. Raises
    BadRequestException if no such season exists — seasons are created
    explicitly by admins, not on the fly. (Replaces the old
    quarter_service.resolve_quarter_id.)
    """
    season = (
        db.query(Season)
        .filter(
            Season.company_id == company_id,
            Season.start_date <= d,
            Season.end_date >= d,
        )
        .first()
    )
    if not season:
        raise BadRequestException("You have to add a Season covering this date")
    return season.id


def _enforce_single_current_on_create(
    data: dict, db, current_user: Optional[User] = None
) -> dict:
    """A company has at most one current season — clear the others first."""
    if data.get("is_current") and data.get("company_id"):
        SeasonRepository(db).clear_current_for_company(data["company_id"])
    return data


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update seasons
    that belong to their own company. SUPER_ADMIN bypasses this check.

    When current_user is None the call is internal (test, script, background
    job) and this hook does not gate it. HTTP-facing auth is enforced upstream
    at the router via check_permissions; this hook only scopes already-
    authenticated requests to their own data.
    """
    if current_user is None:
        return data

    if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
        return data

    existing = db.query(Season).filter(Season.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit seasons in your own company.")

    return data


def _season_pre_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """Compose the ownership check with the single-current-season rule."""
    data = _enforce_company_scope_on_update(obj_id, data, db, current_user)

    if data.get("is_current"):
        existing = db.query(Season).filter(Season.id == obj_id).first()
        company_id = data.get("company_id") or (existing.company_id if existing else None)
        if company_id:
            SeasonRepository(db).clear_current_for_company(company_id, except_id=obj_id)

    return data


class SeasonService(CrudService[Season]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            SeasonRepository(db),
            hooks=CrudHooks(
                pre_create=_enforce_single_current_on_create,
                pre_update=_season_pre_update,
            ),
        )

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(Season, obj_id)
        if not obj:
            raise NotFoundException("Season not found")
        self.db.delete(obj)
        self.db.commit()
