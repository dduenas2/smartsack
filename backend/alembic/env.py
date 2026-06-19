"""
Entorno de Alembic para SmartSack.

- Lee DATABASE_URL desde la configuración de la app (Pydantic Settings).
- Importa `app.models` para que `Base.metadata` contenga todas las tablas
  y autogenerate funcione.
- Soporta migraciones online (con conexión real) y offline (genera SQL).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar la configuración y los modelos del proyecto.
from app.config import settings
from app.database import Base
from app import models  # noqa: F401 — necesario para registrar las tablas en Base.metadata


# ----- Configuración de Alembic -----
config = context.config

# Inyectar la URL real de la BD en la configuración de Alembic.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse a la BD (útil para auditoría/CI)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica migraciones contra la BD configurada."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
