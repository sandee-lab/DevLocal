"""Grok 실제 호출로 리뷰 수정사항 검증. 시트·백업 저장은 mock으로 대체한다."""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import litellm
import pandas as pd

from agents.graph import ko_review_node
from backend.api import routes
from backend.api.schemas import ApprovalRequest
from backend.api.session_manager import Session
from config.constants import LLM_MODEL, LLM_REASONING_EFFORT, SUPPORTED_LANGUAGES, TOOL_STATUS_COLUMN
from utils.cost import build_cost_summary
from utils.llm import _extract_usage
from utils.validation import validate_tags, check_hangul_residue

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "live-review-validation.json"
calls = []
checks = []
result = {"model": LLM_MODEL, "effort": LLM_REASONING_EFFORT, "calls": calls, "checks": checks}
completion = litellm.completion


def observed_completion(**kwargs):
    if len(calls) >= 20:
        raise RuntimeError("검증용 호출 상한 20회 도달")
    assert kwargs["model"] == LLM_MODEL
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["timeout"] == 120
    call = {"number": len(calls) + 1, "ok": False}
    calls.append(call)
    print(f"실제 Grok 호출 {call['number']} 시작", flush=True)
    started = time.perf_counter()
    try:
        response = completion(**kwargs)
        call.update(ok=True, returned_model=response.model, usage=_extract_usage(response))
        return response
    except Exception as error:
        call["error_type"] = type(error).__name__
        raise
    finally:
        call["seconds"] = round(time.perf_counter() - started, 2)
        print(f"실제 Grok 호출 {call['number']}: {'성공' if call['ok'] else '실패'} ({call['seconds']}초)", flush=True)


def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})
    print(f"{'통과' if passed else '실패'}: {name}", flush=True)
    if not passed:
        raise AssertionError(name)


