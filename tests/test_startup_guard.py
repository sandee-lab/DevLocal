"""공유 저장소 없이 Cloud Run에 기동할 때의 안전장치를 검증한다.

DATABASE_URL 설정을 빠뜨린 사고와, 인증만 먼저 적용하는 의도적인 단일 인스턴스
운영은 구분되어야 한다. 전자는 기동 실패, 후자는 SESSION_STORE=memory 선언이 있을
때만 허용한다.
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


def _cloud_run_env(**overrides):
    """Cloud Run 기동 환경 — DATABASE_URL은 항상 제거한 상태로 시작한다."""
    env = {
        "K_SERVICE": "devlocal",
        "AUTH_MODE": "iap",
        "IAP_AUDIENCE": "/projects/1/locations/asia-northeast3/services/devlocal",
        "ADMIN_EMAILS": "admin@example.com",
    }
    env.update(overrides)
    return env


class StartupGuardTests(unittest.TestCase):
    def setUp(self):
        # 실제 개발 환경의 DATABASE_URL이 테스트에 새어들지 않게 한다.
        cleaner = patch.dict(os.environ, {}, clear=False)
        cleaner.start()
        self.addCleanup(cleaner.stop)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SESSION_STORE", None)

    def test_cloud_run_without_database_url_fails(self):
        """선언 없이 DB가 빠지면 조용히 폴백하지 않고 기동에 실패해야 한다."""
        with patch.dict(os.environ, _cloud_run_env()):
            with self.assertRaises(RuntimeError) as caught:
                with TestClient(app):
                    pass
        self.assertIn("SESSION_STORE=memory", str(caught.exception))

    def test_cloud_run_with_declared_memory_store_starts(self):
        """SESSION_STORE=memory를 명시하면 공유 저장소 없이 기동한다."""
        with patch.dict(os.environ, _cloud_run_env(SESSION_STORE="memory")):
            with TestClient(app) as client:
                self.assertEqual(client.get("/healthz").status_code, 200)

    def test_other_session_store_values_are_rejected(self):
        """오타나 임의 값으로 안전장치가 우회되지 않아야 한다."""
        with patch.dict(os.environ, _cloud_run_env(SESSION_STORE="none")):
            with self.assertRaises(RuntimeError):
                with TestClient(app):
                    pass

    def test_local_run_without_database_url_starts(self):
        """로컬(K_SERVICE 없음)은 기존대로 선언 없이 메모리 모드로 동작한다."""
        with patch.dict(os.environ, {"AUTH_MODE": "local"}):
            os.environ.pop("K_SERVICE", None)
            with TestClient(app) as client:
                self.assertEqual(client.get("/healthz").status_code, 200)


if __name__ == "__main__":
    unittest.main()
