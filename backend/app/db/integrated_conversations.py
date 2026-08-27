"""Tenant-scoped persistence for the embedded SaaS experience."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from app.db.data_access import get_zenai_conn


class ConversationNotFound(Exception):
    pass


class ConversationArchived(Exception):
    pass


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


async def ensure_conversation(
    conversation_id: Optional[str],
    org_id: str,
    user_id: str,
    question: str,
    scope: dict[str, Any],
    retention_days: int,
) -> dict:
    conn = await get_zenai_conn()
    try:
        await conn.execute(
            "DELETE FROM integrated_conversations WHERE expires_at <= NOW()"
        )
        if conversation_id:
            row = await conn.fetchrow(
                """SELECT id::text, title, archived, scope, created_at, updated_at
                   FROM integrated_conversations
                   WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3
                     AND expires_at > NOW()""",
                _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
            )
            if not row:
                raise ConversationNotFound()
            if row["archived"]:
                raise ConversationArchived()
            await conn.execute(
                """UPDATE integrated_conversations
                   SET scope = $1::jsonb, updated_at = NOW()
                   WHERE id = $2 AND external_org_id = $3 AND external_user_id = $4""",
                json.dumps(scope), _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
            )
            return dict(row)

        new_id = uuid.uuid4()
        title = " ".join(question.split())[:80] or "New conversation"
        row = await conn.fetchrow(
            """INSERT INTO integrated_conversations
               (id, external_org_id, external_user_id, title, scope, expires_at)
               VALUES ($1, $2, $3, $4, $5::jsonb, NOW() + ($6 * interval '1 day'))
               RETURNING id::text, title, archived, scope, created_at, updated_at""",
            new_id, _uuid(org_id), _uuid(user_id), title, json.dumps(scope),
            max(1, retention_days),
        )
        return dict(row)
    finally:
        await conn.close()


async def save_message(
    conversation_id: str,
    org_id: str,
    user_id: str,
    role: str,
    content: str,
    *,
    message_id: Optional[str] = None,
    insights: Optional[list] = None,
    chart_type: Optional[str] = None,
    chart_data: Optional[list] = None,
    confidence: Optional[str] = None,
    sources: Optional[list] = None,
) -> str:
    conn = await get_zenai_conn()
    try:
        owned = await conn.fetchval(
            """SELECT 1 FROM integrated_conversations
               WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3
                 AND archived = false AND expires_at > NOW()""",
            _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
        )
        if not owned:
            raise ConversationNotFound()
        new_id = _uuid(message_id) if message_id else uuid.uuid4()
        await conn.execute(
            """INSERT INTO integrated_messages
               (id, conversation_id, role, content, insights, chart_type,
                chart_data, confidence, sources)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8, $9::jsonb)""",
            new_id, _uuid(conversation_id), role, content,
            json.dumps(insights or []), chart_type,
            json.dumps(chart_data) if chart_data is not None else None,
            confidence, json.dumps(sources or []),
        )
        await conn.execute(
            """UPDATE integrated_conversations SET updated_at = NOW()
               WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3""",
            _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
        )
        return str(new_id)
    finally:
        await conn.close()


async def list_conversations(
    org_id: str,
    user_id: str,
    limit: int,
    cursor: Optional[str] = None,
    include_archived: bool = False,
) -> dict:
    conn = await get_zenai_conn()
    try:
        params: list[Any] = [_uuid(org_id), _uuid(user_id), include_archived, limit + 1]
        cursor_clause = ""
        if cursor:
            params.append(_uuid(cursor))
            cursor_clause = """AND (c.updated_at, c.id) < (
                SELECT updated_at, id FROM integrated_conversations
                WHERE id = $5 AND external_org_id = $1 AND external_user_id = $2
            )"""
        rows = await conn.fetch(
            f"""SELECT c.id::text, c.title, c.archived, c.scope, c.created_at, c.updated_at,
                      (SELECT content FROM integrated_messages m
                       WHERE m.conversation_id = c.id
                       ORDER BY m.created_at DESC LIMIT 1) AS preview
                 FROM integrated_conversations c
                WHERE c.external_org_id = $1 AND c.external_user_id = $2
                  AND c.expires_at > NOW() AND ($3 OR c.archived = false)
                  {cursor_clause}
                ORDER BY c.updated_at DESC, c.id DESC LIMIT $4""",
            *params,
        )
        items = [dict(row) for row in rows[:limit]]
        return {
            "items": items,
            "next_cursor": items[-1]["id"] if len(rows) > limit else None,
        }
    finally:
        await conn.close()


async def get_conversation(conversation_id: str, org_id: str, user_id: str) -> dict:
    conn = await get_zenai_conn()
    try:
        conversation = await conn.fetchrow(
            """SELECT id::text, title, archived, scope, created_at, updated_at
               FROM integrated_conversations
               WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3
                 AND expires_at > NOW()""",
            _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
        )
        if not conversation:
            raise ConversationNotFound()
        messages = await conn.fetch(
            """SELECT m.id::text, m.role, m.content, m.insights, m.chart_type,
                      m.chart_data, m.confidence, m.sources, m.created_at,
                      f.rating AS feedback
               FROM integrated_messages m
               LEFT JOIN integrated_feedback f ON f.message_id = m.id
               WHERE m.conversation_id = $1
               ORDER BY m.created_at, m.id""",
            _uuid(conversation_id),
        )
        result = dict(conversation)
        result["messages"] = [dict(row) for row in messages]
        return result
    finally:
        await conn.close()


async def update_conversation(
    conversation_id: str,
    org_id: str,
    user_id: str,
    title: Optional[str],
    archived: Optional[bool],
) -> dict:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            """UPDATE integrated_conversations SET
                 title = COALESCE($4, title),
                 archived = COALESCE($5, archived),
                 updated_at = NOW()
               WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3
                 AND expires_at > NOW()
               RETURNING id::text, title, archived, scope, created_at, updated_at""",
            _uuid(conversation_id), _uuid(org_id), _uuid(user_id), title, archived,
        )
        if not row:
            raise ConversationNotFound()
        return dict(row)
    finally:
        await conn.close()


async def delete_conversation(conversation_id: str, org_id: str, user_id: str) -> None:
    conn = await get_zenai_conn()
    try:
        result = await conn.execute(
            """DELETE FROM integrated_conversations
               WHERE id = $1 AND external_org_id = $2 AND external_user_id = $3""",
            _uuid(conversation_id), _uuid(org_id), _uuid(user_id),
        )
        if result != "DELETE 1":
            raise ConversationNotFound()
    finally:
        await conn.close()


async def save_feedback(
    message_id: str,
    org_id: str,
    user_id: str,
    rating: str,
    comment: Optional[str],
) -> dict:
    conn = await get_zenai_conn()
    try:
        owned = await conn.fetchval(
            """SELECT 1 FROM integrated_messages m
               JOIN integrated_conversations c ON c.id = m.conversation_id
               WHERE m.id = $1 AND m.role = 'assistant'
                 AND c.external_org_id = $2 AND c.external_user_id = $3
                 AND c.expires_at > NOW()""",
            _uuid(message_id), _uuid(org_id), _uuid(user_id),
        )
        if not owned:
            raise ConversationNotFound()
        row = await conn.fetchrow(
            """INSERT INTO integrated_feedback
               (id, message_id, external_org_id, external_user_id, rating, comment)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (message_id) DO UPDATE SET
                 rating = EXCLUDED.rating, comment = EXCLUDED.comment, updated_at = NOW()
               RETURNING message_id::text, rating, comment, updated_at""",
            uuid.uuid4(), _uuid(message_id), _uuid(org_id), _uuid(user_id),
            rating, comment,
        )
        return dict(row)
    finally:
        await conn.close()


async def get_exportable_message(message_id: str, org_id: str, user_id: str) -> dict:
    """Return only a persisted assistant snapshot owned by this SaaS principal."""
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            """SELECT m.id::text, m.content, m.insights, m.chart_type, m.chart_data,
                      m.confidence, m.sources, m.created_at
               FROM integrated_messages m
               JOIN integrated_conversations c ON c.id = m.conversation_id
               WHERE m.id = $1 AND m.role = 'assistant'
                 AND c.external_org_id = $2 AND c.external_user_id = $3
                 AND c.expires_at > NOW()""",
            _uuid(message_id), _uuid(org_id), _uuid(user_id),
        )
        if not row:
            raise ConversationNotFound()
        return dict(row)
    finally:
        await conn.close()
