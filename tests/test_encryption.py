"""
Tests that verify financial data is encrypted at rest.

No plaintext of sensitive values should appear in the raw DB columns.
All tests operate directly on ORM objects — no HTTP layer needed.
"""
import os

import pytest

from conftest import make_expense, make_month
from database import (
    MonthlyData,
    MonthlyExpense,
    User,
    decrypt_value,
    encrypt_value,
)
from security import get_password_hash


class TestEncryptionHelpers:
    def test_encrypt_produces_non_plaintext(self):
        original = "sensitive_value"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert "sensitive_value" not in encrypted

    def test_decrypt_roundtrip(self):
        original = "hello world 123"
        assert decrypt_value(encrypt_value(original)) == original

    def test_encrypt_none_returns_none(self):
        assert encrypt_value(None) is None

    def test_decrypt_none_returns_none(self):
        assert decrypt_value(None) is None

    def test_encrypt_is_non_deterministic(self):
        """Same plaintext must produce different ciphertext each call (Fernet behaviour)."""
        val = "same_input"
        enc1 = encrypt_value(val)
        enc2 = encrypt_value(val)
        assert enc1 != enc2

    def test_missing_encryption_key_raises(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
            from database import get_encryption_key
            get_encryption_key()


class TestUserFieldEncryption:
    def test_username_not_stored_as_plaintext(self, db):
        user = User(
            email="enc_test@example.com",
            password_hash=get_password_hash("TestPass1!"),
            email_verified=True,
        )
        user.username = "verysecretname"
        db.add(user)
        db.commit()
        db.refresh(user)

        raw_col = user._username_encrypted
        assert raw_col != "verysecretname"
        assert "verysecretname" not in (raw_col or "")

    def test_username_hybrid_property_decrypts_correctly(self, db):
        user = User(
            email="enc_test2@example.com",
            password_hash=get_password_hash("TestPass1!"),
            email_verified=True,
        )
        user.username = "secretusername"
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.username == "secretusername"


class TestMonthlyDataEncryption:
    def test_month_field_not_plaintext(self, db, verified_user):
        m = MonthlyData(user_id=verified_user.id)
        m.month = "2026-01"
        m.salary_planned = 3000.0
        db.add(m)
        db.commit()
        db.refresh(m)

        assert "2026-01" not in (m._month_encrypted or "")
        assert m.month == "2026-01"

    def test_salary_not_plaintext(self, db, verified_user):
        m = MonthlyData(user_id=verified_user.id)
        m.month = "2026-02"
        m.salary_planned = 99999.0
        db.add(m)
        db.commit()
        db.refresh(m)

        assert "99999" not in (m._salary_planned_encrypted or "")
        assert m.salary_planned == pytest.approx(99999.0)


class TestMonthlyExpenseEncryption:
    def test_expense_name_not_plaintext(self, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month, name="Top Secret Expense")

        assert "Top Secret Expense" not in (expense._name_encrypted or "")
        assert expense.name == "Top Secret Expense"

    def test_expense_category_not_plaintext(self, db, verified_user):
        month = make_month(db, verified_user)
        expense = make_expense(db, month, category="HiddenCategory")

        assert "HiddenCategory" not in (expense._category_encrypted or "")
        assert expense.category == "HiddenCategory"

    def test_expense_amounts_not_plaintext(self, db, verified_user):
        month = make_month(db, verified_user)
        e = MonthlyExpense(monthly_data_id=month.id)
        e.name = "Test"
        e.category = "Housing"
        e.planned_amount = 1234.56
        e.actual_amount = 789.01
        db.add(e)
        db.commit()
        db.refresh(e)

        assert "1234.56" not in (e._planned_amount_encrypted or "")
        assert "789.01" not in (e._actual_amount_encrypted or "")
        assert e.planned_amount == pytest.approx(1234.56)
        assert e.actual_amount == pytest.approx(789.01)

    def test_password_hash_is_bcrypt_not_plaintext(self, db):
        """Password hashes are bcrypt-hashed, not Fernet-encrypted."""
        user = User(
            email="pw_test@example.com",
            password_hash=get_password_hash("TestPass1!"),
            email_verified=True,
        )
        db.add(user)
        db.commit()

        # bcrypt hashes start with $2b$
        assert user.password_hash.startswith("$2b$")
        assert "TestPass1!" not in user.password_hash
