# database.py
import os
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean, create_engine, Column, Index, Integer, String, Float, DateTime,
    ForeignKey, Text, Date, UniqueConstraint
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
        pool_size=10,
        max_overflow=20,
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

    # Preferred display currency (ISO 4217 code, e.g. "GBP", "USD", "EUR")
    base_currency = Column(String(3), nullable=False, default="GBP", server_default="GBP")

    # Monthly email digest opt-in (default True — new users receive the digest)
    digest_enabled = Column(Boolean, nullable=False, default=True, server_default="1")

    # Onboarding wizard completion flag (default False — new users see the wizard)
    has_completed_onboarding = Column(Boolean, nullable=False, default=False, server_default="0")

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
    __table_args__ = (
        Index("ix_monthly_data_user_id", "user_id"),
    )
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

    # Currency of this expense (ISO 4217 code); defaults to user's base_currency at save time
    currency = Column(String(3), nullable=False, default="GBP", server_default="GBP")

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


class BudgetAlert(Base):
    """
    A configurable alert that fires when a category's actual spending
    reaches a given percentage of its planned budget.
    All sensitive fields encrypted at rest.
    """
    __tablename__ = "budget_alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Threshold percentage (e.g. 80 = fire when actual >= 80% of planned)
    threshold_pct = Column(Integer, nullable=False, default=80)

    # Whether this alert is enabled
    active = Column(Boolean, default=True, nullable=False)

    # Soft delete
    deleted_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ENCRYPTED fields
    _category_encrypted = Column("category_encrypted", String(512), nullable=False)

    user = relationship("User")

    @hybrid_property
    def category(self):
        return decrypt_value(self._category_encrypted) if self._category_encrypted else None

    @category.setter
    def category(self, value):
        self._category_encrypted = encrypt_value(value) if value else None


class Notification(Base):
    """
    An in-app notification for a user (e.g. budget alert triggered).
    Title and message are encrypted; dedup_key is an unencrypted hash
    used to prevent duplicate notifications.
    """
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Notification type — not sensitive (e.g. "budget_alert")
    type = Column(String(64), nullable=False, default="budget_alert")

    # NULL = unread; set = read timestamp
    read_at = Column(DateTime, nullable=True, default=None)

    # Deduplication key (e.g. "ba:{alert_id}:{YYYY-MM}") — unencrypted
    dedup_key = Column(String(128), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # ENCRYPTED fields
    _title_encrypted = Column("title_encrypted", String(512), nullable=False)
    _message_encrypted = Column("message_encrypted", String(512), nullable=False)

    user = relationship("User")

    @hybrid_property
    def title(self):
        return decrypt_value(self._title_encrypted) if self._title_encrypted else None

    @title.setter
    def title(self, value):
        self._title_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def message(self):
        return decrypt_value(self._message_encrypted) if self._message_encrypted else None

    @message.setter
    def message(self, value):
        self._message_encrypted = encrypt_value(value) if value else None


class AuditLog(Base):
    """
    Immutable record of every create/update/delete on a MonthlyExpense row.
    changed_fields is a JSON string: {"before": {...}, "after": {...}}.
    Stores plaintext field values (decrypted at write time) so history is
    readable without the encryption key at query time.
    expense_id is intentionally NOT a foreign key so history persists after
    the expense row is soft-deleted.
    """
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expense_id = Column(Integer, nullable=False, index=True)
    # action: "create" | "update" | "delete"
    action = Column(String(16), nullable=False)
    # JSON: {"before": null|{...}, "after": null|{...}}
    changed_fields = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class ExchangeRate(Base):
    """
    Daily exchange rates synced from Frankfurter API (open.er-api.com fallback).
    Rates are stored relative to EUR as the base to allow cross-currency math.
    e.g. base='EUR', target='GBP', rate=0.86 means 1 EUR = 0.86 GBP.
    """
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True, index=True)
    # Base currency (always 'EUR' from our sync source)
    base = Column(String(3), nullable=False, index=True)
    # Target currency ISO 4217 code
    target = Column(String(3), nullable=False, index=True)
    # How many target units equal 1 base unit
    rate = Column(Float, nullable=False)
    # Date this rate is valid for
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("base", "target", "date", name="uq_exchange_rate_base_target_date"),
    )


