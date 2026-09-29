---
name: add-scheduler-job
description: Add a nightly/daily/monthly background job to the WaterPoloMaster APScheduler setup — idempotent job function with its own session, cron registration in club timezone ordered against existing jobs, run_job_now support, and tests. Use for recurring billing, status transitions, reminders or cleanups.
argument-hint: "<job_name> <schedule, e.g. daily 00:45>"
---

# Scheduler job `$0` ($1)

Read `.claude/rules/scheduler.md`, `app/scheduler/scheduler.py`, and `app/scheduler/billing_jobs.py` (+ its test).

1. **Function** in the matching module (`billing_jobs.py`, `contract_jobs.py`, `training_jobs.py`, or a new
   `<area>_jobs.py`): `def run_<name>_job() -> None` — opens its own session (copy the pattern used by the sibling jobs),
   loops rows, calls services/repositories with `current_user=None`, commits per row or per batch as siblings do,
   **logs and skips** a bad row, closes the session in `finally`.
2. **Idempotent**: a second run the same day changes nothing (unique constraints + "already done" checks).
3. **Dates**: `club_today()`; never naive `date.today()`.
4. **Register** in `init_scheduler()`: `CronTrigger(...)` in club timezone, stable `id="<name>_job"`,
   `replace_existing=True`, and a comment explaining its position relative to the other jobs (which must run first).
5. **Manual run**: make it callable from `run_job_now.py` like the others.
6. **Tests** (`app/scheduler/<area>_jobs_test.py`): happy path, run twice → no duplicates, bad row skipped while others
   processed, date edges with `freeze_club_today` (patch the module's own `club_today` import if needed).
7. Remind Mijo: one uvicorn worker in production, otherwise the job runs once per worker.
