"""기존 파이프라인에 공유 세션, 작업 재개, 서버 간 SSE 전달을 연결한다."""

import asyncio
import base64
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

import pandas as pd
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger("devlocal.persistence")
runtime = None

FIELDS = (
    "id", "thread_id", "current_step", "initial_state", "graph_result", "logs",
    "cached_ko_review_results", "cached_ko_tokens", "initial_started", "final_response",
    "pending_updates", "final_plan", "sheet_url", "job", "backup_filename",
)
CSV_FIELDS = ("backup_csv", "ko_report_csv", "translation_report_csv")


def snapshot(session):
    data = {key: getattr(session, key, None) for key in FIELDS}
    data["df"] = json.loads(session.df.to_json(orient="split", force_ascii=False)) if session.df is not None else None
    for key in CSV_FIELDS:
        value = getattr(session, key, None)
        data[key] = base64.b64encode(value).decode("ascii") if value is not None else None
    return data


def hydrate(data, checkpointer):
    from backend.api.session_manager import Session
    session = Session(checkpointer)
    for key in FIELDS:
        if key in data:
            setattr(session, key, data[key])
    session.config = {"configurable": {"thread_id": session.thread_id}}
    frame = data.get("df")
    session.df = pd.DataFrame(**frame) if frame is not None else None
    for key in CSV_FIELDS:
        if data.get(key) is not None:
            setattr(session, key, base64.b64decode(data[key], validate=True))
    return session


class Scope:
    def __init__(self, store, sid=None):
        self.store = store
        row = store.load(sid) if sid else None
        self.revision = row["revision"] if row else None
        self.session = hydrate(row["payload"], store.checkpointer) if row else None
        if self.session:
            self.bind()

    def create(self):
        from backend.api.session_manager import Session
        self.session = Session(self.store.checkpointer)
        self.bind()
        return self.session

    def bind(self):
        self.session.persist = self.save
        self.session.publish = self.publish
        self.session.is_current = self.is_current

    def is_current(self):
        row = self.store.load(self.session.id)
        return row is not None and row["payload"]["thread_id"] == self.session.thread_id

    def save(self, event=None):
        if self.session:
            self.revision = self.store.save(snapshot(self.session), self.revision, event)

    def publish(self, kind, data):
        if kind in {"ko_review_ready", "final_review_ready", "done", "error"}:
            self.session.job = None
            self.save((kind, data))
        else:
            self.store.publish(self.session.id, self.session.thread_id, kind, data)


class SharedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def shared_handler(request):
            if runtime is None:
                return await handler(request)
            from backend.api.session_manager import session_scope
            from backend.storage import StaleSession
            sid = request.path_params.get("session_id")
            writing = request.method != "GET"
            # 승인·취소 요청은 서버 전체에서 직렬화한다. 실행 작업은 별도 lock을 쓴다.
            guard = runtime.store.guard(f"command:{sid}") if sid and writing else nullcontext(True)
            acquired = await asyncio.to_thread(guard.__enter__)
            if not acquired:
                await asyncio.to_thread(guard.__exit__, None, None, None)
                raise HTTPException(409, "다른 요청을 처리 중입니다. 잠시 후 다시 시도하세요")
            token = None
            try:
                scope = await asyncio.to_thread(Scope, runtime.store, sid)
                if sid and scope.session is None:
                    raise HTTPException(404, "Session not found")
                token = session_scope.set(scope)
                response = await handler(request)
                if writing:
                    await asyncio.to_thread(scope.save)
                return response
            except StaleSession as error:
                raise HTTPException(409, "다른 요청이 세션을 변경했습니다. 상태를 새로고침하세요") from error
            finally:
                if token is not None:
                    session_scope.reset(token)
                await asyncio.to_thread(guard.__exit__, None, None, None)
        return shared_handler


def schedule(executor, function, session, *args):
    if session.publish is None:
        return executor.submit(function, session, *args)
    session.job = {"phase": "initial" if function.__name__ == "_run_initial_phase" else "translation"}
    if session.job["phase"] == "translation":
        session.job["decision"] = args[0]