class Investment(Base):
    """
    A single investment holding (stock, ETF, fund, crypto, etc.).
    Ticker is stored unencrypted for price-sync lookups.
    All financial fields (units, purchase price) are encrypted at rest.
    """
    __tablename__ = "investments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Public ticker symbol — not encrypted (required for Yahoo Finance price sync)
    ticker = Column(String(20), nullable=True)  # nullable for funds/assets without a ticker

    # Asset type: stock | etf | fund | crypto | other
    asset_type = Column(String(16), nullable=False, default="stock")

    # Currency of the investment (ISO 4217)
    currency = Column(String(3), nullable=False, default="GBP")

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, default=None)

    # ENCRYPTED fields
    _name_encrypted = Column("name_encrypted", String(512), nullable=False)
    _units_encrypted = Column("units_encrypted", String(512), nullable=False)
    _purchase_price_encrypted = Column("purchase_price_encrypted", String(512), nullable=False)
    _notes_encrypted = Column("notes_encrypted", String(512), nullable=True)

    user = relationship("User")
    prices = relationship("InvestmentPrice", back_populates="investment", cascade="all, delete-orphan")

    @hybrid_property
    def name(self):
        return decrypt_value(self._name_encrypted) if self._name_encrypted else None

    @name.setter
    def name(self, value):
        self._name_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def units(self):
        val = decrypt_value(self._units_encrypted) if self._units_encrypted else "0.0"
        return float(val)

    @units.setter
    def units(self, value):
        self._units_encrypted = encrypt_value(str(value))

    @hybrid_property
    def purchase_price(self):
        val = decrypt_value(self._purchase_price_encrypted) if self._purchase_price_encrypted else "0.0"
        return float(val)

    @purchase_price.setter
    def purchase_price(self, value):
        self._purchase_price_encrypted = encrypt_value(str(value))

    @hybrid_property
    def notes(self):
        return decrypt_value(self._notes_encrypted) if self._notes_encrypted else None

    @notes.setter
    def notes(self, value):
        self._notes_encrypted = encrypt_value(value) if value else None


class InvestmentPrice(Base):
    """
    Daily price snapshot for an investment holding.
    Stored as plaintext float — price data alone is not personally identifying.
    """
    __tablename__ = "investment_prices"
    id = Column(Integer, primary_key=True, index=True)
    investment_id = Column(Integer, ForeignKey("investments.id"), nullable=False)

    # Price per unit in the investment's currency
    price = Column(Float, nullable=False)

    # When this price was fetched
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    investment = relationship("Investment", back_populates="prices")


class Household(Base):
    """
    A shared budget household. One owner, one or more members.
    All members' expenses roll up into the household budget view.
    """
    __tablename__ = "households"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Human-readable name (e.g. "Smith Family Budget")
    name = Column(String(128), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, default=None)

    owner = relationship("User", foreign_keys=[owner_id])
    memberships = relationship("HouseholdMembership", back_populates="household", cascade="all, delete-orphan")
    invites = relationship("HouseholdInvite", back_populates="household", cascade="all, delete-orphan")


class HouseholdMembership(Base):
    """
    Links a user to a household. role: 'owner' or 'member'.
    Owner row is created automatically when the household is created.
    """
    __tablename__ = "household_memberships"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # role: owner | member
    role = Column(String(16), nullable=False, default="member")
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_member"),
    )

    household = relationship("Household", back_populates="memberships")
    user = relationship("User")


class HouseholdInvite(Base):
    """
    A pending invitation to join a household. Token sent by email; hashed at rest.
    Expires after 7 days. Single-use.
    """
    __tablename__ = "household_invites"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    # Invitee's email — unencrypted so we can match on accept
    invitee_email = Column(String(320), nullable=False, index=True)

    # SHA-256 hash of the raw token sent in the email link
    token_hash = Column(String(64), unique=True, index=True, nullable=False)

    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    household = relationship("Household", back_populates="invites")


