---
name: pr
description: Commit the current backend work and open a pull request into develop with a structured description (changes by layer, migration steps, FE contract impact). Only when explicitly asked.
argument-hint: "[PR title]"
disable-model-invocation: true
allowed-tools: Bash(git:*) Bash(gh:*) Bash(pytest:*) Bash(python -m pytest:*) Bash(alembic heads:*)
---

# Open PR → develop

## State

- Branch: !`git branch --show-current`
- Status: !`git status --porcelain`
- Ahead of develop: !`git log --oneline develop..HEAD 2>/dev/null`

## Steps

1. Never commit on `develop`/`main` — create `feature/<kebab>` first (ask for the name if unclear). With a large pile
   of unrelated uncommitted work, propose splitting it into several focused PRs (by feature) instead of one.
2. Run `/verify` (full suite). Stop on failures.
3. Stage only related files. Never stage: `.env`, `*.db`, `excel/`, `__pycache__/`, `.DS_Store`,
   `.claude/settings.local.json`, personal scratch scripts. Show the staged list.
4. Commit: `feat(<feature>): <imperative summary>` (≤72 chars), body with notable decisions. One migration per PR
   where possible.
5. `git push -u origin <branch>`; `gh pr create --base develop --title "<title>" --body-file <tmp>`:

```markdown
## What
## Why
## How
- Models/migration: … (revision id, reversible? backfill?)
- Service/rules: …
- Endpoints & permissions: … (roles, scoping)
## Frontend impact
- Breaking: yes/no — docs/frontend/<file>.md
## Deploy steps
- [ ] backup DB  - [ ] `alembic upgrade head`  - [ ] …
## Testing
- `pytest` — N passed
```

Title: `$ARGUMENTS` if given. Return the PR URL.
