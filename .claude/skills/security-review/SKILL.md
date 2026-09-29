---
name: security-review
description: Multi-tenant security audit of WaterPoloMaster backend endpoints by the read-only security-reviewer agent — permissions, company/academy scoping, child-row checks, role mapping, auth/token handling. Use before go-live, before merging new endpoints, or on request. Pass "all" to audit the whole API.
argument-hint: "[all | paths — default: changed files]"
context: fork
agent: security-reviewer
---

Run a security review of the WaterPoloMaster backend.

Scope: $ARGUMENTS (empty = files changed on this branch + uncommitted; `all` = every router in `app/features/`).

## Changed routers/services

!`git diff --name-only develop...HEAD -- 'app/**/*_router.py' 'app/**/*_service.py' 'app/**/*_repository.py' app/core/ 2>/dev/null; git status --porcelain -- app/`

Build the endpoint inventory, trace every accepted id to a company check, review `ROLE_PERMISSIONS`, and return your
standard report with severities and the tests that would prove each finding.
