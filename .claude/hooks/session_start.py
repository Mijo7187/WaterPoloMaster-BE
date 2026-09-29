#!/usr/bin/env python3
"""SessionStart — short repo snapshot; stdout is added to Claude's context."""
import os
import subprocess

project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def git(*args):
    r = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


branch = git("branch", "--show-current") or "(detached)"
dirty = [l for l in git("status", "--porcelain").splitlines() if l.strip()]
ahead = git("rev-list", "--count", "develop..HEAD")

lines = [f"Branch: {branch}" + (f" ({ahead} commit(s) ahead of develop)" if ahead and ahead != "0" else "")]
lines.append(f"Uncommitted files: {len(dirty)}")
if branch in ("develop", "main"):
    lines.append(f'Note: on protected branch "{branch}" — create a feature branch before committing.')
if len(dirty) > 30:
    lines.append("Note: large uncommitted change set — don't mix new work into it; suggest committing/splitting first.")
print("\n".join(lines))
