---
paths:
  - "app/features/**"
  - "app/core/permissions.py"
  - "app/core/security.py"
  - "app/common/**"
---

# Auth, permissions & company scoping

Multi-tenant: several clubs share one database from go-live. **A missing scope check is a data leak between
clubs** — treat it as a blocking bug, not a nit.

## Layer 1 — RBAC at the router (every endpoint, no exceptions)

`dependencies=[Depends(check_permissions(Permission.X))]`.
New permission → add to `Permission` enum **and** to `ROLE_PERMISSIONS` for each role that should have it
(`SUPER_ADMIN` gets `list(Permission)` automatically). Roles: SUPER_ADMIN, ADMIN, COACH, PLAYER, USER
(`User.roles` is a JSON list — a user can hold several). Which roles get a new permission is a product decision:
ask Mijo if not specified; default proposal = ADMIN full, COACH read (+ write for training/tournament areas).
Naming: `VIEW_XS` (list), `VIEW_X`, `CREATE_X`, `UPDATE_X`, `DELETE_X` / `DEACTIVATE_X`.

## Layer 2 — company scope (every tenant-owned row)

Preferred (framework):

- CRUD router: `scope_by_company=True` → list filtered by the caller's company; get/update/deactivate of a
  foreign row → 404/403; create/update with a foreign `company_id` → 403. Requires a `company_id` column **or**
  an overridden `company_scope_clause` (e.g. `group` scopes through `season.company_id`).
- Manual endpoints: call the service helpers yourself —
  `service.enforce_company_read(id, user)` (GET), `service.enforce_company_scope(id, user)` (PUT/DELETE/actions),
  `service.enforce_company_in_data(data, user)` (payload `company_id`),
  `company_id=service.company_scope_for(user)` for lists.
- Child rows without `company_id` (installments, group_user, training_users, segments): check the **parent's**
  company before acting.

Legacy: `_enforce_company_scope_on_update` hooks in training/season — fine to keep, don't copy into new entities.

`current_user is None` means an internal call (tests, scripts, scheduler) — hooks skip scoping then. HTTP requests
always have a user (the router injects it), so never use `None` as a way to bypass checks from an endpoint.

## Academy nuance

Seasons are often owned by the ACADEMY, selections/users by its member clubs. "Same company" is too strict for
pairings like season↔selection — use `academy_of(company)` from `group_service` ("same academy" test).
Scoping of *reads* is still per company unless a feature deliberately exposes academy-wide data — ask.

## Where each check lives

| Check | Lives in |
|---|---|
| role allows this kind of action | router `check_permissions` |
| this user may touch this row / this company_id | `scope_by_company` / `enforce_company_*` (or a service hook) |
| body is valid | Pydantic schema (+ merged-state validation in `pre_update`) |
| referenced row exists | service/hook → `NotFoundException` |
| token valid, user active | `get_current_active_user` |

## Tests required for any new endpoint

own company ✅ · other company ❌ (404/403) · SUPER_ADMIN on other company ✅ · role without permission → 403 ·
no token → 401. See `group_test.py` (`own` / `other` / `coach_headers` fixtures).
