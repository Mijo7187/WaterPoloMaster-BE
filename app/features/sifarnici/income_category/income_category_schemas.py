import uuid
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import CrudFilters, CrudResponseSchema


class IncomeCategoryResponse(CrudResponseSchema):
    label: str
    wallet_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class IncomeCategoryFilters(CrudFilters):
    wallet_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    label__ilike: Optional[str] = None
