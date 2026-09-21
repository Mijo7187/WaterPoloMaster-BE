# ============================================
# SEASON SELECTION USER SERVICE - Business Logic
# ============================================

from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.features.season_selection_user.season_selection_user_model import SeasonSelectionUser
from app.features.season_selection_user.season_selection_user_repository import (
    SeasonSelectionUserRepository,
)


class SeasonSelectionUserService(CrudService[SeasonSelectionUser]):
    def __init__(self, db: Session):
        super().__init__(db, SeasonSelectionUserRepository(db))

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> SeasonSelectionUser:
        season = self.repository.get_season(schema.season_id)
        if season is None:
            raise NotFoundException("Season not found")
        selection = self.repository.get_selection(schema.selection_id)
        if selection is None:
            raise NotFoundException("Selection not found")
        user = self.repository.get_user(schema.user_id)
        if user is None:
            raise NotFoundException("User not found")

        if not (season.company_id == selection.company_id == user.company_id):
            raise BadRequestException(
                "Season, selection and user must belong to the same company."
            )

        # None → SUPER_ADMIN or internal call, unrestricted.
        company_id = self.company_scope_for(current_user)
        if company_id is not None and season.company_id != company_id:
            raise ForbiddenException("You can only manage records in your own company.")

        if not selection.is_active:
            raise BadRequestException("Selection is not active.")

        if self.repository.exists(schema.season_id, schema.selection_id, schema.user_id):
            raise ConflictException("User is already in this selection for this season.")

        return super().create(schema, current_user=current_user)

    def delete(self, obj_id: int) -> None:
        if not self.repository.delete(obj_id):
            raise NotFoundException("Season selection user entry not found")
