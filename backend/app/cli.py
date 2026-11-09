"""Admin command line.

    uv run python -m app.cli create-admin --email you@example.com
    uv run python -m app.cli purge-old-data [--days 90]

The password is always read with getpass (twice), never from an argument, so it
can't end up in shell history or the process list.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable

from app.core.config import get_settings
from app.core.db import make_engine, make_sessionmaker
from app.services.auth_service import MIN_PASSWORD_LENGTH, AuthService
from app.services.retention_service import DEFAULT_RETENTION_DAYS, PurgeResult, purge_old_data


def prompt_password(read: Callable[[str], str] = getpass.getpass) -> str:
    first = read(f"Password (min {MIN_PASSWORD_LENGTH} chars): ")
    second = read("Repeat password: ")
    if first != second:
        raise ValueError("Passwords do not match.")
    return first


async def create_admin(email: str, password: str, database_url: str | None = None) -> str:
    settings = get_settings()
    engine = make_engine(database_url or settings.database_url.get_secret_value())
    try:
        async with make_sessionmaker(engine)() as session:
            user = await AuthService(session, settings).create_admin(email, password)
            return user.email
    finally:
        await engine.dispose()


async def purge(days: int, database_url: str | None = None) -> PurgeResult:
    engine = make_engine(database_url or get_settings().database_url.get_secret_value())
    try:
        async with make_sessionmaker(engine)() as session:
            return await purge_old_data(session, days)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Create an admin user (prompts for password)")
    create.add_argument("--email", required=True)
    purge_parser = sub.add_parser(
        "purge-old-data", help="Blank visitor metadata and remove old login records"
    )
    purge_parser.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS)
    args = parser.parse_args(argv)

    try:
        if args.command == "create-admin":
            password = prompt_password()
            email = asyncio.run(create_admin(args.email, password))
            print(f"Created admin {email}")
            return 0
        result = asyncio.run(purge(args.days))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Older than {args.days} days: blanked {result.messages_blanked} messages, "
        f"removed {result.login_attempts_deleted} login attempts and "
        f"{result.sessions_deleted} expired sessions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
