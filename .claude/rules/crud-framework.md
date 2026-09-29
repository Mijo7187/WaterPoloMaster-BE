---
paths:
  - "app/common/**"
  - "app/features/**"
---

# Generic CRUD framework (`app/common/crud/`)

Best current reference entity: **`membership`** (hooks calling repository methods, `ValidationException`,
readable 409 before the DB constraint, `scope_by_company=True`, custom DELETE). Simple one: `season`.
Manual-router reference: `group`, `wallet`.

## Pieces

| Piece | Key API |
|---|---|
| `CrudRepository[M]` | `create`, `get_by_id(id, company_id=None)`, `list_query(filters, company_id)`, `get_list` → `(items, total)`, `update`, `soft_delete`; override `get_list_relations()` / `get_by_id_relations()` (independent!), `apply_create_relations` / `apply_update_relations` (M2M), `company_scope_clause(company_id)`, `get_summary(filters, company_id)` |
| `CrudService[M]` | `create(schema, current_user)`, `get_by_id`, `get_list`, `get_summary`, `update(id, schema, current_user)`, `soft_delete`; `company_scope_for(user)`, `enforce_company_read`, `enforce_company_scope`, `enforce_company_in_data` |
| `CrudHooks` | `pre_create(data, db, current_user) -> dict`, `post_create(obj, db, current_user)`, `pre_update(obj_id, data, db, current_user) -> dict`, `post_update(obj, db, current_user)` |
| `create_crud_router(...)` | `prefix, tag, service_factory, create_conf, update_conf, get_by_id_conf, get_list_conf, enable_soft_delete=False, deactivate_dependencies=[], scope_by_company=False, id_type=int` → `APIRouter` you can extend |
| `CrudEndpointConfig` | `schema`, `dependencies`, `response_schema` (create only: return the object instead of `[id]`) |
| `CrudListEndpointConfig` | `schema`, `filters`, `summary_schema`, `dependencies` |
| `CrudFilters` | `page` (1), `size` (20, ≤100), `order_by`, `order_dir` (asc/desc), `created_at__gte/lte` |

Generated endpoints: `POST /`, `GET /`, `GET /{id}`, `PUT /{id}` (+ `POST /{id}/deactivate` with soft delete).
Hard delete is always a custom endpoint on the returned router (see `season_router.py`).

## Filters — `field__operator`

`eq` (default), `like`, `ilike`, `gte`, `lte`, `gt`, `lt`, `neq`, `isnull`; a comma-separated string → `IN`.
Declare every accepted param on `XFilters(CrudFilters)` as `Optional[...] = None` — undeclared params are ignored
by FastAPI, and a declared field that isn't a model column is silently skipped by `_apply_filter`.
Filters that aren't simple columns (e.g. `wallet_id` on payment, date overlap on contracts by season) → handle them
in an overridden `list_query` in the repository, never in the router.

## Hooks — how to write them

- Pure functions at module level, named `_x_pre_create` etc.; compose small checks inside one hook.
- Hooks get `db` — use a repository for lookups: `XRepository(db).get_selection(id)`.
- Convert enums to values when the column is a plain string (`data["status"] = data["status"].value`).
- Merge-then-validate on update: a PATCH-style payload may hold only one field; load the existing row and validate
  the merged state (see `_validate_term_months` in membership).
- Raise `ValidationException(["field"], "msg")` for field-level business errors (FE pins them to the field),
  `ConflictException` for duplicates, `NotFoundException` for missing references, `ForbiddenException` for scope.

## Responses

Always `success_response(data=..., messages=[...], status_code=...)`; list shape
`{items, pagination: {total, page, size, pages}, summary}`. `model_validate(obj).model_dump()` through a schema —
never return ORM objects. Custom endpoints on a CRUD router re-read with `service.get_by_id` to get eager-loaded
relations before serializing.

## Summaries

See skill `/add-list-summary`: override `get_summary` in the repository aggregating over
`self.list_query(filters, company_id)`, add `XSummary(CrudSummarySchema)`, pass `summary_schema=` on `get_list_conf`,
document the shape in `docs/frontend/`.
