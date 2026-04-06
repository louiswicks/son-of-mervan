#!/usr/bin/env python3
"""CLI script for database migration and cleanup operations.

Never expose these as HTTP endpoints — run them manually from the shell.

Usage:
    python scripts/migrate.py migrate            # Migrate plaintext columns to Fernet-encrypted
    python scripts/migrate.py cleanup            # Drop old unencrypted columns after migration
    python scripts/migrate.py check-month YYYY-MM  # Inspect a month's data for a given user email
"""
import argparse
import os
import sys

# Allow imports from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_migrate(_args: argparse.Namespace) -> None:
    """Run migrate_to_encrypted.py as a subprocess."""
    import subprocess

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(project_root, "migrate_to_encrypted.py")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


def cmd_cleanup(_args: argparse.Namespace) -> None:
    """Drop old unencrypted columns from all tables."""
    from sqlalchemy import text
    from database import engine

    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS username"))

        for col in [
            "month", "salary_planned", "salary_actual",
            "total_planned", "total_actual", "remaining_planned", "remaining_actual",
        ]:
            conn.execute(text(f"ALTER TABLE monthly_data DROP COLUMN IF EXISTS {col}"))

        for col in ["name", "category", "planned_amount", "actual_amount"]:
            conn.execute(text(f"ALTER TABLE monthly_expenses DROP COLUMN IF EXISTS {col}"))

        conn.commit()

    print("Old unencrypted columns dropped successfully.")


def cmd_check_month(args: argparse.Namespace) -> None:
    """Print decrypted data for a specific month and user email."""
    from database import get_db, User, MonthlyData, MonthlyExpense

    db = next(get_db())
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            sys.exit(f"User not found: {args.email}")

        all_months = db.query(MonthlyData).filter(MonthlyData.user_id == user.id).all()
        month_row = next((r for r in all_months if r.month == args.month), None)
        if not month_row:
            sys.exit(f"No data found for month {args.month!r} and user {args.email!r}")

        expenses = (
            db.query(MonthlyExpense)
            .filter(MonthlyExpense.monthly_data_id == month_row.id)
            .all()
        )

        print(f"Month:             {month_row.month}")
        print(f"Salary planned:    {month_row.salary_planned}")
        print(f"Salary actual:     {month_row.salary_actual}")
        print(f"Total planned:     {month_row.total_planned}")
        print(f"Total actual:      {month_row.total_actual}")
        print(f"Remaining planned: {month_row.remaining_planned}")
        print(f"Remaining actual:  {month_row.remaining_actual}")
        print(f"\nExpenses ({len(expenses)}):")
        for exp in expenses:
            print(
                f"  [{exp.category}] {exp.name}: "
                f"planned={exp.planned_amount}, actual={exp.actual_amount}"
            )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Son-of-Mervan database management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="Migrate plaintext columns to Fernet-encrypted columns")
    sub.add_parser("cleanup", help="Drop old unencrypted columns after migration is verified")

    check_p = sub.add_parser("check-month", help="Inspect a month's data for a user")
    check_p.add_argument("month", help="Month in YYYY-MM format")
    check_p.add_argument("email", help="User email address")

    args = parser.parse_args()

    dispatch = {
        "migrate": cmd_migrate,
        "cleanup": cmd_cleanup,
        "check-month": cmd_check_month,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
