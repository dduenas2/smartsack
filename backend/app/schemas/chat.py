"""
Schemas Pydantic del módulo de chat.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessageDTO(BaseModel):
    """Un turno del historial del cliente."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """Payload del endpoint POST /api/chat/message."""

    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatMessageDTO] = Field(default_factory=list, max_length=20)


class ToolCallDTO(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result_preview: str = ""


class ChatResponseDTO(BaseModel):
    reply: str
    mode: Literal["llm", "fallback"]
    tool_calls: List[ToolCallDTO] = []
    error: Optional[str] = None


class ChatStatusResponse(BaseModel):
    """GET /api/chat/status — qué modo está activo."""

    llm_available: bool
    model: Optional[str] = None
    fallback_keywords: List[str]
