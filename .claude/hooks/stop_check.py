#!/usr/bin/env python3
"""Stop — before Claude finishes a turn: run pytest for every feature folder touched by uncommitted changes, and
check that model changes come with a migration and that new models are imported in alembic/env.py.
Only reports problems caused by the current changes. Exit 2 = keep working; stderr explains why."""
import json
import os
import re
import subprocess
import sys

data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
if data.get("stop_hook_active"):
    sys.exit(0)  # already continuing because of this hook — don't loop

project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def run(cmd, timeout=280, env=None):
    return subprocess.run(cmd, cwd=project, capture_output=True, text=True, timeout=timeout, env=env)


status = run(["git", "status", "--porcelain", "--untracked-files=all"], timeout=20)
if status.returncode != 0:
    sys.exit(0)

entries = []
for line in status.stdout.splitlines():
    if not line.strip():
        continue
    code, path = line[:2], line[3:].split(" -> ")[-1].strip('"')
    entries.append((code, path))

changed_py = [p for c, p in entries if p.endswith(".py") and "D" not in c]
if not changed_py:
    sys.exit(0)

problems = []

# ── Migration sanity ─────────────────────────────────────────────────────────
model_changes = [p for p in changed_py if re.search(r"_models?\.py$", p) and p.startswith("app/")]
new_migrations = [p for c, p in entries if p.startswith("alembic/versions/") and p.endswith(".py") and c.strip() in ("??", "A")]
if model_changes and not new_migrations:
    problems.append(
        "Model file(s) changed but no new migration in alembic/versions/: "
        + ", ".join(model_changes)
        + "\nTests don't catch this (they build tables from metadata). Run /migration, or explain why no schema change happened."
    )
new_models = [p for c, p in entries if c.strip() == "??" and re.search(r"_model\.py$", p)]
if new_models:
    try:
        env_py = open(os.path.join(project, "alembic", "env.py"), encoding="utf-8").read()
    except OSError:
        env_py = ""
    for p in new_models:
        module = p[:-3].replace("/", ".")
        if module not in env_py:
            problems.append(f"New model {p} is not imported in alembic/env.py — autogenerate won't see it.")

# ── Tests for touched features ───────────────────────────────────────────────
targets = set()
for p in changed_py:
    m = re.match(r"^(app/features/(?:sifarnici/)?[^/]+)/", p)
    if m:
        targets.add(m.group(1))
    elif p.startswith("app/scheduler/"):
        targets.add("app/scheduler")
targets = sorted(t for t in targets if any(
    f.endswith("_test.py") for f in os.listdir(os.path.join(project, t))
) if os.path.isdir(os.path.join(project, t)))

if targets:
    env = dict(os.environ)
    if not os.path.exists(os.path.join(project, ".env")):
        env.setdefault("APP_ENV", "testing")
        env.setdefault("DATABASE_URL", "sqlite:///./test.db")
        env.setdefault("SECRET_KEY", "test-secret-key")
    try:
        res = run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *targets], env=env)
        out_all = res.stdout + res.stderr
        if "No module named pytest" in out_all:
            pass  # hook ran outside the project's venv — /verify covers it
        elif res.returncode not in (0, 5):  # 5 = no tests collected
            tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-40:])
            problems.append(f"Tests fail in {', '.join(targets)}:\n{tail}")
    except subprocess.TimeoutExpired:
        problems.append(f"pytest for {', '.join(targets)} exceeded the hook timeout — run /verify manually.")
    except FileNotFoundError:
        pass

if problems:
    print("\n\n".join(problems) + "\n\nFix these before finishing (or explain to Mijo why they are expected).", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
