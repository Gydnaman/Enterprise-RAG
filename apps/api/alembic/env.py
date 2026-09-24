from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, event, pool
from sqlalchemy.engine import make_url

from rag_workbench.adapters.database import Base
from rag_workbench.adapters import models  # noqa: F401 - registers metadata tables
from rag_workbench.config import settings


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
url = os.getenv("DATABASE_URL", settings.database_url).replace("%", "%%")
config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database = make_url(url).database if url.startswith("sqlite") else None
    if database and database != ":memory:" and not database.startswith("file:"):
        Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    if url.startswith("sqlite"):
        @event.listens_for(connectable, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
