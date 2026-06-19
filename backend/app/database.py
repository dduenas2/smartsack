"""
Configuración de la base de datos PostgreSQL para SmartSack.

Define el engine de SQLAlchemy, la SessionLocal y la clase Base de la que
heredarán todos los modelos ORM. Expone también la dependencia `get_db`
para inyectar sesiones en los endpoints de FastAPI.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# Engine único compartido por toda la aplicación.
# pool_pre_ping=True valida cada conexión antes de usarla, evitando errores
# por conexiones cerradas tras periodos de inactividad.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # Cambiar a True para ver el SQL generado en desarrollo.
)


# Fábrica de sesiones. autoflush=False da control explícito al programador.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos SQLAlchemy del proyecto.

    Los modelos en `app/models/*.py` heredarán de esta clase para que
    Alembic pueda detectarlos y generar migraciones automáticamente.
    """

    pass


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia de FastAPI que entrega una sesión por petición.

    Se inyecta en los endpoints con `db: Session = Depends(get_db)`.
    Garantiza que la sesión se cierre al terminar la petición incluso
    si ocurre una excepción.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
