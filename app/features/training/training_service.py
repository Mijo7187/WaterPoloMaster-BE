# ============================================
# TRAINING SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.common.crud.crud_schemas import CrudHooks
from app.core.api.exceptions import ForbiddenException
from app.features.season.season_service import resolve_season_id
from app.features.training.training_model import Training
from app.features.training.training_repository import TrainingRepository
from app.features.users.users_models import User, UserRole


def _convert_enums_on_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert status enum to its string value before insert."""
    if "status" in data and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    return data


def _training_pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert enums and resolve the season from the training date before insert."""
    data = _convert_enums_on_create(data, db, current_user)
    data["season_id"] = resolve_season_id(db, data["company_id"], data["training_date"])
    return data


def _convert_enums_on_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert status enum to its string value before update."""
    if "status" in data and data["status"] is not None and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    return data


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update trainings
    that belong to their own company. SUPER_ADMIN bypasses this check.

    Reference implementation of the framework's row-level auth convention —
    every pre_update hook that needs ownership scoping follows this shape:
    read the existing row, compare to current_user, raise ForbiddenException
    on mismatch.

    When current_user is None the call is internal (test, script, background
    job) and this hook does not gate it. HTTP-facing auth is enforced upstream
    at the router via check_permissions; this hook only scopes already-
    authenticated requests to their own data.
    """
    if current_user is None:
        return data

    if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
        return data

    existing = db.query(Training).filter(Training.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit trainings in your own company.")

    return data


def _training_pre_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Compose the ownership check with the enum-conversion step."""
    data = _enforce_company_scope_on_update(obj_id, data, db, current_user)
    data = _convert_enums_on_update(obj_id, data, db, current_user)
    return data


class TrainingService(CrudService[Training]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            TrainingRepository(db),
            hooks=CrudHooks(
                pre_create=_training_pre_create,
                pre_update=_training_pre_update,
            )
        )