def state_events(session):
    """최초 연결에도 완료 상태를 전달하여 연결 전에 발생한 이벤트 유실을 보완한다."""
    from config.constants import REQUIRED_COLUMNS
    from utils.cost import build_cost_summary
    from utils.rows import merge_ko_reviews
    result = session.graph_result or session.initial_state or {}
    original = result.get("original_data", [])
    yield "original_data", {"rows": [{"key": r.get(REQUIRED_COLUMNS["key"], ""),
                                      "korean": r.get(REQUIRED_COLUMNS["korean"], ""),
                                      "row_index": r.get("_row_index", i)} for i, r in enumerate(original)]}
    if session.current_step == "ko_review":
        reviews = merge_ko_reviews(original, result.get("ko_review_results", []))
        yield "ko_review_ready", {"results": reviews, "count": len(reviews), "report": None}
    elif session.current_step == "final_review":
        yield "node_update", {"node": "reviewer", "step": "translating", "logs": session.logs}
        cost = build_cost_summary(*(result.get(key, 0) for key in (
            "total_input_tokens", "total_output_tokens", "total_reasoning_tokens", "total_cached_tokens")))
        yield "final_review_ready", {"review_results": result.get("review_results", []),
                                     "failed_rows": result.get("failed_rows", []), "cost": cost, "report": None}
    elif session.current_step == "done":
        yield "done", session.final_response
    elif session.current_step == "idle":
        yield "error", {"message": "작업이 중단되었습니다. 새 세션에서 다시 시작하세요"}
    else:
        yield "node_update", {"node": "translator" if session.current_step == "translating" else "data_backup",
                              "step": session.current_step, "logs": session.logs}


async def shared_stream(session):
    store = runtime.store
    cursor = await asyncio.to_thread(store.cursor, session.id)
    current = await asyncio.to_thread(Scope, store, session.id)
    async def events():
        nonlocal cursor
        for kind, data in state_events(current.session):
            yield {"event": kind, "data": json.dumps(data, ensure_ascii=False)}
            if kind in {"done", "error"}:
                return
        while True:
            rows = await asyncio.to_thread(store.events, session.id, cursor)
            for row in rows:
                cursor = row["id"]
                yield {"id": str(cursor), "event": row["kind"], "data": json.dumps(row["data"], ensure_ascii=False)}
                if row["kind"] in {"done", "error"}:
                    return
            await asyncio.sleep(0.5)
    return EventSourceResponse(events(), ping=15)


class Runtime:
    def __init__(self, store):
        self.store = store
        self.stop = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="durable-job")
        self.active = {}
        self.thread = threading.Thread(target=self.dispatch, daemon=True)

    def dispatch(self):
        while not self.stop.is_set():
            try:
                self.active = {sid: future for sid, future in self.active.items() if not future.done()}
                for sid in self.store.jobs():
                    if sid not in self.active and len(self.active) < 4:
                        self.active[sid] = self.executor.submit(self.run_job, sid)
            except Exception:
                logger.exception("공유 작업 큐 조회 실패")
            self.stop.wait(1)

    def run_job(self, sid):
        from backend.api import routes
        from backend.storage import StaleSession
        try:
            with self.store.guard(f"worker:{sid}") as acquired:
                if not acquired:
                    return
                scope = Scope(self.store, sid)
                session = scope.session
                if not session or not session.job:
                    return
                job = session.job
                session.initial_started = True
                if job["phase"] != "cancel":
                    # 연결 단절 후 다른 worker가 인계받아도 두 실행이 같은
                    # 체크포인트를 덮어쓰지 않도록 새 thread_id로 분기한다.
                    thread_id = str(uuid.uuid4())
                    self.store.fork_checkpoint(session.thread_id, thread_id)
                    session.thread_id = thread_id
                    session.config = {"configurable": {"thread_id": thread_id}}
                    scope.save()
                if job["phase"] == "initial":
                    routes._run_initial_phase(session)
                elif job["phase"] == "cancel":
                    with self.store.guard(f"command:{sid}") as command_acquired:
                        if not command_acquired:
                            return
                        # API의 복원 완료와 lock 획득 사이에 상태가 바뀔 수 있다.
                        scope = Scope(self.store, sid)
                        session = scope.session
                        if not session.job or session.job["phase"] != "cancel":
                            return
                        routes._restore_cancelled_phase(session)
                else:
                    routes._run_translation_phase(session, job["decision"])
                session.job = None
                scope.save()
        except StaleSession:
            # 취소나 다음 승인이 저장된 이후에는 이전 작업을 덮어쓰지 않는다.
            logger.info("이전 작업 결과 무효화: %s", sid)
        except Exception:
            # DB 장애·프로세스 중단 시 job은 남아 다음 dispatcher가 복구한다.
            logger.exception("공유 작업 실행 중단: %s", sid)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        self.executor.shutdown(wait=True)
        self.store.close()
