# ============================================
# CRUD - Generic Base Service
# ============================================
# Reusable service layer with standard CRUD logic.
# Supports lifecycle hooks and many-to-many relations.
#
# USAGE (simple):
#   class PoolService(CrudService[Pool]):
#       def __init__(self, db: Session):
#           super().__init__(db, PoolRepository(db))
#
# USAGE (with hooks):
#   class TrainingService(CrudService[Training]):
#       def __init__(self, db: Session):
#           hooks = CrudHooks(
#               pre_create=lambda data, db, current_user: {**data, "status": data["status"].value},
#           )
#           super().__init__(db, TrainingRepository(db), hooks=hooks)
#
# Hook signatures (all receive current_user as the last positional argument):
#   pre_create(data: dict, db: Session, current_user: Optional[User]) -> dict
#   post_create(obj: Model, db: Session, current_user: Optional[User]) -> None
#   pre_update(obj_id: int, data: dict, db: Session, current_user: Optional[User]) -> dict
#   post_update(obj: Model, db: Session, current_user: Optional[User]) -> None
#
# Row-level authorization (e.g. "only allow editing rows in your own company")
# belongs in pre_update — raise ForbiddenException from the hook.
#
# For many-to-many relations, override apply_create_relations / apply_update_relations
# in the repository subclass — not in the service.
# ============================================

from sqlalchemy.orm import Session
from typing import Optional, List, TypeVar, Generic, Any, Dict, Tuple

from pydantic import BaseModel

from app.core.api.exceptions import ForbiddenException, NotFoundException
from app.core.db.base import Base
from app.common.crud.crud_repository import CrudRepository
from app.common.crud.crud_schemas import CrudFilters, CrudHooks

ModelType = TypeVar("ModelType", bound=Base)


class CrudService(Generic[ModelType]):
    """
    Generic service with standard CRUD business logic.

    Responsibilities:
    - Lifecycle hooks (pre/post create/update) — receive current_user
    - NotFoundException raising

    NOT responsible for:
    - Relations (repository owns this)
    - model_dump (repository owns this)
    - Pagination (repository owns this)
    - SQLAlchemy queries (repository owns this)
    """

    def __init__(
        self,
        db: Session,
        repository: CrudRepository[ModelType],
        hooks: Optional[CrudHooks] = None,
    ):
        self.db = db
        self.repository = repository
        self.hooks = hooks or CrudHooks()

    # ── CRUD operations ─────────────────────────────

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> ModelType:
        data = schema.model_dump()
        if self.hooks.pre_create:
            data = self.hooks.pre_create(data, self.db, current_user)
        obj = self.repository.create(data)
        if self.hooks.post_create:
            self.hooks.post_create(obj, self.db, current_user)
        return obj

    def get_by_id(self, obj_id: int, company_id: Optional[int] = None) -> ModelType:
        obj = self.repository.get_by_id(obj_id, company_id=company_id)
        if not obj:
            raise NotFoundException("Resource not found")
        return obj

    def get_list(self, filters: CrudFilters, company_id: Optional[int] = None) -> Tuple[List[ModelType], int]:
        return self.repository.get_list(filters=filters, company_id=company_id)

    def update(self, obj_id: int, schema: BaseModel, current_user: Optional[Any] = None) -> ModelType:
        data = schema.model_dump(exclude_unset=True)
        if self.hooks.pre_update:
            data = self.hooks.pre_update(obj_id, data, self.db, current_user)
        obj = self.repository.update(obj_id, data)
        if not obj:
            raise NotFoundException("Resource not found")
        if self.hooks.post_update:
            self.hooks.post_update(obj, self.db, current_user)
        return obj

    def soft_delete(self, obj_id: int, company_id: Optional[int] = None) -> ModelType:
        self.get_by_id(obj_id, company_id=company_id)
        obj = self.repository.soft_delete(obj_id)
        if not obj:
            raise NotFoundException("Resource not found")
        return obj

    # ── Company scoping ─────────────────────────────

    @staticmethod
    def company_scope_for(current_user: Optional[Any]) -> Optional[int]:
        """
        Which company a request is restricted to.
        None → unrestricted (SUPER_ADMIN, or internal call without a user).
        """
        from app.core.permissions import is_super_admin

        if current_user is None:
            return None
        if is_super_admin(current_user):
            return None
        return current_user.company_id

    def _enforce_company(self, obj_id: Any, current_user: Optional[Any], message: str) -> None:
        """
        Guard one row against the caller's company scope.

        Missing row → NotFoundException. Row that exists but belongs to another
        company → ForbiddenException. The second lookup only runs on the failure
        path, so the happy path stays a single query.
        """
        company_id = self.company_scope_for(current_user)
        if company_id is None:
            return
        if self.repository.get_by_id(obj_id, company_id=company_id) is not None:
            return
        if self.repository.get_by_id(obj_id) is None:
            raise NotFoundException("Resource not found")
        raise ForbiddenException(message)

    def enforce_company_read(self, obj_id: Any, current_user: Optional[Any]) -> None:
        """Read guard — GET /{id}."""
        self._enforce_company(
            obj_id, current_user, "You can only view records in your own company."
        )

    def enforce_company_scope(self, obj_id: Any, current_user: Optional[Any]) -> None:
        """Write guard — update, deactivate, delete."""
        self._enforce_company(
            obj_id, current_user, "You can only manage records in your own company."
        )

    def enforce_company_in_data(self, data: dict, current_user: Optional[Any]) -> None:
        """
        Non-SUPER_ADMIN users may not create a row in, or move a row to,
        another company. Applies to create and update payloads.
        """
        company_id = self.company_scope_for(current_user)
        if company_id is None or "company_id" not in data:
            return
        if data["company_id"] != company_id:
            raise ForbiddenException("You can only manage records in your own company.")
