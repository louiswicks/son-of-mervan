import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# --- Database setup ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./budget.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)

    months = relationship("MonthlyData", back_populates="owner", cascade="all, delete-orphan")

class MonthlyData(Base):
    """
    One row per user per month. Holds summary fields for both planned and actual.
    Detailed line items live in MonthlyExpense (planned_amount & actual_amount).
    """
    __tablename__ = "monthly_data"
    id = Column(Integer, primary_key=True, index=True)
    month = Column(String, index=True, nullable=False)  # e.g. "2025-08"

    # salary
    salary_planned = Column(Float, default=0.0)
    salary_actual = Column(Float, default=0.0)

    # totals
    total_planned = Column(Float, default=0.0)
    total_actual = Column(Float, default=0.0)

    # remaining
    remaining_planned = Column(Float, default=0.0)
    remaining_actual = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # owner
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="months")

    # detailed items
    expenses = relationship("MonthlyExpense", back_populates="monthly", cascade="all, delete-orphan")

class MonthlyExpense(Base):
    """
    A single line item for a given month. Holds both planned and actual amounts.
    """
    __tablename__ = "monthly_expenses"
    id = Column(Integer, primary_key=True, index=True)
    monthly_data_id = Column(Integer, ForeignKey("monthly_data.id"), nullable=False)

    name = Column(String, nullable=False)
    category = Column(String, nullable=False)

    planned_amount = Column(Float, default=0.0)
    actual_amount = Column(Float, default=0.0)

    monthly = relationship("MonthlyData", back_populates="expenses")

# --- Helpers ---
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
