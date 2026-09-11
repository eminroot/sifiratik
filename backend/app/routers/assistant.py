from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import i18n
from app.database.database import get_db
from app.security import Principal, require_writer
from app.routers.deps import resolve_period
from app.schemas.assistant import AssistantStatus, ChatReply, ChatRequest
from app.services import assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatus)
def assistant_status(
    period: str = Depends(resolve_period), db: Session = Depends(get_db)
) -> AssistantStatus:
    """Whether the assistant is configured, so the interface can say why not."""
    enabled, model, detail = assistant_service.status()
    return AssistantStatus(enabled=enabled, model=model, detail=detail)


@router.get("/suggestions", response_model=list[str])
def assistant_suggestions(
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
) -> list[str]:
    return assistant_service.suggested_questions(db, period, lang)


@router.post("/chat", response_model=ChatReply)
async def assistant_chat(
    payload: ChatRequest,
    period: str = Depends(resolve_period),
    lang: str = Depends(i18n.resolve_lang),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_writer),
) -> ChatReply:
    """One turn against Gemini, grounded in the current period's figures."""
    reply = await assistant_service.ask(
        db,
        message=payload.message,
        history=payload.history,
        period=period,
        company_id=payload.company_id,
        lang=lang,
    )
    _enabled, model, _detail = assistant_service.status()
    return ChatReply(reply=reply, model=model, period=period)
