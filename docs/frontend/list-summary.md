# List summary — frontend integration

Backend list endpoints now return a `summary` next to `items` and `pagination`. This file describes the shape per endpoint.

## 1. List response shape (every CRUD list)

```json
{
  "status": 200,
  "messages": [],
  "data": {
    "items": [ ... ],
    "pagination": { "total": 42, "page": 1, "size": 20, "pages": 3 },
    "summary": { ... } | null
  },
  "detail": null
}
```

- `summary` covers **all rows that match the filters, across every page**. Page and size don't change it.
- It **does** follow the list filters. For example, `?status=debt` gives debt-only totals.
- It follows company scope. An ADMIN only gets totals for their own company.
- Money fields come back as JSON **numbers**, e.g. `150.0` or `0`.
- Every CRUD list now has the `summary` key. Lists without a summary send `null`.
- **Exception:** `GET /api/wallet/` is a hand-written endpoint and has **no** `summary` key at all.

## 2. `GET /api/payment/` (always has a summary)

Totals are always returned. "Income" and "outcome" are seen from one side, and which side depends on the request:

| request | seen from | income | outcome |
|---|---|---|---|
| `?wallet_id=<uuid>` | that wallet | received by the wallet | sent by the wallet |
| ADMIN, no `wallet_id` | the admin's club wallet | received by the club | paid out by the club |
| SUPER_ADMIN, no `wallet_id` | all clubs in the app | players paying clubs (membership and tournament fees) | clubs paying out (salaries, pools) |

| field | type | meaning |
|---|---|---|
| `total_income` | number | COMPLETED, income |
| `total_outcome` | number | COMPLETED, outcome |
| `balance` | number | `total_income - total_outcome` |
| `pending_income` | number | PENDING, owed **to** us, not yet due |
| `pending_outcome` | number | PENDING, owed **by** us, not yet due |
| `total_debt` | number | DEBT: we owe this and it is overdue |
| `debt_receivable` | number | DEBT: others owe us and it is overdue |
| `count` | number | rows matching the filters |

FAILED and REFUNDED payments count toward `count` but are in no money bucket.

Other payment endpoints are unchanged: `POST /api/payment/`, `GET /api/payment/{id}` and
`PUT /api/payment/{id}` keep the same URLs and response shapes.

## 3. `GET /api/contract/` (always has a summary)

| field | type | meaning |
|---|---|---|
| `count` | number | contracts matching the filters |
| `by_status` | object | `{ "draft": n, "active": n, "ended": n, "cancelled": n }`. Every key is always present. |
| `monthly_income` | number | sum of `amount` for ACTIVE membership contracts billed **monthly** |
| `monthly_outcome` | number | sum of `amount` for ACTIVE staff contracts (salaries) |

Term (block) memberships are not in `monthly_income` because they are billed once.

## 4. `GET /api/training/` (always has a summary)

| field | type | meaning |
|---|---|---|
| `count` | number | trainings matching the filters |
| `by_status` | object | `{ "INCOMING": n, "IN_PROCESS": n, "FINISHED": n, "CANCELLED": n }` (**UPPERCASE** keys). Every key is always present. |
| `total_price` | number | sum of `price`, **excluding CANCELLED** |

Contract status keys are lowercase and training status keys are uppercase. This matches the status
values each entity already uses.

## 5. TypeScript types

```ts
export interface IPagination { total: number; page: number; size: number; pages: number; }

export interface IListResponse<T, S = null> {
  items: T[];
  pagination: IPagination;
  summary: S | null;
}

export interface IPaymentSummary {
  total_income: number;
  total_outcome: number;
  balance: number;
  pending_income: number;
  pending_outcome: number;
  total_debt: number;
  debt_receivable: number;
  count: number;
}

export interface IContractSummary {
  count: number;
  by_status: { draft: number; active: number; ended: number; cancelled: number };
  monthly_income: number;
  monthly_outcome: number;
}

export interface ITrainingSummary {
  count: number;
  by_status: { INCOMING: number; IN_PROCESS: number; FINISHED: number; CANCELLED: number };
  total_price: number;
}

// usage
// IListResponse<IPayment, IPaymentSummary>   — GET /api/payment/ (optionally ?wallet_id=...)
// IListResponse<IContract, IContractSummary> — GET /api/contract/
// IListResponse<ITraining, ITrainingSummary> — GET /api/training/
// IListResponse<ICompany>                    — any other list (summary is null)
```

## 6. How to check
Open `/docs`, or call these while logged in, and check `data.summary`:
- `GET /api/payment/?wallet_id=<uuid>`
- `GET /api/payment/` as SUPER_ADMIN, which should return totals for the whole app
- `GET /api/contract/?size=1`, where the totals should still cover all contracts
- `GET /api/training/`
