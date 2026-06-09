"""Grant (or revoke) platform-admin to a user by email.

Platform admin is the SPIN Lab operator role that can reach the admin panel,
impersonate users, reset passwords, etc. It is intentionally settable only out
of band — this management command and the dev seed — never through the app UI's
self-service flows.

Run inside the backend container (the stack must be up):
    docker compose exec backend python scripts/grant_platform_admin.py user@example.com
    # revoke:
    docker compose exec backend python scripts/grant_platform_admin.py user@example.com --revoke
    # or via Make:
    make grant-admin email=user@example.com
"""

import argparse
import sys

from database.sessions import Session, init_db


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grant/revoke platform-admin by email.")
    parser.add_argument("email", help="email address of the user")
    parser.add_argument(
        "--revoke", action="store_true", help="revoke instead of grant platform-admin"
    )
    args = parser.parse_args(argv)

    init_db()
    from database.models import user

    s = Session()
    try:
        u = s.query(user).filter(user.email == args.email).first()
        if u is None:
            print(f"No user found with email {args.email!r}.", file=sys.stderr)
            return 1
        u.is_platform_admin = not args.revoke
        s.commit()
        verb = "Revoked" if args.revoke else "Granted"
        print(f"{verb} platform-admin for {u.email} (id={u.id}).")
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main())
