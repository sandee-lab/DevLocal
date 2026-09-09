# ── Stage 1: React 프론트엔드 빌드 ──
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python 백엔드 + 정적 파일 서빙 ──
FROM python:3.11-slim
WORKDIR /app

# Python 의존성
# constraints.txt로 버전을 고정한다 — requirements.txt는 >= 만 선언하므로
# 이것이 없으면 배포할 때마다 전 의존성이 최신으로 밀린다 (파일 헤더 참조).
COPY backend/requirements.txt backend/constraints.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -c backend/constraints.txt

# 소스 코드 복사
COPY backend/ backend/
COPY agents/ agents/
COPY config/ config/
COPY utils/ utils/
COPY docs/ docs/

# React 빌드 결과물 복사
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Cloud Run은 PORT 환경변수를 주입함
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
