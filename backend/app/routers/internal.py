"""Private endpoints used by the NexDokandar backend."""

from datetime import date
from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.core.config import Settings, get_settings
from app.models.request_context import SaaSRequestContext
from app.security.delegation import get_saas_request_context
from app.services.tool_chat_pipeline import process_tool_chat
from app.services.csv_export import build_message_csv
from app.db import integrated_conversations as conversations


router = APIRouter()


class DateRange(BaseModel):
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.from_date > self.to_date:
            raise ValueError("date range start must be before or equal to end")
        if (self.to_date - self.from_date).days > 366:
            raise ValueError("date range cannot exceed 366 days")
        return self


class InternalChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[UUID] = None
    date_range: Optional[DateRange] = None
    capabilities: tuple[str, ...] = ()


class IntegrationContextResponse(BaseModel):
    user_id: UUID
    org_id: UUID
    role: str
    selected_location_id: Optional[UUID]
    locale: str
    timezone: str
    request_id: str
    execution_mode: Literal["curated_tools", "text_to_sql_disabled"]


class ConversationPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    archived: Optional[bool] = None

    @model_validator(mode="after")
    def has_change(self) -> "ConversationPatch":
        if self.title is None and self.archived is None:
            raise ValueError("title or archived is required")
        if self.title is not None:
            object.__setattr__(self, "title", " ".join(self.title.split()))
        return self


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    comment: Optional[str] = Field(default=None, max_length=1000)


def _require_insights(context: SaaSRequestContext) -> None:
    if not context.has_any_feature("ai_features", "insights"):
        raise HTTPException(status_code=403, detail="AI Insights is not enabled")
    if not context.has_permission("insights"):
        raise HTTPException(status_code=403, detail="AI Insights permission is required")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Conversation or message not found")


@router.get("/context", response_model=IntegrationContextResponse)
async def get_integration_context(
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
    settings: Settings = Depends(get_settings),
) -> IntegrationContextResponse:
    """Authenticated handshake endpoint for SaaS integration verification."""
    return IntegrationContextResponse(
        user_id=context.user_id,
        org_id=context.org_id,
        role=context.role,
        selected_location_id=context.selected_location_id,
        locale=context.locale,
        timezone=context.timezone,
        request_id=context.request_id,
        execution_mode=(
            "curated_tools" if settings.enable_curated_tools else "text_to_sql_disabled"
        ),
    )


@router.post("/chat")
async def internal_chat(
    request: InternalChatRequest,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
):
    """Stream an answer produced only from allowlisted, tenant-scoped tools."""
    _require_insights(context)
    if not settings.enable_curated_tools:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Curated AI tools are not enabled",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing delegation token")

    scope = {
        "location_id": (
            str(context.selected_location_id) if context.selected_location_id else None
        ),
        **(request.date_range.model_dump(by_alias=True) if request.date_range else {}),
    }
    try:
        conversation = await conversations.ensure_conversation(
            str(request.conversation_id) if request.conversation_id else None,
            str(context.org_id), str(context.user_id), request.question, scope,
            settings.conversation_retention_days,
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc
    except conversations.ConversationArchived as exc:
        raise HTTPException(status_code=409, detail="Conversation is archived") from exc

    conversation_id = conversation["id"]
    try:
        await conversations.save_message(
            conversation_id, str(context.org_id), str(context.user_id),
            "user", request.question,
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc
    event_stream = process_tool_chat(
        question=request.question,
        conversation_id=conversation_id,
        date_range=(request.date_range.model_dump(by_alias=True) if request.date_range else None),
        context=context,
        delegation_token=authorization.removeprefix("Bearer ").strip(),
        persist_messages=True,
        persist_user_message=False,
    )
    return StreamingResponse(
        event_stream,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Request-Id": context.request_id,
            "X-Conversation-Id": conversation_id,
        },
    )


@router.get("/conversations")
async def list_integrated_conversations(
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
    cursor: Optional[UUID] = None,
    limit: int = Query(default=20, ge=1, le=50),
    include_archived: bool = False,
):
    _require_insights(context)
    return await conversations.list_conversations(
        str(context.org_id), str(context.user_id), limit,
        str(cursor) if cursor else None, include_archived,
    )


@router.get("/conversations/{conversation_id}")
async def get_integrated_conversation(
    conversation_id: UUID,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
):
    _require_insights(context)
    try:
        return await conversations.get_conversation(
            str(conversation_id), str(context.org_id), str(context.user_id)
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc


@router.patch("/conversations/{conversation_id}")
async def patch_integrated_conversation(
    conversation_id: UUID,
    request: ConversationPatch,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
):
    _require_insights(context)
    try:
        return await conversations.update_conversation(
            str(conversation_id), str(context.org_id), str(context.user_id),
            request.title, request.archived,
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc


@router.delete("/conversations/{conversation_id}", status_code=204)
async def remove_integrated_conversation(
    conversation_id: UUID,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
) -> Response:
    _require_insights(context)
    try:
        await conversations.delete_conversation(
            str(conversation_id), str(context.org_id), str(context.user_id)
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc
    return Response(status_code=204)


@router.post("/messages/{message_id}/feedback")
async def create_integrated_feedback(
    message_id: UUID,
    request: FeedbackRequest,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
):
    _require_insights(context)
    try:
        return await conversations.save_feedback(
            str(message_id), str(context.org_id), str(context.user_id),
            request.rating, request.comment,
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc


@router.get("/messages/{message_id}/export")
async def export_integrated_message(
    message_id: UUID,
    context: Annotated[SaaSRequestContext, Depends(get_saas_request_context)],
    format: Literal["csv"] = "csv",
    settings: Settings = Depends(get_settings),
) -> Response:
    _require_insights(context)
    try:
        message = await conversations.get_exportable_message(
            str(message_id), str(context.org_id), str(context.user_id)
        )
    except conversations.ConversationNotFound as exc:
        raise _not_found() from exc
    content = build_message_csv(message, max_rows=settings.ai_result_row_limit)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ai-insight-{message_id}.csv"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
