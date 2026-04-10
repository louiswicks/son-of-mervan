"""
Application configuration via environment variables.
Uses pydantic-settings so missing required vars cause a loud startup crash.
"""
import sys
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

logger = logging.getLogger(__name__)


# Current application version — bump on each Phase completion going forward
VERSION = "1.16.0"

# Static changelog — newest entry first
CHANGELOG: list[dict] = [
    {"version": "1.16.0", "date": "2026-04-09", "summary": "Phase 16: Reliability & DX — email verification resend, token cleanup, iCal export, month-close card, API changelog"},
    {"version": "1.15.0", "date": "2026-04-08", "summary": "Phase 15: Open Banking — TrueLayer OAuth, transaction sync, draft review, bank disconnect"},
    {"version": "1.14.0", "date": "2026-04-07", "summary": "Phase 14: UI/UX Overhaul — navigation redesign, budget page layout, global visual polish"},
    {"version": "1.13.0", "date": "2026-04-06", "summary": "Phase 13: Performance & Security — code splitting, TOTP 2FA, expense notes/tags, email preferences, session manager"},
    {"version": "1.12.0", "date": "2026-04-05", "summary": "Phase 12: Usability & Production Hardening — budget copy forward, net worth tracker, accessibility, full data export, milestone notifications"},
    {"version": "1.11.0", "date": "2026-04-04", "summary": "Phase 11: Power Features — custom categories, CSV import, cashflow forecast, debt payoff, spending streaks"},
    {"version": "1.10.0", "date": "2026-04-03", "summary": "Phase 10: Operational Excellence — backup/restore scripts, audit log, currency support, AI financial review"},
    {"version": "1.0.0", "date": "2026-01-01", "summary": "Initial release — core budget planning, monthly tracker, savings goals, recurring expenses, alerts"},
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required — no default. App will not start without this.
    JWT_SECRET_KEY: str

    # Optional with safe defaults
    DATABASE_URL: str = ""
    ENCRYPTION_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = ""
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,https://louiswicks.github.io"
    EMAIL_VERIFY_TTL_MIN: int = 60
    PASSWORD_RESET_TTL_MIN: int = 60
    REFRESH_TOKEN_TTL_DAYS: int = 30
    LOG_LEVEL: str = "INFO"
    # "production" enables HSTS and other prod-only security headers
    ENVIRONMENT: str = "development"
    # Sentry DSN — leave empty to disable error reporting (safe for local dev)
    SENTRY_DSN: str = ""
    # Redis URL for caching — leave empty to run without cache (safe for local dev)
    REDIS_URL: str = ""
    # Anthropic API key for AI financial review — leave empty to disable (safe for local dev)
    ANTHROPIC_API_KEY: str = ""

    # TrueLayer open banking — leave empty to disable (safe for local dev)
    TRUELAYER_CLIENT_ID: str = ""
    TRUELAYER_CLIENT_SECRET: str = ""
    TRUELAYER_REDIRECT_URI: str = "http://localhost:8000/banking/callback"
    # Set to True to use TrueLayer sandbox (mock bank data)
    TRUELAYER_SANDBOX: bool = True

    # GoCardless Bank Account Data (formerly Nordigen) — leave empty to disable
    # Sign up free at https://bankaccountdata.gocardless.com
    # Supports HSBC, Santander, Monzo, and most major UK banks
    GOCARDLESS_SECRET_ID: str = ""
    GOCARDLESS_SECRET_KEY: str = ""
    GOCARDLESS_REDIRECT_URI: str = "http://localhost:8000/banking/callback/gocardless"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JWT_SECRET_KEY must not be empty")
        return v


def get_settings() -> Settings:
    """
    Load and validate settings. Exits the process with a clear error message
    if any required variable is missing or invalid.
    """
    try:
        return Settings()
    except Exception as e:
        logging.basicConfig(level=logging.CRITICAL)
        logging.critical(
            "[FATAL] Configuration error — application cannot start: %s  "
            "Set the missing environment variables and restart.",
            e,
        )
        sys.exit(1)


# Module-level singleton — imported by security.py and main.py
settings = get_settings()
