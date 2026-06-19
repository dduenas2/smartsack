"""
Enumeraciones compartidas del dominio SmartSack.

Centraliza los valores válidos de campos categóricos para que tanto los
modelos SQLAlchemy como los esquemas Pydantic referencien la misma fuente
de verdad. Cada enum hereda de `str` para serializar limpiamente a JSON
y para que PostgreSQL los almacene como tipos ENUM nativos.
"""

import enum


class UserRole(str, enum.Enum):
    """Roles de usuario permitidos por el sistema."""

    OPERATOR = "operario"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class MachineType(str, enum.Enum):
    """Tipos de máquina presentes en una planta de sacos de papel."""

    TUBULADORA = "tubuladora"   # Forma el tubo de papel desde la bobina.
    IMPRESORA = "impresora"     # Imprime gráfica/lote en el saco.
    FONDADORA = "fondadora"     # Cierra el fondo del saco.
    EMPACADORA = "empacadora"   # Empaca y palletiza los sacos terminados.


class MachineStatus(str, enum.Enum):
    """Estado operativo actual de una máquina (semáforo del Digital Twin)."""

    RUNNING = "running"          # En producción.
    STOPPED = "stopped"          # Detenida (parada no planificada).
    MAINTENANCE = "maintenance"  # En mantenimiento programado.
    IDLE = "idle"                # Disponible sin orden asignada.


class OrderStatus(str, enum.Enum):
    """Ciclo de vida de una orden de producción."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


class OrderPriority(str, enum.Enum):
    """Prioridad comercial de la orden — afecta secuenciación y alertas."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EventType(str, enum.Enum):
    """Tipos de evento que un operario o el sistema pueden registrar."""

    START = "start"                  # Inicio de orden en una máquina.
    STOP = "stop"                    # Parada no planificada.
    PAUSE = "pause"                  # Pausa breve (ej. break del operario).
    RESUME = "resume"                # Reanudación tras pausa/parada.
    FORMAT_CHANGE = "format_change"  # Cambio de formato/setup.
    INCIDENT = "incident"            # Incidencia (calidad, seguridad, etc.).
    MAINTENANCE = "maintenance"      # Inicio o fin de mantenimiento.
    END = "end"                      # Fin de orden.
    # Reporte de producción del operario: incremento (puede ser negativo
    # para corregir mermas o errores). El campo `quantity` lleva el delta;
    # `order.quantity_produced` se actualiza en la misma transacción.
    PRODUCTION_UPDATE = "production_update"


class ShiftName(str, enum.Enum):
    """Nombre de los tres turnos diarios de la planta."""

    TURNO_1 = "turno_1"  # 06:00 – 14:00
    TURNO_2 = "turno_2"  # 14:00 – 22:00
    TURNO_3 = "turno_3"  # 22:00 – 06:00 (cruza medianoche)


class OperationStatus(str, enum.Enum):
    """
    Ciclo de vida de una operación dentro de la ruta IMP→TUB→FON→EMP.

    pending: aún no le toca el turno (operaciones previas sin completar).
    ready:   la operación anterior cerró; el operario puede tomarla.
    in_progress: en ejecución por un operario.
    completed:   cerrada; promueve la siguiente a `ready`.
    """

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ScrapReason(str, enum.Enum):
    """
    Categorías de desperdicio para análisis Pareto.

    quality_defect: producto con defectos (color, registro, sellado).
    setup_loss:     pérdida durante setup/cambio de formato.
    material_break: rotura de bobina, pliego o tubo durante el proceso.
    other:          cualquier otra causa (justificar en `description`).
    """

    QUALITY_DEFECT = "quality_defect"
    SETUP_LOSS = "setup_loss"
    MATERIAL_BREAK = "material_break"
    OTHER = "other"
