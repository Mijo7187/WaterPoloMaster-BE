from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Callable, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field


# ── Base Schemas ────────────────────────────────────

class CrudBaseSchema(BaseModel):
    """Base fields shared by most entities."""
    model_config = ConfigDict(from_attributes=True)


class CrudCreateSchema(CrudBaseSchema):
    """Base schema for creating an entity."""


class CrudUpdateSchema(BaseModel):
    """Base schema for updating an entity. All fields optional."""
    model_config = ConfigDict(from_attributes=True)


class CrudResponseSchema(CrudCreateSchema):
    """Base schema for returning an entity."""
    id: int
    # created_at: datetime
    # updated_at: Optional[datetime] = None


# ── Pagination + Filters ────────────────────────────

class CrudFilters(BaseModel):
    """
    Base filter schema with built-in pagination.
    All modules should extend this.

    Pagination params (page, size) are extracted automatically
    in the repository — no need to handle them in service or router.

    Field naming convention for filters:
        field__ilike  → ILIKE %value%  (case-insensitive search)
        field__like   → LIKE %value%   (case-sensitive search)
        field__gte    → >= value
        field__lte    → <= value
        field__gt     → > value
        field__lt     → < value
        field__neq    → != value
        field__isnull → IS NULL / IS NOT NULL
        field         → = value (default equality)
        field_id      → = value OR IN (1,2,3) if comma-separated
    """
    created_at__gte: Optional[datetime] = None
    created_at__lte: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    order_by: Optional[str] = None
    order_dir: str = Field(default="desc", pattern="^(asc|desc)$")

    def to_offset(self) -> int:
        return (self.page - 1) * self.size


# ── Lifecycle Hooks ─────────────────────────────────

@dataclass
class CrudHooks:
    """
    Optional lifecycle callbacks for CRUD operations.

    - pre_create / pre_update: receive (data: dict, db) → return transformed dict
    - post_create / post_update: receive (obj, db) → side-effects (no return value)
    """
    pre_create:  Optional[Callable[..., dict]] = None
    post_create: Optional[Callable[..., None]] = None
    pre_update:  Optional[Callable[..., dict]] = None
    post_update: Optional[Callable[..., None]] = None


# ── Relation Config (many-to-many) ──────────────────

@dataclass
class RelationConfig:
    """
    Declares a many-to-many field that the CRUD factory
    should handle automatically during create / update.

    - field_name:        schema field containing a list of IDs (e.g. "users_list")
    - relationship_attr: model attribute to assign to       (e.g. "users")
    - related_model:     SQLAlchemy model to query IDs from (e.g. User)
    """
    field_name: str
    relationship_attr: str
    related_model: Any  # Type[Base] — kept as Any to avoid circular imports


# ── Endpoint Configuration ──────────────────────────

class CrudEndpointConfig(BaseModel):
    """
    Config for create, update, and get_by_id endpoints.
    No filters — those are only on list endpoints.
    """
    schema: Type[BaseModel]
    dependencies: List[Any] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CrudListEndpointConfig(BaseModel):
    """
    Config for get_list endpoint.
    Extends base config with filters for field__operator querying.
    """
    schema: Type[BaseModel]
    filters: Optional[Type[CrudFilters]] = None
    dependencies: List[Any] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ── Pagination Response ─────────────────────────────

class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int
    page: int
    size: int
    pages: int


class PaginatedResponse(BaseModel):
    """Standard paginated list response."""
    items: List[Any]
    pagination: PaginationMeta