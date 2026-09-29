---
paths:
  - "app/scheduler/**"
  - "run_job_now.py"
---

# Scheduler jobs (APScheduler, in-process)

- Registered in `app/scheduler/scheduler.py` via `init_scheduler()` (called on app startup); cron times are in
  `settings.CLUB_TIMEZONE`, not server time.
- Current schedule (order matters): 23:59 `nightly_training_job` · 00:01 `daily_contract_status_job` ·
  00:05 on the 1st `monthly_recurring_billing_job` (membership + staff periods) · 00:15 `nightly_billing_job` ·
  00:30 `daily_debt_job`. Re-read `scheduler.py` before adding one and place it relative to these.
- Every job must be **idempotent** (safe to run twice, e.g. after a restart) and **skip-and-log** bad rows instead of
  aborting the batch.
- Jobs open their own DB session and call services/repositories with `current_user=None` (internal call — scoping
  hooks skip). They must not call HTTP endpoints.
- Test with `app/scheduler/*_test.py` patterns + `freeze_club_today`; `run_job_now.py` runs a job manually in dev.
- `replace_existing=True` and a stable `id` for every job.
- Multiple uvicorn workers would run jobs N times — keep a single worker in production or move jobs out (flag it if
  deployment changes).
