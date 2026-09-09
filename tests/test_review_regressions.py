"""전체 리뷰에서 발견한 데이터 손상·상태 전환 오류의 회귀 검증."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from agents.nodes.reviewer import reviewer_node
from agents.nodes.translator import translator_node
from agents.nodes.writer import writer_node
from backend.api import routes
from backend.api.schemas import ApprovalRequest, StartRequest
from backend.api.session_manager import Session
from config.constants import REQUIRED_COLUMNS, SUPPORTED_LANGUAGES, Status, TOOL_STATUS_COLUMN
from utils.diff_report import generate_ko_diff_report, generate_translation_diff_report
from utils.sheets import batch_format_cells, batch_update_sheet
from config import app_config
from backend.api.session_manager import SessionManager

KO = REQUIRED_COLUMNS["korean"]
EN = SUPPORTED_LANGUAGES["en"]


class RowRegressionTests(unittest.TestCase):
    def test_selected_range_writes_and_formats_original_sheet_row(self):
        df = pd.DataFrame([{EN: "old"}] * 5).iloc[3:5]
        ws = MagicMock()
        updates = [{"row_index": 0, "column_name": EN, "value": "new", "change_type": "translation"}]
        batch_update_sheet(ws, updates, df)
        batch_format_cells(ws, updates, df)
        self.assertEqual(ws.update_cells.call_args.args[0][0].row, 5)
        request = ws.spreadsheet.batch_update.call_args.args[0]["requests"][0]
        self.assertEqual(request["repeatCell"]["range"]["startRowIndex"], 4)

    def test_ko_report_preserves_duplicate_keys(self):
        original = [{"Key": "same", KO: "첫째"}, {"Key": "same", KO: "둘째"}]
        report, _ = generate_ko_diff_report(original, original)
        self.assertTrue(report.empty)

    def test_translation_report_preserves_duplicate_keys(self):
        old = [{"Key": "same", "lang": "en", "old": "first"}, {"Key": "same", "lang": "en", "old": "second"}]
        new = [{"Key": "same", "lang": "en", "new": "one"}, {"Key": "same", "lang": "en", "new": "two"}]
        report, _ = generate_translation_diff_report(old, new)
        self.assertEqual(report["기존 번역"].tolist(), ["first", "second"])

    def test_writer_deduplicates_failures_and_skips_unchanged_status(self):
        state = {
            "original_data": [{EN: "same", TOOL_STATUS_COLUMN: Status.COMPLETED}, {EN: "", TOOL_STATUS_COLUMN: ""}],
            "review_results": [{"key": "ok", "lang": "en", "translated": "same", "row_index": 0}],
            "failed_rows": [{"row_index": 1, "lang": "en"}, {"row_index": 1, "lang": "ja"}],
        }
        updates = writer_node(state)["_updates"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["value"], Status.REVIEW_FAILED)

    def test_writer_rejects_negative_row_indices(self):
        result = writer_node({
            "original_data": [{EN: "original"}],
            "review_results": [{"key": "bad", "lang": "en", "translated": "wrong", "row_index": -1}],
            "failed_rows": [{"row_index": 9}],
        })
        self.assertEqual(result["_updates"], [])

    def test_approved_korean_corrections_do_not_cross_duplicate_keys(self):
        captured = []

        def fake_call(**kwargs):
            captured.extend(r[KO] for r in kwargs["items"])
            return [], kwargs["items"], {"input": 0, "output": 0, "reasoning": 0, "cached": 0}

        state = {
            "original_data": [{"Key": "same", KO: "첫째", "_row_index": 0}, {"Key": "same", KO: "둘째", "_row_index": 1}],
            "ko_review_results": [{"key": "same", "revised": "첫째 수정", "row_index": 0}],
            "ko_approval_result": "approved", "target_languages": ["en"],
        }
        with patch("agents.nodes.translator.llm_chunk_with_completeness", side_effect=fake_call):
            translator_node(state, {})
        self.assertEqual(captured, ["첫째 수정", "둘째"])

    def test_duplicate_keys_have_independent_retry_budgets(self):
        state = {
            "original_data": [{"Key": "same", KO: "{tag} 안녕", "_row_index": i} for i in range(4)],
            "translation_results": [{"key": "same", "lang": "en", "translated": "Hi", "row_index": i} for i in range(4)],
        }
        result = reviewer_node(state, {})
        self.assertEqual(len(result["_needs_retry"]), 4)
        self.assertEqual(result["failed_rows"], [])

    def test_empty_translation_is_not_silently_dropped(self):
        result = reviewer_node({
            "original_data": [{"Key": "a", KO: "안녕", "_row_index": 0}],
            "translation_results": [{"key": "a", "lang": "en", "translated": "", "row_index": 0}],
        }, {})
        self.assertEqual(len(result["failed_rows"]), 1)

    def test_cancelled_chunk_never_calls_llm(self):
        from concurrent.futures import CancelledError
        state = {"original_data": [{"Key": "a", KO: "안녕", "_row_index": 0}], "target_languages": ["en"]}
        with patch("agents.nodes.translator.llm_chunk_with_completeness") as call:
            with self.assertRaises(CancelledError):
                translator_node(state, {"configurable": {"is_cancelled": lambda: True}})
            call.assert_not_called()


class SessionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.lookup = patch.object(routes.session_manager, "get", return_value=self.session)
        self.lookup.start()
        self.addCleanup(self.lookup.stop)

    def test_reconnecting_sse_starts_initial_phase_once(self):
        async def check():
            self.session.current_step = "loading"
            with patch.object(routes.executor, "submit") as submit:
                await routes.api_stream(self.session.id)
                await routes.api_stream(self.session.id)
                self.assertEqual(submit.call_count, 1)
        asyncio.run(check())

    def test_sse_reconnect_wakes_old_consumer_without_stealing_events(self):
        async def check():
            self.session.current_step = "ko_review"
            response = await routes.api_stream(self.session.id)
            previous_queue = self.session.event_queue
            await routes.api_stream(self.session.id)
            self.assertIsNot(previous_queue, self.session.event_queue)
            self.assertEqual(previous_queue.get_nowait()[0], "_sse_close")
            with self.assertRaises(StopAsyncIteration):
                await anext(response.body_iterator)
        asyncio.run(check())

    def test_stale_worker_cannot_emit_into_new_graph(self):
        async def check():
            self.session._loop = asyncio.get_running_loop()
            self.session.event_queue = asyncio.Queue()
            emit = routes._make_emitter(self.session)
            self.session.graph = MagicMock()
            emit("log_line", {"text": "폐기된 작업"})
            await asyncio.sleep(0.01)
            self.assertEqual(self.session.logs, [])
            self.assertTrue(self.session.event_queue.empty())
        asyncio.run(check())

    def test_session_pool_never_evicts_active_work(self):
        manager = SessionManager()
        manager.MAX_SESSIONS = 1
        session = manager.create()
        session.current_step = "translating"
        with self.assertRaises(ValueError):
            manager.create()
        self.assertIs(manager.get(session.id), session)


    def test_translation_error_returns_session_to_idle(self):
        self.session.current_step = "translating"
        self.session.graph = MagicMock()
        self.session.graph.stream.side_effect = RuntimeError("모의 실패")
        routes._run_translation_phase(self.session, "approved")
        self.assertEqual(self.session.current_step, "idle")

    def test_duplicate_approval_is_rejected(self):
        async def check():
            self.session.current_step = "translating"
            with patch.object(routes.executor, "submit") as submit:
                with self.assertRaises(routes.HTTPException) as error:
                    await routes.api_approve_ko(self.session.id, ApprovalRequest(decision="approved"))
                self.assertEqual(error.exception.status_code, 409)
                submit.assert_not_called()
        asyncio.run(check())


class GraphIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        rows = [{"Key": "same", KO: text, EN: "", "_row_index": i}
                for i, text in enumerate(["첫째", "둘째"])]
        self.session.initial_state = {
            "original_data": rows, "backup_data": rows,
            "target_languages": ["en"], "sheet_name": "테스트",
        }
        self.session.df = pd.DataFrame(rows).drop(columns="_row_index")
        self.session.worksheet = MagicMock()
        self.ko_changed = True
        self.ko_sources = []

        def fake_ko(**kwargs):
            return [(r, {"key": r["key"], "original": r[KO],
                         "revised": r[KO] + (" 수정" if self.ko_changed else ""),
                         "changes": "교정"}) for r in kwargs["items"]], [], self.usage()

        def fake_translate(**kwargs):
            self.ko_sources.extend(r[KO] for r in kwargs["items"])
            return [(r, {"translated": f"English {r['_row_index']}"}) for r in kwargs["items"]], [], self.usage()

        def fake_review(**kwargs):
            return [(r, {"reason": "정상", "issues": []}) for r in kwargs["items"]], [], self.usage()

        for patcher in [
            patch.object(routes.session_manager, "get", return_value=self.session),
            patch("agents.graph.llm_chunk_with_completeness", side_effect=fake_ko),
            patch("agents.nodes.translator.llm_chunk_with_completeness", side_effect=fake_translate),
            patch("agents.nodes.reviewer.llm_chunk_with_completeness", side_effect=fake_review),
            patch.object(routes, "save_backup_to_folder"),
            patch.object(routes, "_load_config", return_value={}),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def usage():
        return {"input": 10, "output": 5, "reasoning": 1, "cached": 2}

    def approve_ko(self, decisions=None):
        with patch.object(routes.executor, "submit") as submit:
            asyncio.run(routes.api_approve_ko(
                self.session.id, ApprovalRequest(decision="approved", decisions=decisions or {}),
            ))
        function, *args = submit.call_args.args
        function(*args)

    def test_individual_rejections_reach_translation_and_sheet_write(self):
        routes._run_initial_phase(self.session)
        self.assertEqual(self.session.current_step, "ko_review")
        self.approve_ko({"ri_1": "rejected"})
        self.assertEqual(self.ko_sources, ["첫째 수정", "둘째"])
        self.assertEqual(self.session.current_step, "final_review")
        response = routes.api_approve_final(self.session.id, ApprovalRequest(
            decision="approved", decisions={"0_en": "rejected"},
        ))
        cells = self.session.worksheet.update_cells.call_args.args[0]
        self.assertEqual([(cell.row, cell.value) for cell in cells], [(3, "English 1")])
        self.assertTrue(response["translations_applied"])
        self.assertEqual(self.session.current_step, "done")

    def test_zero_korean_suggestions_auto_approve_once(self):
        self.ko_changed = False
        routes._run_initial_phase(self.session)
        self.assertEqual(self.session.current_step, "final_review")
        self.assertEqual(self.ko_sources, ["첫째", "둘째"])

    def test_cancel_restores_cached_review_without_new_llm_call(self):
        routes._run_initial_phase(self.session)
        self.approve_ko()
        old_graph = self.session.graph
        with patch("agents.graph.llm_chunk_with_completeness") as llm:
            result = asyncio.run(routes.api_cancel(self.session.id))
            llm.assert_not_called()
        self.assertEqual(result["status"], "ko_review")
        self.assertIsNot(old_graph, self.session.graph)
        self.assertEqual(len(routes.api_state(self.session.id).ko_review_results), 2)

    def test_failed_sheet_write_can_retry_without_resuming_finished_graph(self):
        self.ko_changed = False
        routes._run_initial_phase(self.session)
        request = ApprovalRequest(decision="approved")
        with patch.object(routes, "batch_update_sheet", side_effect=[RuntimeError("모의 저장 실패"), None]) as write:
            with self.assertRaises(routes.HTTPException):
                routes.api_approve_final(self.session.id, request)
            self.assertEqual(self.session.current_step, "final_review")
            with patch.object(self.session.graph, "invoke") as invoke:
                response = routes.api_approve_final(self.session.id, request)
                invoke.assert_not_called()
            self.assertEqual(write.call_count, 2)
            self.assertEqual(response["status"], "done")
            self.assertEqual(routes.api_approve_final(self.session.id, request), response)
            self.assertEqual(write.call_count, 2)

    def test_reject_all_never_writes_sheet(self):
        self.ko_changed = False
        routes._run_initial_phase(self.session)
        result = routes.api_approve_final(self.session.id, ApprovalRequest(decision="rejected"))
        self.session.worksheet.update_cells.assert_not_called()
        self.assertFalse(result["translations_applied"])


class ConfigAndValidationTests(unittest.TestCase):
    def test_start_without_end_preserves_selected_range(self):
        session = Session()
        df = pd.DataFrame([{"Key": str(i), KO: "문장", "Shared Comments": "", EN: "", TOOL_STATUS_COLUMN: ""} for i in range(5)])
        with patch.object(routes.session_manager, "create", return_value=session), \
             patch.object(routes, "connect_to_sheet", return_value=MagicMock()), \
             patch.object(routes, "load_sheet_data", return_value=df), \
             patch.object(routes, "_load_config", return_value={}):
            routes.api_start(StartRequest(sheet_url="mock", sheet_name="test", row_start=4))
        self.assertEqual(session.df.index.tolist(), [3, 4])
        self.assertEqual([r["_row_index"] for r in session.initial_state["original_data"]], [0, 1])

    def test_forbidden_sheet_is_rejected_before_connecting(self):
        with patch.object(routes, "connect_to_sheet") as connect:
            with self.assertRaises(routes.HTTPException):
                routes.api_start(StartRequest(sheet_url="mock", sheet_name="수정금지_Common"))
            connect.assert_not_called()

    def test_static_files_cannot_escape_build_directory(self):
        from backend.main import app, serve_spa
        from fastapi.testclient import TestClient
        for path in ["../package.json", "../../config/constants.py", "api/unknown"]:
            with self.assertRaises(routes.HTTPException):
                asyncio.run(serve_spa(path))
        with patch("backend.main.validate_environment") as validate:
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/unknown").status_code, 404)
            validate.assert_called_once()

    def test_config_merge_and_invalid_root(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with patch.object(app_config, "_CONFIG_PATH", path):
                path.write_text("[]", encoding="utf-8")
                self.assertEqual(app_config.load_config(), {})
                app_config.save_config({"saved_url": "test"})
                app_config.save_config({"game_synopsis": "새 설정"})
                self.assertEqual(app_config.load_config(), {"saved_url": "test", "game_synopsis": "새 설정"})

    def test_failed_config_replace_preserves_original(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            with patch.object(app_config, "_CONFIG_PATH", path):
                app_config.save_config({"value": "original"})
                with patch.object(app_config.os, "replace", side_effect=OSError("모의 실패")):
                    with self.assertRaises(OSError):
                        app_config.save_config({"value": "new"})
                self.assertEqual(app_config.load_config(), {"value": "original"})
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_approval_and_range_are_rejected(self):
        with self.assertRaises(ValueError):
            ApprovalRequest(decision="anything")
        for start, end in [(-1, 0), (5, 2)]:
            with self.assertRaises(ValueError):
                StartRequest(sheet_url="test", sheet_name="test", row_start=start, row_end=end)



if __name__ == "__main__":
    unittest.main()
