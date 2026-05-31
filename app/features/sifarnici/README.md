# Sifarnici Module — Configuration Reference

> **Purpose**: This file is the single source of truth for the `app.features.sifarnici` module.
> Point Copilot here (`read app/features/sifarnici/README.md`) to give it full context.

---

## Architecture Overview

`sifarnici` is a generic CRUD module. Each entity (pool, country, city, …) follows an identical 6-file structure and inherits from shared base classes. No custom business logic is needed for basic entities — just declare the model, schemas, repository, service, and router.

### Base classes (shared by all entities)

| File | Class / Function | Role |
|---|---|---|
| `base_schemas.py` | `SifarnikBaseSchema` | Base Pydantic model — provides `name: str` (required, max 255) |
| | `SifarnikCreateSchema(SifarnikBaseSchema)` | Base create schema — inherits `name` |
| | `SifarnikUpdateSchema(BaseModel)` | Base update schema — `name: Optional[str]` (all fields optional) |
| | `SifarnikResponseSchema(SifarnikBaseSchema)` | Base response — adds `id`, `created_at`, `updated_at`, `model_config = ConfigDict(from_attributes=True)` |
| `base_repository.py` | `BaseRepository[ModelType]` | Generic SQLAlchemy repository: `create(dict)`, `get_by_id(int)`, `get_list(skip, limit)`, `update(id, dict)` |
| `base_service.py` | `BaseService[ModelType]` | Generic service layer: wraps repository, converts Pydantic → dict, raises `NotFoundException` on missing resources |
| `base_router.py` | `create_sifarnik_router(...)` | Router factory — generates 4 endpoints: `POST /`, `GET /`, `GET /{id}`, `PUT /{id}`. All responses use `success_response()` wrapper. |

### Router factory signature

```python
create_sifarnik_router(
    prefix: str,          # e.g. "/pools"
    tag: str,             # e.g. "Pools" — used in OpenAPI docs & success messages
    service_factory,      # lambda db: PoolService(db)
    create_schema,        # PoolCreate
    update_schema,        # PoolUpdate
    response_schema,      # PoolResponse
) -> APIRouter
```

---

## Existing Entities

### 1. Country (`country/`)

- **Table**: `country`
- **API**: `/api/country`
- **Tag**: `Country`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer PK | no | autoincrement |
| `name` | String(255) | no | |
| `is_active` | Boolean | no | default `True` |
| `created_at` | DateTime(tz) | no | server_default `now()` |
| `updated_at` | DateTime(tz) | yes | onupdate `now()` |

- **Relationships**: `cities` → one-to-many to `City` (back_populates="country")

### 2. City (`city/`)

- **Table**: `city`
- **API**: `/api/city`
- **Tag**: `City`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer PK | no | autoincrement |
| `name` | String(255) | no | |
| `country_id` | Integer FK → `country.id` | no | |
| `is_active` | Boolean | no | default `True` |
| `created_at` | DateTime(tz) | no | server_default `now()` |
| `updated_at` | DateTime(tz) | yes | onupdate `now()` |

- **Relationships**: `country` → many-to-one to `Country` (back_populates="cities")

### 3. Pool (`pool/`)

- **Table**: `pool`
- **API**: `/api/pool`
- **Tag**: `Pool`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer PK | no | autoincrement |
| `name` | String(255) | no | |
| `address` | String(500) | yes | |
| `address_number` | String(50) | yes | |
| `phone` | String(50) | yes | |
| `email` | String(255) | yes | |
| `city_id` | Integer FK → `city.id` | yes | |
| `country_id` | Integer FK → `country.id` | yes | |
| `is_active` | Boolean | no | default `True` |
| `created_at` | DateTime(tz) | no | server_default `now()` |
| `updated_at` | DateTime(tz) | yes | onupdate `now()` |

- **Relationships**: `city` → City, `country` → Country

---

## How to Add a New Entity

Follow these steps exactly:

### Step 1 — Create the folder

```
app/features/sifarnici/<entity>/
    __init__.py          # empty
    <entity>_model.py
    <entity>_schemas.py
    <entity>_repository.py
    <entity>_service.py
    <entity>_router.py
```

### Step 2 — Model (`<entity>_model.py`)

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.db.base import Base

class EntityName(Base):
    __tablename__ = "entity_names"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # ... add custom columns here ...

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Step 3 — Schemas (`<entity>_schemas.py`)

```python
from typing import Optional
from app.features.sifarnici.base_schemas import (
    SifarnikCreateSchema, SifarnikUpdateSchema, SifarnikResponseSchema,
)

class EntityCreate(SifarnikCreateSchema):
    is_active: Optional[bool] = True
    # ... add custom fields ...

class EntityUpdate(SifarnikUpdateSchema):
    is_active: Optional[bool] = None
    # ... add custom fields (all Optional) ...

class EntityResponse(SifarnikResponseSchema):
    is_active: bool = True
    # ... add custom fields ...
```

### Step 4 — Repository (`<entity>_repository.py`)

```python
from sqlalchemy.orm import Session
from app.features.sifarnici.base_repository import BaseRepository
from app.features.sifarnici.<entity>.<entity>_model import EntityName

class EntityRepository(BaseRepository[EntityName]):
    def __init__(self, db: Session):
        super().__init__(db, EntityName)
```

### Step 5 — Service (`<entity>_service.py`)

```python
from sqlalchemy.orm import Session
from app.features.sifarnici.base_service import BaseService
from app.features.sifarnici.<entity>.<entity>_model import EntityName
from app.features.sifarnici.<entity>.<entity>_repository import EntityRepository

class EntityService(BaseService[EntityName]):
    def __init__(self, db: Session):
        super().__init__(db, EntityRepository(db))
```

### Step 6 — Router (`<entity>_router.py`)

```python
from app.features.sifarnici.base_router import create_sifarnik_router
from app.features.sifarnici.<entity>.<entity>_schemas import EntityCreate, EntityUpdate, EntityResponse
from app.features.sifarnici.<entity>.<entity>_service import EntityService

router = create_sifarnik_router(
    prefix="/<entity_plural>",
    tag="EntityPlural",
    service_factory=lambda db: EntityService(db),
    create_schema=EntityCreate,
    update_schema=EntityUpdate,
    response_schema=EntityResponse,
)
```

### Step 7 — Register

1. **`app/main.py`** — add import and `app.include_router(router, prefix="/api")`
2. **`alembic/env.py`** — add `from app.features.sifarnici.<entity>.<entity>_model import EntityName  # noqa: F401`
3. Run: `alembic revision --autogenerate -m "add_<entity>_table"` then `alembic upgrade head`

> **Tip**: If the new table has a `Boolean` NOT NULL column and existing rows would be affected, add `server_default=sa.text('true')` in the generated migration before running `alembic upgrade head`.

---

## Key Dependencies

- **ORM**: SQLAlchemy (declarative base at `app.core.db.base.Base`)
- **Validation**: Pydantic v2 (`model_dump`, `model_validate`, `ConfigDict`)
- **API**: FastAPI (`APIRouter`, `Depends`)
- **DB Session**: `app.core.db.database.get_db`
- **Response wrapper**: `app.core.api.responses.success_response`
- **Errors**: `app.core.api.exceptions.NotFoundException`
- **Migrations**: Alembic (autogenerate from Base.metadata)
