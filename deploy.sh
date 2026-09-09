#!/bin/bash
# DevLocal — GCP Cloud Run 배포 스크립트
set -euo pipefail

PROJECT_ID="local-488014"
SERVICE_NAME="devlocal"
REGION="asia-northeast3"  # 서울 리전

echo "═══════════════════════════════════════════"
echo "  DevLocal → GCP Cloud Run 배포"
echo "═══════════════════════════════════════════"

# ── 1. 사전 체크 ──
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI가 설치되어 있지 않습니다."
    echo "   https://cloud.google.com/sdk/docs/install 에서 설치해주세요."
    exit 1
fi

# ── 2. 공유 저장소·접근 제어 사전 설정 ──
# IAP 사용자 권한은 docs/P1_OPERATIONS.md에 따라 먼저 준비한다.
: "${RUNTIME_SERVICE_ACCOUNT:?Secret 접근 권한이 있는 서비스 계정을 지정하세요}"
: "${ADMIN_EMAILS:?설정 관리자의 이메일을 쉼표로 구분하여 지정하세요}"
export ADMIN_EMAILS

# DB는 선택 사항이다. DATABASE_SECRET과 CLOUD_SQL_INSTANCE를 함께 지정하면
# 공유 PostgreSQL 모드로, 지정하지 않으면 단일 인스턴스 메모리 모드로 배포한다.
# 메모리 모드는 인증(IAP)만 먼저 적용하기 위한 과도기 구성이다 — P1_OPERATIONS.md 참조.
if [ -n "${DATABASE_SECRET:-}" ] && [ -n "${CLOUD_SQL_INSTANCE:-}" ]; then
    STORE_ARGS=(
        --add-cloudsql-instances "$CLOUD_SQL_INSTANCE"
        --set-secrets "DATABASE_URL=${DATABASE_SECRET}"
    )
    MAX_INSTANCES=5
    echo "🗄️  공유 PostgreSQL 모드 (max-instances=${MAX_INSTANCES})"
else
    # 이전 리비전에 남은 DB 연결·Secret을 명시적으로 제거해 구성이 섞이지 않게 한다.
    STORE_ARGS=(--clear-cloudsql-instances --clear-secrets)
    MAX_INSTANCES=1
    export SESSION_STORE=memory
    echo "⚠️  공유 저장소 없이 배포합니다 (max-instances=${MAX_INSTANCES})"
    echo "    인스턴스가 교체되면 진행 중 세션과 UI에서 변경한 설정이 유실됩니다."
fi
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
export IAP_AUDIENCE="/projects/${PROJECT_NUMBER}/locations/${REGION}/services/${SERVICE_NAME}"
ENV_FILE=$(mktemp)
chmod 600 "$ENV_FILE"
trap 'rm -f "$ENV_FILE"' EXIT
# venv의 python을 쓴다 — 이 스크립트는 python-dotenv가 필요한데, 맨몸 python3는
# 이 머신에서 3.13을 가리키며 프로젝트 의존성이 없다 (run_dev.sh와 같은 처리).
VENV="${VENV:-$HOME/.venvs/devlocal}"
if [ -x "$VENV/Scripts/python.exe" ]; then
    PY="$VENV/Scripts/python.exe"          # Windows
elif [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"                  # macOS / Linux
else
    echo "❌ venv를 찾을 수 없습니다 — $VENV" >&2
    echo "   run_dev.sh의 안내에 따라 venv를 먼저 만드세요." >&2
    exit 1
fi
"$PY" scripts/deployment_env.py "$ENV_FILE"

# ── 4. GCP 프로젝트 설정 ──
gcloud config set project "$PROJECT_ID" --quiet

# ── 5. 필요한 API 활성화 ──
echo "🔧 GCP API 활성화 중..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com iap.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com --quiet

# ── 6. Cloud Build로 이미지 빌드 + Cloud Run 배포 ──
echo "🚀 빌드 + 배포 시작... (2-5분 소요)"
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --no-allow-unauthenticated \
    --iap \
    --service-account "$RUNTIME_SERVICE_ACCOUNT" \
    "${STORE_ARGS[@]}" \
    --memory 512Mi \
    --timeout 300 \
    --max-instances "$MAX_INSTANCES" \
    --min-instances 1 \
    --no-cpu-throttling \
    --env-vars-file "$ENV_FILE" \
    --quiet

gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --region "$REGION" \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
    --role=roles/run.invoker --quiet

# ── 7. 배포 URL 출력 ──
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)")

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ 배포 완료!"
echo "  🌐 URL: $SERVICE_URL"
echo "  📋 IAP 접근 권한이 있는 팀원만 사용할 수 있습니다"
echo "═══════════════════════════════════════════"
