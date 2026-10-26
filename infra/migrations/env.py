from alembic import context

from clearledger import (
    case_models,  # noqa: F401
    correlation_models,  # noqa: F401
    evidence_models,  # noqa: F401
    finance_models,  # noqa: F401
    investigation_models,  # noqa: F401
    review_models,  # noqa: F401
)
from clearledger.config import Settings
from clearledger.db import build_engine
from clearledger.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=Settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Integration tests supply their disposable connection explicitly.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = build_engine(Settings().database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
