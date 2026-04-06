# database.py
import os
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean, create_engine, Column, Integer, String, Float, DateTime, 
    ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property

# ---------- Encryption Setup ----------
def get_encryption_key():
    """
    Derives encryption key from environment variable.
    ENCRYPTION_KEY should be a 32-byte base64-encoded string.
    Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable not set!")
    return key.encode()

def get_fernet():
    """Returns Fernet instance for encryption/decryption"""
    return Fernet(get_encryption_key())

def encrypt_value(value):
    """Encrypt a string value"""
    if value is None:
        return None
    f = get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value):
    """Decrypt an encrypted string"""
    if encrypted_value is None:
        return None
    f = get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()

# ---------- Engine / Session ----------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./budget.db"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    connect_args = {}
    if DATABASE_URL.startswith("postgresql"):
        connect_args = {"sslmode": "require"}
    
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------- Models ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    
    # UNENCRYPTED - needed for login/lookups
    email = Column(String(320), unique=True, index=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    verification_sent_at = Column(DateTime, default=datetime.utcnow)
    
    # ENCRYPTED - stored as text, encrypted
    _username_encrypted = Column("username_encrypted", String(512), nullable=True)
    
    # Password hash stays as-is (already hashed, not encrypted)
    password_hash = Column(String(255), nullable=False)
    
    # Soft-delete timestamp — NULL means active, set means pending 30-day data removal
    deleted_at = Column(DateTime, nullable=True, default=None)

    months = relationship("MonthlyData", back_populates="owner", cascade="all, delete-orphan")
    
    # Hybrid property for transparent encryption/decryption
    @hybrid_property
    def username(self):
        """Decrypt username when accessed"""
        if self._username_encrypted:
            return decrypt_value(self._username_encrypted)
        return None
    
    @username.setter
    def username(self, value):
        """Encrypt username when set"""
        if value:
            self._username_encrypted = encrypt_value(value)
        else:
            self._username_encrypted = None

    @username.expression
    def username(cls):
        """
        SQL expression fallback — returns the raw encrypted column.
        Since Fernet is non-deterministic, SQL equality comparisons against
        plaintext will never match. All username lookups that need to find a
        user by their plaintext username must decrypt in Python (O(n) scan).
        This expression exists solely to prevent AttributeError when the
        property is referenced at class level (e.g. in a filter clause).
        """
        return cls._username_encrypted


class MonthlyData(Base):
    """
    One row per user per month. All financial data encrypted.
    """
    __tablename__ = "monthly_data"
    id = Column(Integer, primary_key=True, index=True)
    
    # ENCRYPTED - month identifier
    _month_encrypted = Column("month_encrypted", String(512), nullable=False)
    
    # ENCRYPTED - salary (stored as encrypted strings)
    _salary_planned_encrypted = Column("salary_planned_encrypted", String(512), default=None)
    _salary_actual_encrypted = Column("salary_actual_encrypted", String(512), default=None)
    
    # ENCRYPTED - totals
    _total_planned_encrypted = Column("total_planned_encrypted", String(512), default=None)
    _total_actual_encrypted = Column("total_actual_encrypted", String(512), default=None)
    
    # ENCRYPTED - remaining
    _remaining_planned_encrypted = Column("remaining_planned_encrypted", String(512), default=None)
    _remaining_actual_encrypted = Column("remaining_actual_encrypted", String(512), default=None)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="months")
    expenses = relationship("MonthlyExpense", back_populates="monthly", cascade="all, delete-orphan")
    
    # Hybrid properties for transparent access
    @hybrid_property
    def month(self):
        return decrypt_value(self._month_encrypted) if self._month_encrypted else None
    
    @month.setter
    def month(self, value):
        self._month_encrypted = encrypt_value(value) if value else None
    
    @hybrid_property
    def salary_planned(self):
        val = decrypt_value(self._salary_planned_encrypted) if self._salary_planned_encrypted else "0.0"
        return float(val)
    
    @salary_planned.setter
    def salary_planned(self, value):
        self._salary_planned_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def salary_actual(self):
        val = decrypt_value(self._salary_actual_encrypted) if self._salary_actual_encrypted else "0.0"
        return float(val)
    
    @salary_actual.setter
    def salary_actual(self, value):
        self._salary_actual_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def total_planned(self):
        val = decrypt_value(self._total_planned_encrypted) if self._total_planned_encrypted else "0.0"
        return float(val)
    
    @total_planned.setter
    def total_planned(self, value):
        self._total_planned_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def total_actual(self):
        val = decrypt_value(self._total_actual_encrypted) if self._total_actual_encrypted else "0.0"
        return float(val)
    
    @total_actual.setter
    def total_actual(self, value):
        self._total_actual_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def remaining_planned(self):
        val = decrypt_value(self._remaining_planned_encrypted) if self._remaining_planned_encrypted else "0.0"
        return float(val)
    
    @remaining_planned.setter
    def remaining_planned(self, value):
        self._remaining_planned_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def remaining_actual(self):
        val = decrypt_value(self._remaining_actual_encrypted) if self._remaining_actual_encrypted else "0.0"
        return float(val)
    
    @remaining_actual.setter
    def remaining_actual(self, value):
        self._remaining_actual_encrypted = encrypt_value(str(value))


class MonthlyExpense(Base):
    """
    A single line item for a given month. All details encrypted.
    """
    __tablename__ = "monthly_expenses"
    id = Column(Integer, primary_key=True, index=True)
    monthly_data_id = Column(Integer, ForeignKey("monthly_data.id"), nullable=False)
    
    # ENCRYPTED fields
    _name_encrypted = Column("name_encrypted", String(512), nullable=False)
    _category_encrypted = Column("category_encrypted", String(512), nullable=False)
    _planned_amount_encrypted = Column("planned_amount_encrypted", String(512), default=None)
    _actual_amount_encrypted = Column("actual_amount_encrypted", String(512), default=None)

    # Soft-delete timestamp — NULL means not deleted
    deleted_at = Column(DateTime, nullable=True, default=None)

    monthly = relationship("MonthlyData", back_populates="expenses")
    
    # Hybrid properties
    @hybrid_property
    def name(self):
        return decrypt_value(self._name_encrypted) if self._name_encrypted else None
    
    @name.setter
    def name(self, value):
        self._name_encrypted = encrypt_value(value) if value else None
    
    @hybrid_property
    def category(self):
        return decrypt_value(self._category_encrypted) if self._category_encrypted else None
    
    @category.setter
    def category(self, value):
        self._category_encrypted = encrypt_value(value) if value else None
    
    @hybrid_property
    def planned_amount(self):
        val = decrypt_value(self._planned_amount_encrypted) if self._planned_amount_encrypted else "0.0"
        return float(val)
    
    @planned_amount.setter
    def planned_amount(self, value):
        self._planned_amount_encrypted = encrypt_value(str(value))
    
    @hybrid_property
    def actual_amount(self):
        val = decrypt_value(self._actual_amount_encrypted) if self._actual_amount_encrypted else "0.0"
        return float(val)
    
    @actual_amount.setter
    def actual_amount(self, value):
        self._actual_amount_encrypted = encrypt_value(str(value))


class PasswordResetToken(Base):
    """
    Single-use password reset tokens. Raw token is sent in email;
    only a SHA-256 hash is stored here to prevent DB leakage attacks.
    """
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class RefreshToken(Base):
    """
    Long-lived refresh tokens (30-day TTL) stored as httpOnly cookies.
    Only the SHA-256 hash is persisted; the raw token lives in the cookie.
    """
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class RecurringExpense(Base):
    """
    A recurring expense template that auto-generates MonthlyExpense rows.
    Frequencies: daily, weekly, monthly, yearly.
    All sensitive fields encrypted at rest.
    """
    __tablename__ = "recurring_expenses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Frequency: daily / weekly / monthly / yearly
    frequency = Column(String(16), nullable=False)

    # Date range (stored as DateTime for consistency with rest of schema)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True, default=None)

    # Tracks when a planned row was last generated; used to avoid duplicate rows
    last_generated_at = Column(DateTime, nullable=True, default=None)

    # Soft delete
    deleted_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ENCRYPTED fields
    _name_encrypted = Column("name_encrypted", String(512), nullable=False)
    _category_encrypted = Column("category_encrypted", String(512), nullable=False)
    _planned_amount_encrypted = Column("planned_amount_encrypted", String(512), nullable=False)

    user = relationship("User")

    @hybrid_property
    def name(self):
        return decrypt_value(self._name_encrypted) if self._name_encrypted else None

    @name.setter
    def name(self, value):
        self._name_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def category(self):
        return decrypt_value(self._category_encrypted) if self._category_encrypted else None

    @category.setter
    def category(self, value):
        self._category_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def planned_amount(self):
        val = decrypt_value(self._planned_amount_encrypted) if self._planned_amount_encrypted else "0.0"
        return float(val)

    @planned_amount.setter
    def planned_amount(self, value):
        self._planned_amount_encrypted = encrypt_value(str(value))


class SavingsGoal(Base):
    """
    A named savings target with an optional deadline.
    current_amount is computed dynamically from SavingsContribution rows.
    All sensitive fields encrypted at rest.
    """
    __tablename__ = "savings_goals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Optional deadline for the goal
    target_date = Column(DateTime, nullable=True, default=None)

    # Soft delete
    deleted_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ENCRYPTED fields
    _name_encrypted = Column("name_encrypted", String(512), nullable=False)
    _target_amount_encrypted = Column("target_amount_encrypted", String(512), nullable=False)

    user = relationship("User")
    contributions = relationship("SavingsContribution", back_populates="goal", cascade="all, delete-orphan")

    @hybrid_property
    def name(self):
        return decrypt_value(self._name_encrypted) if self._name_encrypted else None

    @name.setter
    def name(self, value):
        self._name_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def target_amount(self):
        val = decrypt_value(self._target_amount_encrypted) if self._target_amount_encrypted else "0.0"
        return float(val)

    @target_amount.setter
    def target_amount(self, value):
        self._target_amount_encrypted = encrypt_value(str(value))


class SavingsContribution(Base):
    """
    A single contribution toward a SavingsGoal.
    amount is encrypted; note is optional and encrypted.
    """
    __tablename__ = "savings_contributions"
    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("savings_goals.id"), nullable=False)

    # Date the contribution was made (defaults to UTC today)
    contributed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ENCRYPTED fields
    _amount_encrypted = Column("amount_encrypted", String(512), nullable=False)
    _note_encrypted = Column("note_encrypted", String(512), nullable=True)

    goal = relationship("SavingsGoal", back_populates="contributions")

    @hybrid_property
    def amount(self):
        val = decrypt_value(self._amount_encrypted) if self._amount_encrypted else "0.0"
        return float(val)

    @amount.setter
    def amount(self, value):
        self._amount_encrypted = encrypt_value(str(value))

    @hybrid_property
    def note(self):
        return decrypt_value(self._note_encrypted) if self._note_encrypted else None

    @note.setter
    def note(self, value):
        self._note_encrypted = encrypt_value(value) if value else None


# ---------- Helpers ----------
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
