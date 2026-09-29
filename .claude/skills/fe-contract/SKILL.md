---
name: fe-contract
description: Document backend API changes for the WaterPoloMaster frontend — writes docs/frontend/<topic>.md with endpoints, field tables, filters, errors and ready-to-paste TypeScript types, and lists the FE files to update when ../WaterPoloMaster-FE is available. Use after schema/router/enum changes or when asked what the frontend needs.
argument-hint: "[feature or topic — default: everything changed on this branch]"
context: fork
agent: fe-contract-sync
---

Document the API contract changes for the frontend.

Topic: $ARGUMENTS (empty = everything changed on this branch vs `develop` plus uncommitted work).

## Changed API files

!`git diff --name-only develop...HEAD -- 'app/**/*_schemas.py' 'app/**/*_router.py' 'app/**/*_model.py' 2>/dev/null; git status --porcelain -- 'app/**/*_schemas.py' 'app/**/*_router.py' 'app/**/*_model.py'`

## FE repo present?

!`test -d ../WaterPoloMaster-FE && echo "yes: ../WaterPoloMaster-FE" || echo "no — skip the FE file list"`

Write or update `docs/frontend/<topic>.md` in the format of `docs/frontend/list-summary.md`, mark breaking changes,
include TypeScript interfaces using the FE conventions (`IPostX`, `IGetX`, `FXList`, `IXSummary`, enums with identical
values), and return the file path + a short summary.
