# 아키텍처 상세

## 프로젝트 구조
```
run_dev.sh                # FastAPI(8000) + Vite(5173) 동시 실행 스크립트
.env                      # XAI_API_KEY + GCP_SERVICE_ACCOUNT_JSON_PATH (gitignore)
.gcp_service_account.json # GCP 서비스 계정 JSON (gitignore)
.app_config.json          # 시트 URL/백업폴더/Glossary/프롬프트 영속 저장 (gitignore)

backend/
  config.py               # 환경변수 기반 설정
  main.py                 # FastAPI 앱 (CORS, /api 라우터)
  api/
    routes.py             # 10개 REST+SSE 엔드포인트
    schemas.py            # Pydantic 요청/응답 모델
    session_manager.py    # 서버사이드 세션 (LRU, max 10, 그래프 인스턴스 보유)

frontend/
  src/
    index.css             # Tailwind v4 @theme 디자인 토큰 (색상/타이포/애니메이션)
    App.tsx               # currentStep 기반 화면 라우팅 + 애니메이션 전환
    types/index.ts        # TypeScript 인터페이스 (AppStep, SSE 이벤트, 설정 등)
    store/useAppStore.ts  # Zustand 전역 상태 (연결/세션/HITL/청크/설정/All Sheets)
    api/client.ts         # 9개 API 래퍼 함수
    hooks/
      useSSE.ts           # EventSource SSE 훅 (자동 재연결, 세션 동기화)
      useSheetQueue.ts    # All Sheets 모드 자동 순차 처리
      useNavigationGuard.ts # 작업 중 브라우저 새로고침/닫기 방지
      useCountUp.ts       # 숫자 카운트업 애니메이션
    components/
      Header.tsx, Footer.tsx, StepIndicator.tsx, ConfirmModal.tsx, SettingsModal.tsx
    screens/
      DataSourceScreen.tsx      # Step 1: 시트 연결 + 탭 선택 + 모드 설정
      KoReviewWorkspace.tsx     # Step 1-2 통합: 데이터 로드 + 한국어 검수
      TranslationWorkspace.tsx  # Step 3-4 통합: 번역 진행 + 최종 검수
      DoneScreen.tsx            # Step 5: 완료 요약 + Push to Sheets
    utils/
      diffHighlight.tsx, stagger.ts

agents/
  graph.py                # LangGraph StateGraph (8 Node + HITL 2곳)
  state.py                # LocalizationState TypedDict
  prompts.py              # 시스템 프롬프트 (번역/검수/한국어교정)
  nodes/                  # data_backup, context_glossary, translator, reviewer, writer

config/
  constants.py            # 상수 (CHUNK_SIZE=50, LLM_MODEL, 태그패턴 등)
  glossary.py             # 언어별 Glossary 딕셔너리 + 기본값

utils/
  sheets.py               # gspread 래퍼 (인증, 로드, 백업, Batch Write, Backoff, 셀 포맷팅)
  validation.py           # 정규식 태그 검증 + Glossary 후처리
  diff_report.py          # Diff 리포트 CSV 생성
  cost_tracker.py         # 토큰/비용 추적 (CostTracker 클래스)
  drip_feed.py            # SSE 드립피드 유틸 (150ms 간격 항목별 전송)

app.py                    # (Legacy) Streamlit 메인 앱
```

## 그래프 워크플로우
```
data_backup → context_glossary → ko_review → ko_approval(HITL 1)
  → translator → reviewer → [should_retry → translator 재순환 가능]
  → final_approval(HITL 2) → [approved → writer → END / rejected → END]
```
- `ko_review`: AI 한국어 맞춤법 분석만 수행 (interrupt 없음, 결과 state에 저장)
- `ko_approval`: interrupt()로 사용자 승인 대기 (HITL 1)
- `final_approval`: interrupt()로 최종 승인 대기 (HITL 2)
- **중요**: AI 분석과 interrupt를 반드시 별도 노드로 분리할 것 (invoke 시 결과 유실 방지)

## 아키텍처 패턴 (크로스파일 이해 필요)
- **드립피드 스트리밍**: 노드가 청크 결과를 150ms 간격 1항목씩 SSE 전송 (`drip_feed.py`) → 프론트엔드 partial 배열에 누적 (`useSSE.ts` → Zustand) → 부드러운 테이블 채워짐
- **SSE 세대 카운터**: Cancel/재연결 시 `_sse_generation` 증가 → 이전 세대 emitter는 이벤트 전송 스킵 (`session_manager.py` + `routes.py`)
- **ko_review 캐싱**: Cancel 시 ko_review 결과를 세션에 캐싱 → 재실행 시 `ko_review_node`가 캐시 감지하고 LLM 스킵 (`routes.py` + `nodes/ko_review.py`)
- **row_index 추적**: `/start`에서 `_row_index` 부여 → 중복 Key가 있어도 노드 간 결과 매핑 가능 (`routes.py` → 모든 노드)
- **재시도 루프**: Reviewer 태그 검증 실패 + 재시도 < 3회 → `_needs_retry` → `should_retry()` 조건부 엣지로 translator 재순환 (`reviewer.py` → `graph.py`)
- **시트 미기록 원칙**: 번역 결과는 HITL 2 승인 전까지 메모리에만 존재 → Cancel 시 시트 롤백 불필요 (`routes.py approve-final`)
- **스레드→비동기 브릿지**: 백그라운드 스레드가 `asyncio.run_coroutine_threadsafe()`로 async Queue에 이벤트 전달 (`routes.py _make_emitter`)
