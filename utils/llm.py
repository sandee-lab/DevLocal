"""LLM 호출 공통 유틸 — JSON 파싱 실패 시 청크 분할 재시도."""

import json
import logging
from typing import Callable

import litellm

from config.constants import LLM_MODEL

logger = logging.getLogger("devlocal.llm")


def _norm_key(value) -> str:
    """매칭용 key 정규화 — LLM은 같은 key를 int/str 어느 쪽으로도 돌려줄 수 있으므로
    요청/응답 양쪽을 문자열로 통일해 타입 불일치로 인한 매칭 실패를 방지."""
    return "" if value is None else str(value)


def split_warmup_tasks(tasks: list, prompt_key: Callable) -> tuple[list, list]:
    """
    청크 작업 목록을 (warmup, rest)로 분리.

    각 unique system_prompt별 첫 task만 warmup으로 보낸다.
    warmup을 먼저 직렬로 실행하면 xAI 자동 prompt caching이 그 시스템 프롬프트를
    캐시에 적재하고, 이후 같은 conv_id의 병렬 호출이 캐시 hit이 됨.

    prompt_key: task에서 system_prompt 식별자(id 또는 hash 등)를 추출하는 함수.
    """
    seen: set = set()
    warmup: list = []
    rest: list = []
    for t in tasks:
        k = prompt_key(t)
        if k not in seen:
            seen.add(k)
            warmup.append(t)
        else:
            rest.append(t)
    return warmup, rest


def _strip_codeblock(content: str) -> str:
    """LLM 응답 앞뒤 ```...``` 코드블록 마커 제거."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
    return content


def _extract_usage(response) -> dict:
    """litellm 응답에서 토큰 사용량 추출 (xAI reasoning/cached 포함)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input": 0, "output": 0, "reasoning": 0, "cached": 0}

    reasoning = 0
    cached = 0
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details:
        reasoning = getattr(completion_details, "reasoning_tokens", 0) or 0
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details:
        cached = getattr(prompt_details, "cached_tokens", 0) or 0

    return {
        "input": getattr(usage, "prompt_tokens", 0) or 0,
        "output": getattr(usage, "completion_tokens", 0) or 0,
        "reasoning": reasoning,
        "cached": cached,
    }


def _combine_usage(*usages: dict) -> dict:
    """여러 호출의 토큰 사용량을 합산."""
    combined = {"input": 0, "output": 0, "reasoning": 0, "cached": 0}
    for u in usages:
        for k in combined:
            combined[k] += u.get(k, 0)
    return combined


def llm_json_call(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    timeout: int = 120,
    conv_id: str | None = None,
) -> tuple[list, dict]:
    """
    단일 LLM 호출 + JSON 파싱.
    반환: (parsed_items_list, usage_dict)
    예외: json.JSONDecodeError, litellm 오류 등은 그대로 raise.

    conv_id: xAI Grok prompt caching 친화 라우팅 키. 같은 값을 가진
    요청은 같은 서버로 라우팅되어 캐시 prefix를 공유 → cached_tokens 증가.
    """
    extra_headers = {"x-grok-conv-id": conv_id} if conv_id else None
    response = litellm.completion(
        model=LLM_MODEL,
        api_key=api_key,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout=timeout,
        extra_headers=extra_headers,
    )
    content = _strip_codeblock(response.choices[0].message.content)
    parsed = json.loads(content)
    if not isinstance(parsed, list):
        parsed = [parsed]
    usage = _extract_usage(response)
    if usage["input"]:
        cached = usage["cached"]
        hit_ratio = (cached / usage["input"] * 100) if usage["input"] else 0
        logger.info(
            "LLM usage: input=%d output=%d cached=%d (hit %.1f%%) conv_id=%s",
            usage["input"], usage["output"], cached, hit_ratio, conv_id or "-",
        )
    return parsed, usage


