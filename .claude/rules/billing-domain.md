---
paths:
  - "app/features/membership/**"
  - "app/features/contract/**"
  - "app/features/contract_installment/**"
  - "app/features/payment/**"
  - "app/features/wallet/**"
  - "app/features/group/**"
  - "app/features/group_user/**"
  - "app/scheduler/**"
  - "seed_*.py"
---

# Billing domain — load-bearing invariants

Money is real from go-live. Every change here needs tests for the invariant it touches.

## Chain

`membership` (price catalog: one plan per `(company, selection, program, billing_type)`)
→ `contract` (MEMBERSHIP or STAFF; snapshots `amount`, `billing_type`, `term_months` at signing)
→ `contract_installment` (one row per billed period, machine-generated)
→ `payment` (sender wallet → receiver wallet, typed by `PaymentTypeCode`, points at a `payable`)
→ `wallet` (polymorphic owner: company or user; **balance computed from payments, never stored**).

## billing_type

- **MONTHLY** — open-ended: `price` = monthly amount, `contract.end_date` NULL, the monthly job adds one installment
  per ACTIVE month. Cancel by setting `end_date`; never re-sign.
- **TERM** — one fixed block: `price` = whole block, `term_months` = length, `end_date = start_date + term_months`
  (inclusive). Exactly one installment written at activation; the recurring job never touches it. Next block = new contract.
- STAFF contracts behave like MEMBERSHIP MONTHLY (one `amount` per ACTIVE month, same job).

## Rules

- `contract.amount` is the **per-installment** price, never a term total. Editing/retiring a membership never moves a
  signed contract.
- Clients never send a schedule. Installments are generated; editing one is a local correction and does not re-derive
  the contract.
- Generation is **idempotent** (`UNIQUE(contract_id, period_start)`); jobs skip-and-log a bad row, never abort the batch.
- Dues go `PENDING → DEBT` when the due date passes unpaid (daily debt job). Every "outstanding" query uses
  `payment_model.OUTSTANDING_STATUSES`, never `== PENDING`.
- An installment's `payment_status` is read off its payment — lateness is decided in one place, no read-time date math.
- Contract status follows dates (DRAFT → ACTIVE → ENDED) via the 00:01 job; CANCELLED is manual.
- A group is `(season, selection)`; creating a MEMBERSHIP contract auto-enrols the user into the academy's current
  season's group for the plan's selection (best-effort: skipped without a current season, never fails the contract).
- Debt per group is **derived** (contract → membership → selection + installment period → season), not stored.
- Payment types are a code-owned enum (`PaymentTypeCode`), not a šifarnik table; each type fixes sender/receiver
  semantics and direction (drives summary income/outcome).
- Schemas serialize money to JSON numbers (the FE expects numbers, see `docs/frontend/list-summary.md`).
- Money columns are `Numeric(10|12, 2)`; do arithmetic in `Decimal`, never float.
- Dates: "today" is `club_today()` from `app/utils/dateUtils.py` (`CLUB_TIMEZONE`, Europe/Belgrade) — never naive
  `date.today()`. In tests use `freeze_club_today(d)` (it patches `contract_service.club_today`; a new module that
  imports `club_today` needs its own patch target).

## Before changing anything here

1. Read the comment blocks atop `membership_model.py`, `contract_service.py`, `billing_jobs.py`.
2. State which invariant the change touches and how the tests prove it still holds.
3. Data already in production (historical PK Taš011 records) must stay valid — prefer additive changes;
   any backfill is a reviewed migration or script, run only with Mijo's OK.
