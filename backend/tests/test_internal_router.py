import unittest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.routers.internal import router


class InternalRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_key = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        cls.public_key = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def setUp(self):
        self.user_id = uuid4()
        self.org_id = uuid4()
        self.location_id = uuid4()
        self.settings = Settings(
            _env_file=None,
            zenai_debug=False,
            zenai_mode="integrated",
            saas_delegation_public_key=self.public_key,
            saas_internal_service_key="service-secret",
        )
        app = FastAPI()
        app.include_router(router, prefix="/internal/v1")
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = TestClient(app)

    def token(self, permissions=None, features=None):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": "nexdokandar-backend",
            "aud": "nexdokandar-ai",
            "sub": str(self.user_id),
            "org_id": str(self.org_id),
            "role": "admin",
            "allowed_location_ids": [str(self.location_id)],
            "selected_location_id": str(self.location_id),
            "permissions": permissions if permissions is not None else ["insights"],
            "features": features if features is not None else ["ai_features"],
            "locale": "en-BD",
            "timezone": "Asia/Dhaka",
            "request_id": "router-test",
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def headers(self, **token_options):
        return {
            "Authorization": f"Bearer {self.token(**token_options)}",
            "X-ZenAI-Service-Key": "service-secret",
        }

    def test_context_requires_both_service_key_and_delegation(self):
        response = self.client.get(
            "/internal/v1/context",
            headers={"Authorization": f"Bearer {self.token()}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_context_returns_only_trusted_scope(self):
        response = self.client.get(
            "/internal/v1/context", headers=self.headers()
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_id"], str(self.user_id))
        self.assertEqual(body["org_id"], str(self.org_id))
        self.assertEqual(body["selected_location_id"], str(self.location_id))
        self.assertNotIn("permissions", body)
        self.assertNotIn("features", body)

    def test_chat_fails_closed_without_entitlement(self):
        response = self.client.post(
            "/internal/v1/chat",
            headers=self.headers(features=[]),
            json={"question": "Summarize sales"},
        )
        self.assertEqual(response.status_code, 403)

    def test_chat_validates_date_range(self):
        response = self.client.post(
            "/internal/v1/chat",
            headers=self.headers(),
            json={
                "question": "Summarize sales",
                "date_range": {"from": "2026-08-20", "to": "2026-08-01"},
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_conversation_read_passes_both_owner_scopes(self):
        conversation_id = uuid4()
        payload = {
            "id": str(conversation_id), "title": "Sales", "archived": False,
            "scope": {}, "messages": [],
        }
        with patch(
            "app.routers.internal.conversations.get_conversation",
            new=AsyncMock(return_value=payload),
        ) as reader:
            response = self.client.get(
                f"/internal/v1/conversations/{conversation_id}",
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 200)
        reader.assert_awaited_once_with(
            str(conversation_id), str(self.org_id), str(self.user_id)
        )

    def test_foreign_or_missing_conversation_has_same_not_found_response(self):
        conversation_id = uuid4()
        with patch(
            "app.routers.internal.conversations.get_conversation",
            new=AsyncMock(side_effect=__import__(
                "app.db.integrated_conversations", fromlist=["ConversationNotFound"]
            ).ConversationNotFound()),
        ):
            response = self.client.get(
                f"/internal/v1/conversations/{conversation_id}",
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Conversation or message not found")

    def test_feedback_requires_message_ownership(self):
        message_id = uuid4()
        from app.db.integrated_conversations import ConversationNotFound
        with patch(
            "app.routers.internal.conversations.save_feedback",
            new=AsyncMock(side_effect=ConversationNotFound()),
        ):
            response = self.client.post(
                f"/internal/v1/messages/{message_id}/feedback",
                headers=self.headers(),
                json={"rating": "up"},
            )
        self.assertEqual(response.status_code, 404)

    def test_export_uses_owned_persisted_message_snapshot(self):
        message_id = uuid4()
        snapshot = {
            "id": str(message_id),
            "content": "Sales result",
            "chart_data": [{"date": "2026-08-19", "revenue": 500}],
            "confidence": "high",
            "sources": [{"tool": "sales_summary"}],
            "created_at": "2026-08-19T00:00:00Z",
        }
        with patch(
            "app.routers.internal.conversations.get_exportable_message",
            new=AsyncMock(return_value=snapshot),
        ) as reader:
            response = self.client.get(
                f"/internal/v1/messages/{message_id}/export?format=csv",
                headers=self.headers(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("revenue", response.text)
        reader.assert_awaited_once_with(
            str(message_id), str(self.org_id), str(self.user_id)
        )


if __name__ == "__main__":
    unittest.main()
