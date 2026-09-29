---
name: review
description: Architecture, correctness and contract review of the current backend branch (or given paths) by the read-only code-reviewer agent in a forked context. Use before committing or opening a PR, or when asked to review changes.
argument-hint: "[paths or branch — default: this branch vs develop + uncommitted]"
context: fork
agent: code-reviewer
---

Review these WaterPoloMaster backend changes.

Target: $ARGUMENTS (empty = this branch vs `develop` plus uncommitted work).

## Branch diff

!`git diff --stat develop...HEAD 2>/dev/null | tail -40`

## Uncommitted

!`git status --porcelain`

Read every changed file fully, apply your checklist and `.claude/rules/`, run pytest for the touched features, and
return the verdict in your standard format including the contract delta for the FE.
