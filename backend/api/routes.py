"""API 라우트 — REST + SSE endpoints"""

import asyncio
import io
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger("devlocal.api")

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import (
    ApprovalRequest,
    ConnectRequest,
    ConnectResponse,
    SessionStateResponse,
    StartRequest,
    StartResponse,
)
from backend.api.session_manager import session_manager
from config.constants import (
    LLM_PRICING,
    REQUIRED_COLUMNS,
    SUPPORTED_LANGUAGES,
    Status,
    TOOL_STATUS_COLUMN,
)
from utils.diff_report import generate_ko_diff_report, generate_translation_diff_report
from utils.sheets import (
    batch_format_cells,
    batch_update_sheet,
    connect_to_sheet,
    create_backup_csv,
    ensure_tool_status_column,
    extract_project_name,
    get_bot_email,
    get_worksheet_names,
    load_sheet_data,
    save_backup_to_folder,
)

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=4)

# ── 로컬 설정 파일 ──────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".app_config.json"


def _build_cost_summary(input_t: int, output_t: int, reasoning_t: int, cached_t: int) -> dict:
    """토큰 사용량으로 cost summary 생성 — SSE/REST 양쪽 단일 진실 출처."""
    non_cached_input = max(input_t - cached_t, 0)
    cost = (
        non_cached_input * LLM_PRICING["input"]
        + cached_t * LLM_PRICING["cached_input"]
        + (output_t + reasoning_t) * LLM_PRICING["output"]
    )
    return {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "reasoning_tokens": reasoning_t,
        "cached_tokens": cached_t,
        "estimated_cost_usd": round(cost, 4),
    }


def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(data: dict):
    try:
        existing = _load_config()
        existing.update(data)
        _CONFIG_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("Config save failed: %s", e)


# ── Sheet Connection ─────────────────────────────────────────────────