def llm_json_call_with_split(
    system_prompt: str,
    items: list,
    user_prompt_builder: Callable[[list], str],
    api_key: str,
    timeout: int = 120,
    conv_id: str | None = None,
    _depth: int = 0,
    _max_depth: int = 6,
) -> tuple[list, dict]:
    """
    LLM 호출 + JSON 파싱. 파싱 실패 시 items를 절반으로 분할하여 재귀 호출.

    - 큰 청크에서 LLM 응답이 잘리거나 깨지는 truncation 문제를 자동 복구.
    - 최소 단위(1행) 또는 _max_depth 도달 시 마지막 JSONDecodeError를 raise.
    - 분할 호출의 토큰 사용량은 모두 합산하여 반환.
    """
    user_prompt = user_prompt_builder(items)

    try:
        return llm_json_call(system_prompt, user_prompt, api_key, timeout, conv_id=conv_id)
    except json.JSONDecodeError as e:
        if len(items) <= 1 or _depth >= _max_depth:
            logger.error(
                "LLM JSON 파싱 실패 — 더 이상 분할 불가 (items=%d, depth=%d): %s",
                len(items), _depth, e,
            )
            raise

        mid = len(items) // 2
        logger.warning(
            "LLM JSON 파싱 실패 — 청크 분할 재시도 (%d → %d + %d, depth=%d): %s",
            len(items), mid, len(items) - mid, _depth, e,
        )
        left, left_usage = llm_json_call_with_split(
            system_prompt, items[:mid], user_prompt_builder, api_key, timeout,
            conv_id=conv_id, _depth=_depth + 1, _max_depth=_max_depth,
        )
        right, right_usage = llm_json_call_with_split(
            system_prompt, items[mid:], user_prompt_builder, api_key, timeout,
            conv_id=conv_id, _depth=_depth + 1, _max_depth=_max_depth,
        )
        return left + right, _combine_usage(left_usage, right_usage)


def llm_chunk_with_completeness(
    system_prompt: str,
    items: list,
    user_prompt_builder: Callable[[list], str],
    api_key: str,
    item_key_fn: Callable[[dict], str],
    response_key_fn: Callable[[dict], str] = None,
    timeout: int = 120,
    max_retries: int = 2,
    conv_id: str | None = None,
) -> tuple[list[tuple[dict, dict]], list[dict], dict]:
    """
    LLM 호출 + 응답 무결성 검증. 누락된 요청 항목만 재요청 (최대 max_retries회).

    동작:
      1) llm_json_call_with_split 호출 (JSON 파싱 실패는 분할로 복구)
      2) 응답 항목을 key + 청크 내 순서로 요청 항목과 매칭
      3) 매칭 실패한 요청만 다시 LLM에 보냄 (누락 키 재요청)
      4) max_retries 후에도 매칭 안 된 항목은 missing으로 반환

    중복 key 처리: 같은 key가 N개면 응답에서도 N개여야 정상. 모자라면 모자란 수만큼 누락.

    Args:
      item_key_fn: 요청 항목에서 key 추출 (예: lambda r: r["Key"])
      response_key_fn: LLM 응답 항목에서 key 추출 (기본: it.get("key", ""))

    반환:
      pairs:   [(req_item, resp_item), ...]  — 매칭 성공한 (요청, 응답) 쌍
      missing: [req_item, ...]               — 재시도 후에도 응답 없는 요청
      usage:   합산 토큰 사용량
    """
    if response_key_fn is None:
        response_key_fn = lambda r: r.get("key", "")  # noqa: E731

    pending = list(items)
    pairs: list[tuple[dict, dict]] = []
    total_usage = {"input": 0, "output": 0, "reasoning": 0, "cached": 0}

    for attempt in range(max_retries + 1):
        if not pending:
            break

        try:
            response_items, usage = llm_json_call_with_split(
                system_prompt=system_prompt,
                items=pending,
                user_prompt_builder=user_prompt_builder,
                api_key=api_key,
                timeout=timeout,
                conv_id=conv_id,
            )
        except Exception as e:
            logger.error(
                "LLM 호출 실패 (completeness 시도 %d/%d, 잔여 %d개): %s",
                attempt + 1, max_retries + 1, len(pending), e,
            )
            break

        total_usage = _combine_usage(total_usage, usage)

        # key + 청크 내 순서 기준으로 요청-응답 매칭
        pending_by_key: dict[str, list[dict]] = {}
        for it in pending:
            pending_by_key.setdefault(_norm_key(item_key_fn(it)), []).append(it)
        consumed: dict[str, int] = {}
        matched_ids: set[int] = set()

        for resp in response_items:
            if not isinstance(resp, dict):
                continue
            rk = _norm_key(response_key_fn(resp))
            bucket = pending_by_key.get(rk)
            if not bucket:
                continue
            idx = consumed.get(rk, 0)
            if idx < len(bucket):
                req = bucket[idx]
                pairs.append((req, resp))
                matched_ids.add(id(req))
                consumed[rk] = idx + 1

        new_pending = [it for it in pending if id(it) not in matched_ids]
        if len(new_pending) == len(pending):
            logger.warning(
                "LLM completeness: 시도 %d에서 매칭된 항목 없음, 재시도 중단 (잔여 %d개)",
                attempt + 1, len(new_pending),
            )
            break

        if new_pending:
            logger.warning(
                "LLM completeness: 시도 %d/%d 후 %d/%d 누락 → 재요청",
                attempt + 1, max_retries + 1, len(new_pending), len(items),
            )

        pending = new_pending

    return pairs, pending, total_usage
