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

# ── 2. .env에서 XAI_API_KEY 읽기 ──
if [ -f .env ]; then
    XAI_API_KEY=$(grep -E "^XAI_API_KEY=" .env | cut -d'=' -f2-)
else
    echo "❌ .env 파일이 없습니다."
    exit 1
fi

if [ -z "$XAI_API_KEY" ]; then
    echo "❌ .env에 XAI_API_KEY가 설정되지 않았습니다."
    exit 1
fi

# ── 3. GCP 서비스 계정 JSON 읽기 ──
GCP_JSON_PATH=$(grep -E "^GCP_SERVICE_ACCOUNT_JSON_PATH=" .env | cut -d'=' -f2- || true)
GCP_JSON_PATH="${GCP_JSON_PATH:-.gcp_service_account.json}"

if [ ! -f "$GCP_JSON_PATH" ]; then
    echo "❌ GCP 서비스 계정 파일이 없습니다: $GCP_JSON_PATH"
    exit 1
fi

# JSON을 한 줄로 변환하여 임시 env 파일 생성
GCP_JSON=$(python3 -c "import sys,json; print(json.dumps(json.load(open('$GCP_JSON_PATH'))))")

ENV_FILE=$(mktemp)
trap 'rm -f "$ENV_FILE"' EXIT

python3 -c "
import json, sys
env = {
    'XAI_API_KEY': '''${XAI_API_KEY}''',
    'GCP_SERVICE_ACCOUNT_JSON': json.dumps(json.load(open('$GCP_JSON_PATH')))
}
# YAML 형식으로 출력
for k, v in env.items():
    print(f'{k}: {json.dumps(v)}')
" > "$ENV_FILE"

echo "✅ Secrets 로드 완료"

# ── 4. GCP 프로젝트 설정 ──
gcloud config set project "$PROJECT_ID" --quiet

# ── 5. 필요한 API 활성화 ──
echo "🔧 GCP API 활성화 중..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com --quiet

# ── 6. Cloud Build로 이미지 빌드 + Cloud Run 배포 ──
echo "🚀 빌드 + 배포 시작... (2-5분 소요)"
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --max-instances 5 \
    --env-vars-file "$ENV_FILE" \
    --quiet

# ── 7. 배포 URL 출력 ──
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)")

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ 배포 완료!"
echo "  🌐 URL: $SERVICE_URL"
echo "  📋 이 URL을 팀원에게 공유하세요"
echo "═══════════════════════════════════════════"
