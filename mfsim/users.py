"""Manage accounts from the command line.

    python -m mfsim.users list
    python -m mfsim.users add NAME        # prompts for the password
    python -m mfsim.users passwd NAME     # resets it and signs NAME out everywhere
    python -m mfsim.users delete NAME     # removes the account and everything it uploaded
"""

from __future__ import annotations

import argparse
import getpass
import sys

from .store import AuthError, Store


def _ask_password() -> str:
    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Again: "):
        sys.exit("The passwords don't match.")
    return pw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mfsim.users", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["list", "add", "passwd", "delete"])
    parser.add_argument("username", nargs="?")
    args = parser.parse_args(argv)
    if args.action != "list" and not args.username:
        parser.error(f"{args.action} needs a username")

    Store.init()
    with Store() as store:
        if args.action == "list":
            for u in store.list_users():
                print(f"{u['username']:<32} created {u['created_at']}  {u['uploads']} upload(s)")
            return 0
        user = store.user_by_name(args.username)
        try:
            if args.action == "add":
                store.create_user(args.username, _ask_password())
                print(f"Created {args.username}.")
            elif not user:
                sys.exit(f"No user called {args.username}.")
            elif args.action == "passwd":
                store.set_password(user["id"], _ask_password())
                print(f"Changed the password for {user['username']}.")
            else:
                if input(f"Delete {user['username']} and all their uploads? [y/N] ").lower() != "y":
                    return 1
                store.delete_user(user["id"])
                print(f"Deleted {user['username']}.")
        except AuthError as e:
            sys.exit(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
