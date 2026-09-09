"""TEST_DATABASE_URL의 서버에 임시 DB를 만들어 실제 PostgreSQL 복구를 검증한다."""

import os
import json
import subprocess
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from backend import persistence
from backend.api import routes
from backend.persistence import Runtime, Scope
from config.constants import REQUIRED_COLUMNS, SUPPORTED_LANGUAGES, TOOL_STATUS_COLUMN

KO = REQUIRED_COLUMNS["korean"]
EN = SUPPORTED_LANGUAGES["en"]


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "격리된 PostgreSQL 테스트 서버 설정이 필요합니다")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from backend.storage import PostgresStorage
        cls.admin = psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True)
        cls.database = "devlocal_test_" + uuid.uuid4().hex
        cls.admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database)))
        cls.url = make_conninfo(os.environ["TEST_DATABASE_URL"], dbname=cls.database)
        cls.a, cls.b = PostgresStorage(cls.url), PostgresStorage(cls.url)
        cls.a.setup()
        cls.b.setup()

    @classmethod
    def tearDownClass(cls):
        from psycopg import sql
        cls.a.close()
        cls.b.close()
        cls.admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.database)))
        cls.admin.close()

    def setUp(self):
        self.runtime_a, self.runtime_b = Runtime(self.a), Runtime(self.b)
        self.addCleanup(self.runtime_a.executor.shutdown)
        self.addCleanup(self.runtime_b.executor.shutdown)
        self.changed = True
        self.usage = {"input": 1, "output": 1, "reasoning": 0, "cached": 0}
        self.ko_calls = 0
        self.translation_calls = 0

        def ko(**kwargs):
            self.ko_calls += 1
            return [(r, {"revised": r[KO] + (" 수정" if self.changed else ""), "changes": "교정"}) for r in kwargs["items"]], [], self.usage

        def translate(**kwargs):
            self.translation_calls += 1
            return [(r, {"translated": f"English {r['_row_index']}"}) for r in kwargs["items"]], [], self.usage

        def review(**kwargs):
            return [(r, {"reason": "정상", "issues": []}) for r in kwargs["items"]], [], self.usage

        self.sheet = MagicMock()
        self.sheet.worksheet.return_value = self.sheet
        for patcher in [
            patch.dict(os.environ, {"AUTH_MODE": "local"}),
            patch.object(persistence, "runtime", self.runtime_a),
            patch("agents.graph.llm_chunk_with_completeness", side_effect=ko),
            patch("agents.nodes.translator.llm_chunk_with_completeness", side_effect=translate),
            patch("agents.nodes.reviewer.llm_chunk_with_completeness", side_effect=review),
            patch.object(routes, "connect_to_sheet", return_value=self.sheet),
            patch.object(routes, "save_backup_to_folder"),
            patch.object(routes, "_load_config", return_value={}),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        from backend.main import app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def create(self):
        scope = Scope(self.a)
        session = scope.create()
        rows = [{"Key": "same", KO: text, EN: "", "_row_index": i} for i, text in enumerate(["첫째", "둘째"])]
        session.initial_state = {"original_data": rows, "backup_data": rows, "target_languages": ["en"], "sheet_name": "테스트"}
        session.df = pd.DataFrame(rows, index=[7, 8]).drop(columns="_row_index")
        session.sheet_url = "https://example.test/synthetic"
        session.backup_csv = b"synthetic backup"
        session.current_step = "loading"
        session.job = {"phase": "initial"}
        scope.save()
        return session.id

    def final_review(self):
        self.changed = False
        sid = self.create()
        self.runtime_a.run_job(sid)
        self.assertEqual(Scope(self.b, sid).session.current_step, "final_review")
        return sid

    def test_other_server_restores_dataframe_checkpoints_and_individual_approval(self):
        sid = self.create()
        self.runtime_a.run_job(sid)
        recovered = Scope(self.b, sid).session
        self.assertEqual(recovered.df.index.tolist(), [7, 8])
        self.assertEqual(recovered.backup_csv, b"synthetic backup")
        self.assertEqual(recovered.graph.get_state(recovered.config).next, ("ko_approval",))
        persistence.runtime = self.runtime_b
        response = self.client.post(f"/api/approve-ko/{sid}", json={"decision": "approved", "decisions": {"ri_1": "rejected"}})
        self.assertEqual(response.status_code, 200, response.text)
        self.runtime_a.run_job(sid)
        response = self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved", "decisions": {"0_en": "rejected"}})
        self.assertEqual(response.status_code, 200, response.text)
        cells = self.sheet.update_cells.call_args.args[0]
        self.assertEqual([(c.row, c.value) for c in cells], [(10, "English 1")])
        persistence.runtime = self.runtime_a
        self.assertEqual(self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved"}).json(), response.json())
        self.assertEqual(self.sheet.update_cells.call_count, 1)
        self.assertIn("event: done", self.client.get(f"/api/stream/{sid}").text)

    def test_crash_after_korean_checkpoint_does_not_repeat_llm(self):
        sid = self.create()
        session = Scope(self.a, sid).session
        list(session.graph.stream(session.initial_state, session.config))
        self.assertEqual(self.ko_calls, 1)
        self.runtime_b.run_job(sid)
        self.assertEqual(self.ko_calls, 1)
        self.assertEqual(Scope(self.a, sid).session.current_step, "ko_review")

    def test_crash_after_translation_checkpoint_restores_final_review(self):
        sid = self.create()
        self.runtime_a.run_job(sid)
        self.assertEqual(self.client.post(f"/api/approve-ko/{sid}", json={"decision": "approved"}).status_code, 200)
        abandoned = Scope(self.a, sid).session
        abandoned.publish = lambda *_: None
        routes._run_translation_phase(abandoned, "approved")
        before = self.translation_calls
        self.runtime_b.run_job(sid)
        self.assertEqual(self.translation_calls, before)
        self.assertEqual(Scope(self.b, sid).session.current_step, "final_review")

    def test_cancel_fences_old_worker_and_events(self):
        from backend.storage import StaleSession
        sid = self.final_review()
        old = Scope(self.a, sid)
        persistence.runtime = self.runtime_b
        self.assertEqual(self.client.post(f"/api/cancel/{sid}").status_code, 200)
        self.assertFalse(old.is_current())
        old.publish("translation_chunk", {"stale": True})
        with self.assertRaises(StaleSession):
            old.save()
        self.assertFalse(any(row["data"].get("stale") for row in self.b.events(sid)))
        self.assertEqual(Scope(self.a, sid).session.current_step, "ko_review")

    def test_sheet_retry_after_new_server_uses_persisted_updates(self):
        sid = self.final_review()
        with patch.object(routes, "batch_update_sheet", side_effect=RuntimeError("테스트 저장 실패")):
            response = self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved", "decisions": {"0_en": "rejected"}})
            self.assertEqual(response.status_code, 500)
        recovered = Scope(self.b, sid).session
        self.assertIsNotNone(recovered.pending_updates)
        persistence.runtime = self.runtime_b
        response = self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([(c.row, c.value) for c in self.sheet.update_cells.call_args.args[0]], [(10, "English 1")])

    def test_cross_server_command_and_worker_locks_are_exclusive(self):
        sid = self.final_review()
        with self.a.guard(f"command:{sid}") as acquired:
            self.assertTrue(acquired)
            persistence.runtime = self.runtime_b
            self.assertEqual(self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved"}).status_code, 409)
        with self.a.guard(f"worker:{sid}"):
            with self.b.guard(f"worker:{sid}") as acquired:
                self.assertFalse(acquired)
        self.sheet.update_cells.assert_not_called()

    def test_shared_config_parallel_merges_keep_both_changes(self):
        key = uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.a.save_config, {key + "a": "first"})
            b = pool.submit(self.b.save_config, {key + "b": "second"})
            a.result()
            b.result()
        config = self.b.load_config()
        self.assertEqual((config[key + "a"], config[key + "b"]), ("first", "second"))

    def test_start_queues_job_before_sse_connection(self):
        df = pd.DataFrame([{"Key": "a", KO: "문장", EN: "", "Shared Comments": "", TOOL_STATUS_COLUMN: ""}])
        with patch.object(routes, "load_sheet_data", return_value=df):
            response = self.client.post("/api/start", json={"sheet_url": "synthetic", "sheet_name": "테스트"})
        self.assertEqual(response.status_code, 200, response.text)
        sid = response.json()["session_id"]
        self.assertIn(sid, self.b.jobs())
        self.runtime_b.run_job(sid)
        self.assertEqual(self.client.get(f"/api/state/{sid}").json()["current_step"], "ko_review")

    def test_fresh_process_restores_approval_checkpoint(self):
        sid = self.create()
        self.runtime_a.run_job(sid)
        code = """
import json, os
from backend.storage import PostgresStorage
from backend.persistence import Scope
store = PostgresStorage(os.environ['TEST_SESSION_DATABASE'])
try:
    session = Scope(store, os.environ['TEST_SESSION_ID']).session
    print(json.dumps({'step': session.current_step, 'next': session.graph.get_state(session.config).next, 'index': session.df.index.tolist()}))
finally:
    store.close()
"""
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", code],
                                env={**os.environ, "TEST_SESSION_DATABASE": self.url, "TEST_SESSION_ID": sid},
                                capture_output=True, text=True, encoding="utf-8", timeout=40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"step": "ko_review", "next": ["ko_approval"], "index": [7, 8]})

    def test_crash_during_cancel_recovers_without_llm(self):
        sid = self.final_review()
        interrupted = Scope(self.a, sid)
        interrupted.session.reset_graph()
        interrupted.session.current_step = "loading"
        interrupted.session.job = {"phase": "cancel"}
        interrupted.save()
        before = self.ko_calls
        self.runtime_b.run_job(sid)
        self.assertEqual(self.ko_calls, before)
        self.assertEqual(Scope(self.b, sid).session.current_step, "ko_review")

    def test_crash_before_pending_updates_save_keeps_original_decision(self):
        from langgraph.types import Command
        sid = self.final_review()
        interrupted = Scope(self.a, sid)
        session = interrupted.session
        session.final_plan = {"decision": "approved", "decisions": {"0_en": "rejected"}}
        interrupted.save()
        accepted = [r for r in session.graph_result["review_results"] if r["row_index"] == 1]
        session.graph.update_state(session.config, {"review_results": accepted})
        session.graph.invoke(Command(resume="approved"), session.config)
        persistence.runtime = self.runtime_b
        response = self.client.post(f"/api/approve-final/{sid}", json={"decision": "approved"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([(c.row, c.value) for c in self.sheet.update_cells.call_args.args[0]], [(10, "English 1")])

    def test_rejection_can_resume_after_process_loss(self):
        sid = self.final_review()
        interrupted = Scope(self.a, sid)
        interrupted.session.final_plan = {"decision": "rejected", "decisions": {}}
        interrupted.save()
        persistence.runtime = self.runtime_b
        response = self.client.post(f"/api/approve-final/{sid}", json={"decision": "rejected"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["translations_applied"])
        self.sheet.update_cells.assert_not_called()
