"""LangGraph 워크플로우 정의 — 6 Node + HITL 2곳 interrupt"""

import re
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from agents.state import LocalizationState
from agents.prompts import build_ko_proofreader_prompt
from agents.nodes.data_backup import data_backup_node
from agents.nodes.context_glossary import context_glossary_node
from agents.nodes.translator import translator_node
from utils.drip_feed import drip_feed_emit
from utils.llm import llm_chunk_with_completeness
from agents.nodes.reviewer import reviewer_node
from agents.nodes.writer import writer_node
from backend.config import get_xai_api_key
from config.constants import REQUIRED_COLUMNS, CHUNK_SIZE, TAG_PATTERNS


# ── 한국어 검수 노드 (AI 분석만, interrupt 없음) ─────────────────────

def ko_review_node(state: LocalizationState, config: RunnableConfig) -> dict:
    """
    한국어 맞춤법/띄어쓰기 검수 — AI 분석만 수행.
    interrupt는 별도 ko_approval_node에서 처리.
    """
    original_data = state.get("original_data", [])
    logs = list(state.get("logs", []))
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)
    total_reasoning_tokens = state.get("total_reasoning_tokens", 0)
    total_cached_tokens = state.get("total_cached_tokens", 0)

    # 청크별 이벤트 emitter (없으면 무시)
    emitter = config.get("configurable", {}).get("event_emitter") if config else None

    # ── Fast path: Cancel 복귀 시 캐시된 결과 재사용 (LLM 스킵) ──
    existing_results = state.get("ko_review_results", [])
    if existing_results:
        logs.append(f"[한국어 검수] 캐시 결과 사용: {len(existing_results)}행 (스킵)")
        return {
            "ko_review_results": existing_results,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_reasoning_tokens": total_reasoning_tokens,
            "total_cached_tokens": total_cached_tokens,
            "logs": logs,
        }

    api_key = get_xai_api_key()

    # 한국어 원문 수집
    ko_rows = []
    for row in original_data:
        key = row.get(REQUIRED_COLUMNS["key"], "")
        ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
        row_index = row.get("_row_index")
        if ko_text:
            ko_rows.append({"key": key, REQUIRED_COLUMNS["korean"]: ko_text, "_row_index": row_index})

    logs.append(f"[한국어 검수] 대상: {len(ko_rows)}행")

    # 청크 단위로 AI 검수
    ko_review_results = []
    system_prompt = build_ko_proofreader_prompt()
    total_ko_rows = len(ko_rows)
    processed_count = 0
    restored_count = 0
    missing_count = 0

    total_ko_chunks = (len(ko_rows) + CHUNK_SIZE - 1) // CHUNK_SIZE

    def _build_ko_prompt(subset: list[dict]) -> str:
        return "\n\n".join(
            f"Key: {r['key']}\nKorean: {r[REQUIRED_COLUMNS['korean']]}"
            for r in subset
        )

    for chunk_idx, chunk_start in enumerate(range(0, len(ko_rows), CHUNK_SIZE)):
        chunk = ko_rows[chunk_start:chunk_start + CHUNK_SIZE]
        chunk_items_out: list[dict] = []

        if emitter:
            emitter("heartbeat", {
                "node": "ko_review",
                "lang": "ko",
                "chunk": chunk_idx + 1,
                "total_chunks": total_ko_chunks,
                "chunk_size": len(chunk),
            })

        try:
            pairs, missing, usage = llm_chunk_with_completeness(
                system_prompt=system_prompt,
                items=chunk,
                user_prompt_builder=_build_ko_prompt,
                api_key=api_key,
                item_key_fn=lambda r: r["key"],
                timeout=120,
            )

            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]
            total_reasoning_tokens += usage["reasoning"]
            total_cached_tokens += usage["cached"]

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
                            restored_count += 1

                chunk_items_out.append(item)

            # 응답 누락 — 원본 ko 그대로 + comment 명시
            for src in missing:
                missing_count += 1
                logs.append(
                    f"[한국어 검수] 응답 누락 — key={src['key']} (row={src.get('_row_index')})"
                )
                chunk_items_out.append({
                    "key": src["key"],
                    "original": src[REQUIRED_COLUMNS["korean"]],
                    "revised": src[REQUIRED_COLUMNS["korean"]],
                    "comment": "AI 검수 응답 누락",
                    "has_issue": False,
                    "row_index": src.get("_row_index"),
                })

            ko_review_results.extend(chunk_items_out)

            # 청크별 부분 결과 emit
            processed_count += len(chunk)
            if emitter and chunk_items_out:
                drip_feed_emit(
                    emitter,
                    "ko_review_chunk",
                    chunk_items_out,
                    progress_base=processed_count - len(chunk_items_out),
                    total=total_ko_rows,
                )

        except Exception as e:
            processed_count += len(chunk)
            logs.append(f"[한국어 검수] 오류: {e}")

    if restored_count:
        logs.append(
            f"[한국어 검수] 태그 손상 수정 {restored_count}건 원본 복원"
        )
    if missing_count:
        logs.append(
            f"[한국어 검수] 응답 누락 {missing_count}건 — 원본 유지"
        )
    logs.append(f"[한국어 검수] 최종 수정 제안: {len([r for r in ko_review_results if r.get('has_issue')])}건")

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
