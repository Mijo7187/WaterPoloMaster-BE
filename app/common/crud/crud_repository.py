# ============================================
# CRUD - Generic Base Repository
# ============================================
# Reusable repository with standard CRUD operations.
# Every repository can inherit from this class
# and get create, get_by_id, get_list, update,
# soft_delete, and relation handling out of the box.
#
# USAGE:
#   class PoolRepository(CrudRepository[Pool]):
#       def __init__(self, db: Session):
#           super().__init__(db, Pool)
# ============================================



from sqlalchemy.orm import Session
from typing import Optional, List, Type, TypeVar, Generic, Any, Tuple

from app.core.db.base import Base
from app.common.crud.crud_schemas import CrudFilters

ModelType = TypeVar("ModelType", bound=Base)
 
 
class CrudRepository(Generic[ModelType]):
    """
    Generic repository with standard CRUD operations.
 
    Responsibilities:
    - All SQLAlchemy queries
    - Relation loading (via get_list_relations / get_by_id_relations)
    - Filter parsing (field__operator convention)
    - Pagination (page/size extracted from CrudFilters)
    - model_dump (Pydantic → dict happens here, not in service/router)
    """
 
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model
 
    # ── Override in subclass ────────────────────────
 
    def get_list_relations(self) -> List[Any]:
        """
        Selectinload options applied on get_list queries.
        Override in subclass repository.

        Example:
            return [
                lambda: selectinload(Company.city),
            ]
        """
        return []

    def get_by_id_relations(self) -> List[Any]:
        """
        Selectinload options applied on get_by_id queries.
        Independent from get_list_relations — override separately.

        Example:
            return [
                lambda: selectinload(Company.city),
                lambda: selectinload(Company.country),
            ]
        """
        return []
 
    def _apply_filter(self, q, key: str, value: Any):
        """
        Parse field__operator convention and apply SQLAlchemy filter.
 
        Supported operators:
            eq, like, ilike, gte, lte, gt, lt, neq, isnull
 
        Special cases:
            - No operator → equality (eq)
            - Comma-separated value → IN filter automatically
        """
        if "__" in key:
            field, operator = key.rsplit("__", 1)
        else:
            field, operator = key, "eq"
 
        if not hasattr(self.model, field):
            return q
 
        column = getattr(self.model, field)
 
        # Auto IN for comma-separated values
        if isinstance(value, str) and "," in value:
            values = [v.strip() for v in value.split(",")]
            return q.filter(column.in_(values))
 
        match operator:
            case "eq":
                q = q.filter(column == value)
            case "like":
                q = q.filter(column.like(f"%{value}%"))
            case "ilike":
                q = q.filter(column.ilike(f"%{value}%"))
            case "gte":
                q = q.filter(column >= value)
            case "lte":
                q = q.filter(column <= value)
            case "gt":
                q = q.filter(column > value)
            case "lt":
                q = q.filter(column < value)
            case "neq":
                q = q.filter(column != value)
            case "isnull":
                q = q.filter(column.is_(None) if value else column.isnot(None))
            case _:
                q = q.filter(column == value)
 
        return q

    def apply_create_relations(self, db_obj: ModelType, data: dict) -> None:
        """
        Hook called inside create() after the model is instantiated.
        Override in subclass to assign many-to-many relations.

        Example:
            def apply_create_relations(self, db_obj, data):
                user_ids = data.pop("users_list", [])
                if user_ids:
                    db_obj.users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        """

    def apply_update_relations(self, db_obj: ModelType, data: dict) -> None:
        """
        Hook called inside update() after scalar fields are set.
        Override in subclass to reassign many-to-many relations.

        Example:
            def apply_update_relations(self, db_obj, data):
                if "users_list" in data:
                    user_ids = data.pop("users_list")
                    db_obj.users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        """
 
    # ── CRUD operations ─────────────────────────────
 
    def create(self, data: dict) -> ModelType:
        from sqlalchemy import inspect as sa_inspect
        column_keys = {prop.key for prop in sa_inspect(self.model).mapper.iterate_properties
                       if hasattr(prop, "columns")}
        model_data = {k: v for k, v in data.items() if k in column_keys}
        db_obj = self.model(**model_data)
        self.apply_create_relations(db_obj, data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
 
    def company_scope_clause(self, company_id: int):
        """
        The rows one company may see. Override where the key is not company_id
        (Company itself) or where other companies are deliberately visible.
        """
        if not hasattr(self.model, "company_id"):
            raise AttributeError(
                f"{self.model.__name__} has no company_id column — cannot scope by company"
            )
        return self.model.company_id == company_id

    def _apply_company_scope(self, q, company_id: Optional[int]):
        """
        Restrict a query to rows of one company.
        company_id=None means "no scope" (SUPER_ADMIN or internal call).
        """
        if company_id is None:
            return q
        return q.filter(self.company_scope_clause(company_id))

    def get_by_id(self, obj_id: int, company_id: Optional[int] = None) -> Optional[ModelType]:
        q = self.db.query(self.model)
        for opt in self.get_by_id_relations():
            q = q.options(opt() if callable(opt) else opt)
        q = self._apply_company_scope(q, company_id)
        return q.filter(self.model.id == obj_id).first()

    _LIST_CONTROL_KEYS = ("page", "size", "order_by", "order_dir")

    def list_query(self, filters: CrudFilters, company_id: Optional[int] = None):
        """
        The filtered, company-scoped query behind get_list — without
        pagination, ordering or relation loading.

        get_list pages over it; get_summary aggregates over it, so a
        summary always covers exactly the rows the list is showing.
        """
        filter_dict = filters.model_dump(exclude_unset=True)
        for key in self._LIST_CONTROL_KEYS:
            filter_dict.pop(key, None)

        q = self.db.query(self.model)
        q = self._apply_company_scope(q, company_id)

        for key, value in filter_dict.items():
            if value is None:
                continue
            q = self._apply_filter(q, key, value)
        return q

    def get_summary(self, filters: CrudFilters, company_id: Optional[int] = None) -> Optional[dict]:
        """
        Aggregates over the whole filtered set (not the current page).
        Override in subclass; None means "this list has no summary".

        Example:
            row = self.list_query(filters, company_id).with_entities(
                func.count(Foo.id), func.coalesce(func.sum(Foo.amount), 0),
            ).one()
            return {"count": row[0], "total_amount": row[1]}
        """
        return None

    def get_list(self, filters: CrudFilters, company_id: Optional[int] = None) -> Tuple[List[ModelType], int]:
        """
        Returns (items, total) tuple.
        Pagination, filtering, and relation loading all handled here.
        model_dump happens here — service and router stay clean.

        company_id, when given, is always applied on top of the
        client filters — a client-sent company_id cannot widen it.
        """
        page = filters.page
        size = filters.size
        order_by_field = filters.order_by
        order_dir = filters.order_dir if "order_dir" in filters.model_fields_set else "asc"
        offset = (page - 1) * size

        q = self.list_query(filters, company_id)

        # Apply default relations
        for opt in self.get_list_relations():
            q = q.options(opt() if callable(opt) else opt)

        # Apply ordering
        if order_by_field and hasattr(self.model, order_by_field):
            col = getattr(self.model, order_by_field)
            order_clause = col.desc() if order_dir == "desc" else col.asc()
        else:
            order_clause = self.model.id.asc()

        total = q.count()
        items = q.order_by(order_clause).offset(offset).limit(size).all()
 
        return items, total
 
    def update(self, obj_id: int, data: dict) -> Optional[ModelType]:
        db_obj = self.get_by_id(obj_id)
        if not db_obj:
            return None
        for key, value in data.items():
            setattr(db_obj, key, value)
        self.apply_update_relations(db_obj, data)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
 
    def soft_delete(self, obj_id: int) -> Optional[ModelType]:
        db_obj = self.get_by_id(obj_id)
        if not db_obj:
            return None
        db_obj.is_active = False
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj