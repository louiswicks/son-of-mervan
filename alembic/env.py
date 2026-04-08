import os
import sys
from logging.config import fileConfig


from alembic import context

# Make project root importable so we can import database.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import models so Alembic autogenerate can detect schema.
# engine is reused so PostgreSQL SSL args are inherited automatically.
from database import Base, DATABASE_URL, engine as app_engine  # noqa: E402

# Alembic Config object giving access to alembic.ini values.
config = context.config

# Override sqlalchemy.url from the DATABASE_URL environment variable so
# migrations always run against the same database as the application.
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Provide our models' metadata so autogenerate can diff the schema.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL to stdout, no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the shared application engine."""
    # Reuse the engine already created in database.py so that connection
    # arguments (e.g. sslmode=require for PostgreSQL) are inherited correctly.
    with app_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
