"""LangGraph 워크플로우 정의 — 6 Node + HITL 2곳 interrupt"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from agents.state import LocalizationState
from agents.prompts import build_ko_proofreader_prompt
from agents.nodes.data_backup import data_backup_node
from agents.nodes.context_glossary import context_glossary_node
from agents.nodes.translator import translator_node
from utils.drip_feed import drip_feed_emit, emit_log_line, emit_log_lines
from utils.llm import llm_chunk_with_completeness, split_warmup_tasks
from agents.nodes.reviewer import reviewer_node
from agents.nodes.writer import writer_node
from backend.config import get_xai_api_key
from config.constants import REQUIRED_COLUMNS, CHUNK_SIZE, LLM_CHUNK_PARALLELISM, SUPPORTED_LANGUAGES, TAG_PATTERNS


# ── 한국어 검수 노드 (AI 분석만, interrupt 없음) ─────────────────────

def ko_review_node(state: LocalizationState, config: RunnableConfig) -> dict:
    """
    한국어 맞춤법/띄어쓰기 검수 — AI 분석만 수행.
    interrupt는 별도 ko_approval_node에서 처리.
    """
    original_data = state.get("original_data", [])
    mode = state.get("mode", "A")
    target_languages = state.get("target_languages", [])
    logs = list(state.get("logs", []))
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)
    total_reasoning_tokens = state.get("total_reasoning_tokens", 0)
    total_cached_tokens = state.get("total_cached_tokens", 0)

    # 청크별 이벤트 emitter (없으면 무시)
    emitter = config.get("configurable", {}).get("event_emitter") if config else None
    # xAI Grok prompt caching 라우팅 키 — 같은 thread_id 요청을 같은 서버로 보내 캐시 prefix 공유
    conv_id = config.get("configurable", {}).get("thread_id") if config else None

    # ── Fast path: Cancel 복귀 시 캐시된 결과 재사용 (LLM 스킵) ──
    existing_results = state.get("ko_review_results", [])
    if existing_results:
        line = f"[한국어 검수] 캐시 결과 사용: {len(existing_results)}행 (스킵)"
        logs.append(line)
        emit_log_line(emitter, line)
        return {
            "ko_review_results": existing_results,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_reasoning_tokens": total_reasoning_tokens,
            "total_cached_tokens": total_cached_tokens,
            "logs": logs,
        }

    api_key = get_xai_api_key()

    # 한국어 원문 수집 — Mode B는 신규 번역 대상(타겟 언어 중 하나라도 빈칸)인 행만
    target_lang_cols = [SUPPORTED_LANGUAGES.get(lg, "") for lg in target_languages]
    target_lang_cols = [c for c in target_lang_cols if c]
    ko_rows = []
    skipped_by_mode_b = 0
    for row in original_data:
        key = row.get(REQUIRED_COLUMNS["key"], "")
        ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
        row_index = row.get("_row_index")
        if not ko_text:
            continue
        if mode == "B" and target_lang_cols:
            needs_translation = any(
                not (row.get(col, "") or "").strip() for col in target_lang_cols
            )
            if not needs_translation:
                skipped_by_mode_b += 1
                continue
        ko_rows.append({"key": key, REQUIRED_COLUMNS["korean"]: ko_text, "_row_index": row_index})

    if skipped_by_mode_b:
        skip_line = f"[한국어 검수] Mode B 스킵: 이미 모든 타겟 언어 채워진 행 {skipped_by_mode_b}건"
        logs.append(skip_line)
        emit_log_line(emitter, skip_line)
    logs.append(f"[한국어 검수] 대상: {len(ko_rows)}행")
    emit_log_line(emitter, f"[한국어 검수] 대상: {len(ko_rows)}행")

    # 청크 단위로 AI 검수 (병렬 실행)
    ko_review_results: list[dict] = []
    system_prompt = build_ko_proofreader_prompt()
    total_ko_rows = len(ko_rows)
    restored_count = 0
    missing_count = 0

    total_ko_chunks = (len(ko_rows) + CHUNK_SIZE - 1) // CHUNK_SIZE

    def _build_ko_prompt(subset: list[dict]) -> str:
        return "\n\n".join(
            f"Key: {r['key']}\nKorean: {r[REQUIRED_COLUMNS['korean']]}"
            for r in subset
        )

    # 작업 평탄화: (chunk_idx, chunk)
    tasks: list[tuple[int, list[dict]]] = []
    for chunk_idx, chunk_start in enumerate(range(0, len(ko_rows), CHUNK_SIZE)):
        tasks.append((chunk_idx, ko_rows[chunk_start:chunk_start + CHUNK_SIZE]))

    lock = threading.Lock()
    cumulative_done = 0

    def _process(chunk_idx: int, chunk: list[dict]):
        if emitter:
            emitter("heartbeat", {
                "node": "ko_review",
                "lang": "ko",
                "chunk": chunk_idx + 1,
                "total_chunks": total_ko_chunks,
                "chunk_size": len(chunk),
            })

        chunk_items_out: list[dict] = []
        local_logs: list[str] = []
        local_restored = 0
        local_missing = 0
        usage = None

        try:
            pairs, missing, usage = llm_chunk_with_completeness(
                system_prompt=system_prompt,
                items=chunk,
                user_prompt_builder=_build_ko_prompt,
                api_key=api_key,
                item_key_fn=lambda r: r["key"],
                timeout=120,
                conv_id=conv_id,
            )

            for src, item in pairs:
                item["comment"] = item.pop("changes", "")
                item["has_issue"] = item.get("original", "") != item.get("revised", "")
                item["row_index"] = src.get("_row_index")

                # 태그 검증 — 손상 시 원본 복원
                if item["has_issue"]:
                    original = src[REQUIRED_COLUMNS["korean"]]
                    revised = item.get("revised", "")
                    if original and revised:
                        tag_broken = False
                        for pattern in TAG_PATTERNS:
                            if sorted(re.findall(pattern, original)) != sorted(re.findall(pattern, revised)):
                                tag_broken = True
                                break
                        if tag_broken:
                            item["revised"] = original
                            item["has_issue"] = False
                            item["comment"] = ""
                            local_restored += 1

                chunk_items_out.append(item)

            # ko_review 프롬프트는 "변경 없는 행은 포함하지 마세요"라고 명시 → missing은 보통 정상 생략.
            # 행별 스팸 로그 대신 청크 요약만 남긴다.
            for src in missing:
                local_missing += 1
                chunk_items_out.append({
                    "key": src["key"],
                    "original": src[REQUIRED_COLUMNS["korean"]],
                    "revised": src[REQUIRED_COLUMNS["korean"]],
                    "comment": "",
                    "has_issue": False,
                    "row_index": src.get("_row_index"),
                })

            suggested = len(chunk_items_out) - local_missing
            local_logs.append(
                f"[한국어 검수] 청크 {chunk_idx + 1}/{total_ko_chunks} 완료 "
                f"— 수정 제안 {suggested}건, 변경 없음 {local_missing}건"
            )
        except Exception as e:
            local_logs.append(f"[한국어 검수] 오류 (청크 {chunk_idx + 1}): {e}")

        return chunk_idx, chunk_items_out, usage, local_logs, local_restored, local_missing

    def _handle_result(result):
        nonlocal total_input_tokens, total_output_tokens, total_reasoning_tokens
        nonlocal total_cached_tokens, restored_count, missing_count, cumulative_done
        _ci, chunk_items_out, usage, local_logs, local_restored, local_missing = result
        if usage:
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]
            total_reasoning_tokens += usage["reasoning"]
            total_cached_tokens += usage["cached"]
        logs.extend(local_logs)
        emit_log_lines(emitter, local_logs)
        restored_count += local_restored
        missing_count += local_missing
        ko_review_results.extend(chunk_items_out)
        if emitter and chunk_items_out:
            drip_feed_emit(
                emitter,
                "ko_review_chunk",
                chunk_items_out,
                progress_base=cumulative_done,
                total=total_ko_rows,
            )
            cumulative_done += len(chunk_items_out)

    if tasks:
        # warm-up: system_prompt가 1개라 첫 task만 sync 실행 → xAI 캐시 prefix 적재
        warmup_tasks, rest_tasks = split_warmup_tasks(tasks, prompt_key=lambda t: 0)
        for t in warmup_tasks:
            _handle_result(_process(*t))
        if rest_tasks:
            with ThreadPoolExecutor(max_workers=LLM_CHUNK_PARALLELISM) as exe:
                futures = [exe.submit(_process, *t) for t in rest_tasks]
                for fut in as_completed(futures):
                    with lock:
                        _handle_result(fut.result())

    if restored_count:
        line = f"[한국어 검수] 태그 손상 수정 {restored_count}건 원본 복원"
        logs.append(line)
        emit_log_line(emitter, line)
    if missing_count:
        line = (
            f"[한국어 검수] 변경 없음 {missing_count}건 "
            f"— LLM이 응답에서 생략 (원본 유지, 정상)"
        )
        logs.append(line)
        emit_log_line(emitter, line)
    final_line = f"[한국어 검수] 최종 수정 제안: {len([r for r in ko_review_results if r.get('has_issue')])}건"
    logs.append(final_line)
    emit_log_line(emitter, final_line)

    return {
        "ko_review_results": ko_review_results,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cached_tokens": total_cached_tokens,
        "logs": logs,
    }


# ── 한국어 검수 승인 노드 (HITL 1 interrupt) ────────────────────────

def ko_approval_node(state: LocalizationState) -> dict:
    """
    한국어 검수 결과를 사용자에게 보여주고 승인 대기 (HITL 1).
    """
    ko_review_results = state.get("ko_review_results", [])
    logs = list(state.get("logs", []))

    # HITL 1 — 사용자 승인 대기
    approval = interrupt({
        "type": "ko_review",
        "results": ko_review_results,
        "count": len(ko_review_results),
    })

    logs.append(f"[한국어 검수] 사용자 결정: {approval}")

    return {
        "ko_approval_result": approval,
        "logs": logs,
    }


# ── 최종 승인 노드 (HITL 2 interrupt 포함) ────────────────────────────

def final_approval_node(state: LocalizationState) -> dict:
    """
    번역 검수 완료 후, 시트에 쓰기 전 최종 승인을 기다림 (HITL 2).
    """
    review_results = state.get("review_results", [])
    failed_rows = state.get("failed_rows", [])
    logs = list(state.get("logs", []))

    logs.append(
        f"[최종 승인 대기] 번역 완료: {len(review_results)}건, "
        f"실패: {len(failed_rows)}건"
    )

    # HITL 2 — 최종 승인 대기
    approval = interrupt({
        "type": "final_approval",
        "review_results": review_results,
        "failed_rows": failed_rows,
    })

    return {
        "final_approval_result": approval,
        "logs": logs,
    }


# ── 조건부 분기 함수 ──────────────────────────────────────────────────

def should_retry(state: LocalizationState) -> str:
    """Node 4 → Node 3 재순환 또는 최종 승인으로 분기"""
    needs_retry = state.get("_needs_retry", [])
    if needs_retry:
        return "translator"
    return "final_approval"


def should_write(state: LocalizationState) -> str:
    """최종 승인 결과에 따라 쓰기 또는 종료"""
    approval = state.get("final_approval_result", "")
    if approval == "approved":
        return "writer"
    return END


# ── 그래프 빌드 ───────────────────────────────────────────────────────

def build_graph():
    """LangGraph StateGraph 구성 및 컴파일"""
    workflow = StateGraph(LocalizationState)

    # 노드 등록
    workflow.add_node("data_backup", data_backup_node)
    workflow.add_node("context_glossary", context_glossary_node)
    workflow.add_node("ko_review", ko_review_node)
    workflow.add_node("ko_approval", ko_approval_node)
    workflow.add_node("translator", translator_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("final_approval", final_approval_node)
    workflow.add_node("writer", writer_node)

    # 엣지 연결
    workflow.set_entry_point("data_backup")
    workflow.add_edge("data_backup", "context_glossary")
    workflow.add_edge("context_glossary", "ko_review")
    workflow.add_edge("ko_review", "ko_approval")
    # ko_approval → (HITL 1 interrupt 후 resume) → translator
    workflow.add_edge("ko_approval", "translator")
    workflow.add_edge("translator", "reviewer")
    # reviewer → 조건부: retry가 필요하면 translator, 아니면 final_approval
    workflow.add_conditional_edges("reviewer", should_retry)
    # final_approval → 조건부: approved면 writer, 아니면 END
    workflow.add_conditional_edges("final_approval", should_write)
    workflow.add_edge("writer", END)

    # 체크포인터 (MemorySaver — 세션 내 유지)
    checkpointer = MemorySaver()
    graph = workflow.compile(checkpointer=checkpointer)

    return graph, checkpointer
