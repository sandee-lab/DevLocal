"""API 라우트 — REST + SSE endpoints"""

import asyncio
import io
import json
import logging
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
from backend.persistence import SharedRoute, schedule, shared_stream
from config.constants import (
    FORBIDDEN_SHEETS,
    REQUIRED_COLUMNS,
    SUPPORTED_LANGUAGES,
)
from config.app_config import load_config as _load_config, save_config as _save_config
from utils.rows import merge_ko_reviews
from utils.cost import build_cost_summary
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

router = APIRouter(route_class=SharedRoute)
executor = ThreadPoolExecutor(max_workers=4)

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
    session = None
    try:
        if req.sheet_name in FORBIDDEN_SHEETS:
            raise ValueError("번역이 금지된 시트입니다")
        session = session_manager.create()
        session.sheet_url = req.sheet_url
        session.current_step = "loading"
        if session.publish is not None:
            session.job = {"phase": "initial"}
        session.spreadsheet = connect_to_sheet(req.sheet_url)
        ws = session.spreadsheet.worksheet(req.sheet_name)
        df = load_sheet_data(ws)

        # 필수 컬럼 검증 — 누락 시 그래프 실행 전 즉시 실패
        missing = [col for col in REQUIRED_COLUMNS.values() if col not in df.columns]
        if missing:
            raise ValueError(
                f"시트 '{req.sheet_name}'에 필수 컬럼이 없습니다: {', '.join(missing)}"
            )

        # 타겟 언어 결정 — 요청 언어(비어 있으면 전체 지원 언어) 중 시트에 컬럼이 있는 언어만
        requested_langs = req.target_languages or list(SUPPORTED_LANGUAGES)
        target_languages = [
            lang for lang in dict.fromkeys(requested_langs)
            if SUPPORTED_LANGUAGES.get(lang) in df.columns
        ]
        if not target_languages:
            raise ValueError(
                f"시트 '{req.sheet_name}'에 번역 대상 언어 컬럼이 없습니다. "
                f"지원 컬럼: {', '.join(SUPPORTED_LANGUAGES.values())}"
            )
        logger.info("Target languages for '%s': %s", req.sheet_name, target_languages)

        df = ensure_tool_status_column(ws, df)

        df = df.iloc[max(req.row_start - 1, 0):req.row_end or None]

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
            "target_languages": target_languages,
            "original_data": records,
            "backup_data": df.to_dict("records"),
            "ko_review_results": [],
            "translation_results": [],
            "review_results": [],
            "failed_rows": [],
            "ko_approval_result": None,
            "final_approval_result": None,
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
        if session is not None:
            session_manager.delete(session.id)
        logger.error("Pipeline start failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── SSE Stream ───────────────────────────────────────────────────────


def _initial_input(session, graph, config):
    if session.publish is not None and graph.get_state(config).values:
        return None
    return session.initial_state


def _translation_input(session, graph, config, decision):
    if session.publish is not None:
        state = graph.get_state(config)
        if state.next != ("ko_approval",):
            return None
    return Command(resume=decision)

def _make_emitter(session, graph=None):
    """실행 그래프를 고정하여 취소된 작업의 로그·이벤트를 차단한다."""
    graph = graph if graph is not None else session.graph

    def emit(event_type: str, data: dict):
        with session.lock:
            if session.graph is not graph:
                return
            if event_type == "log_line" and data.get("text"):
                session.logs.append(data["text"])
            loop = session._loop
        if session.publish is not None:
            session.publish(event_type, data)
            return
        if loop is None or loop.is_closed():
            return

        def enqueue():
            with session.lock:
                if session.graph is graph and session.event_queue is not None:
                    session.event_queue.put_nowait((event_type, data))
        try:
            loop.call_soon_threadsafe(enqueue)
        except RuntimeError:
            logger.warning("종료된 SSE 이벤트 루프: %s", session.id)
    return emit


def _phase_context(session, graph=None, graph_config=None):
    with session.lock:
        graph = graph if graph is not None else session.graph
        config = graph_config if graph_config is not None else session.config
    emitter = _make_emitter(session, graph)
    return graph, {
        **config,
        "configurable": {
            **config["configurable"], "event_emitter": emitter,
            "is_cancelled": lambda: session.graph is not graph or not session.is_current(),
        },
    }, emitter


def _phase_error(session, graph, error):
    with session.lock:
        if session.graph is not graph:
            return
        session.reset_graph()
        session.current_step = "idle"
    _make_emitter(session)("error", {"message": str(error)})


def _run_initial_phase(session, graph=None, graph_config=None):
    """초기 phase 실행 (data_backup → context_glossary → ko_review → ko_approval interrupt)"""
    graph, config, emitter = _phase_context(session, graph, graph_config)
    if session.graph is not graph:
        return
    node_emitter = emitter
    try:

        for event in graph.stream(
            _initial_input(session, graph, config), config=config, stream_mode="updates"
        ):
            if session.graph is not graph:
                return
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
        state_snapshot = graph.get_state(config)
        result = state_snapshot.values
        ko_results_raw = result.get("ko_review_results", [])

        with session.lock:
            if session.graph is not graph:
                return
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
        ko_results = merge_ko_reviews(result.get("original_data", []), ko_results_raw)

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
            with session.lock:
                if session.graph is not graph:
                    return
                session.ko_report_df = report_df
                session.ko_report_csv = report_csv
            ko_report_data = report_df.to_dict("records")

        if not any(r.get("has_issue") for r in ko_results):
            with session.lock:
                if session.graph is not graph:
                    return
                session.current_step = "translating"
                if session.publish is not None:
                    session.job = {"phase": "translation", "decision": "approved"}
            session.persist()
            emitter("node_update", {"node": "translator", "step": "translating", "logs": session.logs})
            _run_translation_phase(session, "approved", graph, config)
            return

        emitter("ko_review_ready", {
            "results": ko_results,
            "count": len(ko_results),
            "report": ko_report_data,
        })
    except Exception as e:
        if session.graph is not graph:
            return
        logger.error("Initial phase error for session %s: %s", session.id, e, exc_info=True)
        _phase_error(session, graph, e)


@router.get("/stream/{session_id}")
async def api_stream(session_id: str):
    """SSE 스트림 — 파이프라인 실시간 이벤트"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.publish is not None:
        return await shared_stream(session)

    logger.info("SSE stream opened: %s (step=%s)", session_id, session.current_step)

    loop = asyncio.get_running_loop()
    with session.lock:
        session._loop = loop
        session._sse_generation += 1
        current_gen = session._sse_generation
        old_queue = session.event_queue
        queue = asyncio.Queue()
        if old_queue is not None:
            while not old_queue.empty():
                queue.put_nowait(old_queue.get_nowait())
            old_queue.put_nowait(("_sse_close", {}))
        session.event_queue = queue
        should_start = session.current_step == "loading" and not session.initial_started
        if should_start:
            session.initial_started = True
            schedule(executor, _run_initial_phase, session, session.graph, session.config)

    async def event_generator():
        while session._sse_generation == current_gen:
            try:
                event_type, data = await asyncio.wait_for(
                    queue.get(), timeout=300
                )
                if event_type == "_sse_close" or session._sse_generation != current_gen:
                    break
                yield {"event": event_type, "data": json.dumps(data, ensure_ascii=False)}
                if event_type in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


# ── HITL 1: KR Approval ─────────────────────────────────────────────

def _run_translation_phase(session, resume_value: str, graph=None, graph_config=None):
    """번역 phase 실행 (translator → reviewer → final_approval interrupt)"""
    graph, config, emitter = _phase_context(session, graph, graph_config)
    if session.graph is not graph:
        return
    try:

        for event in graph.stream(
            _translation_input(session, graph, config, resume_value), config, stream_mode="updates"
        ):
            if session.graph is not graph:
                return
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
        state_snapshot = graph.get_state(config)
        result = state_snapshot.values
        with session.lock:
            if session.graph is not graph:
                return
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
            with session.lock:
                if session.graph is not graph:
                    return
                session.translation_report_df = report_df
                session.translation_report_csv = report_csv
            report_data = report_df.to_dict("records")

        cost_summary = build_cost_summary(
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
        if session.graph is not graph:
            return
        logger.error("Translation phase error for session %s: %s", session.id, e, exc_info=True)
        _phase_error(session, graph, e)


@router.post("/approve-ko/{session_id}")
async def api_approve_ko(session_id: str, req: ApprovalRequest):
    """HITL 1: 한국어 검수 승인/거부 → 번역 phase 시작"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("KR approval: session=%s, decision=%s", session_id, req.decision)

    loop = asyncio.get_event_loop()
    with session.lock:
        if session.current_step != "ko_review":
            raise HTTPException(status_code=409, detail="한국어 승인 대기 상태가 아닙니다")
        reviews = merge_ko_reviews(
            session.graph_result.get("original_data", []),
            session.graph_result.get("ko_review_results", []),
        )
        for review in reviews:
            if req.decisions.get(f"ri_{review['row_index']}", req.decisions.get(review["key"])) == "rejected":
                review.update(revised=review["original"], has_issue=False, comment="")
        session.graph.update_state(session.config, {"ko_review_results": reviews})
        session.current_step = "translating"
        session._loop = loop
        # Cancel 후 재진입 시 SSE 재연결 전에 호출될 수 있으므로 queue 확보
        if session.event_queue is None:
            session.event_queue = asyncio.Queue()

        # 작업 예약도 lock 안에서 처리하여 취소와 교차하지 않게 한다.
        schedule(executor, _run_translation_phase, session, req.decision, session.graph, session.config)

    return {"status": "translating"}


# ── HITL 2: Final Approval ───────────────────────────────────────────

@router.post("/approve-final/{session_id}")
def api_approve_final(session_id: str, req: ApprovalRequest):
    """동기 I/O는 FastAPI 작업 스레드에서 실행하고, 완료한 요청은 재사용한다."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    with session.lock:
        if session.current_step == "done" and session.final_response is not None:
            return session.final_response
        if session.current_step != "final_review" or session.finalizing:
            raise HTTPException(status_code=409, detail="최종 승인 대기 상태가 아닙니다")
        if session.final_plan and req.decision != session.final_plan["decision"]:
            raise HTTPException(status_code=409, detail="이미 저장된 승인 결정으로 재시도해야 합니다")
        if req.decision == "rejected" and session.pending_updates is not None:
            raise HTTPException(status_code=409, detail="시트 쓰기 재시도가 필요합니다")
        session.finalizing = True

    try:
        if session.final_plan is None:
            session.final_plan = req.model_dump()
            session.persist()
        req = ApprovalRequest(**session.final_plan)
        approved = req.decision == "approved"
        if approved:
            if session.pending_updates is None:
                reviews = session.graph_result.get("review_results", [])
                accepted = [r for r in reviews if req.decisions.get(
                    f"{r['row_index']}_{r['lang']}" if r.get("row_index") is not None
                    else f"{r['key']}_{r['lang']}"
                ) != "rejected"]
                checkpoint = session.graph.get_state(session.config)
                if checkpoint.next == ("final_approval",):
                    session.graph.update_state(session.config, {"review_results": accepted})
                if not checkpoint.next and checkpoint.values.get("final_approval_result") == "approved":
                    result = checkpoint.values
                else:
                    result = session.graph.invoke(
                        Command(resume="approved") if checkpoint.next == ("final_approval",) else None,
                        config=session.config,
                    )
                with session.lock:
                    session.graph_result = result
                    session.logs = result.get("logs", [])
                    session.pending_updates = result.get("_updates", [])
                session.persist()
            updates = session.pending_updates
            if updates and session.worksheet is None and session.sheet_url:
                session.spreadsheet = connect_to_sheet(session.sheet_url)
                session.worksheet = session.spreadsheet.worksheet(session.initial_state["sheet_name"])
            if updates and session.worksheet is not None and session.df is not None:
                sheet_name = (session.initial_state or {}).get("sheet_name", "unknown")
                save_backup_to_folder(session.df, sheet_name, folder=_load_config().get("backup_folder", "./backups"))
                batch_update_sheet(session.worksheet, updates, session.df)
                try:
                    batch_format_cells(session.worksheet, updates, session.df)
                except Exception as error:
                    logger.warning("Cell formatting failed (non-critical): %s", error)
        else:
            checkpoint = session.graph.get_state(session.config)
            if checkpoint.next:
                session.graph.invoke(Command(resume="rejected"), config=session.config)
            updates = []
        response = {"status": "done", "updates_count": len(updates), "translations_applied": approved}
        with session.lock:
            session.final_response = response
            session.current_step = "done"
        _make_emitter(session)("done", response)
        return response
    except Exception as error:
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        with session.lock:
            session.finalizing = False


# ── Cancel ───────────────────────────────────────────────────────────


def _restore_cancelled_phase(session):
    graph, config = session.graph, session.config
    cancel_state = {**session.initial_state,
                    "ko_review_results": session.cached_ko_review_results,
                    "_ko_review_cached": True}
    for key, value in zip(
        ("total_input_tokens", "total_output_tokens", "total_reasoning_tokens", "total_cached_tokens"),
        session.cached_ko_tokens,
    ):
        cancel_state[key] = value
    existing = graph.get_state(config).values if session.publish is not None else None
    for event in graph.stream(None if existing else cancel_state, config=config, stream_mode="updates"):
        if "__interrupt__" in event:
            break
    result = graph.get_state(config).values
    with session.lock:
        session.graph_result = result
        session.logs = result.get("logs", [])
        session.current_step = "ko_review"
    if session.publish is not None:
        session.publish("ko_review_ready", {
            "results": merge_ko_reviews(result.get("original_data", []), result.get("ko_review_results", [])),
            "count": len(result.get("original_data", [])), "report": None,
        })
    return {"status": "ko_review"}

@router.post("/cancel/{session_id}")
async def api_cancel(session_id: str):
    """현재 실행을 무효화한 뒤 캐시로 한국어 승인 대기를 복원한다."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    with session.lock:
        if session.current_step not in {"translating", "final_review"} or session.finalizing or session.pending_updates is not None or session.final_plan is not None:
            raise HTTPException(status_code=409, detail="취소할 수 있는 상태가 아닙니다")
        session.reset_graph()
        session.current_step = "loading"
        session.initial_started = True
        if session.publish is not None:
            session.job = {"phase": "cancel"}
        graph = session.graph
        # 연결은 유지하되 취소 전 대기 이벤트만 비운다.
        if session.event_queue is not None:
            while not session.event_queue.empty():
                session.event_queue.get_nowait()

    try:
        # 새 thread_id를 먼저 저장해 다른 서버의 취소 전 작업을 차단한다.
        session.persist()
        return await asyncio.to_thread(_restore_cancelled_phase, session)
    except Exception as error:
        _phase_error(session, graph, error)
        raise HTTPException(status_code=500, detail=str(error)) from error


# ── State Query ──────────────────────────────────────────────────────

@router.get("/state/{session_id}", response_model=SessionStateResponse)
def api_state(session_id: str):
    """세션 상태 조회"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    with session.lock:
        result = session.graph_result or {}
        current_step = session.current_step
        logs = list(session.logs)
        final_response = session.final_response or {}

    ko_count = 0
    review_count = 0
    fail_count = 0
    cost_summary = None
    total_rows = 0
    ko_review_results = None
    review_results_data = None
    failed_rows_data = None
    original_rows_data = None

    if result:
        ko_count = len(result.get("ko_review_results", []))
        review_count = len(result.get("review_results", []))
        fail_count = len(result.get("failed_rows", []))
        total_rows = len(result.get("original_data", []))
        cost_summary = build_cost_summary(
            result.get("total_input_tokens", 0),
            result.get("total_output_tokens", 0),
            result.get("total_reasoning_tokens", 0),
            result.get("total_cached_tokens", 0),
        )

        # 세션 복원용: 테이블 표시를 위한 original_rows (loading/translating 포함)
        orig = result.get("original_data", [])
        if orig:
            original_rows_data = [
                {"key": r.get(REQUIRED_COLUMNS["key"], ""),
                 "korean": r.get(REQUIRED_COLUMNS["korean"], ""),
                 "row_index": r.get("_row_index", i)}
                for i, r in enumerate(orig)
            ]

        # 세션 복원용: HITL 대기 단계일 때 실제 데이터 포함
        if current_step == "ko_review":
            ko_results_raw = result.get("ko_review_results", [])
            ko_review_results = merge_ko_reviews(
                result.get("original_data", []), ko_results_raw,
            )
        elif current_step == "final_review":
            review_results_data = result.get("review_results", [])
            failed_rows_data = result.get("failed_rows", [])

    return SessionStateResponse(
        session_id=session.id,
        current_step=current_step,
        ko_review_count=ko_count,
        review_count=review_count,
        fail_count=fail_count,
        cost_summary=cost_summary,
        logs=logs,
        translations_applied=final_response.get("translations_applied", False),
        updates_count=final_response.get("updates_count", 0),
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
    try:
        _save_config(data)
    except OSError as error:
        raise HTTPException(status_code=500, detail="설정을 저장하지 못했습니다") from error
    return {"status": "saved"}
