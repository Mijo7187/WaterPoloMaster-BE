<!--
  Loaded into every session. Keep this under ~200 lines.
  HTML comments are stripped on load — use them for human-only notes.
  Multi-step procedures live in .claude/skills/ (loaded only when invoked).
-->

# WaterPoloMaster Backend

FastAPI + SQLAlchemy 2 + Pydantic v2 backend for club/payment management. SQLite in dev, Postgres-ready. Vertical (feature-based) architecture on top of a generic CRUD framework in `app/common/crud/`.

## Commands

```bash
pip install -r requirements.txt                          # install
python run.py                                            # dev server (uvicorn, reload, host/port from .env)
pytest                                                   # tests (in-memory SQLite via conftest.py)
alembic revision --autogenerate -m "describe change"     # generate migration
alembic upgrade head                                     # apply migrations
```

No linter/formatter is configured in the repo. Don't introduce one unless asked.

## Folder map

```
app/
├── main.py                    FastAPI app, router registration
├── core/
│   ├── config.py              Settings (pydantic-settings, .env)
│   ├── db/                    Base, session, get_db dependency
│   ├── api/                   Exception handlers, success_response, exceptions
│   ├── security.py            JWT + bcrypt utilities
│   ├── permissions.py         Permission enum + check_permissions dependency factory
│   └── redis.py               Redis client (token revocation)
├── common/crud/               Generic CRUD framework (see below)
├── features/                  One folder per feature: {feature}_{model,schemas,repository,service,router}.py
│   ├── auth/  users/  company/  training/  wallet/  payment/
│   └── sifarnici/             Reference data (country, city, payment_type, expense/income category)
└── utils/                     Helpers (dateUtils.py)

alembic/                       Migrations
tests/                         Pytest suite
conftest.py                    Test DB fixtures (in-memory SQLite)
run.py                         Dev entry point
```

## Architecture rules — strict layering, never cross

- **Repositories** are the only place SQLAlchemy queries/sessions live. No business logic.
- **Services** hold business logic, orchestration, transactions. Call repositories — never the ORM directly.
- **Routers** handle HTTP only: request/response shaping, auth dependencies, status codes. No DB, no business logic.
- **Pydantic schemas** for all request/response IO. Keep ORM models and Pydantic schemas separate (never return a SQLAlchemy model directly from a route).

## Generic CRUD framework — idioms

The framework lives in [app/common/crud/](app/common/crud/). Every concrete entity follows the same shape — match it.

