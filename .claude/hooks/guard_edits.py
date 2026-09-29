#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit) — block edits to protected files and NEW code that breaks the
architecture rules in .claude/rules/. Only the new text is inspected, so touching legacy code that already
contains a violation is allowed; adding a new one is not. Exit 2 = block, stderr goes back to Claude."""
import json
import os
import re
import subprocess
import sys

data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
tool_input = data.get("tool_input") or {}
file_path = tool_input.get("file_path") or ""
if not file_path:
    sys.exit(0)

rel = os.path.relpath(os.path.abspath(os.path.join(project, file_path)), project).replace(os.sep, "/")


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


# ── Protected files ──────────────────────────────────────────────────────────
if re.search(r"(^|/)\.env(\..*)?$", rel) and not rel.endswith(".env.example"):
    block(f"BLOCKED: {rel} may contain secrets — ask Mijo to change it (edit .env.example for documentation).")
if rel.endswith((".db", ".sqlite", ".sqlite3")):
    block(f"BLOCKED: {rel} is a database file — never edit it directly.")
if rel.startswith("excel/"):
    block(f"BLOCKED: {rel} is source data from the club — read it, don't modify it.")
if rel.startswith(".git/"):
    block("BLOCKED: never edit .git internals.")

# Committed migrations may already be applied somewhere → create a new revision instead.
if re.match(r"^alembic/versions/.+\.py$", rel):
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=project, capture_output=True, text=True,
    ).returncode == 0
    if tracked:
        block(
            f"BLOCKED: {rel} is a committed migration and may already be applied. "
            "Create a new revision with `alembic revision --autogenerate -m ...` instead (see /migration)."
        )

if not (rel.endswith(".py") and (rel.startswith("app/") or rel == "conftest.py")):
    sys.exit(0)

# ── Collect new text ─────────────────────────────────────────────────────────
chunks = []
for key in ("content", "new_string"):
    if isinstance(tool_input.get(key), str):
        chunks.append(tool_input[key])
for edit in tool_input.get("edits") or []:
    if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
        chunks.append(edit["new_string"])
text = "\n".join(chunks)
if not text:
    sys.exit(0)

# drop comment lines so explanations don't trigger rules
code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))

is_test = rel.endswith("_test.py") or rel == "conftest.py" or rel.startswith("tests/")
is_router = rel.endswith("_router.py")
is_service = rel.endswith("_service.py")
billing_area = re.match(
    r"^app/(features/(contract|contract_installment|payment|wallet|membership|group|group_user)/|scheduler/)", rel
)

violations = []
if re.search(r"\bpydantic\.v1\b", code):
    violations.append("pydantic.v1 import — Pydantic v2 only.")
if is_router and re.search(r"\bdb\.(query|add|commit|execute|delete|flush|get)\(", code):
    violations.append(
        "database access in a router — move it to a repository method and call it via the service "
        "(.claude/rules/architecture.md)."
    )
if is_service and re.search(r"\braise\s+HTTPException\b", code):
    violations.append("HTTPException raised in a service — raise an AppException subclass (NotFound/Forbidden/BadRequest/Conflict/ValidationException).")
if billing_area and not is_test and re.search(r"\bdate\.today\(\)", code):
    violations.append("naive date.today() in billing/scheduler code — use club_today() from app/utils/dateUtils.py.")
if not is_test and re.search(r"^\s*print\(", code, re.M):
    violations.append("print() in app code — use logging (or remove the debug output).")
if re.search(r"except\s*:", code):
    violations.append("bare `except:` — catch a specific exception (or `except Exception` and log/re-raise).")

if violations:
    block(
        f"BLOCKED edit to {rel}:\n- " + "\n- ".join(violations)
        + "\n\nRewrite the change to follow the rule. If this is a deliberate exception, explain why to Mijo and let him apply it."
    )
sys.exit(0)
