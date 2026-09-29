---
name: verify
description: Run the WaterPoloMaster backend checks for the current changes — syntax, ruff F (undefined names/unused vars), pytest for touched features (or the full suite), alembic single-head and model-vs-migration sanity — and report new problems separately from baseline. Use before saying a task is done, before commits and PRs.
argument-hint: "[--full]"
allowed-tools: Bash(pytest:*) Bash(python -m pytest:*) Bash(python -m py_compile:*) Bash(ruff check:*) Bash(alembic heads:*) Bash(git:*)
---

# Verify

## Changed files

!`git diff --name-only develop...HEAD 2>/dev/null; git status --porcelain | awk '{print $NF}'`

## Steps

1. **Syntax**: `python -m py_compile <changed .py files>`.
2. **Ruff (pyflakes only)**, if installed: `ruff check --select F --ignore F401 <changed .py files>`.
   No formatter, no style rules — the repo has none configured. (Baseline: ~32 unused imports exist; ignore F401
   unless you introduced it.)
3. **Tests**:
   - touched features: `pytest app/features/<name>/ -q` for each feature folder touched (+ `app/scheduler/` if jobs or
     billing services changed);
   - **full** `pytest -q` (~4 min) if `$ARGUMENTS` has `--full`, or anything in `app/common/`, `app/core/`,
     `conftest.py`, or a widely used model/service (users, company, payment, contract) changed.
   - Baseline: 492 passed, 0 failed. Any failure is new unless proven otherwise.
   - No `.env`? prefix with `APP_ENV=testing DATABASE_URL=sqlite:///./test.db SECRET_KEY=x`.
4. **Migrations**:
   - a `*_model.py` changed but no new file in `alembic/versions/` → missing migration (tests won't catch it —
     they build tables from metadata);
   - new model file not imported in `alembic/env.py`;
   - `alembic heads` → one head.
5. **Contract**: a schema/router/enum change without a `docs/frontend/` note → flag it (`/fe-contract`).

## Report

```
Syntax   ✅/❌
Ruff F   ✅/❌ (n new)
Tests    ✅/❌ (passed/failed — which suite)
Alembic  ✅/❌ (heads, missing migration?, env.py?)
Contract ✅/⚠️  (FE note needed?)
```
List each new problem with file:line and the fix. Never report green with red in the touched code.
