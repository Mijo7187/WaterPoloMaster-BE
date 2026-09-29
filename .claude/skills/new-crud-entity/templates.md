# CRUD entity templates

Placeholders: `{name}` snake_case, `{Name}` PascalCase, `{NAME}` UPPER_SNAKE. Example fields marked `# EXAMPLE`.
Reference implementations: `membership` (hooks + scoping), `season` (simple + hard delete), `group` (parent scope).

## {name}_model.py

```python
# ============================================
# {NAME} MODEL - Database Table
# ============================================
# <why this table exists, what is unique, who owns a row>
# ============================================

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db.base import Base


class {Name}(Base):
    __tablename__ = "{name}"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_{name}_company_name"),  # EXAMPLE
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # EXAMPLE
    is_active = Column(Boolean, nullable=False, default=True)  # EXAMPLE (soft delete)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company")

    def __repr__(self):
        return f"<{Name}(id={self.id}, name='{self.name}')>"
```

## {name}_schemas.py

```python
# ============================================
# {NAME} SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.company.company_schemas import CompanyListResponse


class {Name}Create(CrudCreateSchema):
    company_id: int
    name: str  # EXAMPLE
    is_active: bool = True  # EXAMPLE


class {Name}Update(CrudUpdateSchema):
    company_id: Optional[int] = None
    name: Optional[str] = None  # EXAMPLE
    is_active: Optional[bool] = None  # EXAMPLE


class {Name}ListResponse(CrudResponseSchema):
    """Lightweight projection for lists and for nesting in other responses."""

    company_id: int
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class {Name}Response(CrudResponseSchema):
    """Detail view — nested relations must be eager-loaded in get_by_id_relations."""

    company_id: int
    name: str
    is_active: bool
    company: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class {Name}Filters(CrudFilters):
    """
    ?name__ilike=...  ?is_active=true
    Pagination (inherited): page (1), size (20, max 100), order_by, order_dir
    """

    company_id: Optional[int] = None
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
```

## {name}_repository.py

```python
# ============================================
# {NAME} REPOSITORY - Database Operations
# ============================================

from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.{name}.{name}_model import {Name}


class {Name}Repository(CrudRepository[{Name}]):
    def __init__(self, db: Session):
        super().__init__(db, {Name})

    def get_by_id_relations(self):
        return [lambda: selectinload({Name}.company)]

    # ── Lookups used by service hooks ───────────────

    def find_duplicate(
        self, company_id: int, name: str, exclude_id: Optional[int] = None
    ) -> Optional[{Name}]:
        q = self.db.query({Name}).filter(
            {Name}.company_id == company_id, {Name}.name == name
        )
        if exclude_id is not None:
            q = q.filter({Name}.id != exclude_id)
        return q.first()
```

Parent-scoped entity (no `company_id` column) — override instead of adding the column:

```python
    def company_scope_clause(self, company_id: int):
        return {Name}.parent_id.in_(select(Parent.id).where(Parent.company_id == company_id))
```

## {name}_service.py

```python
# ============================================
# {NAME} SERVICE - Business Logic
# ============================================

from typing import Optional

from sqlalchemy.orm import Session

from app.common.crud.crud_schemas import CrudHooks
from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import ConflictException
from app.features.{name}.{name}_model import {Name}
from app.features.{name}.{name}_repository import {Name}Repository
from app.features.users.users_models import User


def _assert_unique(db, company_id, name, exclude_id: Optional[int] = None) -> None:
    """Readable 409 before the DB constraint turns it into an IntegrityError."""
    if company_id is None or name is None:
        return
    if {Name}Repository(db).find_duplicate(company_id, name, exclude_id=exclude_id):
        raise ConflictException("A {name} with this name already exists in this company.")


def _{name}_pre_create(data: dict, db, current_user: Optional[User] = None) -> dict:
    _assert_unique(db, data.get("company_id"), data.get("name"))
    return data


def _{name}_pre_update(
    obj_id: int, data: dict, db, current_user: Optional[User] = None
) -> dict:
    # Validate the MERGED row: a partial update may carry only one of the fields.
    existing = {Name}Repository(db).get_by_id(obj_id)
    if existing is None:
        return data  # CrudService raises NotFoundException after the hook
    _assert_unique(
        db,
        data.get("company_id", existing.company_id),
        data.get("name", existing.name),
        exclude_id=obj_id,
    )
    return data


class {Name}Service(CrudService[{Name}]):
    def __init__(self, db: Session):
        super().__init__(
            db,
            {Name}Repository(db),
            hooks=CrudHooks(pre_create=_{name}_pre_create, pre_update=_{name}_pre_update),
        )
```

Company scoping is NOT done here — `scope_by_company=True` on the router handles list/get/update/deactivate and
foreign `company_id` in payloads.

## {name}_router.py

