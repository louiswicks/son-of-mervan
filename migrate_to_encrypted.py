import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import your encryption functions
from database import encrypt_value

# Connect to database
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def migrate_users():
    """Migrate users table"""
    session = Session()
    
    # Add new encrypted column
    session.execute(text("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS username_encrypted VARCHAR(512);
    """))
    
    # Migrate existing data
    users = session.execute(text("SELECT id, username FROM users WHERE username IS NOT NULL"))
    for user_id, username in users:
        encrypted = encrypt_value(username)
        session.execute(
            text("UPDATE users SET username_encrypted = :enc WHERE id = :id"),
            {"enc": encrypted, "id": user_id}
        )
    
    session.commit()
    print("✓ Users migrated")

def migrate_monthly_data():
    """Migrate monthly_data table"""
    session = Session()
    
    # Add encrypted columns
    columns = [
        "month_encrypted VARCHAR(512)",
        "salary_planned_encrypted VARCHAR(512)",
        "salary_actual_encrypted VARCHAR(512)",
        "total_planned_encrypted VARCHAR(512)",
        "total_actual_encrypted VARCHAR(512)",
        "remaining_planned_encrypted VARCHAR(512)",
        "remaining_actual_encrypted VARCHAR(512)"
    ]
    
    for col in columns:
        session.execute(text(f"ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS {col}"))
    
    # Migrate data
    rows = session.execute(text("""
        SELECT id, month, salary_planned, salary_actual, 
               total_planned, total_actual, remaining_planned, remaining_actual
        FROM monthly_data
    """))
    
    for row in rows:
        session.execute(text("""
            UPDATE monthly_data SET
                month_encrypted = :month,
                salary_planned_encrypted = :sp,
                salary_actual_encrypted = :sa,
                total_planned_encrypted = :tp,
                total_actual_encrypted = :ta,
                remaining_planned_encrypted = :rp,
                remaining_actual_encrypted = :ra
            WHERE id = :id
        """), {
            "month": encrypt_value(row[1]),
            "sp": encrypt_value(str(row[2])),
            "sa": encrypt_value(str(row[3])),
            "tp": encrypt_value(str(row[4])),
            "ta": encrypt_value(str(row[5])),
            "rp": encrypt_value(str(row[6])),
            "ra": encrypt_value(str(row[7])),
            "id": row[0]
        })
    
    session.commit()
    print("✓ Monthly data migrated")

def migrate_monthly_expenses():
    """Migrate monthly_expenses table"""
    session = Session()
    
    # Add encrypted columns
    columns = [
        "name_encrypted VARCHAR(512)",
        "category_encrypted VARCHAR(512)",
        "planned_amount_encrypted VARCHAR(512)",
        "actual_amount_encrypted VARCHAR(512)"
    ]
    
    for col in columns:
        session.execute(text(f"ALTER TABLE monthly_expenses ADD COLUMN IF NOT EXISTS {col}"))
    
    # Migrate data
    rows = session.execute(text("""
        SELECT id, name, category, planned_amount, actual_amount
        FROM monthly_expenses
    """))
    
    for row in rows:
        session.execute(text("""
            UPDATE monthly_expenses SET
                name_encrypted = :name,
                category_encrypted = :cat,
                planned_amount_encrypted = :pa,
                actual_amount_encrypted = :aa
            WHERE id = :id
        """), {
            "name": encrypt_value(row[1]),
            "cat": encrypt_value(row[2]),
            "pa": encrypt_value(str(row[3])),
            "aa": encrypt_value(str(row[4])),
            "id": row[0]
        })
    
    session.commit()
    print("✓ Monthly expenses migrated")

def cleanup_old_columns():
    """
    ONLY RUN THIS AFTER VERIFYING MIGRATION WORKED!
    This drops the old unencrypted columns.
    """
    session = Session()
    
    # Drop old columns from users
    session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS username"))
    
    # Drop old columns from monthly_data
    old_cols = ["month", "salary_planned", "salary_actual", 
                "total_planned", "total_actual", "remaining_planned", "remaining_actual"]
    for col in old_cols:
        session.execute(text(f"ALTER TABLE monthly_data DROP COLUMN IF EXISTS {col}"))
    
    # Drop old columns from monthly_expenses
    old_cols = ["name", "category", "planned_amount", "actual_amount"]
    for col in old_cols:
        session.execute(text(f"ALTER TABLE monthly_expenses DROP COLUMN IF EXISTS {col}"))
    
    session.commit()
    print("✓ Old columns dropped")

if __name__ == "__main__":
    print("Starting migration...")
    migrate_users()
    migrate_monthly_data()
    migrate_monthly_expenses()
    print("\n✅ Migration complete!")
    print("\n⚠️  VERIFY YOUR DATA BEFORE RUNNING cleanup_old_columns()!")