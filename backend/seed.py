"""Seed >=2 test accounts (brief requirement, phase 5 task 5).

Usage:
    cd backend && source venv/Scripts/activate
    python seed.py

Idempotent: re-running skips accounts that already exist instead of
erroring. Credentials come from env vars so real passwords are never
hardcoded in this file; if unset, a random password is generated and
printed once so it can be copied into the private submission note.
DO NOT commit generated/real credentials to a public repo -- see
_plan/phase5.txt task 5 and 00_agent_ground_rules.txt rule 10.
"""

import os
import secrets

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.models import User, db  # noqa: E402

SEED_ACCOUNTS = [
    (os.environ.get("SEED_USER1_EMAIL", "tester1@example.com"), os.environ.get("SEED_USER1_PASSWORD")),
    (os.environ.get("SEED_USER2_EMAIL", "tester2@example.com"), os.environ.get("SEED_USER2_PASSWORD")),
]


def seed():
    app = create_app(Config)
    with app.app_context():
        for email, password in SEED_ACCOUNTS:
            existing = User.query.filter_by(email=email).first()
            if existing is not None:
                print(f"skip {email} (already exists)")
                continue

            generated = password is None
            if generated:
                password = secrets.token_urlsafe(12)

            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            note = " (generated -- copy this into the private submission note now)" if generated else ""
            print(f"created {email} / {password}{note}")


if __name__ == "__main__":
    seed()
