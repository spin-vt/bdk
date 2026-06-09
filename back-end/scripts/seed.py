"""Seed a minimal dev dataset so you can log in and click around:
one organization + one verified admin user + an empty sample filing.

Run inside the backend container (the stack must be up):
    make seed
    # or: docker compose exec backend python scripts/seed.py

Idempotent: does nothing if the dev user already exists.
"""

from datetime import date

from werkzeug.security import generate_password_hash

from database.models import folder, organization, user
from database.sessions import Session, init_db

EMAIL = "dev@example.com"
PASSWORD = "devpassword"  # noqa: S105 — dev-only seed credential


def main():
    init_db()  # ensure tables exist
    s = Session()
    try:
        if s.query(user).filter(user.email == EMAIL).first():
            print(f"User {EMAIL} already exists — nothing to seed.")
            return

        org = organization(name="Dev ISP", provider_id=999999, brand_name="Dev ISP")
        s.add(org)
        s.flush()  # assign org.id

        s.add(
            user(
                email=EMAIL,
                password=generate_password_hash(PASSWORD, method="pbkdf2:sha256"),
                verified=True,
                is_admin=True,
                # Dev login doubles as the platform admin so /admin is reachable
                # out of the box.
                is_platform_admin=True,
                organization_id=org.id,
            )
        )

        f = folder(
            name="Sample Filing", type="upload", deadline=date(2025, 9, 1), organization_id=org.id
        )
        s.add(f)
        s.commit()
        print("Seeded:")
        print(f"  organization : {org.name} (id={org.id})")
        print(f"  login        : {EMAIL} / {PASSWORD}")
        print(f"  filing       : id={f.id}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
