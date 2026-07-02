# ============================================
# QUARTER SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.common.crud.crud_schemas import CrudHooks
from app.core.api.exceptions import ForbiddenException, NotFoundException
from app.features.quarter.quarter_model import Quarter
from app.features.quarter.quarter_repository import QuarterRepository
from app.features.users.users_models import User, UserRole


def _convert_enums_on_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert quarter_type enum to its string value before insert."""
    if "quarter_type" in data and hasattr(data["quarter_type"], "value"):
        data["quarter_type"] = data["quarter_type"].value
    return data


def _convert_enums_on_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert quarter_type enum to its string value before update."""
    if "quarter_type" in data and data["quarter_type"] is not None and hasattr(data["quarter_type"], "value"):
        data["quarter_type"] = data["quarter_type"].value
    return data


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update quarters
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

    existing = db.query(Quarter).filter(Quarter.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit quarters in your own company.")

    return data


def _quarter_pre_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Compose the ownership check with the enum-conversion step."""
    data = _enforce_company_scope_on_update(obj_id, data, db, current_user)
    data = _convert_enums_on_update(obj_id, data, db, current_user)
    return data


class QuarterService(CrudService[Quarter]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            QuarterRepository(db),
            hooks=CrudHooks(
                pre_create=_convert_enums_on_create,
                pre_update=_quarter_pre_update,
            )
        )

    def delete(self, obj_id: int) -> None:
        obj = self.db.get(Quarter, obj_id)
        if not obj:
            raise NotFoundException("Quarter not found")
        self.db.delete(obj)
        self.db.commit()
