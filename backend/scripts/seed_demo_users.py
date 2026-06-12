"""Seed demo users into the database.

Can be run as a standalone script or imported by the application.

Usage:
    cd backend
    python -m scripts.seed_demo_users
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_USERS = [
    {
        "name": "Ahmad Rizki",
        "email": "admin@jembatanbaru.co.id",
        "password": "admin123",
        "role": "admin",
        "department": "Accounting Tax",
        "avatar": "AR",
    },
    {
        "name": "Siti Rahayu",
        "email": "director@jembatanbaru.co.id",
        "password": "exec123",
        "role": "executive",
        "department": "Board",
        "avatar": "SR",
    },
    {
        "name": "Budi Santoso",
        "email": "demand@jembatanbaru.co.id",
        "password": "demand123",
        "role": "staff",
        "department": "Demand Supply",
        "avatar": "BS",
    },
    {
        "name": "Dewi Kusuma",
        "email": "finance@jembatanbaru.co.id",
        "password": "finance123",
        "role": "staff",
        "department": "Finance",
        "avatar": "DK",
    },
]


def generate_sql() -> str:
    """Generate SQL INSERT statements for demo users with bcrypt password hashes."""
    lines = [
        "-- Demo users for Executive Copilot",
        "-- Passwords are bcrypt-hashed. Plaintext passwords listed in comments for reference.",
        "-- Run this against the kb_manager.db SQLite database.",
        "",
        "INSERT OR IGNORE INTO users (name, email, role, department, status, password_hash, avatar, created_at, updated_at)",
        "VALUES",
    ]

    values = []
    for user in DEMO_USERS:
        hashed = pwd_context.hash(user["password"])
        values.append(
            f"  ('{user['name']}', '{user['email']}', '{user['role']}', "
            f"'{user['department']}', 'active', '{hashed}', '{user['avatar']}', "
            f"datetime('now'), datetime('now'))  -- password: {user['password']}"
        )

    lines.append(",\n".join(values) + ";")
    return "\n".join(lines)


def seed_to_database():
    """Insert demo users directly into the database (skips existing emails)."""
    import sys
    sys.path.insert(0, ".")

    from app.database import SessionLocal, engine, Base
    from app.models.user import User

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        created = 0
        for user_data in DEMO_USERS:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                print(f"  ⏭  {user_data['email']} already exists, skipping")
                continue

            user = User(
                name=user_data["name"],
                email=user_data["email"],
                role=user_data["role"],
                department=user_data["department"],
                status="active",
                password_hash=pwd_context.hash(user_data["password"]),
                avatar=user_data["avatar"],
            )
            db.add(user)
            created += 1
            print(f"  ✓  Created {user_data['email']} ({user_data['role']})")

        db.commit()
        print(f"\nDone. {created} user(s) created.")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed demo users")
    parser.add_argument("--sql", action="store_true", help="Print SQL instead of inserting into DB")
    args = parser.parse_args()

    if args.sql:
        print(generate_sql())
    else:
        print("Seeding demo users into database...\n")
        seed_to_database()
