"""Node 3: 번역 (LLM) — 청크 단위 번역, Shared Comments 컨텍스트 주입"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.runnables import RunnableConfig
from backend.config import get_xai_api_key
from agents.state import LocalizationState
from agents.prompts import build_translator_prompt
from config.constants import (
    CHUNK_SIZE,
    LLM_CHUNK_PARALLELISM,
    REQUIRED_COLUMNS,
    SUPPORTED_LANGUAGES,
)
from utils.drip_feed import drip_feed_emit, emit_log_line, emit_log_lines
from utils.llm import llm_chunk_with_completeness, split_warmup_tasks
from config.glossary import format_glossary_text


def _build_translation_prompt(rows: list[dict], lang: str) -> str:
    """번역 대상 행들을 프롬프트 메시지로 변환"""
    items = []
    for row in rows:
        key = row.get(REQUIRED_COLUMNS["key"], "")
        ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
        shared_comments = row.get(REQUIRED_COLUMNS["shared_comments"], "")

        item = f"Key: {key}\nKorean: {ko_text}"
        if shared_comments:
            item += f"\nShared Comments (참고): {shared_comments}"
        items.append(item)

    return "\n\n---\n\n".join(items)


def _build_retry_prompt(items: list[dict], lang: str) -> str:
    """재번역 프롬프트 — 이전 번역 실패 피드백 포함"""
    parts = []
    for item in items:
        part = f"Key: {item['key']}\nKorean: {item['source_ko']}"
        if item.get("shared_comments"):
            part += f"\nShared Comments (참고): {item['shared_comments']}"
        part += f"\n이전 번역 (오류 있음): {item['translated']}"
        part += f"\n오류: {'; '.join(item['feedback'])}"
        part += (
            "\n위 오류를 수정하여 다시 번역하세요. "
            "특히 원문의 포맷팅 태그({변수}, <color>, \\n 등)를 "
            "번역 결과에 동일하게 보존해야 하며, "
            "번역 결과에 한국어(한글)가 1글자라도 남으면 안 됩니다 "
            "(관용구·말장난도 반드시 타겟 언어로 의역)."
        )
        parts.append(part)
    return "\n\n---\n\n".join(parts)


def _emit_heartbeat(emitter, node: str, lang: str, chunk_idx: int, total_chunks: int, size: int) -> None:
    """노드 단위 진행 하트비트 — 프론트 stall 감지용."""
    if not emitter:
        return
    emitter("heartbeat", {
        "node": node,
        "lang": lang,
        "chunk": chunk_idx,
        "total_chunks": total_chunks,
        "chunk_size": size,
    })


def _normalize_translated(text: str) -> str:
    """LLM이 JSON 출력에서 \\n을 실제 개행으로 흘릴 때 복원."""
    return text.replace("\n", "\\n").replace("\t", "\\t")


def _translate_retry(state: LocalizationState, needs_retry: list[dict], emitter=None, conv_id: str | None = None) -> dict:
    """재시도 모드: 실패한 항목만 재번역 (병렬 청크 처리)"""
    retry_count = dict(state.get("retry_count", {}))
    logs = list(state.get("logs", []))
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)
    total_reasoning_tokens = state.get("total_reasoning_tokens", 0)
    total_cached_tokens = state.get("total_cached_tokens", 0)
    custom_prompt = state.get("custom_prompt", "")
    game_synopsis = state.get("game_synopsis", "")
    tone_and_manner = state.get("tone_and_manner", "")

    api_key = get_xai_api_key()

    # 언어별 그룹핑
    retry_by_lang: dict[str, list[dict]] = {}
    for item in needs_retry:
        retry_by_lang.setdefault(item["lang"], []).append(item)

    # 작업 평탄화: (lang, chunk_idx, total_chunks, chunk, system_prompt)
    tasks = []
    for lang, items in retry_by_lang.items():
        glossary_text = format_glossary_text(lang)
        system_prompt = build_translator_prompt(
            lang, glossary_text,
            synopsis=game_synopsis, tone=tone_and_manner, custom_prompt=custom_prompt,
        )
        total_chunks = (len(items) + CHUNK_SIZE - 1) // CHUNK_SIZE
        line = f"[Node 3] {lang.upper()} 재번역 대상: {len(items)}건 ({total_chunks}청크)"
        logs.append(line)
        emit_log_line(emitter, line)
        for chunk_idx in range(total_chunks):
            start = chunk_idx * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(items))
            tasks.append((lang, chunk_idx, total_chunks, items[start:end], system_prompt))

    all_results: list[dict] = []
    lock = threading.Lock()

    def _process(lang: str, chunk_idx: int, total_chunks: int, chunk: list[dict], system_prompt: str):
        _emit_heartbeat(emitter, "translator_retry", lang, chunk_idx + 1, total_chunks, len(chunk))
        try:
            pairs, missing, usage = llm_chunk_with_completeness(
                system_prompt=system_prompt,
                items=chunk,
                user_prompt_builder=lambda subset: _build_retry_prompt(subset, lang),
                api_key=api_key,
                item_key_fn=lambda it: it["key"],
                timeout=120,
                conv_id=conv_id,
            )
            local_results: list[dict] = []
            for src, ti in pairs:
                local_results.append({
                    "key": src["key"],
                    "lang": lang,
                    "translated": _normalize_translated(ti.get("translated", "")),
                    "row_index": src.get("row_index"),
                })
            for src in missing:
                local_results.append({
                    "key": src["key"],
                    "lang": lang,
                    "translated": "",
                    "error": "LLM 응답 누락 (재요청 후에도 미반환)",
                    "row_index": src.get("row_index"),
                })
            local_logs = [
                f"[Node 3] 재번역 응답 누락 — key={s['key']} ({lang})" for s in missing
            ]
            return "ok", chunk_idx, lang, local_results, usage, local_logs
        except Exception as e:
            local_logs = [f"[Node 3] 재번역 오류 (청크 {chunk_idx + 1}, {lang}): {e}"]
            err_results = [
                {
                    "key": it["key"],
                    "lang": lang,
                    "translated": "",
                    "error": str(e),
                    "row_index": it.get("row_index"),
                }
                for it in chunk
            ]
            return "err", chunk_idx, lang, err_results, None, local_logs

    def _handle_retry_result(result):
        nonlocal total_input_tokens, total_output_tokens, total_reasoning_tokens
        nonlocal total_cached_tokens
        status, _ci, _lg, results, usage, local_logs = result
        all_results.extend(results)
        if usage:
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]
            total_reasoning_tokens += usage["reasoning"]
            total_cached_tokens += usage["cached"]
        logs.extend(local_logs)
        emit_log_lines(emitter, local_logs)

    if tasks:
        # warm-up: lang별 첫 청크를 sync로 → xAI 캐시 적재 후 나머지 병렬
        warmup_tasks, rest_tasks = split_warmup_tasks(tasks, prompt_key=lambda t: t[0])
        for t in warmup_tasks:
            _handle_retry_result(_process(*t))
        if rest_tasks:
            with ThreadPoolExecutor(max_workers=LLM_CHUNK_PARALLELISM) as exe:
                futures = [exe.submit(_process, *t) for t in rest_tasks]
                for fut in as_completed(futures):
                    with lock:
                        _handle_retry_result(fut.result())

    return {
        "translation_results": all_results,
        "_needs_retry": [],
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cached_tokens": total_cached_tokens,
        "retry_count": retry_count,
        "logs": logs,
    }


def translator_node(state: LocalizationState, config: RunnableConfig) -> dict:
    """
    청크 단위 번역 수행 (LLM 호출 병렬화).
    _needs_retry가 있으면 해당 항목만 재번역 (retry 모드).
    없으면 정상 번역:
      모드 A: 전체 행 번역
      모드 B: 타겟 언어 빈칸인 행만 번역
    """
    emitter = config.get("configurable", {}).get("event_emitter") if config else None
    # xAI Grok prompt caching 라우팅 키 — 같은 thread_id 요청을 같은 서버로 보내 캐시 prefix 공유
    conv_id = config.get("configurable", {}).get("thread_id") if config else None

    # 재시도 모드 확인
    needs_retry = state.get("_needs_retry", [])
    if needs_retry:
        return _translate_retry(state, needs_retry, emitter=emitter, conv_id=conv_id)

    # ── 정상 번역 모드 ──
    original_data = state.get("original_data", [])
    mode = state.get("mode", "A")
    target_languages = state.get("target_languages", [])
    ko_approval_result = state.get("ko_approval_result", "approved")
    ko_review_results = state.get("ko_review_results", [])
    retry_count = dict(state.get("retry_count", {}))
    logs = list(state.get("logs", []))
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)
    total_reasoning_tokens = state.get("total_reasoning_tokens", 0)
    total_cached_tokens = state.get("total_cached_tokens", 0)
    custom_prompt = state.get("custom_prompt", "")
    game_synopsis = state.get("game_synopsis", "")
    tone_and_manner = state.get("tone_and_manner", "")

    # 한국어 검수 승인 시, 수정된 텍스트 적용
    working_data = []
    ko_revised_map = {}
    if ko_approval_result == "approved" and ko_review_results:
        for r in ko_review_results:
            ko_revised_map[r["key"]] = r["revised"]

    for row in original_data:
        row_copy = dict(row)
        key = row_copy.get(REQUIRED_COLUMNS["key"], "")
        if key in ko_revised_map:
            row_copy[REQUIRED_COLUMNS["korean"]] = ko_revised_map[key]
        working_data.append(row_copy)

    api_key = get_xai_api_key()

    # 언어별 target 행 필터링 + 작업 평탄화
    tasks: list[tuple] = []  # (lang, chunk_idx, total_chunks, chunk, system_prompt)
    target_rows_total = 0
    last_total_chunks = 0  # state 반환값 호환용

    for lang in target_languages:
        lang_col = SUPPORTED_LANGUAGES.get(lang, "")
        if not lang_col:
            line = f"[Node 3] 지원하지 않는 언어: {lang}"
            logs.append(line)
            emit_log_line(emitter, line)
            continue

        target_rows = []
        for row in working_data:
            key = row.get(REQUIRED_COLUMNS["key"], "")
            ko_text = row.get(REQUIRED_COLUMNS["korean"], "")
            if not ko_text:
                continue
            if mode == "B":
                existing = row.get(lang_col, "")
                if existing and existing.strip():
                    continue
            target_rows.append(row)

        target_rows_total += len(target_rows)
        glossary_text = format_glossary_text(lang)
        system_prompt = build_translator_prompt(
            lang, glossary_text,
            synopsis=game_synopsis, tone=tone_and_manner, custom_prompt=custom_prompt,
        )
        total_chunks = (len(target_rows) + CHUNK_SIZE - 1) // CHUNK_SIZE
        last_total_chunks = total_chunks
        line = f"[Node 3] {lang.upper()} 번역 대상: {len(target_rows)}행 ({total_chunks}청크)"
        logs.append(line)
        emit_log_line(emitter, line)

        for chunk_idx in range(total_chunks):
            start = chunk_idx * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(target_rows))
            tasks.append((lang, chunk_idx, total_chunks, target_rows[start:end], system_prompt))

    if not tasks:
        return {
            "translation_results": [],
            "current_chunk_index": 0,
            "total_chunks": 0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_reasoning_tokens": total_reasoning_tokens,
            "total_cached_tokens": total_cached_tokens,
            "retry_count": retry_count,
            "logs": logs,
        }

    all_results: list[dict] = []
    lock = threading.Lock()
    cumulative_done = 0
    progress_total = max(target_rows_total, 1)

    def _process(lang: str, chunk_idx: int, total_chunks: int, chunk: list[dict], system_prompt: str):
        _emit_heartbeat(emitter, "translator", lang, chunk_idx + 1, total_chunks, len(chunk))
        local_logs: list[str] = []
        try:
            pairs, missing, usage = llm_chunk_with_completeness(
                system_prompt=system_prompt,
                items=chunk,
                user_prompt_builder=lambda subset: _build_translation_prompt(subset, lang),
                api_key=api_key,
                item_key_fn=lambda it: it.get(REQUIRED_COLUMNS["key"], ""),
                timeout=120,
                conv_id=conv_id,
            )
            success_results: list[dict] = []
            for src_row, item in pairs:
                success_results.append({
                    "key": src_row.get(REQUIRED_COLUMNS["key"], ""),
                    "lang": lang,
                    "translated": _normalize_translated(item.get("translated", "")),
                    "row_index": src_row.get("_row_index"),
                })
            missing_results: list[dict] = []
            for src_row in missing:
                k = src_row.get(REQUIRED_COLUMNS["key"], "")
                missing_results.append({
                    "key": k,
                    "lang": lang,
                    "translated": "",
                    "error": "LLM 응답 누락 (재요청 후에도 미반환)",
                    "row_index": src_row.get("_row_index"),
                })
                local_logs.append(
                    f"[Node 3] {lang.upper()} 응답 누락 — key={k} (row={src_row.get('_row_index')})"
                )
            local_logs.append(
                f"[Node 3] {lang.upper()} 청크 {chunk_idx + 1}/{total_chunks} 완료 "
                f"({len(success_results)}/{len(chunk)} 성공)"
            )
            return "ok", lang, chunk_idx, success_results, missing_results, usage, local_logs
        except Exception as e:
            err_results = [
                {
                    "key": row.get(REQUIRED_COLUMNS["key"], ""),
                    "lang": lang,
                    "translated": "",
                    "error": str(e),
                    "row_index": row.get("_row_index"),
                }
                for row in chunk
            ]
            local_logs.append(f"[Node 3] 번역 오류 (청크 {chunk_idx + 1}, {lang}): {e}")
            return "err", lang, chunk_idx, [], err_results, None, local_logs

    def _handle_translate_result(result):
        nonlocal total_input_tokens, total_output_tokens, total_reasoning_tokens
        nonlocal total_cached_tokens, cumulative_done
        status, lang, chunk_idx, success_results, miss_results, usage, local_logs = result
        logs.extend(local_logs)
        emit_log_lines(emitter, local_logs)
        all_results.extend(success_results)
        all_results.extend(miss_results)
        if usage:
            total_input_tokens += usage["input"]
            total_output_tokens += usage["output"]
            total_reasoning_tokens += usage["reasoning"]
            total_cached_tokens += usage["cached"]
        if emitter and success_results:
            drip_feed_emit(
                emitter,
                "translation_chunk",
                success_results,
                progress_base=cumulative_done,
                total=progress_total,
                lang=lang,
            )
            cumulative_done += len(success_results)

    # warm-up: lang별 첫 청크 sync 실행 → xAI 캐시 적재 후 나머지 병렬
    warmup_tasks, rest_tasks = split_warmup_tasks(tasks, prompt_key=lambda t: t[0])
    for t in warmup_tasks:
        _handle_translate_result(_process(*t))
    if rest_tasks:
        with ThreadPoolExecutor(max_workers=LLM_CHUNK_PARALLELISM) as exe:
            futures = [exe.submit(_process, *t) for t in rest_tasks]
            for fut in as_completed(futures):
                with lock:
                    _handle_translate_result(fut.result())

    return {
        "translation_results": all_results,
        "current_chunk_index": last_total_chunks,
        "total_chunks": last_total_chunks,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cached_tokens": total_cached_tokens,
        "retry_count": retry_count,
        "logs": logs,
    }
