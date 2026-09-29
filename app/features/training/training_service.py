# ============================================
# TRAINING SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.common.crud.crud_schemas import CrudHooks
from app.core.api.exceptions import ForbiddenException
from app.features.group.group_service import resolve_group_season_id
from app.features.season.season_service import resolve_season_id
from app.features.training.training_model import Training
from app.features.training.training_repository import TrainingRepository
from app.features.users.users_models import User, UserRole


def _convert_enums_on_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert status enum to its string value before insert."""
    if "status" in data and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    return data


def _resolve_season(db, group_id, company_id, training_date) -> int:
    """The season this training belongs to.

    With a group, the group decides — it already carries a season, and that
    lookup is academy-aware. Without one, fall back to matching the date
    against the company's own seasons.
    """
    if group_id is not None:
        return resolve_group_season_id(db, group_id, company_id, training_date)
    return resolve_season_id(db, company_id, training_date)


def _training_pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    """Convert enums and resolve the season from the group (or date) before insert."""
    data = _convert_enums_on_create(data, db, current_user)
    data["season_id"] = _resolve_season(
        db, data.get("group_id"), data["company_id"], data["training_date"]
    )
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


def _resync_season_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """Re-derive season_id whenever an edit moves what it is derived from.

    season_id is never client-sent, so an edit to the group, the date or the
    company has to re-resolve it — otherwise the stored season keeps pointing
    at the old group's season while the row has moved on.
    """
    if not {"group_id", "training_date", "company_id"} & data.keys():
        return data

    existing = db.query(Training).filter(Training.id == obj_id).first()
    if existing is None:
        return data

    data["season_id"] = _resolve_season(
        db,
        data["group_id"] if "group_id" in data else existing.group_id,
        data.get("company_id") or existing.company_id,
        data.get("training_date") or existing.training_date,
    )
    return data


def _training_pre_update(obj_id: int, data: dict, db, current_user: Optional[User] = None) -> dict:
    """Compose the ownership check, enum conversion and season re-derivation."""
    data = _enforce_company_scope_on_update(obj_id, data, db, current_user)
    data = _convert_enums_on_update(obj_id, data, db, current_user)
    data = _resync_season_on_update(obj_id, data, db, current_user)
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
