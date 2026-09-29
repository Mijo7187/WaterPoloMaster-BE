<!--
  Loaded into every session. Keep this short — details live in .claude/rules/ (path-scoped)
  and multi-step procedures in .claude/skills/. HTML comments are stripped on load.
-->

# WaterPoloMaster — Backend

FastAPI 0.115 + SQLAlchemy 2 (classic `Column(...)` declarative) + Pydantic v2 + Alembic. SQLite in dev
(`waterpolo.db`), Postgres-ready. Redis for token revocation, APScheduler for nightly billing/training jobs.
Vertical, feature-based architecture on a generic CRUD framework in `app/common/crud/`.
Frontend lives in the separate repo `WaterPoloMaster-FE` (React/MobX) — it consumes this API 1:1
(snake_case fields, `{status, messages, data, detail}` envelope).

## Commands

```bash
pip install -r requirements.txt
python run.py                                         # dev server (uvicorn, reload; HOST/PORT from .env) → /docs
pytest                                                # full suite, in-memory SQLite (~4 min, 492 tests)
pytest app/features/season/                           # one feature (seconds–1 min)
pytest app/features/contract/contract_test.py -k debt # one area
alembic revision --autogenerate -m "describe change"  # new migration (then REVIEW it)
alembic upgrade head                                  # apply — ask first
alembic heads                                         # must print exactly one head
```

Tests need `APP_ENV=testing DATABASE_URL=sqlite:///./test.db SECRET_KEY=x` if no `.env` exists (CI sets them).
CI (`.github/workflows/tests.yml`): pytest on push/PR to `develop`, Python 3.12.
No formatter/linter config in the repo — don't add one unless asked. (The Claude hook only runs
`ruff --select F` on edited files to catch undefined names / unused variables; it changes nothing.)

## Folder map

```
app/
├── main.py                 app, CORS (localhost:5173 = FE), router registration (prefix /api), scheduler start
├── core/                   config (pydantic-settings), db/, api/ (envelope, exceptions, handlers),
│                           security (JWT/bcrypt), permissions (Permission enum + ROLE_PERMISSIONS), redis, rate_limit
├── common/crud/            generic CRUD: repository, service, router factory, schemas
├── common/resolver/        polymorphic resolver (payment payable/wallet owner)
├── features/{name}/        {name}_model / _schemas / _repository / _service / _router / _test .py
│   ├── auth users company season group group_user
│   ├── membership contract contract_installment payment wallet      ← billing
│   ├── training training_segments training_users tournament tournament_users
│   └── sifarnici/          country city selection exercise_option expense_category income_category
├── scheduler/              billing_jobs, contract_jobs, training_jobs (+ tests), scheduler.py (cron in CLUB_TIMEZONE)
└── utils/
alembic/ (env.py imports every model!)  conftest.py (fixtures)  seed_*.py / reset_dev_data.py / dev_reset.py
docs/frontend/              API change notes written for the frontend
```

## Golden rules (details in `.claude/rules/`)

1. **Layering**: router = HTTP + auth deps only · service = business logic, hooks, orchestration ·
   repository = every SQLAlchemy query/commit · schemas = all IO. Never return an ORM object from a route.
2. **Every endpoint** has `Depends(check_permissions(Permission.X))`. Tenant data is **company-scoped**
   (`scope_by_company=True` or the `enforce_company_*` helpers). SUPER_ADMIN bypasses scoping.
3. **Errors**: raise `AppException` subclasses (`NotFoundException`, `ForbiddenException`, `BadRequestException`,
   `ConflictException`, `ValidationException`) — never `HTTPException` from services.
4. **Migrations**: always autogenerate, then review; never edit a migration that's committed/applied.
   New model → import it in `alembic/env.py`. Ask before `upgrade`, `downgrade`, dropping columns/tables,
   deleting rows, resetting `waterpolo.db` or running seed/reset scripts.
5. **Money/billing invariants** (see `rules/billing-domain.md`): balances are computed, never stored;
   `contract.amount` is per-installment; installments are machine-generated; outstanding = `OUTSTANDING_STATUSES`.
6. **API changes are FE changes**: renaming/removing a response field, enum value or filter breaks the
   frontend. Note it in `docs/frontend/` (skill `/fe-contract`).
7. Pydantic v2 only. Match the patterns already in the file you edit; don't invent new abstractions.
8. Don't say "done" until the touched features' tests pass (`/verify`).

## Domain in one breath

Company = tenant, `company_type` CLUB | POOL | SUPPLIER | ACADEMY (the FE enum also has TOURNAMENT — known
mismatch, BE rejects it); a club may sit under an
ACADEMY (`academy_id`). Users: exactly one company, `roles` JSON array of SUPER_ADMIN | ADMIN | COACH | PLAYER | USER.
Seasons usually belong to the academy, selections/users to its clubs. Group = (season, selection); group_user = members.
Billing: membership (price plan) → contract (MEMBERSHIP | STAFF) → contract_installment → payment between wallets.
Trainings have segments (SWIMMING, GYM, WORK_WITH_BALL, SPARRING). First real customer: an academy with 5 clubs
(first: PK Taš011), go-live mid-October 2026 — prefer safe, reversible changes.

## Working with Claude here

Skills: `/feature` `/new-crud-entity` `/add-permission` `/add-list-summary` `/migration` `/add-scheduler-job`
`/fe-contract` `/verify` `/review` `/security-review` `/pr`.
Agents: `be-planner` · `entity-scaffolder` · `test-writer` · `migration-reviewer` · `code-reviewer` ·
`security-reviewer` · `fe-contract-sync`.
Explain the *why* behind non-obvious decisions and push back when a request fights the architecture.
Personal overrides: `CLAUDE.local.md`, `.claude/settings.local.json` (gitignored).
