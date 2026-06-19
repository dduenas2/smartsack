"""
Configuración global del backend SmartSack.

Centraliza la lectura de variables de entorno mediante Pydantic Settings.
Cualquier módulo del backend obtiene la configuración importando `settings`
desde aquí, evitando leer os.environ directamente y permitiendo validación
de tipos en tiempo de arranque.
"""

from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """
    Modelo de configuración cargado desde variables de entorno (.env).

    Pydantic valida tipos automáticamente: si una variable obligatoria falta
    o tiene formato incorrecto, la app falla al arrancar con un mensaje claro.
    """

    # ----- Entorno general -----
    environment: str = Field(default="development", alias="ENVIRONMENT")
    project_name: str = Field(default="SmartSack", alias="PROJECT_NAME")
    timezone: str = Field(default="America/Bogota", alias="TZ")

    # ----- PostgreSQL -----
    database_url: str = Field(..., alias="DATABASE_URL")

    # ----- Redis -----
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # ----- Backend -----
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    # ----- Autenticación JWT -----
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=480, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ----- CORS -----
    # NoDecode evita que pydantic-settings intente parsear el valor como JSON;
    # nuestro field_validator lo convierte desde una cadena "a,b,c".
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=list, alias="CORS_ORIGINS"
    )

    # ----- API de Claude -----
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    # ----- Logging -----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        """Convierte una cadena 'a,b,c' en una lista ['a', 'b', 'c']."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una instancia única (cacheada) de Settings.

    Se usa lru_cache para evitar releer .env en cada import; FastAPI también
    puede inyectarla como dependencia mediante Depends(get_settings).
    """
    return Settings()


# Instancia conveniente para usos directos en el código.
settings = get_settings()
