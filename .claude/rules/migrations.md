---
paths:
  - "alembic/**"
  - "app/**/*_model.py"
  - "app/**/*_models.py"
  - "app/core/db/**"
---

# Models & Alembic migrations

## Models

- Classic declarative: `id = Column(Integer, primary_key=True, index=True, autoincrement=True)`,
  `created_at = Column(DateTime(timezone=True), server_default=func.now())`,
  `updated_at = Column(DateTime(timezone=True), onupdate=func.now())`.
- FKs: `ForeignKey("table.id", ondelete=...)` + `index=True`; relationships by string name.
- Business uniqueness as `UniqueConstraint(..., name="uq_<table>_<cols>")` **and** a readable 409 check in the service.
- Enums: `class X(str, enum.Enum)` in the model file.
- Header comment block explaining *why* the table looks like it does (the codebase convention — keep it).
- **New model file → add its import to `alembic/env.py`** (with `# noqa: F401`). Otherwise autogenerate won't see it.

## Workflow (skill `/migration`)

1. Change the model(s).
2. `alembic revision --autogenerate -m "<imperative description>"` — Claude may run this (it only writes a file).
3. **Review the generated file** (agent `migration-reviewer`): autogenerate misses/mangles enum changes, server
   defaults, check constraints, renames (shows as drop+add = data loss!), and SQLite needs
   `op.batch_alter_table` for ALTER COLUMN / constraint changes.
   **Known SQLite noise**: autogenerate against a SQLite DB emits spurious
   `alter_column(..., type_=UUID)` "NUMERIC → UUID" ops for `payment.id`, `payment.*_wallet_id`, `wallet.id`,
   `company.w_id`, `users.w_id`, `expense_category.wallet_id`, `income_category.wallet_id`. Delete them — they are
   reflection artefacts, not real changes.
4. Add manual ops on top when needed (data backfill, enum type alterations). Never rewrite from scratch.
5. `alembic heads` → exactly one head.
6. `alembic upgrade head` — **ask Mijo first**.

## Known: the chain does not replay on a fresh SQLite DB

`alembic upgrade head` on an empty SQLite file fails at `2c2c6cea6117_update_users_table`
(`ADD COLUMN first_name ... NOT NULL` without a default — SQLite refuses it). Postgres accepts it on an empty table.
Before provisioning a new environment (e.g. production Postgres) verify the full chain replays there; for SQLite dev
setups, the DB is created from metadata + `alembic stamp head`. New migrations must add NOT NULL columns with a
`server_default` (or batch add nullable → backfill → alter).

## Never

- Edit a migration that is committed (it may already be applied somewhere). Create a new one instead.
- `alembic downgrade`, drop a column/table, delete rows, or reset `waterpolo.db` without explicit OK.
- Put secrets or environment-specific values in migrations.
- Rely on `test.db`/`waterpolo.db` state — tests use in-memory SQLite via `conftest.py` (tables from `Base.metadata`,
  not from migrations — so a missing migration is NOT caught by tests; check it deliberately).
