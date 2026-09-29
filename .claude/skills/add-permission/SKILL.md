---
name: add-permission
description: Add new Permission values to WaterPoloMaster RBAC and grant them to roles in ROLE_PERMISSIONS, then wire them into endpoints and tests. Use whenever a new endpoint or entity needs access control, or when a role's access should change.
argument-hint: "<PERMISSION_NAME ...> [roles, e.g. ADMIN,COACH]"
---

# Add permission(s): $ARGUMENTS

File: `app/core/permissions.py`.

1. **Enum** — add to `class Permission(str, enum.Enum)` in the section for that feature (keep the grouping comments):
   `VIEW_XS`, `VIEW_X`, `CREATE_X`, `UPDATE_X`, `DELETE_X` (or `DEACTIVATE_X`). Value = name.
2. **Roles** — add to the `ROLE_PERMISSIONS` lists inside the right `#region`:
   - `SUPER_ADMIN` gets everything automatically (`list(Permission)`) — never list it.
   - Which of ADMIN / COACH / PLAYER / USER get it is a **product decision**. If the request doesn't say, ask Mijo;
     propose: ADMIN = full CRUD on club data; COACH = read + write on training/tournament/segments/attendance,
     read on users/seasons/groups; PLAYER/USER = read-only on what concerns them.
   - SUPER_ADMIN-only permissions (academy management, cross-club ops) → add to the enum only, with a comment.
3. **Endpoints** — `dependencies=[Depends(check_permissions(Permission.X))]` on each route / conf.
4. **FE** — the FE's route access (`ROUTES_BY_ROLE`) should match; mention it in the hand-off.
5. **Tests** — for each new permission: a role that has it → allowed; a role that doesn't → 403.

Verify: `python -c "from app.core.permissions import Permission, ROLE_PERMISSIONS; print(len(Permission))"` then the
feature's tests.

Changing an existing role's access (removing a permission) can lock real users out after go-live — call it out.
