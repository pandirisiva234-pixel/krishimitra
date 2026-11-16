"""Create (or promote) an admin account.

    cd backend
    python -m scripts.create_admin --name "Pandri" --phone 9876543210 --email admin@example.com
The password is asked for interactively, so it never appears in the terminal history.
"""
import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import ROLE_ADMIN, Admin, Language, User
from app.schemas.auth import RegisterRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--email")
    parser.add_argument("--designation", default="System Administrator")
    parser.add_argument("--password", help="Avoid on shared machines; prompts if omitted")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password: ")
    if not args.password and password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    try:
        data = RegisterRequest(full_name=args.name, phone=args.phone, email=args.email, password=password)
    except ValidationError as exc:
        sys.exit(f"Invalid input: {exc.errors()[0]['msg']}")

    db = SessionLocal()
    try:
        english = db.scalars(select(Language).where(Language.code == "en")).first()
        if english is None:
            sys.exit("Languages are not seeded. Run: python -m scripts.seed_data")
        user = db.scalars(select(User).where(User.phone == data.phone)).first()
        if user:
            user.role = ROLE_ADMIN
            print(f"Promoted existing user {user.full_name} to admin")
        else:
            user = User(full_name=data.full_name, phone=data.phone, email=data.email, role=ROLE_ADMIN,
                        password_hash=hash_password(data.password), preferred_language_id=english.id)
            db.add(user)
            db.flush()
            print(f"Created admin {user.full_name} ({user.phone})")
        if user.admin_profile is None:
            db.add(Admin(user_id=user.id, designation=args.designation))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
