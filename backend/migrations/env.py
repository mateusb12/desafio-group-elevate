"""Migrations Alembic usando o mesmo engine e metadata da aplicacao."""

from alembic import context
from shared.database import Base, engine

# Cada dominio registra suas tabelas na metadata compartilhada.
from features.auth import models as auth_models  # noqa: F401
from features.dispatcher import models as dispatcher_models  # noqa: F401
from features.leads import models as leads_models  # noqa: F401


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
