"""
Application configuration via environment variables.
Uses pydantic-settings so missing required vars cause a loud startup crash.
"""
import sys
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

logger = logging.getLogger(__name__)


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
        print(
            f"\n[FATAL] Configuration error — application cannot start:\n  {e}\n"
            f"  Set the missing environment variables and restart.\n",
            file=sys.stderr,
        )
        sys.exit(1)


# Module-level singleton — imported by security.py and main.py
settings = get_settings()
