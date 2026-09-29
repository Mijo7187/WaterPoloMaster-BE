---
name: add-list-summary
description: Add an aggregate `summary` (totals/counts over every filtered row, not just the page) to a WaterPoloMaster CRUD list endpoint — repository get_summary over list_query, summary schema, router config, tests and a frontend doc. Use when a list needs totals, counts by status, or money sums.
argument-hint: "<feature_name> [fields, e.g. count,total_amount,by_status]"
---

# Add list summary to `$0`

References: `payment_repository.get_summary` (side-dependent income/outcome), `contract_repository.get_summary`
(`by_status` with every key present), `training_repository.get_summary`.

1. **Repository** (`app/features/$0/$0_repository.py`):
   ```python
   def get_summary(self, filters, company_id=None) -> Optional[dict]:
       q = self.list_query(filters, company_id)          # SAME filtered + scoped query as the list
       row = q.with_entities(
           func.count(Model.id),
           func.coalesce(func.sum(Model.amount), 0),
       ).one()
       return {"count": row[0], "total_amount": row[1]}
   ```
   - Always aggregate over `self.list_query(...)` — never re-implement filters, or totals drift from the rows shown.
   - Status breakdowns: return **every** enum key (0 when absent) so the FE never guards missing keys.
   - Money: `coalesce(sum(...), 0)`; respect billing rules (`OUTSTANDING_STATUSES`, exclude CANCELLED where the
     domain says so).
2. **Schema** (`$0_schemas.py`): `class XSummary(CrudSummarySchema)` with typed fields (`float`/`Decimal` → JSON number,
   `dict[str, int]` for breakdowns).
3. **Router**: `get_list_conf=CrudListEndpointConfig(..., summary_schema=XSummary)`. Manual list routers must call
   `service.get_summary(filters=..., company_id=...)` and include `"summary"` in the response.
4. **Tests**: totals across pages (`?size=1` still returns full totals), filters narrow the summary, other company's
   rows excluded, empty list → zeros not null.
5. **FE doc**: extend `docs/frontend/list-summary.md` (field table + TS interface) — or run `/fe-contract`.
