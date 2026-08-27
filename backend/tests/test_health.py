import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            _env_file=None,
            zenai_mode="standalone",
            saas_internal_service_key="health-secret",
            require_redis_for_readiness=False,
        )
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_liveness_is_public_but_metrics_are_protected(self):
        self.assertEqual(self.client.get("/health/live").status_code, 200)
        self.assertEqual(self.client.get("/metrics").status_code, 401)
        response = self.client.get(
            "/metrics", headers={"X-ZenAI-Service-Key": "health-secret"}
        )
        self.assertEqual(response.status_code, 200)

    @patch("app.main.get_zenai_conn", new_callable=AsyncMock)
    def test_readiness_checks_postgres_without_requiring_redis(self, get_conn):
        conn = AsyncMock()
        conn.fetchval.return_value = 1
        get_conn.return_value = conn
        response = self.client.get(
            "/health/ready", headers={"X-ZenAI-Service-Key": "health-secret"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dependencies"]["postgres"], "ok")
        self.assertEqual(response.json()["dependencies"]["redis"], "not_required")
        conn.close.assert_awaited_once()

    @patch("app.main.get_zenai_conn", new_callable=AsyncMock)
    def test_readiness_returns_503_without_leaking_database_errors(self, get_conn):
        get_conn.side_effect = RuntimeError("postgresql://secret@database")
        response = self.client.get(
            "/health/ready", headers={"X-ZenAI-Service-Key": "health-secret"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertNotIn("secret", response.text)


if __name__ == "__main__":
    unittest.main()
