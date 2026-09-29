# Architecture & layering

```
HTTP ─▶ router ──Depends(check_permissions)──▶ service ──hooks──▶ repository ──▶ SQLAlchemy ──▶ DB
          │  (shape request/response,              │ (business rules,        │ (all queries, commits,
          │   success_response, status codes)      │  orchestration,         │  eager loading, filters,
          └── Pydantic schemas in / out ◀──────────┘  AppExceptions)         │  company_scope_clause, summary)
```

| Layer | Owns | Must NOT |
|---|---|---|
| `*_router.py` | path ops, `dependencies=[Depends(check_permissions(...))]`, `current_user`, `success_response`, response schema `model_validate(...).model_dump()` | `db.query/add/commit/execute`, business rules, `HTTPException` for domain errors |
| `*_service.py` | rules, validation across entities, hooks, transactions spanning repos, raising `AppException`s | raw SQL, building queries inline (new code) |
| `*_repository.py` | every query, `commit`/`refresh`, `get_list_relations` / `get_by_id_relations`, `apply_*_relations`, `company_scope_clause`, `get_summary` | business decisions, HTTP concerns |
| `*_schemas.py` | `XCreate`, `XUpdate` (all Optional), `XResponse`, `XListResponse`, `XFilters`, `XSummary` | ORM imports beyond typing |
| `*_model.py` | table, constraints, relationships, domain enums | logic beyond trivial properties |

Why: the router factory, scoping and summaries all assume queries live in the repository
(`list_query` is shared by list and summary so totals always match the rows). A query in a service or router
silently skips company scoping and eager-loading.

## Cross-feature calls

- A service may instantiate another feature's **service or repository** for orchestration
  (e.g. contract → `GroupService.get_or_create`, training → `resolve_group_season_id`). Keep it one-directional;
  if two features need each other, move the shared helper to the lower-level feature or `app/utils/`.
- Watch circular imports: `crud_router` and `permissions` import auth/users lazily inside functions — do the same
  when a new import would cycle.

## Naming

- Feature folders and files **snake_case singular** (`contract_installment/contract_installment_service.py`).
  Legacy plurals exist (`users`, `training_users`, `tournament_users`, `users_models.py`) — don't rename, don't copy.
- Table names singular (`__tablename__ = "group"` — reserved word, SQLAlchemy quotes it; raw SQL must write `"group"`).
- Routers: `prefix="/{name}"` singular, registered in `main.py` with `prefix="/api"`.
- Enums: `class XStatus(str, enum.Enum)` in the model file; values are what the FE receives — changing one is a breaking API change.

## Known deviations (exist — don't replicate; fix only when asked or when touching that code for a reason)

1. **Queries in services**: `db.query(...)`, `db.get`, `db.commit` appear in ~15 services (contract 20×, season,
   wallet, tournament, …) and in hook functions (`_enforce_company_scope_on_update`). New code: add a repository
   method instead. Hooks receive `db` — instantiate the repository there: `SeasonRepository(db).get_by_id(obj_id)`.
2. **Per-feature ownership hooks** (`_enforce_company_scope_on_update` in training/season) predate the framework's
   `scope_by_company=True` + `enforce_company_*` helpers. New entities use the framework helpers.
3. **Create response is a list**: the CRUD factory returns `data={obj.id}` (a Python *set*) → JSON `[id]`.
   The FE types it as `number`. Use `response_schema=` on `create_conf` for new entities if the FE needs the object;
   don't "fix" the set without coordinating with the FE.
4. Manual list routers (`group`, `group_user`, `wallet`) omit the `summary` key; CRUD lists always send it.
5. `CompanyType` has no `TOURNAMENT`, the FE enum does.
6. `.github/copilot-instructions.md` is empty; `app/features/auth/README.md` shows `HTTPException` examples — these
   rules win.
7. `expense_category_router.py` / `income_category_router.py` query the DB directly in the router;
   `company_model.py` imports `validator` from `pydantic.v1` (unused-looking); `print()` in `main.py`,
   `core/db/database.py`, `exception_handlers.py`. The edit guard blocks *new* occurrences only.
8. Local interpreter produced `cpython-314` caches while CI runs Python 3.12 — avoid 3.13+-only syntax/stdlib.
