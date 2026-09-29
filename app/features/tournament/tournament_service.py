# ============================================
# TOURNAMENT SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.common.crud.crud_schemas import CrudHooks
from app.core.api.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.features.company.company_model import Company, CompanyType
from app.features.group.group_service import resolve_group_season_id
from app.features.season.season_service import resolve_season_id
from app.features.tournament.tournament_model import Tournament
from app.features.tournament.tournament_repository import TournamentRepository
from app.features.users.users_models import User, UserRole


def _validate_pool(pool_id, db) -> None:
    """Ensure pool_id references an existing company of type POOL."""
    company = db.query(Company).filter(Company.id == pool_id).first()
    if not company or company.company_type != CompanyType.POOL.value:
        raise BadRequestException("Pool must be a company of type POOL")


def _resolve_season(db, group_id, company_id, from_date) -> int:
    """The season this tournament belongs to.

    With a group, the group decides — it already carries a season, and that
    lookup is academy-aware. Without one, fall back to matching from_date
    against the company's own seasons.
    """
    if group_id is not None:
        return resolve_group_season_id(db, group_id, company_id, from_date)
    return resolve_season_id(db, company_id, from_date)


def _pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Validate the pool and resolve the season from the group (or from_date)."""
    _validate_pool(data["pool_id"], db)
    data["season_id"] = _resolve_season(
        db, data.get("group_id"), data["company_id"], data["from_date"]
    )
    return data


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update tournaments
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

    existing = db.query(Tournament).filter(Tournament.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit tournaments in your own company.")

    return data


def _resync_season_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """Re-derive season_id whenever an edit moves what it is derived from.

    season_id is never client-sent, so an edit to the group, from_date or the
    company has to re-resolve it — otherwise the stored season keeps pointing
    at the old group's season while the row has moved on.
    """
    if not {"group_id", "from_date", "company_id"} & data.keys():
        return data

    existing = db.query(Tournament).filter(Tournament.id == obj_id).first()
    if existing is None:
        return data

    data["season_id"] = _resolve_season(
        db,
        data["group_id"] if "group_id" in data else existing.group_id,
        data.get("company_id") or existing.company_id,
        data.get("from_date") or existing.from_date,
    )
    return data


def _pre_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Compose the ownership check, pool validation and season re-derivation."""
    data = _enforce_company_scope_on_update(obj_id, data, db, current_user)
    if "pool_id" in data and data["pool_id"] is not None:
        _validate_pool(data["pool_id"], db)
    data = _resync_season_on_update(obj_id, data, db, current_user)
    return data


class TournamentService(CrudService[Tournament]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            TournamentRepository(db),
            hooks=CrudHooks(
                pre_create=_pre_create,
                pre_update=_pre_update,
            )
        )

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(Tournament, obj_id)
        if not obj:
            raise NotFoundException("Tournament not found")
        self.db.delete(obj)
        self.db.commit()
