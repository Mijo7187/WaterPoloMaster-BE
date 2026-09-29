# `.claude/` — Claude Code setup for WaterPoloMaster-BE

| Path | What | Loaded |
|---|---|---|
| `../CLAUDE.md` | commands, folder map, golden rules, domain summary | every session |
| `rules/architecture.md` | layering, cross-feature calls, naming, **known deviations** | every session |
| `rules/*.md` (others) | crud-framework, auth-and-scoping, billing-domain, migrations, testing, api-contract, scheduler | only when matching paths are touched |
| `agents/` | `be-planner`, `entity-scaffolder`, `test-writer`, `migration-reviewer`, `code-reviewer`, `security-reviewer`, `fe-contract-sync` | delegated / on demand |
| `skills/` | `/feature` `/new-crud-entity` `/add-permission` `/add-list-summary` `/migration` `/add-scheduler-job` `/fe-contract` `/verify` `/review` `/security-review` `/pr` | on demand |
| `hooks/` | `guard_edits` (blocks secrets/DB/committed-migration edits + new layering violations), `post_edit_check` (py_compile + ruff F), `stop_check` (tests of touched features, model-without-migration, env.py import), `session_start` | via `settings.json` |
| `settings.json` | shared permissions + hooks | committed |
| `settings.local.json` | personal overrides | gitignored |

Hooks use only the Python stdlib (`python3`). Start Claude with the project venv active so the Stop hook can run
pytest; ruff is optional (`pip install ruff`) — without it the post-edit check does syntax only.
Keep the rules true: update them in the same PR that changes a convention.
