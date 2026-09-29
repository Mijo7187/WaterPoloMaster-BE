---
paths:
  - "app/**/*_test.py"
  - "conftest.py"
  - "tests/**"
---

# Testing (pytest, in-memory SQLite)

- Tests sit next to the code: `app/features/{name}/{name}_test.py`, `app/scheduler/*_test.py`.
- `conftest.py` recreates tables per test (autouse), disables rate limiting, provides `client` (TestClient),
  `db_session`, `mock_redis`, `freeze_club_today`, factories (`create_company`, `create_user`, `create_season`,
  `create_selection`, `create_group`, `create_training`, `create_exercise_option`, …) and auth fixtures
  (`auth_headers` → `(headers, user, company)` for an ADMIN, `super_admin_headers` → `(headers, user)`).
- Authenticated calls patch the token lookup — copy the helper used across feature tests:
  ```python
  def _call(client, method, url, headers, **kwargs):
      with patch("app.features.auth.auth_dependencies.get_access_token") as mock_get:
          mock_get.return_value = headers["Authorization"].split(" ")[1]
          return getattr(client, method)(url, headers=headers, **kwargs)
  ```
- Group tests in classes per behaviour (`TestCreate`, `TestList`, `TestUpdate`, `TestScope`, `TestSummary`).
- Build scenario fixtures like `own` / `other` in `group_test.py` (same data in two companies).

## What every new/changed endpoint needs

| Case | Expect |
|---|---|
| happy path (own company) | 200/201 + response shape (nested relations present) |
| validation error | 422 (`errors[].loc` points at the field for `ValidationException`) |
| missing reference | 404 |
| duplicate / uniqueness | 409 |
| other company's row / company_id | 403 or 404 |
| SUPER_ADMIN on other company | allowed |
| role without the permission (e.g. COACH / PLAYER) | 403 |
| list filters + pagination + summary totals across pages | correct counts |

Billing/scheduler: idempotency (run twice → same rows), skip-and-log on bad rows, `freeze_club_today` for dates.
Bug fix → a regression test that fails before the fix.

## Running

`pytest app/features/<name>/` while iterating (seconds–1 min); full `pytest` (~4 min) before a PR or after touching
`app/common/`, `app/core/`, `conftest.py` or a model used widely. Baseline: 492 passed.
