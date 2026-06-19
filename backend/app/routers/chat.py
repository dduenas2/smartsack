"""
Router /api/chat — asistente conversacional sobre datos de la planta.

Endpoints:
  · POST /message  → manda un mensaje + historial, devuelve la respuesta del asistente.
  · GET  /status   → indica si el LLM está activo o si se usa el modo fallback.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models import User
from app.schemas import (
    ChatRequest,
    ChatResponseDTO,
    ChatStatusResponse,
    ToolCallDTO,
)
from app.services import chat_service
from app.services.chat_service import ChatMessage


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/message",
    response_model=ChatResponseDTO,
    summary="Envía un mensaje al asistente y obtiene la respuesta",
)
def chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_active_user),
) -> ChatResponseDTO:
    history = [ChatMessage(role=m.role, content=m.content) for m in payload.history]
    try:
        result = chat_service.chat(db, message=payload.message, history=history)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del chat: {exc}",
        )

    return ChatResponseDTO(
        reply=result.reply,
        mode=result.mode,
        tool_calls=[ToolCallDTO(**tc.__dict__) for tc in result.tool_calls],
        error=result.error,
    )


@router.get(
    "/status",
    response_model=ChatStatusResponse,
    summary="Muestra qué modo del chat está activo (LLM o fallback)",
)
def chat_status(
    _user: User = Depends(get_current_active_user),
) -> ChatStatusResponse:
    available = chat_service.is_llm_available()
    return ChatStatusResponse(
        llm_available=available,
        model=settings.anthropic_model if available else None,
        fallback_keywords=[
            "alertas", "OEE", "paradas", "máquina", "orden",
            "producción", "sacos", "ayer", "hoy", "última semana",
        ],
    )
