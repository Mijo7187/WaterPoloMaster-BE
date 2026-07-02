from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime, date
from typing import Optional, List

from app.features.users.users_models import UserRole
from app.features.wallet.wallet_schemas import WalletResponse
from app.features.company.company_schemas import CompanyResponse
from app.utils.dateUtils import parse_date
from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudUpdateSchema,
    CrudResponseSchema,
    CrudFilters,
)


class UserBase(CrudCreateSchema):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    first_name: str
    last_name: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=3, max_length=100)
    phone_number: str
    address: Optional[str] = None
    address_number: Optional[str] = None
    date_of_birth: date
    roles: List[UserRole] = [UserRole.USER]
    company_id: Optional[int] = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, v):
        return parse_date(v)

    @field_validator("company_id", mode="after")
    @classmethod
    def validate_company_id(cls, v, info):
        roles = info.data.get("roles", [])
        if UserRole.SUPER_ADMIN not in roles and v is None:
            raise ValueError("company_id is required for non-SUPER_ADMIN users")
        return v


class UserUpdate(CrudUpdateSchema):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    date_of_birth: Optional[date] = None
    roles: Optional[List[UserRole]] = None
    company_id: Optional[int] = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, v):
        return parse_date(v)


class UserListResponse(CrudResponseSchema):
    email: str
    username: Optional[str] = None
    first_name: str
    last_name: str
    is_active: bool
    roles: List[UserRole]
    company_id: Optional[int] = None
    phone_number: str
    # date_of_birth: str
    # created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserResponse(CrudResponseSchema):
    email: str
    username: Optional[str] = None
    first_name: str
    last_name: str
    is_active: bool
    phone_number: str
    address: Optional[str] = None
    address_number: Optional[str] = None
    date_of_birth: date
    roles: List[UserRole]
    company_id: Optional[int] = None
    w_id: Optional[UUID] = None
    w: Optional[WalletResponse] = Field(None, validation_alias="wallet")
    company: Optional[CompanyResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserFilters(CrudFilters):
    email__ilike: Optional[str] = None
    username__ilike: Optional[str] = None
    first_name__ilike: Optional[str] = None
    last_name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    company_id: Optional[int] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
