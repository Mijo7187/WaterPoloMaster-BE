# ============================================
# EXERCISE OPTION SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ForbiddenException
from app.features.sifarnici.exercise_option.exercise_option_model import ExerciseOption
from app.features.sifarnici.exercise_option.exercise_option_repository import ExerciseOptionRepository
from app.features.users.users_models import User, UserRole


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update exercise
    options belonging to their own company. See training_service for the
    canonical form.
    """
    if current_user is None:
        return data

    if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
        return data

    existing = db.query(ExerciseOption).filter(ExerciseOption.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit exercise options in your own company.")

    return data


class ExerciseOptionService(CrudService[ExerciseOption]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            ExerciseOptionRepository(db),
            hooks=CrudHooks(pre_update=_enforce_company_scope_on_update),
        )