```python
# ============================================
# {NAME} ROUTER - API Endpoints
# ============================================

from fastapi import Depends

from app.common.crud.crud_router import create_crud_router
from app.common.crud.crud_schemas import CrudEndpointConfig, CrudListEndpointConfig
from app.core.permissions import Permission, check_permissions
from app.features.{name}.{name}_schemas import (
    {Name}Create,
    {Name}Filters,
    {Name}ListResponse,
    {Name}Response,
    {Name}Update,
)
from app.features.{name}.{name}_service import {Name}Service

router = create_crud_router(
    prefix="/{name}",
    tag="{name}",
    service_factory=lambda db: {Name}Service(db),
    create_conf=CrudEndpointConfig(
        schema={Name}Create,
        dependencies=[Depends(check_permissions(Permission.CREATE_{NAME}))],
    ),
    update_conf=CrudEndpointConfig(
        schema={Name}Update,
        dependencies=[Depends(check_permissions(Permission.UPDATE_{NAME}))],
    ),
    get_by_id_conf=CrudEndpointConfig(
        schema={Name}Response,
        dependencies=[Depends(check_permissions(Permission.VIEW_{NAME}))],
    ),
    get_list_conf=CrudListEndpointConfig(
        schema={Name}ListResponse,
        filters={Name}Filters,
        dependencies=[Depends(check_permissions(Permission.VIEW_{NAME}S))],
    ),
    enable_soft_delete=True,
    deactivate_dependencies=[Depends(check_permissions(Permission.DELETE_{NAME}))],
    scope_by_company=True,
)
```

## main.py + alembic/env.py

```python
# app/main.py — with the other feature imports
from app.features.{name}.{name}_router import router as {name}_router
# … with the other registrations
app.include_router({name}_router, prefix="/api")

# alembic/env.py — with the other model imports
from app.features.{name}.{name}_model import {Name}  # noqa: F401
```

## {name}_test.py

```python
# ============================================
# {NAME} TESTS
# ============================================

from unittest.mock import patch

import pytest

from app.features.users.users_models import UserRole

URL = "/api/{name}/"


def _call(client, method, url, headers, **kwargs):
    with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
        mock_get.return_value = headers["Authorization"].split(" ")[1]
        return getattr(client, method)(url, headers=headers, **kwargs)


@pytest.fixture()
def own(auth_headers):
    headers, user, company = auth_headers
    return {"headers": headers, "user": user, "company": company}


@pytest.fixture()
def other_company(create_company):
    return create_company(name="Other Club")


@pytest.fixture()
def player_headers(own, create_user, mock_redis):
    from app.core.security import create_access_token

    user = create_user(
        email="player@test.com",
        username="player",
        roles=[UserRole.PLAYER],
        company_id=own["company"].id,
    )
    token = create_access_token(
        {"sub": user.email, "user_id": user.id, "roles": user.roles, "type": "access"}
    )
    mock_redis["store_access_token"](user.id, token)
    return {"Authorization": f"Bearer {token}"}


def _create(client, headers, company_id, name="U15 plan"):
    return _call(client, "post", URL, headers, json={"company_id": company_id, "name": name})


class TestCreate:
    def test_happy_path_201(self, client, own):
        response = _create(client, own["headers"], own["company"].id)
        assert response.status_code == 201, response.text

    def test_duplicate_name_409(self, client, own):
        assert _create(client, own["headers"], own["company"].id).status_code == 201
        assert _create(client, own["headers"], own["company"].id).status_code == 409

    def test_missing_required_field_422(self, client, own):
        response = _call(client, "post", URL, own["headers"], json={"company_id": own["company"].id})
        assert response.status_code == 422

    def test_other_company_id_403(self, client, own, other_company):
        assert _create(client, own["headers"], other_company.id).status_code == 403

    def test_role_without_permission_403(self, client, own, player_headers):
        assert _create(client, player_headers, own["company"].id).status_code == 403

    def test_no_token_401(self, client, own):
        response = client.post(URL, json={"company_id": own["company"].id, "name": "x"})
        assert response.status_code in (401, 403)


class TestReadAndScope:
    def test_list_only_own_company(self, client, own, other_company, super_admin_headers):
        sa_headers, _ = super_admin_headers
        assert _create(client, own["headers"], own["company"].id, "Mine").status_code == 201
        assert _create(client, sa_headers, other_company.id, "Theirs").status_code == 201

        response = _call(client, "get", URL, own["headers"])
        assert response.status_code == 200
        names = {i["name"] for i in response.json()["data"]["items"]}
        assert names == {"Mine"}

    def test_get_other_company_row_denied(self, client, own, other_company, super_admin_headers):
        sa_headers, _ = super_admin_headers
        assert _create(client, sa_headers, other_company.id, "Theirs").status_code == 201
        theirs = _call(client, "get", URL, sa_headers).json()["data"]["items"][0]

        response = _call(client, "get", f"{URL}{theirs['id']}", own["headers"])
        assert response.status_code in (403, 404)

    def test_super_admin_sees_all(self, client, own, other_company, super_admin_headers):
        sa_headers, _ = super_admin_headers
        _create(client, own["headers"], own["company"].id, "Mine")
        _create(client, sa_headers, other_company.id, "Theirs")

        response = _call(client, "get", URL, sa_headers)
        assert response.json()["data"]["pagination"]["total"] == 2


class TestUpdate:
    def test_rename_to_existing_name_409(self, client, own):
        _create(client, own["headers"], own["company"].id, "A")
        _create(client, own["headers"], own["company"].id, "B")
        items = _call(client, "get", URL, own["headers"]).json()["data"]["items"]
        b = next(i for i in items if i["name"] == "B")

        response = _call(client, "put", f"{URL}{b['id']}", own["headers"], json={"name": "A"})
        assert response.status_code == 409

    def test_partial_update_200(self, client, own):
        _create(client, own["headers"], own["company"].id, "A")
        row = _call(client, "get", URL, own["headers"]).json()["data"]["items"][0]

        response = _call(client, "put", f"{URL}{row['id']}", own["headers"], json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "A"
```
