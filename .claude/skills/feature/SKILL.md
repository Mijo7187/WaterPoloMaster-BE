---
name: feature
description: End-to-end delivery of a WaterPoloMaster backend feature — plan (be-planner), confirm open questions, implement (entity-scaffolder), tests (test-writer), migration (+ migration-reviewer), verify, review, security review for new endpoints, and a frontend contract note. Use for any feature request touching models, endpoints or business rules.
argument-hint: "<feature description>"
disable-model-invocation: true
---

# Feature: $ARGUMENTS

Orchestrate; delegate heavy work to agents so each has a clean context.

1. **Branch** — not on `develop`/`main`. Uncommitted unrelated work present? Tell Mijo and ask before mixing it in.
   Propose `git switch -c feature/<kebab-name>`.
2. **Plan** → `be-planner`. Show Mijo the plan summary, API contract delta and open questions. **Wait** for answers
   that change the implementation (roles, data semantics, backfills). State obvious defaults and continue.
3. **Implement** → `entity-scaffolder` with the plan's steps.
4. **Tests** → `test-writer` for every new/changed behaviour (scope + role matrix, invariants).
5. **Migration** (if models changed) → `/migration "<message>"`. Never apply it.
6. **Verify** → `/verify` (full suite if common/core/widely used code changed). Fix new failures.
7. **Review** → `/review`; for new/changed endpoints also `/security-review`. Fix Blocking + Should-fix.
8. **FE** → `/fe-contract` for any API change.
9. **Hand-off** — what changed (by layer), decisions + why, migration command for Mijo, FE doc path, how to try it in
   `/docs`, remaining nits. Offer `/pr`; don't commit or push unasked.
