"""Admin command line.

    uv run python -m app.cli create-admin --email you@example.com

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


def prompt_password(read: Callable[[str], str] = getpass.getpass) -> str:
    first = read(f"Password (min {MIN_PASSWORD_LENGTH} chars): ")
    second = read("Repeat password: ")
    if first != second:
        raise ValueError("Passwords do not match.")
    return first


async def create_admin(email: str, password: str, database_url: str | None = None) -> str:
    settings = get_settings()
    engine = make_engine(database_url or settings.database_url)
    try:
        async with make_sessionmaker(engine)() as session:
            user = await AuthService(session, settings).create_admin(email, password)
            return user.email
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Create an admin user (prompts for password)")
    create.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    if args.command == "create-admin":
        try:
            password = prompt_password()
            email = asyncio.run(create_admin(args.email, password))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Created admin {email}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
