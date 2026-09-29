#!/usr/bin/env python3
"""PostToolUse (Edit|Write|MultiEdit) — after a Python file changes: syntax check, then pyflakes-level ruff
(undefined names, redefinitions, unused variables; unused imports ignored because of the existing baseline).
Nothing is modified. Problems go back to Claude via exit 2. Skips ruff silently if it isn't installed."""
import json
import os
import shutil
import subprocess
import sys

data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
file_path = (data.get("tool_input") or {}).get("file_path") or ""
if not file_path:
    sys.exit(0)

abs_path = os.path.abspath(os.path.join(project, file_path))
rel = os.path.relpath(abs_path, project).replace(os.sep, "/")
if not rel.endswith(".py") or not os.path.exists(abs_path) or rel.startswith("alembic/versions/__pycache__"):
    sys.exit(0)

problems = []

compiled = subprocess.run(
    [sys.executable, "-m", "py_compile", abs_path], capture_output=True, text=True
)
if compiled.returncode != 0:
    problems.append(f"Syntax error:\n{compiled.stderr.strip()}")

ruff = shutil.which("ruff")
if ruff and compiled.returncode == 0:
    res = subprocess.run(
        [ruff, "check", "--no-cache", "--select", "F", "--ignore", "F401", "--output-format", "concise", rel],
        cwd=project, capture_output=True, text=True, timeout=60,
    )
    if res.returncode not in (0,):
        out = (res.stdout + res.stderr).strip()
        if out and "All checks passed" not in out:
            problems.append(f"ruff (pyflakes) findings:\n{out}")

if problems:
    print(f"Problems in {rel}:\n\n" + "\n\n".join(problems), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
