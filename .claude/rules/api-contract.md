---
paths:
  - "app/**/*_schemas.py"
  - "app/**/*_router.py"
  - "app/**/*_model.py"
  - "docs/frontend/**"
---

# API contract with the frontend

The FE (`WaterPoloMaster-FE`, usually checked out next to this repo as `../WaterPoloMaster-FE`) mirrors this API
directly: `IPostX` ≈ `XCreate`, `IGetX` ≈ `XResponse`/`XListResponse`, `FXList` ≈ `XFilters`, FE enums = BE enum
values, snake_case field names, no mapping layer. Its axios interceptor unwraps `data` and shows `messages`
(or `detail`) as the error toast — so **`messages` must be human-readable** and are shown to club staff.

## Breaking changes (need a FE change + a note)

- rename/remove a response field, change its type or nullability
- rename/remove an enum value, change enum case
- rename/remove a filter param or change its operator
- change a route path/method, the create response shape, or the list/summary shape
- tighten validation on a field the FE already sends

Non-breaking: adding optional response fields, new endpoints, new optional filters, new enum values the FE can ignore
(still tell the FE if it renders that enum).

## When you change the contract

1. Prefer additive: add the new field, keep the old one until the FE switches.
2. Write/extend a note in `docs/frontend/<topic>.md` (see `list-summary.md` for the format: endpoint, shape table,
   TypeScript interface, how to check) — skill `/fe-contract`.
3. If `../WaterPoloMaster-FE` exists, list the FE files that need updating (types, constants/endpoints, filters).

## Schema conventions

- `XCreate(CrudCreateSchema)` required fields; `XUpdate(CrudUpdateSchema)` every field `Optional[...] = None`
  (partial update via `model_dump(exclude_unset=True)`).
- `XListResponse` = lightweight projection for lists and nesting; `XResponse` = detail with nested relations.
- Nested objects in responses use the other feature's `...ListResponse`.
- Money → JSON number, dates → `YYYY-MM-DD`, datetimes ISO 8601.
- Validation messages: short, specific, English is fine (current codebase) — they are displayed verbatim.
