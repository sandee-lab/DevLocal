"""IAP 서명 검증과 팀 관리자 권한. 로컬 개발 모드는 명시적으로 분리한다."""

import asyncio
import os
import threading
import time
from urllib.parse import urlsplit

from google.auth.transport.requests import Request
from google.auth import jwt
from google.oauth2 import id_token
from starlette.responses import JSONResponse


class CachedCertificates:
    def __init__(self):
        self.lock = threading.Lock()
        self.response = None
        self.expires = 0

    def __call__(self, url, method="GET", **kwargs):
        with self.lock:
            if self.response is None or time.monotonic() >= self.expires:
                response = Request()(url, method=method, timeout=10, **kwargs)
                if response.status != 200:
                    raise ValueError("IAP 인증서를 가져오지 못했습니다")
                self.response = response
                self.expires = time.monotonic() + 300
            return self.response


_certificates = CachedCertificates()


def mode():
    return os.environ.get("AUTH_MODE", "iap" if os.environ.get("K_SERVICE") else "local")


def validate_auth_environment():
    current = mode()
    if current not in {"local", "iap"}:
        raise RuntimeError("AUTH_MODE는 local 또는 iap이어야 합니다")
    if os.environ.get("K_SERVICE") and current != "iap":
        raise RuntimeError("Cloud Run에서는 IAP 인증이 필요합니다")
    if current == "iap" and (not os.environ.get("IAP_AUDIENCE") or not admins()):
        raise RuntimeError("IAP_AUDIENCE와 ADMIN_EMAILS 설정이 필요합니다")


def admins():
    return {value.strip().lower() for value in os.environ.get("ADMIN_EMAILS", "").split(",") if value.strip()}


def verify_assertion(token):
    if jwt.decode_header(token).get("alg") != "ES256":
        raise ValueError("IAP 서명 알고리즘이 올바르지 않습니다")
    claims = id_token.verify_token(
        token, _certificates, audience=os.environ["IAP_AUDIENCE"],
        certs_url="https://www.gstatic.com/iap/verify/public_key",
    )
    if claims.get("iss") != "https://cloud.google.com/iap" or not claims.get("sub") or not claims.get("email"):
        raise ValueError("IAP 발급자 또는 사용자 정보가 올바르지 않습니다")
    if claims["exp"] - claims["iat"] > 660:
        raise ValueError("IAP 토큰 유효 기간이 올바르지 않습니다")
    return claims


class AuthenticationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/healthz":
            return await self.app(scope, receive, send)
        if mode() == "local" and not os.environ.get("K_SERVICE"):
            return await self.app(scope, receive, send)
        headers = {key.decode().lower(): value.decode() for key, value in scope["headers"]}
        token = headers.get("x-goog-iap-jwt-assertion")
        try:
            if mode() != "iap" or not token:
                raise ValueError("IAP 로그인이 필요합니다")
            claims = await asyncio.to_thread(verify_assertion, token)
        except Exception:
            return await JSONResponse({"detail": "인증이 필요합니다. 새로고침 후 다시 로그인하세요"}, status_code=401)(scope, receive, send)
        scope.setdefault("state", {})["user_email"] = claims["email"]
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get("origin")
            if origin and (urlsplit(origin).netloc != headers.get("host") or urlsplit(origin).scheme != "https"):
                return await JSONResponse({"detail": "허용되지 않은 요청 출처입니다"}, status_code=403)(scope, receive, send)
        if scope["path"].rstrip("/") == "/api/config" and scope["method"] == "PUT" and claims["email"].lower() not in admins():
            return await JSONResponse({"detail": "설정 변경은 관리자만 가능합니다"}, status_code=403)(scope, receive, send)
        await self.app(scope, receive, send)
