"""공유 설정·세션·SSE 저장소. 연결 실패 시 로컬 저장소로 폴백하지 않는다."""

import hashlib
from collections import defaultdict
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver


class StaleSession(RuntimeError):
    pass


class PostgresStorage:
    def __init__(self, url):
        self.pool = ConnectionPool(
            url, min_size=1, max_size=16, timeout=10, open=True,
            kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 10},
        )
        try:
            self.pool.wait(timeout=15)
        except Exception:
            self.pool.close()
            raise
        self.checkpointer = PostgresSaver(self.pool)

    def setup(self):
        # 여러 인스턴스의 최초 마이그레이션을 직렬화한다.
        with self.guard("schema", blocking=True):
            with self.pool.connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS devlocal_sessions (
                    id text PRIMARY KEY, revision bigint NOT NULL DEFAULT 1,
                    payload jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())""")
                conn.execute("""CREATE TABLE IF NOT EXISTS devlocal_events (
                    id bigserial PRIMARY KEY, session_id text NOT NULL
                    REFERENCES devlocal_sessions(id) ON DELETE CASCADE,
                    thread_id text NOT NULL, kind text NOT NULL, data jsonb NOT NULL)""")
                conn.execute("""CREATE INDEX IF NOT EXISTS devlocal_events_session
                    ON devlocal_events(session_id, id)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS devlocal_config (
                    id integer PRIMARY KEY CHECK (id = 1), payload jsonb NOT NULL)""")
            self.checkpointer.setup()

    @contextmanager
    def guard(self, name, blocking=False):
        key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big", signed=True)
        with self.pool.connection() as conn:
            fn = "pg_advisory_lock" if blocking else "pg_try_advisory_lock"
            acquired = conn.execute(f"SELECT {fn}(%s) AS acquired", (key,)).fetchone()["acquired"]
            acquired = blocking or acquired
            try:
                yield acquired
            finally:
                if acquired:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))

    def load(self, sid):
        with self.pool.connection() as conn:
            return conn.execute("SELECT revision, payload FROM devlocal_sessions WHERE id=%s", (sid,)).fetchone()

    def fork_checkpoint(self, source, destination):
        """실행 인계 때 체크포인트를 분리해 이전 프로세스의 늦은 쓰기를 격리한다."""
        saved = self.checkpointer.get_tuple({"configurable": {"thread_id": source}})
        if saved is None:
            return
        config = self.checkpointer.put(
            {"configurable": {"thread_id": destination, "checkpoint_ns": ""}},
            saved.checkpoint, saved.metadata, saved.checkpoint["channel_versions"],
        )
        writes = defaultdict(list)
        for task_id, channel, value in saved.pending_writes or []:
            writes[task_id].append((channel, value))
        for task_id, values in writes.items():
            self.checkpointer.put_writes(config, values, task_id)

    def save(self, payload, revision, event=None):
        with self.pool.connection() as conn, conn.transaction():
            if revision is None:
                row = conn.execute("""INSERT INTO devlocal_sessions(id, payload) VALUES (%s,%s)
                    RETURNING revision""", (payload["id"], Jsonb(payload))).fetchone()
            else:
                row = conn.execute("""UPDATE devlocal_sessions SET payload=%s,
                    revision=revision+1, updated_at=now() WHERE id=%s AND revision=%s
                    RETURNING revision""", (Jsonb(payload), payload["id"], revision)).fetchone()
            if row is None:
                raise StaleSession("다른 요청이 세션을 변경했습니다")
            if event:
                self._event(conn, payload["id"], payload["thread_id"], *event)
            return row["revision"]

    def _event(self, conn, sid, thread_id, kind, data):
        conn.execute("""INSERT INTO devlocal_events(session_id, thread_id, kind, data)
            SELECT id, %s, %s, %s FROM devlocal_sessions
            WHERE id=%s AND payload->>'thread_id'=%s""",
                     (thread_id, kind, Jsonb(data), sid, thread_id))

    def publish(self, sid, thread_id, kind, data):
        with self.pool.connection() as conn:
            self._event(conn, sid, thread_id, kind, data)

    def events(self, sid, after=0):
        with self.pool.connection() as conn:
            return conn.execute("""SELECT e.* FROM devlocal_events e
                JOIN devlocal_sessions s ON s.id=e.session_id
                WHERE e.session_id=%s AND e.id>%s AND e.thread_id=s.payload->>'thread_id'
                ORDER BY e.id LIMIT 200""", (sid, after)).fetchall()

    def cursor(self, sid):
        with self.pool.connection() as conn:
            return conn.execute("SELECT coalesce(max(id),0) AS id FROM devlocal_events WHERE session_id=%s", (sid,)).fetchone()["id"]

    def jobs(self):
        with self.pool.connection() as conn:
            return [r["id"] for r in conn.execute("""SELECT id FROM devlocal_sessions
                WHERE payload->'job' != 'null'::jsonb ORDER BY updated_at LIMIT 100""")]

    def load_config(self):
        with self.pool.connection() as conn:
            row = conn.execute("SELECT payload FROM devlocal_config WHERE id=1").fetchone()
            return row["payload"] if row else {}

    def save_config(self, data):
        with self.pool.connection() as conn:
            conn.execute("""INSERT INTO devlocal_config(id,payload) VALUES(1,%s)
                ON CONFLICT(id) DO UPDATE SET payload=devlocal_config.payload || excluded.payload""", (Jsonb(data),))

    def close(self):
        self.pool.close()