class UserCategory(Base):
    """
    User-defined expense category with a display colour.
    The 8 built-in categories are seeded on first GET for each user
    (lazy seeding — no migration data backfill needed).

    Names are stored *unencrypted* because:
      - Category labels ("Housing", "Food") are not sensitive PII.
      - Fernet is non-deterministic, which would make the per-user
        UniqueConstraint unenforceable at the database level.
    """
    __tablename__ = "user_categories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=False, default="#6b7280")
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )


class Debt(Base):
    """
    A user's debt entry (credit card, loan, etc.).
    Name and balance are encrypted at rest. interest_rate and minimum_payment
    are stored as plaintext floats — not PII on their own.
    """
    __tablename__ = "debts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Annual interest rate as a decimal (e.g. 0.18 = 18% APR)
    interest_rate = Column(Float, nullable=False)

    # Fixed monthly minimum payment amount
    minimum_payment = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, default=None)

    # ENCRYPTED fields
    _name_encrypted = Column("name_encrypted", String(512), nullable=False)
    _balance_encrypted = Column("balance_encrypted", String(512), nullable=False)

    user = relationship("User")

    @hybrid_property
    def name(self):
        return decrypt_value(self._name_encrypted) if self._name_encrypted else None

    @name.setter
    def name(self, value):
        self._name_encrypted = encrypt_value(value) if value else None

    @hybrid_property
    def balance(self):
        val = decrypt_value(self._balance_encrypted) if self._balance_encrypted else "0.0"
        return float(val)

    @balance.setter
    def balance(self, value):
        self._balance_encrypted = encrypt_value(str(value))


class NetWorthSnapshot(Base):
    """
    A point-in-time snapshot of the user's net worth.
    assets_json and liabilities_json are encrypted JSON arrays: [{"name": "...", "value": 1234.0}].
    total_assets and total_liabilities are computed sums stored as plaintext floats for read efficiency.
    """
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Plaintext date — not PII on its own
    snapshot_date = Column(Date, nullable=False)

    # Computed totals stored plaintext for efficiency (no sensitive PII on their own)
    total_assets = Column(Float, nullable=False, default=0.0)
    total_liabilities = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, default=None)

    # ENCRYPTED JSON fields (stored as large strings)
    _assets_json_encrypted = Column("assets_json_encrypted", String(4096), nullable=True)
    _liabilities_json_encrypted = Column("liabilities_json_encrypted", String(4096), nullable=True)

    user = relationship("User")

    @hybrid_property
    def assets_json(self):
        raw = decrypt_value(self._assets_json_encrypted) if self._assets_json_encrypted else None
        if not raw:
            return []
        import json
        return json.loads(raw)

    @assets_json.setter
    def assets_json(self, value):
        import json
        self._assets_json_encrypted = encrypt_value(json.dumps(value)) if value is not None else None

    @hybrid_property
    def liabilities_json(self):
        raw = decrypt_value(self._liabilities_json_encrypted) if self._liabilities_json_encrypted else None
        if not raw:
            return []
        import json
        return json.loads(raw)

    @liabilities_json.setter
    def liabilities_json(self, value):
        import json
        self._liabilities_json_encrypted = encrypt_value(json.dumps(value)) if value is not None else None


# Default categories seeded for every new user on their first GET /categories.
DEFAULT_CATEGORIES = [
    ("Housing",        "#ef4444"),
    ("Transportation", "#f97316"),
    ("Food",           "#eab308"),
    ("Utilities",      "#22c55e"),
    ("Insurance",      "#14b8a6"),
    ("Healthcare",     "#3b82f6"),
    ("Entertainment",  "#8b5cf6"),
    ("Other",          "#6b7280"),
]


# ---------- Helpers ----------
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
