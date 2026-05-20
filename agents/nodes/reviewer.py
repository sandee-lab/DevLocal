"""Node 4: 검수 (LLM + Regex) — 태그 검증, Glossary 후처리, AI 품질 검증 (청크 배치)"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.runnables import RunnableConfig
from backend.config import get_xai_api_key
from agents.state import LocalizationState
from agents.prompts import build_reviewer_prompt
from config.constants import (
    CHUNK_SIZE,
    LLM_CHUNK_PARALLELISM,
    MAX_RETRY_COUNT,
    REQUIRED_COLUMNS,
    SUPPORTED_LANGUAGES,
)
from utils.drip_feed import drip_feed_emit, emit_log_line, emit_log_lines
from utils.llm import llm_chunk_with_completeness
from config.glossary import format_glossary_text
from utils.validation import (
    apply_glossary_postprocess,
    check_glossary_compliance,
    validate_tags,
)


_REVIEW_USER_PROMPT_SUFFIX = (
    "\n\n위 번역들을 각각 검수하고, "
    "번역 결과의 적합성을 요약한 reason과 함께 JSON 배열로 출력하세요."
)


def _build_review_prompt_batch(items_for_review: list[dict]) -> str:
    """여러 번역 항목을 하나의 프롬프트로 결합 — old_translation 미포함 (입력 토큰 절감)."""
    parts = []
    for item in items_for_review:
        part = (
            f"Key: {item['key']}\n"
            f"Korean (원문): {item['source_ko']}\n"
            f"Translation ({item['lang']}): {item['translated']}"
        )
        parts.append(part)
    return "\n\n---\n\n".join(parts) + _REVIEW_USER_PROMPT_SUFFIX


def reviewer_node(state: LocalizationState, config: RunnableConfig) -> dict:
    """
    번역 결과물 검수:
    1. Glossary 후처리 (JA 등급명 강제 치환)
    2. 정규식 태그 검증 → 실패 시 재시도(최대 3회) 또는 검수실패 마킹
    3. Glossary 준수 여부 검증 (경고 기록)
    4. AI 품질 검증 + 변경 사유 생성 (청크 배치 LLM 호출, 병렬 실행)

    태그 검증 실패 항목은 _needs_retry로 translator에 재전달.
    3회 재시도 후에도 실패하면 failed_rows에 검수실패로 마킹.
    """
    emitter = config.get("configurable", {}).get("event_emitter") if config else None
    # xAI Grok prompt caching 라우팅 키 — 같은 thread_id 요청을 같은 서버로 보내 캐시 prefix 공유
    conv_id = config.get("configurable", {}).get("thread_id") if config else None

    original_data = state.get("original_data", [])
    translation_results = list(state.get("translation_results", []))
    prev_review_results = list(state.get("review_results", []))

    failed_rows = list(state.get("failed_rows", []))
    retry_count = dict(state.get("retry_count", {}))
    logs = list(state.get("logs", []))
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)
    total_reasoning_tokens = state.get("total_reasoning_tokens", 0)
    total_cached_tokens = state.get("total_cached_tokens", 0)
    custom_prompt = state.get("custom_prompt", "")
    game_synopsis = state.get("game_synopsis", "")
    tone_and_manner = state.get("tone_and_manner", "")

    # 원본 데이터 인덱싱 — row_index 우선 (중복 Key 시 정확한 ko 텍스트 보호),
    # key 기반은 row_index 결손 항목 fallback용
    original_by_ri: dict[int, dict] = {}
    original_map: dict[str, dict] = {}
    for row in original_data:
        ri = row.get("_row_index")
        if ri is not None:
            original_by_ri[ri] = row
        key = row.get(REQUIRED_COLUMNS["key"], "")
        if key and key not in original_map:
            original_map[key] = row

    api_key = get_xai_api_key()

    # ── Step 1~3: 정규식/Glossary 검증 + 재시도 분기 (sequential, 순수 compute) ──
    validated_items = []
    needs_retry_items = []

    for item in translation_results:
        key = item["key"]
        lang = item["lang"]
        translated = item.get("translated", "")
        row_index = item.get("row_index")

        if item.get("error"):
            failed_rows.append({
                "key": key,
                "lang": lang,
                "reason": f"번역 오류: {item['error']}",
                "row_index": row_index,
            })
            continue

        if not translated:
            continue

        if row_index is not None and row_index in original_by_ri:
            original_row = original_by_ri[row_index]
        else:
            original_row = original_map.get(key, {})
            if row_index is not None:
                logs.append(
                    f"[Node 4] row_index 결손 → key fallback — {key} (row={row_index})"
                )
        source_ko = original_row.get(REQUIRED_COLUMNS["korean"], "")

        translated = apply_glossary_postprocess(translated, lang)

        tag_result = validate_tags(source_ko, translated)

        if not tag_result["valid"]:
            count_key = f"{key}_{lang}"
            current = retry_count.get(count_key, 0)

            if current < MAX_RETRY_COUNT:
                retry_count[count_key] = current + 1
                shared_comments = original_row.get(REQUIRED_COLUMNS["shared_comments"], "")
                needs_retry_items.append({
                    "key": key,
                    "lang": lang,
                    "source_ko": source_ko,
                    "shared_comments": shared_comments,
                    "translated": translated,
                    "feedback": tag_result["errors"],
                    "row_index": row_index,
                })
                logs.append(
                    f"[Node 4] 태그 검증 실패 → 재번역 요청 "
                    f"({current + 1}/{MAX_RETRY_COUNT}) — {key} ({lang})"
                )
                continue
            else:
                failed_rows.append({
                    "key": key,
                    "lang": lang,
                    "reason": f"태그 검증 {MAX_RETRY_COUNT}회 실패: {'; '.join(tag_result['errors'])}",
                    "row_index": row_index,
                })
                logs.append(
                    f"[Node 4] 태그 검증 {MAX_RETRY_COUNT}회 초과 → 검수실패 — {key} ({lang})"
                )
                continue

        warnings = []
        glossary_result = check_glossary_compliance(translated, lang, source_ko)
        if not glossary_result["compliant"]:
            warnings.extend(glossary_result["violations"])
            logs.append(
                f"[Node 4] 글로서리 경고 — {key} ({lang}): "
                f"{'; '.join(glossary_result['violations'])}"
            )

        lang_col = SUPPORTED_LANGUAGES.get(lang, "")
        old_translation = original_row.get(lang_col, "")

        validated_items.append({
            "key": key,
            "lang": lang,
            "translated": translated,
            "source_ko": source_ko,
            "old_translation": old_translation,
            "warnings": warnings,
            "row_index": row_index,
        })

    summary_line = (
        f"[Node 4] 정규식/Glossary 검증: 통과 {len(validated_items)}건, "
        f"재시도 {len(needs_retry_items)}건"
    )
    logs.append(summary_line)
    emit_log_line(emitter, summary_line)

    # ── Step 3.5: 변경 없는 항목 LLM 스킵 (translated == old_translation) ──
    # 코드 검증(태그/Glossary)은 이미 통과한 상태 → AI 재검수 무의미.
    # warnings가 있으면 reason에 합성, 없으면 빈 reason.
    unchanged_results: list[dict] = []
    changed_items: list[dict] = []
    for item in validated_items:
        if item["old_translation"] and item["translated"] == item["old_translation"]:
            warnings = list(item["warnings"])
            reason = "; ".join(warnings) if warnings else ""
            unchanged_results.append({
                "key": item["key"],
                "lang": item["lang"],
                "translated": item["translated"],
                "old_translation": item["old_translation"],
                "original_ko": item["source_ko"],
                "reason": reason,
                "row_index": item.get("row_index"),
            })
        else:
            changed_items.append(item)

    if unchanged_results:
        skip_line = f"[Node 4] 변경 없는 항목 즉시 통과: {len(unchanged_results)}건 (LLM 스킵)"
        logs.append(skip_line)
        emit_log_line(emitter, skip_line)

    # ── Step 4+5: AI 품질 검증 + 결합 + 청크별 drip-feed emit (병렬 청크 실행) ──
    lang_groups: dict[str, list[dict]] = {}
    for item in changed_items:
        lang_groups.setdefault(item["lang"], []).append(item)

    progress_total = len(prev_review_results) + len(validated_items) + len(needs_retry_items)
    if progress_total == 0:
        progress_total = max(len(prev_review_results) + len(failed_rows), 1)

    new_review_results: list[dict] = list(unchanged_results)
    lock = threading.Lock()
    cumulative_done = len(prev_review_results)

    # 초기 진행률 신호 + unchanged 결과 drip-feed (LLM 호출 전 즉시 발행)
    if emitter:
        if unchanged_results:
            drip_feed_emit(
                emitter,
                "review_chunk",
                unchanged_results,
                progress_base=cumulative_done,
                total=progress_total,
            )
        else:
            emitter("review_chunk", {
                "chunk_results": [],
                "progress": {
                    "done": cumulative_done,
                    "total": progress_total,
                },
            })
    cumulative_done += len(unchanged_results)

    # 작업 평탄화: (lang, chunk_idx, total_chunks, chunk, system_prompt)
    tasks: list[tuple] = []
    for lang, items in lang_groups.items():
        glossary_text = format_glossary_text(lang)
        system_prompt = build_reviewer_prompt(
            lang, glossary_text,
            synopsis=game_synopsis, tone=tone_and_manner, custom_prompt=custom_prompt,
        )
        total_chunks = (len(items) + CHUNK_SIZE - 1) // CHUNK_SIZE
        for chunk_idx in range(total_chunks):
            start = chunk_idx * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(items))
            tasks.append((lang, chunk_idx, total_chunks, items[start:end], system_prompt))

    def _process(lang: str, chunk_idx: int, total_chunks: int, chunk: list[dict], system_prompt: str):
        if emitter:
            emitter("heartbeat", {
                "node": "reviewer",
                "lang": lang,
                "chunk": chunk_idx + 1,
                "total_chunks": total_chunks,
                "chunk_size": len(chunk),
            })

        local_logs: list[str] = []
        ai_by_item_id: dict[int, dict] = {}
        missing_items: list[dict] = []
        usage = None

        try:
            pairs, missing_items, usage = llm_chunk_with_completeness(
                system_prompt=system_prompt,
                items=chunk,
                user_prompt_builder=_build_review_prompt_batch,
                api_key=api_key,
                item_key_fn=lambda it: it["key"],
                timeout=120,
                conv_id=conv_id,
            )
            for src, ai in pairs:
                ai_by_item_id[id(src)] = ai
        except Exception as e:
            local_logs.append(f"[Node 4] AI 검수 오류 (청크 {chunk_idx + 1}, {lang}): {e}")
            missing_items = list(chunk)

        chunk_results: list[dict] = []
        for item in chunk:
            key = item["key"]
            warnings = list(item["warnings"])
            ai_result = ai_by_item_id.get(id(item))

            if ai_result is None:
                reason_parts = list(warnings)
                if item in missing_items:
                    reason_parts.append("AI 검수 응답 누락 — 수동 검토 권장")
                    local_logs.append(f"[Node 4] AI 검수 응답 누락 — {key} ({lang})")
                reason = "; ".join(reason_parts)
            else:
                reason = ai_result.get("reason", "")
                ai_issues = ai_result.get("issues") or []
                if ai_issues:
                    warnings.extend(ai_issues)
                    local_logs.append(
                        f"[Node 4] AI 검수 경고 — {key} ({lang}): {'; '.join(ai_issues)}"
                    )
                if warnings and not reason:
                    reason = "; ".join(warnings)
                elif warnings and reason:
                    reason = f"{reason} | 경고: {'; '.join(warnings)}"

            chunk_results.append({
                "key": key,
                "lang": lang,
                "translated": item["translated"],
                "old_translation": item["old_translation"],
                "original_ko": item["source_ko"],
                "reason": reason,
                "row_index": item.get("row_index"),
            })

        local_logs.append(
            f"[Node 4] {lang.upper()} 검수 청크 {chunk_idx + 1}/{total_chunks} 완료 ({len(chunk)}건)"
        )
        return chunk_idx, lang, chunk_results, usage, local_logs

    if tasks:
        with ThreadPoolExecutor(max_workers=LLM_CHUNK_PARALLELISM) as exe:
            futures = [exe.submit(_process, *t) for t in tasks]
            for fut in as_completed(futures):
                _ci, _lg, chunk_results, usage, local_logs = fut.result()
                with lock:
                    if usage:
                        total_input_tokens += usage["input"]
                        total_output_tokens += usage["output"]
                        total_reasoning_tokens += usage["reasoning"]
                        total_cached_tokens += usage["cached"]
                    logs.extend(local_logs)
                    emit_log_lines(emitter, local_logs)
                    new_review_results.extend(chunk_results)
                    if emitter and chunk_results:
                        drip_feed_emit(
                            emitter,
                            "review_chunk",
                            chunk_results,
                            progress_base=cumulative_done,
                            total=progress_total,
                        )
                        cumulative_done += len(chunk_results)

    all_review_results = prev_review_results + new_review_results

    # validated_items가 비어있을 때도 progress 이벤트 보장 (엣지 케이스)
    if emitter and not new_review_results:
        emitter("review_chunk", {
            "chunk_results": [],
            "progress": {
                "done": len(all_review_results),
                "total": progress_total,
            },
        })

    end_line = (
        f"[Node 4] 검수 완료: 누적 통과 {len(all_review_results)}건, "
        f"실패 {len(failed_rows)}건, 재시도 대기 {len(needs_retry_items)}건"
    )
    logs.append(end_line)
    emit_log_line(emitter, end_line)

    return {
        "review_results": all_review_results,
        "failed_rows": failed_rows,
        "_needs_retry": needs_retry_items,
        "retry_count": retry_count,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cached_tokens": total_cached_tokens,
        "logs": logs,
    }
