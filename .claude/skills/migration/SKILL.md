---
name: migration
description: Create a WaterPoloMaster Alembic migration safely — check env.py imports, autogenerate, strip known SQLite noise, get it reviewed by migration-reviewer, verify a single head, and hand the upgrade command to Mijo. Use after any model change.
argument-hint: "\"<imperative message, e.g. add academy_id to company>\""
allowed-tools: Bash(alembic revision:*) Bash(alembic heads:*) Bash(alembic history:*) Bash(alembic current:*) Bash(git:*)
---

# Migration: $ARGUMENTS

## Current state

- Heads: !`alembic heads 2>&1 | tail -3`
- Changed models: !`git status --porcelain -- 'app/**/*_model.py' 'app/**/*_models.py' alembic/`

## Steps

1. **env.py** — every new model file is imported in `alembic/env.py` (`# noqa: F401`). Fix before generating.
2. **Generate**: `alembic revision --autogenerate -m "$ARGUMENTS"`
   (needs `.env`, or `APP_ENV=development DATABASE_URL=sqlite:///./waterpolo.db SECRET_KEY=x`). The DB it diffs
   against must be at head (`alembic current`), otherwise the file will contain unrelated ops.
3. **Clean** the generated file:
   - delete the spurious SQLite `NUMERIC → UUID` `alter_column` ops (see `.claude/rules/migrations.md`);
   - wrap ALTER COLUMN / constraint changes for SQLite in `op.batch_alter_table`;
   - NOT NULL column on an existing table → `server_default` or add-nullable → backfill → alter;
   - enum value changes → add manual ops (autogenerate misses them);
   - renames must be `alter_column(new_column_name=...)`, never drop+add.
4. **Review** → delegate to agent `migration-reviewer`; apply its blocking fixes.
5. `alembic heads` → exactly one head.
6. **Stop.** Do not run `alembic upgrade`. Give Mijo:
   ```bash
   cp waterpolo.db waterpolo.db.bak-$(date +%Y%m%d)   # dev backup (prod: pg_dump first)
   alembic upgrade head
   ```
   plus any manual/backfill steps and whether the downgrade is lossy.

Never edit a migration that is already committed — make a new one.
