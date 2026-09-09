"""서버 사이드 세션 관리 — Graph 인스턴스 + 상태"""

import logging
import uuid
import asyncio
import threading
from typing import Optional
from collections import OrderedDict
from contextvars import ContextVar

from agents.graph import build_graph

logger = logging.getLogger("devlocal.session")
session_scope = ContextVar("session_scope", default=None)


class Session:
    """단일 번역 세션"""

    def __init__(self, checkpointer=None):
        self.id = str(uuid.uuid4())
        self._shared_checkpointer = checkpointer
        self.graph, self.checkpointer = build_graph(checkpointer)
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self.current_step = "idle"
        self.spreadsheet = None
        self.worksheet = None
        self.df = None
        self.graph_result = None
        self.logs: list = []
        self.initial_state: Optional[dict] = None
        # Cancel 복구용 ko_review 캐시 (초기 phase 완료 후 저장)
        self.cached_ko_review_results: list = []
        self.cached_ko_tokens: tuple = (0, 0, 0, 0)
        self.initial_started = False
        self.finalizing = False
        self.final_response: Optional[dict] = None
        self.pending_updates: Optional[list] = None
        self.final_plan: Optional[dict] = None
        # SSE event queue (lazy init — async 컨텍스트에서 생성)
        self.event_queue: Optional[asyncio.Queue] = None
        # Lock for thread-safe operations
        self.lock = threading.Lock()
        # Event loop reference (set when SSE stream starts)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # SSE generation counter — 이전 SSE 연결 무효화용
        self._sse_generation: int = 0
        self.sheet_url = ""
        self.job = None
        self.persist = lambda: None
        self.publish = None
        self.is_current = lambda: True

    def reset_graph(self):
        """호출자가 lock을 잡은 상태에서 이전 실행을 무효화한다."""
        self.graph, self.checkpointer = build_graph(self._shared_checkpointer)
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self.graph_result = None
        self.initial_started = False
        self.pending_updates = None
        self.final_plan = None
        self.job = None


class SessionManager:
    """세션 풀 관리 (최대 10개, LRU 방식)"""

    MAX_SESSIONS = 10

    def __init__(self):
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def create(self) -> Session:
        scope = session_scope.get()
        if scope is not None:
            return scope.create()
        with self._lock:
            if len(self._sessions) >= self.MAX_SESSIONS:
                evicted_id = next((sid for sid, s in self._sessions.items()
                                   if s.current_step in {"idle", "done"}), None)
                if evicted_id is None:
                    raise ValueError("진행 중인 세션이 가득 찼습니다. 기존 작업을 먼저 완료해 주세요.")
                self._sessions.pop(evicted_id)
            session = Session()
            self._sessions[session.id] = session
        logger.info("Session created: %s (total: %d)", session.id, len(self._sessions))
        return session

    def get(self, session_id: str) -> Optional[Session]:
        scope = session_scope.get()
        if scope is not None:
            return scope.session if scope.session and scope.session.id == session_id else None
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                self._sessions.move_to_end(session_id)
        return session

    def delete(self, session_id: str):
        scope = session_scope.get()
        if scope is not None:
            scope.session = None
            return
        with self._lock:
            removed = self._sessions.pop(session_id, None)
        if removed:
            logger.info("Session deleted: %s", session_id)


# Singleton
session_manager = SessionManager()
