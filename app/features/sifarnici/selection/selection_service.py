# ============================================
# SELECTION SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ForbiddenException
from app.features.sifarnici.selection.selection_model import Selection
from app.features.sifarnici.selection.selection_repository import SelectionRepository
from app.features.users.users_models import User, UserRole


def _enforce_company_scope_on_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    """
    Row-level authorization: a non-SUPER_ADMIN user may only update selections
    belonging to their own company. See training_service for the canonical form.
    """
    if current_user is None:
        return data

    if UserRole.SUPER_ADMIN.value in (current_user.roles or []):
        return data

    existing = db.query(Selection).filter(Selection.id == obj_id).first()
    if existing and existing.company_id != current_user.company_id:
        raise ForbiddenException("You can only edit selections in your own company.")

    return data


class SelectionService(CrudService[Selection]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            SelectionRepository(db),
            hooks=CrudHooks(pre_update=_enforce_company_scope_on_update),
        )