def main():
    samples = [
        ("duplicate", "체력이 {hp}만큼 회복 됨니다."),
        ("duplicate", "마나가 {mp}만큼 회복 됨니다."),
        ("newline", r"보상을 받으세요.\n다음 모험을 시작하세요."),
        ("tab", r"이름\t점수"),
        ("color", "<color=#FFD700>전설</color> 장비를 획득했습니다."),
        ("bold", "<b>주의</b>: 이 행동은 되돌릴 수 없습니다."),
        ("printf", "%d번째 도전: %s"),
        ("grade", "신화"),
        ("number", "다음 레벨까지 {exp}/{max}"),
        ("unchanged", "서버 점검 중입니다."),
    ]
    rows = [
        {"Key": key, "Korean(ko)": ko, "Shared Comments": "게임 UI 테스트 문구",
         "_row_index": i, TOOL_STATUS_COLUMN: "", **{column: "" for column in SUPPORTED_LANGUAGES.values()}}
        for i, (key, ko) in enumerate(samples)
    ]
    chunk = [{**rows[i % len(rows)], "_row_index": i,
              "Key": rows[i]["Key"] if i < len(rows) else f"sample_{i}"} for i in range(50)]
    session = Session()
    config = {"configurable": {"thread_id": session.thread_id}}
    print("1단계: 실제 한국어 검수 50행", flush=True)
    ko_state = ko_review_node({"original_data": chunk, "target_languages": list(SUPPORTED_LANGUAGES)}, config)
    ko_results = ko_state["ko_review_results"]
    result["ko_50_results"] = ko_results
    result["ko_50_logs"] = ko_state["logs"]
    check("한국어 50행 모두 반환", len(ko_results) == 50)
    check("한국어 50행 응답 누락·호출 오류 없음", not any("응답 누락" in line or "오류 (청크" in line for line in ko_state["logs"]))
    check("중복 Key 한국어 원문 매핑 보존", all(r["original"] == chunk[r["row_index"]]["Korean(ko)"] for r in ko_results))
    check("한국어 교정 태그 보존", all(validate_tags(r["original"], r["revised"])["valid"] for r in ko_results))
    actual_ko = [r for r in ko_results if r["row_index"] < len(rows)]
    issues = [r for r in actual_ko if r["has_issue"]]
    check("실제 교정 제안 생성", bool(issues))
    rejected_ko = issues[0]["row_index"]

    session.initial_state = {
        "sheet_name": "실제 호출 검증", "original_data": rows, "backup_data": rows,
        "target_languages": list(SUPPORTED_LANGUAGES), "ko_review_results": actual_ko,
        "_ko_review_cached": True, "logs": [],
    }
    session.df = pd.DataFrame(rows).drop(columns="_row_index")
    session.df.index = range(7, 7 + len(rows))
    session.worksheet = MagicMock()
    with patch.object(routes.session_manager, "get", return_value=session), \
         patch.object(routes, "save_backup_to_folder"), \
         patch.object(routes, "_load_config", return_value={}):
        routes._run_initial_phase(session)
        check("한국어 승인 대기 도달", session.current_step == "ko_review")
        with patch.object(routes.executor, "submit") as submit:
            asyncio.run(routes.api_approve_ko(session.id, ApprovalRequest(
                decision="approved", decisions={f"ri_{rejected_ko}": "rejected"},
            )))
        function, *args = submit.call_args.args
        print("2단계: 실제 4개 언어 번역·검수", flush=True)
        function(*args)
        check("최종 승인 대기 도달", session.current_step == "final_review")
        state = session.graph_result
        reviews = state.get("review_results", [])
        result["reviews"] = reviews
        result["failed_rows"] = state.get("failed_rows", [])
        result["pipeline_logs"] = state.get("logs", [])
        check("4개 언어 × 10행 = 40건 검수 결과", len(reviews) == 40)
        check("번역 실패 0건", not state.get("failed_rows"))
        check("행·언어 조합 중복/누락 없음", len({(r["row_index"], r["lang"]) for r in reviews}) == 40)
        check("거부한 한국어 교정은 원문으로 번역·검수", all(
            r["original_ko"] == rows[rejected_ko]["Korean(ko)"] for r in reviews if r["row_index"] == rejected_ko))
        check("번역 태그 및 한글 잔존 검사", all(
            validate_tags(r["original_ko"], r["translated"])["valid"] and
            check_hangul_residue(r["original_ko"], r["translated"])["valid"] for r in reviews))
        check("실제 개행·탭이 리터럴로 복원됨", all("\n" not in r["translated"] and "\t" not in r["translated"] for r in reviews))
        check("AI 검수 응답 누락·호출 오류 없음", not any(
            "AI 검수 응답 누락" in r["reason"] for r in reviews))
        approval = routes.api_approve_final(session.id, ApprovalRequest(
            decision="approved", decisions={"0_en": "rejected"},
        ))
        cells = session.worksheet.update_cells.call_args.args[0]
        result["prepared_cells"] = [{"row": c.row, "column": c.col, "value": c.value} for c in cells]
        en_column = list(session.df.columns).index(SUPPORTED_LANGUAGES["en"]) + 1
        check("거부한 영어 셀은 쓰기 목록에서 제외", not any(c.row == 9 and c.col == en_column for c in cells))
        check("선택 범위 원래 행 9~18에만 쓰기", all(9 <= c.row <= 18 for c in cells))
        check("최종 완료 및 중복 승인 재사용", routes.api_approve_final(session.id, ApprovalRequest(decision="approved")) == approval)
        check("Batch 시트 쓰기 1회만 준비", session.worksheet.update_cells.call_count == 1)


if __name__ == "__main__":
    started = time.perf_counter()
    try:
        with patch.object(litellm, "completion", side_effect=observed_completion):
            main()
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["error_type"] = type(error).__name__
        print(f"검증 실패: {type(error).__name__}", flush=True)
    finally:
        usage = {key: sum(c.get("usage", {}).get(key, 0) for c in calls)
                 for key in ("input", "output", "reasoning", "cached")}
        result["cost"] = build_cost_summary(usage["input"], usage["output"], usage["reasoning"], usage["cached"])
        result["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"passed": result["passed"], "calls": len(calls), "seconds": result["elapsed_seconds"], "cost": result["cost"]}, ensure_ascii=False), flush=True)
    sys.exit(0 if result["passed"] else 1)
