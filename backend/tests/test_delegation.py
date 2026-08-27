import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.core.config import Settings
from app.security.delegation import (
    verify_delegation_token,
    verify_internal_service_key,
)


class DelegationTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cls.public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

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

    def make_claims(self, **overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": "nexdokandar-backend",
            "aud": "nexdokandar-ai",
            "sub": str(self.user_id),
            "org_id": str(self.org_id),
            "role": "admin",
            "allowed_location_ids": [str(self.location_id)],
            "selected_location_id": str(self.location_id),
            "permissions": ["insights", "reports"],
            "features": ["ai_features"],
            "locale": "bn-BD",
            "timezone": "Asia/Dhaka",
            "request_id": "request-123",
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(overrides)
        return claims

    def encode(self, claims=None, algorithm="RS256", key=None):
        return jwt.encode(
            claims or self.make_claims(),
            key or self.private_key,
            algorithm=algorithm,
        )

    def test_valid_token_builds_trusted_context(self):
        context = verify_delegation_token(self.encode(), self.settings)

        self.assertEqual(context.user_id, self.user_id)
        self.assertEqual(context.org_id, self.org_id)
        self.assertEqual(context.selected_location_id, self.location_id)
        self.assertTrue(context.has_permission("insights"))
        self.assertTrue(context.has_any_feature("ai_features"))
        self.assertEqual(context.locale, "bn-BD")

    def test_wrong_audience_is_rejected(self):
        token = self.encode(self.make_claims(aud="another-service"))
        with self.assertRaises(HTTPException) as raised:
            verify_delegation_token(token, self.settings)
        self.assertEqual(raised.exception.status_code, 401)

    def test_hs256_token_is_rejected(self):
        token = jwt.encode(self.make_claims(), "attacker-secret", algorithm="HS256")
        with self.assertRaises(HTTPException) as raised:
            verify_delegation_token(token, self.settings)
        self.assertEqual(raised.exception.status_code, 401)

    def test_token_older_than_maximum_age_is_rejected(self):
        now = datetime.now(timezone.utc)
        token = self.encode(
            self.make_claims(
                iat=now - timedelta(minutes=10),
                exp=now + timedelta(minutes=1),
            )
        )
        with self.assertRaises(HTTPException) as raised:
            verify_delegation_token(token, self.settings)
        self.assertIn("too old", raised.exception.detail)

    def test_selected_location_outside_scope_is_rejected(self):
        token = self.encode(
            self.make_claims(selected_location_id=str(uuid4()))
        )
        with self.assertRaises(HTTPException) as raised:
            verify_delegation_token(token, self.settings)
        self.assertEqual(raised.exception.status_code, 401)

    def test_service_key_uses_fail_closed_behavior(self):
        verify_internal_service_key("service-secret", self.settings)
        for key in (None, "", "wrong"):
            with self.subTest(key=key), self.assertRaises(HTTPException):
                verify_internal_service_key(key, self.settings)


class IntegratedConfigurationTests(unittest.TestCase):
    def test_integrated_mode_requires_trust_settings(self):
        settings = Settings(
            _env_file=None,
            debug=False,
            zenai_mode="integrated",
            saas_delegation_public_key="",
            saas_internal_service_key="",
        )
        with self.assertRaises(RuntimeError) as raised:
            settings.validate_runtime_configuration()
        self.assertIn("SAAS_DELEGATION_PUBLIC_KEY", str(raised.exception))
        self.assertIn("SAAS_INTERNAL_SERVICE_KEY", str(raised.exception))

    def test_standalone_mode_keeps_backward_compatible_defaults(self):
        Settings(
            _env_file=None, debug=False, zenai_mode="standalone"
        ).validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
