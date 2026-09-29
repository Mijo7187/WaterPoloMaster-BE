---
name: new-crud-entity
description: Scaffold a new CRUD entity end-to-end on the WaterPoloMaster framework — model, schemas, repository, service with hooks, company-scoped router, permissions, alembic env import, main.py registration and a pytest file covering scope and roles. Use when asked to "add a new entity", "scaffold a feature", "create a CRUD for X", or wire a new resource through every layer.
argument-hint: "<entity_name snake_case singular>"
---

# Scaffold CRUD entity `$0`

## 0. Confirm before generating (ask if any is unclear)

1. **Name**: singular snake_case (`$0`) → class PascalCase, table singular.
2. **Fields**: name, SQL type, nullable, default; which are FKs (target + eager-load on list / on detail?); M2M
   (target model + `xxx_list: List[int]` schema field + relationship attr).
3. **Tenant ownership**: own `company_id` column (→ `scope_by_company=True`) or scoped through a parent
   (→ override `company_scope_clause`, like `group`)? Anything global (reference data for all clubs)?
4. **Delete**: soft (`is_active` + `enable_soft_delete=True`), hard (custom `DELETE` like `season`), or none.
5. **Permissions**: names (`VIEW_{NAME}S`, `VIEW_{NAME}`, `CREATE_{NAME}`, `UPDATE_{NAME}`, `DELETE_{NAME}`) and
   **which roles** get each (product decision — ask).
6. **Business rules**: uniqueness (→ `UniqueConstraint` + readable 409), cross-field validation, derived fields.
7. **Summary** on the list? (→ `/add-list-summary` afterwards)

## 1. Generate in this order (templates: [templates.md](templates.md))

Each file only imports earlier ones.

1. `app/features/$0/__init__.py` (empty)
2. `app/features/$0/$0_model.py`
3. `app/features/$0/$0_schemas.py`
4. `app/features/$0/$0_repository.py`
5. `app/features/$0/$0_service.py`
6. Permissions → run `/add-permission` (enum + `ROLE_PERMISSIONS`) **before** the router
7. `app/features/$0/$0_router.py`
8. Register in `app/main.py`: import next to the others + `app.include_router(<name>_router, prefix="/api")`
9. Import the model in `alembic/env.py` (`# noqa: F401`) — autogenerate is blind without it
10. `app/features/$0/$0_test.py`

Drop template parts that don't apply (no FK → no relations; no uniqueness → no duplicate check).

## 2. Verify

```bash
python -m py_compile app/features/$0/*.py app/main.py app/core/permissions.py
ruff check --select F --ignore F401 app/features/$0          # if ruff is installed
pytest app/features/$0/ -q
```

## 3. Migration — hand over, don't apply

Run `/migration "add $0 table"` (autogenerate + `migration-reviewer`). Do NOT `alembic upgrade`; tell Mijo:

```bash
alembic upgrade head      # after reviewing alembic/versions/<new file>
```

## 4. Frontend

Run `/fe-contract` to write `docs/frontend/$0.md` (types, endpoints, filters) — the FE `/new-module` skill consumes it.
Report: files, endpoints (method · path · permission · scoped), schema fields, test results, migration status.