@router.post("/connect", response_model=ConnectResponse)
def api_connect(req: ConnectRequest):
    """시트 연결 + 시트 목록 반환"""
    try:
        spreadsheet = connect_to_sheet(req.sheet_url)
        sheet_names = get_worksheet_names(spreadsheet)
        bot_email = get_bot_email()
        project_name = extract_project_name(spreadsheet)
        _save_config({"saved_url": req.sheet_url})
        logger.info("Sheet connected: %d tabs found, project=%s", len(sheet_names), project_name or "(none)")
        return ConnectResponse(sheet_names=sheet_names, bot_email=bot_email, project_name=project_name)
    except Exception as e:
        logger.error("Sheet connection failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── Start Pipeline ───────────────────────────────────────────────────

@router.post("/start", response_model=StartResponse)
def api_start(req: StartRequest):
    """번역 파이프라인 시작 — 세션 생성 + 데이터 준비"""
    session = session_manager.create()
    try:
        session.spreadsheet = connect_to_sheet(req.sheet_url)
        ws = session.spreadsheet.worksheet(req.sheet_name)
        df = load_sheet_data(ws)

        # 필수 컬럼 검증 — 누락 시 그래프 실행 전 즉시 실패
        missing = [col for col in REQUIRED_COLUMNS.values() if col not in df.columns]
        if missing:
            raise ValueError(
                f"시트 '{req.sheet_name}'에 필수 컬럼이 없습니다: {', '.join(missing)}"
            )

        df = ensure_tool_status_column(ws, df)

        if req.row_start > 0 and req.row_end > 0:
            df = df.iloc[req.row_start - 1 : req.row_end]
        elif req.row_end > 0:
            df = df.head(req.row_end)

        session.worksheet = ws
        session.df = df

        # in-memory 백업 (다운로드 엔드포인트용 — 시트에는 Write하지 않음)
        filename, csv_bytes = create_backup_csv(df, req.sheet_name)
        session.backup_filename = filename
        session.backup_csv = csv_bytes

        # 게임 설정 로드 (커스텀 프롬프트, 시놉시스, 톤앤매너)
        from config.glossary import get_game_synopsis, get_tone_and_manner

        app_cfg = _load_config()
        custom_prompts = app_cfg.get("custom_prompts", {})
        custom_prompt = custom_prompts.get(req.sheet_name, "")
        game_synopsis = app_cfg.get("game_synopsis") or get_game_synopsis()
        tone_and_manner = app_cfg.get("tone_and_manner") or get_tone_and_manner()

        # 초기 state 저장
        # 각 행에 _row_index 부여 (중복 Key 구분용)
        records = df.to_dict("records")
        for idx, rec in enumerate(records):
            rec["_row_index"] = idx

        session.initial_state = {
            "sheet_name": req.sheet_name,
            "mode": req.mode,
            "target_languages": req.target_languages,
            "original_data": records,
            "backup_data": df.to_dict("records"),
            "ko_review_results": [],
            "translation_results": [],
            "review_results": [],
            "failed_rows": [],
            "diff_report_ko": None,
            "diff_report_translation": None,
            "wait_for_ko_approval": False,
            "ko_approval_result": None,
            "wait_for_final_approval": False,
            "final_approval_result": None,
            "current_chunk_index": 0,
            "total_chunks": 0,
            "retry_count": {},
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_reasoning_tokens": 0,
            "total_cached_tokens": 0,
            "logs": [],
            "_updates": [],
            "_needs_retry": [],
            "custom_prompt": custom_prompt,
            "game_synopsis": game_synopsis,
            "tone_and_manner": tone_and_manner,
        }
        session.current_step = "loading"
        logger.info("Pipeline started: session=%s, sheet=%s, mode=%s",
                     session.id, req.sheet_name, req.mode)
        return StartResponse(session_id=session.id)
    except Exception as e:
        session_manager.delete(session.id)
        logger.error("Pipeline start failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── SSE Stream ───────────────────────────────────────────────────────

def _make_emitter(session):
    """노드에서 호출할 수 있는 이벤트 emitter 클로저 생성.

    log_line 이벤트는 session.logs에도 실시간 append (lock 보호) →
    LogsModal이 polling으로 phase 진행 중에도 라이브 로그를 볼 수 있게 함.
    """
    def emit(event_type: str, data: dict):
        # log_line 인터셉트 — session.logs에 라이브 추가
        if event_type == "log_line" and isinstance(data, dict):
            text = data.get("text", "")
            if text:
                try:
                    with session.lock:
                        session.logs.append(text)
                except Exception as e:
                    logger.warning("log_line append failed: %s", e)

        queue = session.event_queue
        loop = session._loop
        if queue is None or loop is None:
            logger.warning(
                "emit skipped (queue/loop missing): session=%s event=%s",
                session.id, event_type,
            )
            return
        try:
            asyncio.run_coroutine_threadsafe(
                queue.put((event_type, data)),
                loop,
            )
        except Exception as e:
            logger.error(
                "emit failed: session=%s event=%s error=%s",
                session.id, event_type, e,
            )
    return emit


def _make_config_with_emitter(session):
    """event emitter가 주입된 그래프 config 반환"""
    emitter = _make_emitter(session)
    return {
        **session.config,
        "configurable": {
            **session.config.get("configurable", {}),
            "event_emitter": emitter,
        },
    }


def _run_initial_phase(session):
    """초기 phase 실행 (data_backup → context_glossary → ko_review → ko_approval interrupt)"""
    emitter = _make_emitter(session)
    try:
        config = _make_config_with_emitter(session)
        node_emitter = config["configurable"]["event_emitter"]

        for event in session.graph.stream(
            session.initial_state, config=config, stream_mode="updates"
        ):
            if "__interrupt__" in event:
                emitter("interrupt", {})
                break

            node_name = list(event.keys())[0]
            node_output = event[node_name]
            node_logs = node_output.get("logs", [])

            # data_backup 완료 시 원본 데이터를 프론트엔드에 전송
            if node_name == "data_backup":
                orig_data = node_output.get("original_data", [])
                if orig_data:
                    rows = [
                        {"key": r.get(REQUIRED_COLUMNS["key"], ""),
                         "korean": r.get(REQUIRED_COLUMNS["korean"], ""),
                         "row_index": r.get("_row_index", i)}
                        for i, r in enumerate(orig_data)
                    ]
                    node_emitter("original_data", {"rows": rows})

            emitter("node_update", {
                "node": node_name,
                "step": "loading",
                "logs": node_logs,
            })

        # ko_review 결과 수집
        state_snapshot = session.graph.get_state(session.config)
        result = state_snapshot.values
        ko_results_raw = result.get("ko_review_results", [])

        with session.lock:
            session.graph_result = result
            session.logs = result.get("logs", [])
            session.current_step = "ko_review"
            # Cancel 복구용 캐시 저장
            session.cached_ko_review_results = ko_results_raw
            session.cached_ko_tokens = (
                result.get("total_input_tokens", 0),
                result.get("total_output_tokens", 0),
                result.get("total_reasoning_tokens", 0),
                result.get("total_cached_tokens", 0),
            )
        # row_index 우선 매핑 (중복 Key 대응) — ko_review_node가 _row_index를 직접 부여하므로
        # 정상 경로에선 모든 항목이 row_index를 가짐. None은 비정상이므로 로그 후 fallback.
        ko_result_by_ri = {r.get("row_index"): r for r in ko_results_raw if r.get("row_index") is not None}
        ko_result_by_key: dict[str, list] = {}
        orphan_count = 0
        for r in ko_results_raw:
            if r.get("row_index") is None:
                ko_result_by_key.setdefault(r["key"], []).append(r)
                orphan_count += 1
        if orphan_count:
            logger.warning(
                "ko_review_results에 row_index 결손 항목 %d개 — key fallback 사용",
                orphan_count,
            )
        key_consume: dict[str, int] = {}

        original_data = result.get("original_data", [])
        ko_results = []
        for row in original_data:
            key = row.get(REQUIRED_COLUMNS["key"], "")
            ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
            ri = row.get("_row_index")
            if ri is not None and ri in ko_result_by_ri:
                ko_results.append(ko_result_by_ri[ri])
                continue
            # row_index가 없는 항목만 key fallback (비정상 경로)
            bucket = ko_result_by_key.get(key)
            if bucket:
                idx = key_consume.get(key, 0)
                if idx < len(bucket):
                    ko_results.append(bucket[idx])
                    key_consume[key] = idx + 1
                    continue
            # 매칭 실패 — 원본 그대로 (변경 없음)
            ko_results.append({
                "key": key, "original": ko_text, "revised": ko_text,
                "comment": "", "has_issue": False, "row_index": ri,
            })

        # KR diff 리포트 생성
        ko_report_data = None
        if ko_results_raw and session.df is not None:
            original_rows = [
                {"Key": r.get(REQUIRED_COLUMNS["key"], ""),
                 "Korean(ko)": r.get(REQUIRED_COLUMNS["korean"], "")}
                for _, r in session.df.iterrows()
            ]
            revised_rows = [
                {"Key": r["key"],
                 "Korean(ko)": r.get("revised", r.get("original", ""))}
                for r in ko_results
            ]
            report_df, report_csv = generate_ko_diff_report(original_rows, revised_rows)
            session.ko_report_df = report_df
            session.ko_report_csv = report_csv
            ko_report_data = report_df.to_dict("records")

        emitter("ko_review_ready", {
            "results": ko_results,
            "count": len(ko_results),
            "report": ko_report_data,
        })
    except Exception as e:
        logger.error("Initial phase error for session %s: %s", session.id, e, exc_info=True)
        emitter("error", {"message": str(e)})


@router.get("/stream/{session_id}")
async def api_stream(session_id: str):
    """SSE 스트림 — 파이프라인 실시간 이벤트"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("SSE stream opened: %s (step=%s)", session_id, session.current_step)

    loop = asyncio.get_event_loop()
    with session.lock:
        session._loop = loop
        # 이전 SSE 연결 무효화 — generation counter 증가
        session._sse_generation += 1
        current_gen = session._sse_generation
        # Queue: 없을 때만 새로 생성 (SSE 재연결 시 기존 Queue 유지)
        if session.event_queue is None:
            session.event_queue = asyncio.Queue()
        should_start = session.current_step == "loading"

    # loading 상태일 때만 초기 phase 실행 (재연결 시 재실행 방지)
    if should_start:
        executor.submit(_run_initial_phase, session)

    async def event_generator():
        while session._sse_generation == current_gen:
            try:
                event_type, data = await asyncio.wait_for(
                    session.event_queue.get(), timeout=300
                )
                if event_type == "_sse_close":
                    break
                yield {"event": event_type, "data": json.dumps(data, ensure_ascii=False)}
                if event_type in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


# ── HITL 1: KR Approval ─────────────────────────────────────────────

def _run_translation_phase(session, resume_value: str):
    """번역 phase 실행 (translator → reviewer → final_approval interrupt)"""
    emitter = _make_emitter(session)
    try:
        config = _make_config_with_emitter(session)

        for event in session.graph.stream(
            Command(resume=resume_value), config, stream_mode="updates"
        ):
            if "__interrupt__" in event:
                break

            node_name = list(event.keys())[0]
            node_output = event[node_name]
            node_logs = node_output.get("logs", [])

            emitter("node_update", {
                "node": node_name,
                "step": "translating",
                "logs": node_logs,
            })

        # 결과 수집
        state_snapshot = session.graph.get_state(session.config)
        result = state_snapshot.values
        with session.lock:
            session.graph_result = result
            session.logs = result.get("logs", [])
            session.current_step = "final_review"

        # Translation diff report
        review_results = result.get("review_results", [])
        report_data = None
        if review_results:
            old_trans = [{"Key": r["key"], "lang": r["lang"],
                         "old": r.get("old_translation", "")} for r in review_results]
            new_trans = [{"Key": r["key"], "lang": r["lang"],
                         "new": r["translated"], "reason": r.get("reason", "")}
                        for r in review_results]
            report_df, report_csv = generate_translation_diff_report(old_trans, new_trans)
            session.translation_report_df = report_df
            session.translation_report_csv = report_csv
            report_data = report_df.to_dict("records")

        cost_summary = _build_cost_summary(
            result.get("total_input_tokens", 0),
            result.get("total_output_tokens", 0),
            result.get("total_reasoning_tokens", 0),
            result.get("total_cached_tokens", 0),
        )

        emitter("final_review_ready", {
            "review_results": review_results,
            "failed_rows": result.get("failed_rows", []),
            "report": report_data,
            "cost": cost_summary,
        })
    except Exception as e:
        logger.error("Translation phase error for session %s: %s", session.id, e, exc_info=True)
        emitter("error", {"message": str(e)})


@router.post("/approve-ko/{session_id}")
async def api_approve_ko(session_id: str, req: ApprovalRequest):
    """HITL 1: 한국어 검수 승인/거부 → 번역 phase 시작"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("KR approval: session=%s, decision=%s", session_id, req.decision)

    loop = asyncio.get_event_loop()
    with session.lock:
        session.ko_resume_value = req.decision
        session.current_step = "translating"
        session._loop = loop
        # Cancel 후 재진입 시 SSE 재연결 전에 호출될 수 있으므로 queue 확보
        if session.event_queue is None:
            session.event_queue = asyncio.Queue()

    # 백그라운드에서 번역 실행 (시트에는 Write하지 않음 — 최종 컨펌 시점에서 일괄 반영)
    executor.submit(_run_translation_phase, session, req.decision)

    return {"status": "translating"}


def _emit_done(session):
    """SSE done 이벤트 전송 — EventSource 정상 종료용"""
    try:
        if session.event_queue and session._loop:
            asyncio.run_coroutine_threadsafe(
                session.event_queue.put(("done", {})),
                session._loop,
            )
    except Exception:
        pass


# ── HITL 2: Final Approval ───────────────────────────────────────────

@router.post("/approve-final/{session_id}")
async def api_approve_final(session_id: str, req: ApprovalRequest):
    """HITL 2: 최종 승인 → 시트 업데이트 / 거부 → 원복"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Final approval: session=%s, decision=%s", session_id, req.decision)

    config = session.config

    if req.decision == "approved":
        try:
            # 최종 컨펌 직전 백업 생성 (시트 Write 전 안전장치)
            if session.df is not None:
                sheet_name = (session.initial_state or {}).get("sheet_name", "unknown")
                backup_folder = _load_config().get("backup_folder", "./backups")
                save_backup_to_folder(session.df, sheet_name, folder=backup_folder)

            result = session.graph.invoke(Command(resume="approved"), config=config)
            with session.lock:
                session.graph_result = result
                session.logs = result.get("logs", [])

            updates = result.get("_updates", [])
            if updates and session.worksheet and session.df is not None:
                batch_update_sheet(session.worksheet, updates, session.df)
                try:
                    batch_format_cells(session.worksheet, updates, session.df)
                except Exception as e:
                    logger.warning("Cell formatting failed (non-critical): %s", e)

            with session.lock:
                session.current_step = "done"
            _emit_done(session)
            return {
                "status": "done",
                "updates_count": len(updates),
                "translations_applied": True,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # 거부: 중간 Write가 없으므로 원복 불필요 — 세션 정리만 수행
        try:
            session.graph.invoke(Command(resume="rejected"), config=config)
        except Exception as e:
            logger.warning("Rejected graph invoke failed (non-critical): %s", e)

        with session.lock:
            session.current_step = "done"
        _emit_done(session)
        return {"status": "done", "translations_applied": False}


# ── Cancel ───────────────────────────────────────────────────────────

@router.post("/cancel/{session_id}")
def api_cancel(session_id: str):
    """번역 취소 → ko_review로 복귀"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Cancel: session=%s", session_id)

    # ── 이전 SSE 즉시 종료 ──
    # old queue에 _sse_close를 넣어 블로킹된 get()을 깨우고,
    # generation을 증가시켜 event_generator 루프를 종료시킴
    with session.lock:
        old_queue = session.event_queue
        old_loop = session._loop
        session._sse_generation += 1
        session.event_queue = None
    if old_queue and old_loop:
        try:
            asyncio.run_coroutine_threadsafe(
                old_queue.put(("_sse_close", {})),
                old_loop,
            )
        except Exception:
            pass

    from agents.graph import build_graph

    # 그래프 재생성
    session.graph, session.checkpointer = build_graph()
    session.thread_id = str(uuid.uuid4())
    session.config = {"configurable": {"thread_id": session.thread_id}}

    if session.initial_state:
        try:
            # 캐시된 ko_review 결과 주입 → ko_review_node가 LLM 호출 건너뜀
            cancel_state = {**session.initial_state}
            if session.cached_ko_review_results:
                cancel_state["ko_review_results"] = session.cached_ko_review_results
                cancel_state["total_input_tokens"] = session.cached_ko_tokens[0]
                cancel_state["total_output_tokens"] = session.cached_ko_tokens[1]
                cancel_state["total_reasoning_tokens"] = session.cached_ko_tokens[2] if len(session.cached_ko_tokens) > 2 else 0
                cancel_state["total_cached_tokens"] = session.cached_ko_tokens[3] if len(session.cached_ko_tokens) > 3 else 0
                # logs는 비워둠 — data_backup/context_glossary가 새로 쌓고,
                # ko_review_node는 캐시 히트 로그 1줄만 추가

            for ev in session.graph.stream(
                cancel_state, config=session.config, stream_mode="updates"
            ):
                if "__interrupt__" in ev:
                    break

            # 세션 복구용 상태 갱신
            state_snapshot = session.graph.get_state(session.config)
            with session.lock:
                session.graph_result = state_snapshot.values
                session.logs = session.graph_result.get("logs", [])
                session.current_step = "ko_review"
            return {"status": "ko_review"}
        except Exception as e:
            with session.lock:
                session.current_step = "idle"
            raise HTTPException(status_code=500, detail=str(e))

    with session.lock:
        session.current_step = "idle"
    return {"status": "idle"}


# ── State Query ──────────────────────────────────────────────────────

@router.get("/state/{session_id}", response_model=SessionStateResponse)
def api_state(session_id: str):
    """세션 상태 조회"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ko_count = 0
    review_count = 0
    fail_count = 0
    cost_summary = None
    total_rows = 0
    ko_review_results = None
    review_results_data = None
    failed_rows_data = None
    original_rows_data = None

    if session.graph_result:
        ko_count = len(session.graph_result.get("ko_review_results", []))
        review_count = len(session.graph_result.get("review_results", []))
        fail_count = len(session.graph_result.get("failed_rows", []))
        total_rows = len(session.graph_result.get("original_data", []))
        cost_summary = _build_cost_summary(
            session.graph_result.get("total_input_tokens", 0),
            session.graph_result.get("total_output_tokens", 0),
            session.graph_result.get("total_reasoning_tokens", 0),
            session.graph_result.get("total_cached_tokens", 0),
        )

        # 세션 복원용: 테이블 표시를 위한 original_rows (loading/translating 포함)
        orig = session.graph_result.get("original_data", [])
        if orig:
            original_rows_data = [
                {"key": r.get(REQUIRED_COLUMNS["key"], ""),
                 "korean": r.get(REQUIRED_COLUMNS["korean"], "")}
                for r in orig
            ]

        # 세션 복원용: HITL 대기 단계일 때 실제 데이터 포함
        if session.current_step == "ko_review":
            ko_results_raw = session.graph_result.get("ko_review_results", [])
            # row_index 우선 매핑 (중복 Key 대응)
            ko_by_ri = {r.get("row_index"): r for r in ko_results_raw if r.get("row_index") is not None}
            ko_by_key_first = {}
            for r in ko_results_raw:
                ko_by_key_first.setdefault(r.get("key", ""), r)
            original_data = session.graph_result.get("original_data", [])
            ko_review_results = []
            for row in original_data:
                key = row.get(REQUIRED_COLUMNS["key"], "")
                ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
                ri = row.get("_row_index")
                if ri is not None and ri in ko_by_ri:
                    ko_review_results.append(ko_by_ri[ri])
                elif key in ko_by_key_first:
                    ko_review_results.append(ko_by_key_first[key])
                else:
                    ko_review_results.append({
                        "key": key, "original": ko_text,
                        "revised": ko_text, "comment": "", "has_issue": False,
                    })
        elif session.current_step == "final_review":
            review_results_data = session.graph_result.get("review_results", [])
            failed_rows_data = session.graph_result.get("failed_rows", [])

    return SessionStateResponse(
        session_id=session.id,
        current_step=session.current_step,
        ko_review_count=ko_count,
        review_count=review_count,
        fail_count=fail_count,
        cost_summary=cost_summary,
        logs=session.logs,
        ko_review_results=ko_review_results,
        review_results=review_results_data,
        failed_rows=failed_rows_data,
        original_rows=original_rows_data,
        total_rows=total_rows,
    )


# ── Logs (디버그) ─────────────────────────────────────────────────────

@router.get("/logs/{session_id}")
def api_logs(session_id: str):
    """세션 누적 로그 조회 (UI 디버그 버튼용)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "current_step": session.current_step,
        "logs": session.logs or [],
    }


