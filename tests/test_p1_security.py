"""실제 ES256 서명으로 인증 경계와 관리자 권한을 검증한다."""

import json
import os
import time
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.auth import jwt
from google.auth.crypt.es256 import ES256Signer

from backend import auth


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"AUTH_MODE": "iap", "IAP_AUDIENCE": "test-audience", "ADMIN_EMAILS": "admin@example.com"})
        self.env.start()
        self.addCleanup(self.env.stop)
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        self.signer = ES256Signer.from_string(pem, key_id="test-key")
        public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        certs = patch.object(auth, "_certificates", return_value=Mock(status=200, data=json.dumps({"test-key": public}).encode()))
        certs.start()
        self.addCleanup(certs.stop)
        app = FastAPI()
        app.add_middleware(auth.AuthenticationMiddleware)
        for path in ["/api/config", "/api/state/test", "/api/start", "/api/stream/test", "/api/download/test/backup", "/"]:
            app.add_api_route(path, lambda: {"ok": True}, methods=["GET", "PUT", "POST"])
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def token(self, **changes):
        now = int(time.time())
        claims = {"iss": "https://cloud.google.com/iap", "aud": "test-audience", "sub": "user-id",
                  "email": "member@example.com", "iat": now - 1, "exp": now + 599}
        claims.update(changes)
        return jwt.encode(self.signer, claims, header={"alg": "ES256"}).decode()

    def headers(self, **changes):
        return {"X-Goog-IAP-JWT-Assertion": self.token(**changes)}

    def test_missing_signature_and_spoofed_email_are_rejected_everywhere(self):
        for path in ["/", "/api/config", "/api/state/test", "/api/stream/test", "/api/download/test/backup"]:
            self.assertEqual(self.client.get(path, headers={"X-Goog-Authenticated-User-Email": "admin@example.com"}).status_code, 401)

    def test_expired_wrong_audience_and_wrong_issuer_are_rejected(self):
        now = int(time.time())
        for changes in [{"iat": now-700, "exp": now-100}, {"aud": "other"}, {"iss": "other"}, {"iat": now+60}, {"exp": now+900}]:
            self.assertEqual(self.client.get("/api/config", headers=self.headers(**changes)).status_code, 401)

    def test_modified_signature_is_rejected(self):
        token = self.token()
        head, body, signature = token.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        self.assertEqual(self.client.get("/api/config", headers={"X-Goog-IAP-JWT-Assertion": f"{head}.{body}.{signature}"}).status_code, 401)

    def test_member_can_translate_but_only_admin_can_change_config(self):
        self.assertEqual(self.client.get("/api/config", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post("/api/start", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.put("/api/config", headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.put("/api/config", headers=self.headers(email="admin@example.com")).status_code, 200)

    def test_cross_origin_mutation_is_rejected(self):
        headers = {**self.headers(), "Origin": "https://attacker.example"}
        self.assertEqual(self.client.post("/api/start", headers=headers).status_code, 403)

    def test_production_cannot_start_with_local_auth_or_missing_audience(self):
        with patch.dict(os.environ, {"K_SERVICE": "test", "AUTH_MODE": "local"}):
            with self.assertRaises(RuntimeError):
                auth.validate_auth_environment()
            self.assertEqual(self.client.get("/api/config").status_code, 401)
        with patch.dict(os.environ, {"IAP_AUDIENCE": ""}):
            with self.assertRaises(RuntimeError):
                auth.validate_auth_environment()
