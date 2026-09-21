"""
Guarded DEV database reset.

Wipes the development database and rebuilds it from the Alembic migrations.
This is DESTRUCTIVE and deliberately hard to fire by accident. It refuses to
run unless ALL of these hold:

  * APP_ENV is a development-ish value (development / dev / local / testing);
  * the database host is local (SQLite file, or localhost / 127.0.0.1);
  * you pass --yes-i-mean-it, or type the database name back interactively.

A remote Postgres host is rejected outright — there is no flag that overrides
that check, so this can never fire against a staging or production server.

It never calls Base.metadata.drop_all(): the schema is rebuilt the Alembic way
(`alembic upgrade head`) so the database always matches the migration chain.

Usage:
    python dev_reset.py                  # interactive confirmation
    python dev_reset.py --yes-i-mean-it  # non-interactive (scripts/CI)
    python dev_reset.py --seed           # reset, then run the dev seed
"""

import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings  # noqa: E402


DEV_ENVS = {"development", "dev", "local", "testing", "test"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


class GuardFailed(RuntimeError):
    """Raised when the reset is not allowed to proceed."""


def describe_target(url: str):
    """(kind, label) for the connection — kind is 'sqlite' or 'postgres'."""
    if url.startswith("sqlite:"):
        path = url.split("///", 1)[1] if "///" in url else ""
        if not path:
            raise GuardFailed(
                f"Refusing to reset: could not read a database file path out of '{url}'."
            )
        return "sqlite", path

    parsed = urlparse(url)
    if parsed.scheme.startswith("postgres"):
        host = parsed.hostname or ""
        if host not in LOCAL_HOSTS:
            raise GuardFailed(
                f"Refusing to reset: database host '{host}' is not local. "
                "This script only ever touches a local development database, "
                "and there is no flag to override that."
            )
        name = (parsed.path or "").lstrip("/")
        if not name:
            raise GuardFailed(
                f"Refusing to reset: could not read a database name out of '{url}'."
            )
        return "postgres", name

    raise GuardFailed(
        f"Refusing to reset: unsupported database scheme '{parsed.scheme}'. "
        "Only local SQLite and local Postgres are supported."
    )


def check_guards(url: str, app_env: str):
    if app_env.lower() not in DEV_ENVS:
        raise GuardFailed(
            f"Refusing to reset: APP_ENV is '{app_env}', not one of {sorted(DEV_ENVS)}."
        )
    return describe_target(url)


def confirm(kind: str, label: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True

    if not sys.stdin.isatty():
        print(
            "Refusing to reset: not a terminal and --yes-i-mean-it was not passed.",
            file=sys.stderr,
        )
        return False

    name = os.path.basename(label) if kind == "sqlite" else label
    what = f"the file {label}" if kind == "sqlite" else f"every table in database '{label}'"
    print(f"\nThis will DESTROY {what} and rebuild it from scratch.")
    typed = input(f"Type the database name ('{name}') to confirm: ").strip()
    if typed != name:
        print("Confirmation did not match. Nothing was changed.")
        return False
    return True


def reset_sqlite(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted {path}")
    else:
        print(f"{path} did not exist — nothing to delete.")


def reset_postgres(url: str, name: str) -> None:
    """Drop and recreate the public schema. Cheaper and safer than dropping the
    database itself, which would need a connection to another database."""
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    engine.dispose()
    print(f"Dropped and recreated schema 'public' in database '{name}'.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded dev database reset.")
    parser.add_argument(
        "--yes-i-mean-it",
        dest="assume_yes",
        action="store_true",
        help="Skip the interactive confirmation.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Run the dev seed after the reset.",
    )
    args = parser.parse_args()

    try:
        kind, label = check_guards(settings.DATABASE_URL, settings.APP_ENV)
    except GuardFailed as exc:
        print(exc, file=sys.stderr)
        return 1

    if not confirm(kind, label, args.assume_yes):
        return 1

    if kind == "sqlite":
        reset_sqlite(label)
    else:
        reset_postgres(settings.DATABASE_URL, label)

    print("Running: alembic upgrade head")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("Schema rebuilt.")

    if args.seed:
        print("\nRunning dev seed...")
        subprocess.run([sys.executable, "seed_dev_data.py"], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