- **Dynamic filters**: Django-style `field__operator` syntax (`name__ilike`, `created_at__gte`, `id__in` via comma-separated). Parsed in [crud_repository.py:69](app/common/crud/crud_repository.py#L69). Supported operators: `eq` (default), `like`, `ilike`, `gte`, `lte`, `gt`, `lt`, `neq`, `isnull`. Comma-separated values auto-trigger `IN`.
- **Eager loading**: override `get_list_relations()` and `get_by_id_relations()` on the repository subclass — they are **independent** (override separately). Return a list of `lambda: selectinload(Model.relation)`. See [training_repository.py:16-28](app/features/training/training_repository.py#L16-L28).
- **Many-to-many**: override `apply_create_relations()` / `apply_update_relations()` on the repository — not the service. See [training_repository.py:30-38](app/features/training/training_repository.py#L30-L38).
- **Pagination**: `page` / `size` live on the `CrudFilters` base class ([crud_schemas.py:55-56](app/common/crud/crud_schemas.py#L55-L56)). Defaults page=1, size=20, max size=100. Extracted automatically — don't handle in service or router.
- **Endpoint configs are separated**: `create_conf`, `update_conf`, `get_by_id_conf` use `CrudEndpointConfig`; `get_list_conf` uses `CrudListEndpointConfig` (adds `filters`). Each takes a Pydantic `schema` and a list of FastAPI `dependencies`.
- **Lifecycle hooks**: `CrudHooks(pre_create, post_create, pre_update, post_update)` passed to the service `__init__`. `pre_create(data, db)` and `pre_update(obj_id, data, db)` return a transformed dict. Use for enum→value conversion, derived field computation, etc. See [training_service.py](app/features/training/training_service.py).
- **Router factory**: `create_crud_router(prefix, tag, service_factory, create_conf, update_conf, get_by_id_conf, get_list_conf, enable_soft_delete=False)`. Returns an `APIRouter` — you can attach custom endpoints to it after creation.
- **Manual router pattern** is also fine when CRUD doesn't fit (custom endpoints, computed responses). See [wallet_router.py](app/features/wallet/wallet_router.py).
- **Response envelope**: routers return `success_response(data=..., messages=[...], status_code=...)` — list endpoints return `{ items, pagination: { total, page, size, pages } }`.

### Concrete entity file naming and inheritance signatures

For an entity `Foo`, create five files under `app/features/foo/`:

| File | Inherits from |
|---|---|
| `foo_model.py` | `Base` (from `app.core.db.base`) |
| `foo_schemas.py` | `FooCreate(CrudCreateSchema)`, `FooUpdate(CrudUpdateSchema)`, `FooResponse(CrudResponseSchema)`, `FooListResponse(CrudResponseSchema)`, `FooFilters(CrudFilters)` |
| `foo_repository.py` | `FooRepository(CrudRepository[Foo])` — `super().__init__(db, Foo)` |
| `foo_service.py` | `FooService(CrudService[Foo])` — `super().__init__(db, FooRepository(db), hooks=...)` |
| `foo_router.py` | `create_crud_router(...)` factory call |

Then register the router in [app/main.py](app/main.py).

For full step-by-step scaffolding, use the `new-crud-entity` skill.

## Golden rules

- **Never hand-edit Alembic migrations.** Always autogenerate with `alembic revision --autogenerate -m "..."` and review the output. If autogenerate misses something (e.g. enum changes, server defaults), add manual ops on top — don't rewrite from scratch.
- **Ask before destructive DB ops**: dropping tables/columns, deleting rows, `alembic downgrade`, truncating, resetting `waterpolo.db`. Confirm even in dev.
- **Match existing patterns** in the file being edited rather than inventing new ones. The framework's whole point is consistency — don't add a new abstraction layer on the side.
- **Don't bypass the layering** for convenience. If a router needs a DB query, that's a sign the repository or service is missing a method — add it there.
- **Pydantic v2 syntax only** (`model_config = ConfigDict(from_attributes=True)`, `model_dump(exclude_unset=True)`, `model_validate(obj)`). Don't import from `pydantic.v1`.
- **SQLAlchemy 2.0 idioms** — but most models in this repo use the classic `Column(...)` declarative style. Match what's already there.

## Auth & authorization

Two layers of access control. Both are required for any mutating endpoint.

### Layer 1 — Coarse RBAC at the router (always)

Every endpoint gets a `dependencies=[Depends(check_permissions(Permission.X))]`. Permissions live in [app/core/permissions.py](app/core/permissions.py); add new ones to the `Permission` enum and the `ROLE_PERMISSIONS` mapping for the roles that should hold them.

Roles today (`UserRole` enum in [users_models.py:20](app/features/users/users_models.py#L20)):
- `SUPER_ADMIN` — all permissions
- `ADMIN` — most permissions, scoped to their own company in practice
- `USER` — read-only on users

`User.roles` is a JSON array — users can hold multiple roles simultaneously.

<!--
  Planned role expansion: coach, player, parent, club_admin, supplier.
  Ask before adding new roles — they need to be added to the UserRole enum,
  the ROLE_PERMISSIONS mapping, and possibly bespoke route dependencies.
-->

### Layer 2 — Row-level ownership in `pre_update` (when needed)

When a user with the right permission still shouldn't be allowed to touch a specific record (e.g. an ADMIN editing trainings outside their own company), the check belongs in a `pre_update` hook on the service. **Not in the router. Not in the repository.**

Reference implementation: [training_service.py](app/features/training/training_service.py) — `_enforce_company_scope_on_update`. Pattern:

1. Hook receives `(obj_id, data, db, current_user)`.
2. If `current_user is None` — internal call (test, script, background job), skip. HTTP auth is enforced upstream by `check_permissions`; this hook only scopes already-authenticated requests.
3. SUPER_ADMIN bypasses.
4. Fetch the existing row; compare `existing.company_id` to `current_user.company_id`.
5. Mismatch → `raise ForbiddenException("...")`.
6. Return `data` unchanged.

The framework injects `current_user` automatically when an endpoint goes through `create_crud_router`. Manual routers (e.g. [payment_router.py](app/features/payment/payment_router.py)) need to pass `current_user=Depends(get_current_active_user)` and forward it: `service.create(data, current_user=current_user)`.

### Where each kind of check lives — quick reference

| Check | Lives in |
|---|---|
| "Does this user's role grant this *kind* of action?" | Router `dependencies` via `check_permissions(Permission.X)` |
| "Can this user touch this *specific* record?" | `pre_update` (or `pre_create`) hook on the service |
| "Is the request body valid?" | Pydantic schema |
| "Does this row exist?" | `CrudService` raises `NotFoundException` automatically |
| "Is this token valid / user authenticated?" | `get_current_user` / `get_current_active_user` dependency |

### Product context (informs scoping decisions)

- **Personas**: club admins/staff, coaches, players (adult), parents of youth players, suppliers.
- **Feature areas**: payments + wallet ledger, trainings/scheduling, company/pool/supplier management, sifarnici (reference data: country, city, payment_type, expense/income category). Planned: match/game tracking, stats, attendance.
- **Company entity** is overloaded — `company_type` is `CLUB | POOL | SUPPLIER`. A "club" and a "pool" are both companies. Users belong to exactly one company via `company_id`.
