"""
Servicios de lógica de negocio del backend SmartSack.

Aísla la lógica de los routers para mantener endpoints delgados y testeables.
Incluye actualmente: auth_service. Más servicios se sumarán con cada paso
del proyecto (oee_service, prediction_service, chat_service).
"""

from app.services import auth_service  # noqa: F401  (reexporte de conveniencia)

__all__ = ["auth_service"]
