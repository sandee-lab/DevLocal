"""FastAPI 메인 앱"""

import logging
import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("devlocal")

# 프로젝트 루트를 sys.path에 추가 (agents, config, utils 임포트용)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_environment()
    from backend.auth import validate_auth_environment
    from backend import persistence
    from config.app_config import use_shared_store
    validate_auth_environment()
    database_url = os.environ.get("DATABASE_URL")
    if os.environ.get("K_SERVICE") and not database_url:
        # 공유 저장소 없이 운영하려면 명시적으로 선언해야 한다. 조용한 폴백은 금지 —
        # DATABASE_URL 설정을 빠뜨린 사고와, 인증만 먼저 적용하는 의도적인 단일
        # 인스턴스 운영을 구분하기 위해서다.
        if os.environ.get("SESSION_STORE") != "memory":
            raise RuntimeError(
                "Cloud Run에서는 공유 PostgreSQL DATABASE_URL이 필요합니다. "
                "공유 저장소 없이 단일 인스턴스로 운영하려면 SESSION_STORE=memory를 설정하세요"
            )
        logger.warning(
            "공유 저장소 없이 기동 — max-instances=1 전제. 인스턴스가 교체되면 "
            "진행 중인 세션과 UI에서 변경한 설정이 유실됩니다"
        )
    store = None
    try:
        if database_url:
            from backend.storage import PostgresStorage
            store = PostgresStorage(database_url)
            await asyncio.to_thread(store.setup)
            use_shared_store(store)
            persistence.runtime = persistence.Runtime(store)
            persistence.runtime.thread.start()
        yield
    finally:
        if persistence.runtime is not None:
            await asyncio.to_thread(persistence.runtime.close)
            persistence.runtime = None
        elif store is not None:
            store.close()
        use_shared_store(None)


app = FastAPI(title="DevLocal API", version="2.0.0", lifespan=lifespan)

# CORS — 개발 환경용 (프로덕션 단일 컨테이너에서는 same-origin이라 불필요)
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from backend.auth import AuthenticationMiddleware
app.add_middleware(AuthenticationMiddleware)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

app.include_router(router, prefix="/api")

# ── 정적 파일 서빙 (프로덕션: React 빌드 결과물) ──
_STATIC_DIR = _PROJECT_ROOT / "frontend" / "dist"

async def serve_spa(full_path: str):
    """빌드 디렉터리 내부 파일만 제공하고, 앱 경로에는 index.html을 반환한다."""
    file_path = (_STATIC_DIR / full_path).resolve()
    if (
        full_path == "api" or full_path.startswith("api/")
        or not file_path.is_relative_to(_STATIC_DIR.resolve())
    ):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path if file_path.is_file() else _STATIC_DIR / "index.html")


if _STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")
    app.get("/{full_path:path}")(serve_spa)


def validate_environment():
    from backend.config import get_xai_api_key, get_gcp_credentials

    issues = []
    if not get_xai_api_key():
        issues.append("XAI_API_KEY is not set in .env")
    creds = get_gcp_credentials()
    if not creds or not creds.get("client_email"):
        issues.append("GCP service account credentials not found or invalid")

    if issues:
        for issue in issues:
            logger.error("ENV VALIDATION FAILED: %s", issue)
        logger.warning("Server started with missing credentials. Some features will fail.")
    else:
        logger.info("Environment validation passed")
