# ============================================
# COMPANY SCHEMAS - Data Validation
# ============================================

from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field
from typing import Optional

from app.common.crud.crud_schemas import CrudResponseSchema, CrudUpdateSchema
from app.features.company.company_model import CompanyType
from app.features.wallet.wallet_schemas import WalletResponse
from app.common.crud import CrudFilters,CrudCreateSchema
from app.features.sifarnici.city.city_schemas import CityResponse
from app.features.sifarnici.country.country_schemas import CountryResponse


class CompanyCreate(CrudCreateSchema):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    address: str = Field(..., max_length=500)
    city_id: int
    country_id: int
    phone_number: str = Field(..., max_length=50)
    email: EmailStr
    company_type: CompanyType


class CompanyUpdate(CrudUpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    address: Optional[str] = Field(None, max_length=500)
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    phone_number: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    company_type: Optional[CompanyType] = None


class CompanyListResponse(CrudResponseSchema):
    """Lightweight schema for list view — includes nested city and country."""

    name: str
    is_active: bool
    company_type: str
    city: Optional[CityResponse] = None
    country: Optional[CountryResponse] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CompanyResponse(CrudResponseSchema):
    """Full schema for get by id — includes all fields."""

    name: str
    is_active: bool
    address: Optional[str] = None
    city: Optional[CityResponse] = None
    country: Optional[CountryResponse] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    company_type: str
    w_id: Optional[UUID] = None
    w: Optional[WalletResponse] = Field(None, validation_alias="wallet")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CompanyFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    email__ilike: Optional[str] = None
    phone_number__ilike: Optional[str] = None
    address__ilike: Optional[str] = None
    company_type: Optional[CompanyType] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
