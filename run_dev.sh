#!/bin/bash
# DevLocal 개발서버 동시 실행 스크립트
# Backend: FastAPI (port 8000) + Frontend: Vite (port 5173)

trap 'kill 0' EXIT

cd "$(dirname "$0")"

# Python 3.11 venv.
# 프로젝트가 OneDrive 동기화 폴더 안에 있어 venv(약 700MB/3만 파일)를 밖에 둔다.
# 다른 경로를 쓰려면 VENV 환경변수로 지정.
VENV="${VENV:-$HOME/.venvs/devlocal}"
if [ -x "$VENV/Scripts/python.exe" ]; then
    PY="$VENV/Scripts/python.exe"          # Windows
elif [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"                  # macOS / Linux
else
    echo "오류: venv를 찾을 수 없습니다 — $VENV" >&2
    echo "생성 방법:" >&2
    echo "  python3.11 -m venv \"$VENV\"" >&2
    echo "  \"$VENV\"/Scripts/python.exe -m pip install -r backend/requirements.txt -r requirements.txt" >&2
    exit 1
fi

echo "Starting FastAPI backend on :8000... ($("$PY" -V))"
"$PY" -m uvicorn backend.main:app --reload --port 8000 &

echo "Starting Vite frontend on :5173..."
cd frontend && npm run dev &

wait
