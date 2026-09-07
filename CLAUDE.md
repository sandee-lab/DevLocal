# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
구글 스프레드시트 기반 게임 텍스트(한국어)를 AI(Grok 4.6)로 다국어(EN, JA, ZH-CN, ZH-TW) 자동 번역/검수하는 웹앱.

## 기술 스택
- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS v4 + Zustand (SPA)
- **Backend**: FastAPI + SSE (sse-starlette) + uvicorn
- **Agent Orchestration**: LangGraph 0.6 (8 Node + HITL 2곳 interrupt)
- **Google Sheets**: gspread (Batch Read/Write + Exponential Backoff)
- **LLM**: LiteLLM → xai/grok-4.6 (reasoning_effort=low, timeout=120s)
- **Data**: Pandas
- **Legacy**: Streamlit (app.py — 기존 버전, 별도 실행 가능)

## 개발 명령어
```bash
./run_dev.sh                                    # FastAPI(8000) + Vite(5173) 동시 실행
python3 -m uvicorn backend.main:app --reload --port 8000  # 백엔드만
cd frontend && npm run dev                      # 프론트엔드만
cd frontend && npm run build                    # TypeScript 체크 + 프로덕션 빌드
cd frontend && npm run lint                     # ESLint
pip install -r backend/requirements.txt         # 백엔드 의존성
./deploy.sh                                     # GCP Cloud Run 배포 (asia-northeast3)
```
- Vite `/api` → `localhost:8000` 프록시 (`vite.config.ts`)
- 테스트 프레임워크 미설정 (pytest, vitest 없음)
- Dockerfile: 멀티스테이지 (Node 22 → Python 3.11-slim), Cloud Run 단일 컨테이너

## 핵심 규칙
- 타겟 언어는 `SUPPORTED_LANGUAGES`(config/constants.py)가 단일 출처 — 시트에 해당 컬럼(`English(en)`/`Japanese(ja)`/`Chinese_CN(zh-CN)`/`Chinese_TW(zh-TW)`)이 존재하는 언어만 자동 번역 (타겟 컬럼은 필수 아님, 프론트는 빈 target_languages 전송)
- 포맷팅 태그({변수}, <color>, \n 등) 보존은 정규식 하드코딩으로 검증 (LLM 의존 X)
- JA 등급명은 Glossary 강제 치환 (의역 절대 금지)
- Google Sheets: 개별 cell.update() 금지 → 반드시 Batch Update
- Google Sheets: 1회 전체 로드 후 DataFrame 내에서 작업
- HITL 2단계: 한국어 검수 승인 → 최종 번역 승인 (interrupt 2곳)
- LLM 호출은 반드시 청크 배치(CHUNK_SIZE=50) + timeout=120s 적용
- Reviewer도 청크 배치 호출 (개별 호출 절대 금지 — rate limit 및 멈춤 원인)
- 번역 에러 시 그래프 재생성 후 idle로 복구 (translating 멈춤 상태 방지)
- Writer: 원본 값과 비교하여 실제 변경된 셀만 시트 업데이트 & 컬러링
- Writer: 같은 Key가 일부 언어 성공 + 일부 실패 시, Tool_Status는 "검수실패"로 단일 설정
- 한국어 검수 제안 0건 시 자동 승인 (빈 카드 표시 안 함)
- 시트 URL/백업폴더는 `.app_config.json`에 영속 저장 (gitignore 포함)
- Translator: LLM JSON 파싱 후 `\n`→`\\n`, `\t`→`\\t` 리터럴 복원 필수

## 구현 워크플로우 규칙
- 각 구현 단계(Phase)마다 바로 코드를 작성하지 않는다
- 먼저 해당 단계의 점검 체크리스트를 작성하고, 점검을 통과한 뒤 구현에 들어간다

## LLM 설정
- **모델**: `xai/grok-4.6` — **CHUNK_SIZE**: 50행 — **timeout**: 120초
- **`reasoning_effort`는 반드시 `low`** (`LLM_REASONING_EFFORT`) — 4.6 기본값 high로 두면 장문 청크에서 reasoning 토큰이 4000~7000개로 폭증해 **timeout 실패 + 비용 3배**. low에서 reasoning 20~80개로 정상화
- **`reasoning_effort`는 `allowed_openai_params`와 함께 보내야 한다** — litellm 1.85 번들 모델맵에 grok-4.6이 없어, 모델맵 원격 조회 실패 시 번들로 폴백해 파라미터를 "미지원" 판정하고 호출을 거부한다(`UnsupportedParamsError` → **번역 전건 실패**). 네트워크 상태에 따라 되다 말다 하므로 재현이 어렵다. `drop_params=True`는 금지 — 파라미터가 조용히 버려져 high로 되돌아간다
- **가격** (2026-09 xAI 공식 docs.x.ai 확인): input **$2.00/1M**, output **$6.00/1M**, cached_input **$0.50/1M**
- 모델 비교는 `scripts/compare_models.py` (실제 시트·실제 프롬프트로 결함률/비용/속도 측정, `모델@effort` 문법 지원)
- **주의**: xAI/Grok은 `completion_tokens`와 `reasoning_tokens`를 별도 리포트 → **합산 필요** (OpenAI 표준과 다름)
- 번역 결과의 한글 잔존은 `check_hangul_residue()`(utils/validation.py)로 정규식 검증 → 태그 검증과 동일한 재번역 루프 합류 (번역문 == 원문이면 의도적 통과로 예외)

## Secrets / 설정
- `.env` — `XAI_API_KEY`, `GCP_SERVICE_ACCOUNT_JSON_PATH` → `backend/config.py`로 접근
- `.gcp_service_account.json` — GCP 서비스 계정 JSON (gitignore)
- 봇 이메일 (시트 편집자 초대 필요): `local-agent@local-488014.iam.gserviceaccount.com`
- 금지 시트 (UI 드롭다운 노출 금지): 사용법, Texture, 수정금지_Common

## 참고 문서
- PRD_v2.md: 상세 요구사항
- DEVELOPMENT_PLAN.md: 구현 계획서
- docs/USER_GUIDE.md: 사용자 가이드 (비개발자용)
- memory/ui-design-rules.md: Stitch 기반 UI 디자인 토큰/컴포넌트 규칙

## 상세 문서 (자동 로드되지 않음 — 해당 작업 시 직접 읽을 것)
| 파일 | 내용 | 언제 읽는가 |
|------|------|-------------|
| `.claude/docs/architecture.md` | 프로젝트 구조, 그래프 워크플로우, 아키텍처 패턴 7개 | 파일 위치 파악, 그래프/노드/크로스파일 패턴 이해 시 |
| `.claude/docs/frontend.md` | UI 아키텍처, 디자인 시스템, SSE/HITL UX 흐름 | 프론트엔드 수정 시 |
| `.claude/docs/api-reference.md` | API 엔드포인트 10개, SSE 이벤트 타입 목록 | API 추가/수정 시 |