# ── Downloads ────────────────────────────────────────────────────────

@router.get("/download/{session_id}/{file_type}")
def api_download(session_id: str, file_type: str):
    """CSV 다운로드"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if file_type == "backup":
        data = getattr(session, "backup_csv", None)
        name = getattr(session, "backup_filename", "backup.csv")
    elif file_type == "ko_report":
        data = getattr(session, "ko_report_csv", None)
        name = "ko_review_report.csv"
    elif file_type == "translation_report":
        data = getattr(session, "translation_report_csv", None)
        name = "translation_diff_report.csv"
    elif file_type == "failed":
        if session.graph_result:
            failed = session.graph_result.get("failed_rows", [])
            if failed:
                data = pd.DataFrame(failed).to_csv(index=False).encode("utf-8")
            else:
                data = None
        else:
            data = None
        name = "review_failed_rows.csv"
    elif file_type == "logs":
        data = "\n".join(session.logs).encode("utf-8") if session.logs else None
        name = "execution_log.txt"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown file type: {file_type}")

    if not data:
        raise HTTPException(status_code=404, detail="No data available")

    media_type = "text/plain" if file_type == "logs" else "text/csv"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ── Config (saved URL) ──────────────────────────────────────────────

@router.get("/guide")
def api_guide():
    """USER_GUIDE.md를 섹션별로 파싱하여 반환 (런타임 파일 읽기)"""
    guide_path = Path(__file__).resolve().parent.parent.parent / "docs" / "USER_GUIDE.md"
    if not guide_path.exists():
        raise HTTPException(status_code=404, detail="Guide not found")

    content = guide_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    title = ""
    sections = []
    current_section = None

    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            if current_section:
                sections.append(current_section)
            current_section = {
                "id": line[3:].strip().lower().replace(" ", "-"),
                "title": line[3:].strip(),
                "content": "",
            }
        elif current_section is not None:
            current_section["content"] += line + "\n"

    if current_section:
        sections.append(current_section)

    for s in sections:
        s["content"] = s["content"].strip()

    return {"title": title, "sections": sections}


@router.get("/config")
def api_get_config():
    """저장된 설정 조회 (bot_email 포함, 기본값 병합)"""
    from config.glossary import get_glossary, get_game_synopsis, get_tone_and_manner

    cfg = _load_config()
    cfg["bot_email"] = get_bot_email()
    # 기본값 병합 — 파일에 없으면 fallback 포함
    if "glossary" not in cfg:
        cfg["glossary"] = get_glossary()
    if "game_synopsis" not in cfg:
        cfg["game_synopsis"] = get_game_synopsis()
    if "tone_and_manner" not in cfg:
        cfg["tone_and_manner"] = get_tone_and_manner()
    return cfg


@router.put("/config")
def api_save_config(data: dict):
    """설정 저장"""
    _save_config(data)
    return {"status": "saved"}
