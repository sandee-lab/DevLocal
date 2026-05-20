"""
xai/grok-4.3 모델 호출 검증 + 효율 측정 스크립트.

목적:
  1. config.constants.LLM_MODEL("xai/grok-4.3") 가 실제 xAI API에서 정상 호출되는지 확인
  2. 청크 사이즈별(25/50/100행) 응답 누락률·JSON 무결성·소요 시간·토큰 사용량 측정
  3. utils.llm.llm_json_call_with_split (JSON 파싱 실패 시 분할 재시도) 헬퍼 동작 검증

사용:
  python scripts/verify_model.py
"""

import json
import sys
import time
from pathlib import Path

# Windows 콘솔 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_xai_api_key
from config.constants import LLM_MODEL, CHUNK_SIZE, LLM_PRICING
from utils.llm import llm_json_call, llm_json_call_with_split


# ── 1) 최소 호출 — 모델 라우팅·인증 확인 ──────────────────────────────

def smoke_test() -> bool:
    """단일 키 한 줄 번역으로 라우팅·인증·기본 JSON 응답 확인."""
    print(f"\n[1/3] Smoke test — 모델 라우팅 확인 (model={LLM_MODEL})")
    system_prompt = (
        "You translate Korean game text into English. "
        'Output JSON array only: [{"key": "...", "translated": "..."}]'
    )
    user_prompt = "Key: greet_01\nKorean: 안녕하세요"
    api_key = get_xai_api_key()
    if not api_key:
        print("  FAIL: XAI_API_KEY 환경변수 없음")
        return False

    t0 = time.time()
    try:
        items, usage = llm_json_call(system_prompt, user_prompt, api_key, timeout=60)
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        return False
    elapsed = time.time() - t0

    print(f"  OK: {elapsed:.2f}s, items={len(items)}, usage={usage}")
    print(f"  응답: {json.dumps(items, ensure_ascii=False)[:200]}")
    return True


# ── 2) 청크 사이즈별 효율 + 누락률 측정 ──────────────────────────────

SAMPLE_KO_ROWS = [
    "체력 회복 물약",
    "공격력이 {amount}만큼 증가합니다.",
    "전설의 검 <color=#FFD700>엑스칼리버</color>",
    "보스를 처치하면 {gold}골드를 획득합니다.",
    "다음 레벨까지 {exp}/{max}",
    "스킬을 사용할 수 없는 상태입니다.",
    "장비를 강화하시겠습니까?",
    "강화에 실패했습니다.\\n다시 시도하세요.",
    "퀘스트를 완료했습니다!",
    "친구 요청을 보냈습니다.",
    "이 아이템은 거래가 불가능합니다.",
    "남은 시간: {time}",
    "최대 {count}개까지 보관 가능합니다.",
    "상점에서 {item}을(를) 구매했습니다.",
    "일일 보상을 받으세요.",
    "이벤트가 종료되었습니다.",
    "<b>주의</b>: 이 행동은 되돌릴 수 없습니다.",
    "PvP 매칭 중...",
    "%d번째 시도",
    "전투 결과: 승리",
    "캐릭터 이름을 입력하세요.",
    "이미 사용 중인 이름입니다.",
    "비밀번호가 일치하지 않습니다.",
    "서버 점검 중입니다.",
    "업데이트가 필요합니다.",
]


def _build_prompt(rows: list[dict]) -> str:
    return "\n\n---\n\n".join(
        f"Key: {r['key']}\nKorean: {r['ko']}" for r in rows
    )


def chunk_efficiency_test(size: int) -> dict:
    """
    size 행 청크 1회 호출 → 응답 누락률·소요시간·토큰 측정.
    누락률 = (요청 키 수 - 응답에서 발견된 고유 키 수) / 요청 키 수.
    """
    print(f"\n[2/3] 청크 효율 측정 — size={size}")
    items_in = []
    base = SAMPLE_KO_ROWS
    for i in range(size):
        items_in.append({"key": f"k_{i:03d}", "ko": base[i % len(base)]})

    system_prompt = (
        "You translate Korean game text into English. "
        "Preserve formatting tags exactly: {var}, %d, %s, \\n, <color>, <b> etc. "
        'Output JSON array only: [{"key": "...", "translated": "..."}, ...]. '
        "Include EVERY input key in the output, in the same order."
    )

    api_key = get_xai_api_key()
    t0 = time.time()
    try:
        result, usage = llm_json_call_with_split(
            system_prompt=system_prompt,
            items=items_in,
            user_prompt_builder=_build_prompt,
            api_key=api_key,
            timeout=120,
        )
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FAIL ({elapsed:.2f}s): {type(e).__name__}: {e}")
        return {"size": size, "ok": False, "error": str(e)}

    elapsed = time.time() - t0
    requested_keys = {r["key"] for r in items_in}
    returned_keys = {r.get("key", "") for r in result if isinstance(r, dict)}
    missing = requested_keys - returned_keys
    extras = returned_keys - requested_keys
    miss_rate = len(missing) / size

    # 포맷 태그 보존 검사
    tag_violations = 0
    for src in items_in:
        if "{" in src["ko"] or "%" in src["ko"] or "<" in src["ko"] or "\\n" in src["ko"]:
            match = next((r for r in result if r.get("key") == src["key"]), None)
            if match is None:
                continue
            translated = str(match.get("translated", ""))
            for tok in ("{amount}", "{gold}", "{exp}", "{max}", "{time}", "{count}", "{item}",
                        "<color=#FFD700>", "</color>", "<b>", "</b>", "%d", "\\n"):
                if tok in src["ko"] and tok not in translated:
                    tag_violations += 1

    throughput = size / elapsed if elapsed > 0 else 0
    # cached_tokens는 prompt_tokens에 이미 포함 → 차감 후 cached 단가 별도 적용
    non_cached_input = max(usage["input"] - usage["cached"], 0)
    cost_usd = (
        non_cached_input * LLM_PRICING["input"]
        + usage["cached"] * LLM_PRICING["cached_input"]
        + (usage["output"] + usage["reasoning"]) * LLM_PRICING["output"]
    )
    print(f"  OK: {elapsed:.2f}s ({throughput:.1f} 행/s)")
    print(f"  반환: {len(result)}건 / 요청: {size}건 (누락 {len(missing)}, 추가 {len(extras)}, 누락률 {miss_rate*100:.1f}%)")
    print(f"  토큰: in={usage['input']} out={usage['output']} reasoning={usage['reasoning']} cached={usage['cached']}")
    print(f"  태그 손실 의심: {tag_violations}건")
    print(f"  비용 (이 호출): ${cost_usd:.5f}")

    return {
        "size": size,
        "ok": True,
        "elapsed": elapsed,
        "throughput": throughput,
        "returned": len(result),
        "missing": len(missing),
        "extras": len(extras),
        "miss_rate": miss_rate,
        "tag_violations": tag_violations,
        "usage": usage,
        "cost_usd": cost_usd,
    }


# ── 3) JSON 분할 재시도 헬퍼 동작 확인 (의도적 파싱 실패 유도) ─────────

def split_retry_test() -> bool:
    """user_prompt_builder가 raise하여 의도적으로 실패시 분할 재귀가 동작하는지."""
    print("\n[3/4] 분할 재시도 헬퍼 단위 동작 확인 (mock)")
    from utils.llm import llm_json_call_with_split as helper

    # 정상 호출만 모방하여 분할 로직 자체를 점검 (실제 LLM 호출 X)
    fake_items = [{"key": f"k_{i}", "ko": "x"} for i in range(4)]
    call_log = []

    import utils.llm as llm_mod
    original = llm_mod.llm_json_call

    def fake_call(system_prompt, user_prompt, api_key, timeout=120):
        call_log.append(len(user_prompt))
        # 첫 호출(전체) → 파싱 실패 시뮬레이션
        if len(call_log) == 1:
            raise json.JSONDecodeError("truncated", user_prompt, 0)
        return [{"key": "x", "translated": "y"}], {"input": 10, "output": 5, "reasoning": 0, "cached": 0}

    llm_mod.llm_json_call = fake_call
    try:
        result, usage = helper(
            system_prompt="x",
            items=fake_items,
            user_prompt_builder=lambda items: "_".join(it["key"] for it in items),
            api_key="fake",
            timeout=10,
        )
    finally:
        llm_mod.llm_json_call = original

    print(f"  호출 횟수: {len(call_log)} (예상: 1회 실패 + 2회 성공 = 3회)")
    print(f"  합산 usage: {usage}")
    expected_total = {"input": 20, "output": 10, "reasoning": 0, "cached": 0}
    ok = len(call_log) == 3 and usage == expected_total
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def completeness_test() -> bool:
    """
    llm_chunk_with_completeness 검증:
      시나리오 1) 정상 — 모든 키 반환
      시나리오 2) 일부 누락 — 누락분 재요청으로 복구
      시나리오 3) 끝까지 누락 — missing으로 반환
      시나리오 4) 중복 key — 응답 개수 부족 시 정확히 누락 카운트
    """
    print("\n[4/4] llm_chunk_with_completeness 단위 동작 확인 (mock)")
    from utils.llm import llm_chunk_with_completeness as helper

    import utils.llm as llm_mod
    original = llm_mod.llm_json_call

    all_ok = True

    # 시나리오 1: 정상 — 1회 호출, 누락 0
    items = [{"key": f"k_{i}"} for i in range(5)]
    def s1_call(sp, up, ak, timeout=120):
        return ([{"key": f"k_{i}", "translated": f"t_{i}"} for i in range(5)],
                {"input": 100, "output": 50, "reasoning": 10, "cached": 0})
    llm_mod.llm_json_call = s1_call
    pairs, missing, usage = helper("sp", items, lambda x: "p", "ak", lambda r: r["key"])
    s1_ok = len(pairs) == 5 and len(missing) == 0 and usage["input"] == 100
    print(f"  시나리오1 정상: pairs={len(pairs)}, missing={len(missing)}, "
          f"usage_input={usage['input']} → {'OK' if s1_ok else 'FAIL'}")
    all_ok &= s1_ok

    # 시나리오 2: 1차 호출에서 2개 누락 → 재요청 시 모두 반환
    items = [{"key": f"k_{i}"} for i in range(5)]
    call_count = [0]
    def s2_call(sp, up, ak, timeout=120):
        call_count[0] += 1
        if call_count[0] == 1:
            # k_3, k_4 누락
            return ([{"key": f"k_{i}", "translated": f"t_{i}"} for i in range(3)],
                    {"input": 80, "output": 40, "reasoning": 0, "cached": 0})
        # 재요청 — k_3, k_4 반환
        return ([{"key": "k_3", "translated": "t_3"}, {"key": "k_4", "translated": "t_4"}],
                {"input": 30, "output": 15, "reasoning": 0, "cached": 0})
    llm_mod.llm_json_call = s2_call
    pairs, missing, usage = helper("sp", items, lambda x: "p", "ak", lambda r: r["key"])
    s2_ok = (call_count[0] == 2 and len(pairs) == 5 and len(missing) == 0
             and usage["input"] == 110)
    print(f"  시나리오2 부분누락→복구: calls={call_count[0]}, pairs={len(pairs)}, "
          f"missing={len(missing)}, usage_input={usage['input']} → {'OK' if s2_ok else 'FAIL'}")
    all_ok &= s2_ok

    # 시나리오 3: 매번 같은 키만 반환 → 진전 없음 감지 후 중단
    items = [{"key": f"k_{i}"} for i in range(3)]
    def s3_call(sp, up, ak, timeout=120):
        return ([{"key": "k_0", "translated": "t_0"}],
                {"input": 50, "output": 25, "reasoning": 0, "cached": 0})
    llm_mod.llm_json_call = s3_call
    pairs, missing, usage = helper("sp", items, lambda x: "p", "ak", lambda r: r["key"])
    # 1회차에 k_0 매칭 → 잔여 k_1, k_2 재요청 → 또 k_0만 반환되어 진전 없음 → 중단
    s3_ok = len(pairs) == 1 and len(missing) == 2
    print(f"  시나리오3 영구누락: pairs={len(pairs)}, missing={len(missing)} → "
          f"{'OK' if s3_ok else 'FAIL'}")
    all_ok &= s3_ok

    # 시나리오 4: 응답에 노이즈(list 아닌 항목 + 엉뚱한 key) 섞여도 정상 매칭
    items = [{"key": f"k_{i}"} for i in range(3)]
    def s4_call(sp, up, ak, timeout=120):
        return ([
            "not a dict",                              # 무시
            {"key": "unknown", "translated": "junk"},  # 무시 (요청에 없는 key)
            {"key": "k_0", "translated": "t_0"},
            {"key": "k_1", "translated": "t_1"},
            {"key": "k_2", "translated": "t_2"},
        ], {"input": 50, "output": 25, "reasoning": 0, "cached": 0})
    llm_mod.llm_json_call = s4_call
    pairs, missing, usage = helper("sp", items, lambda x: "p", "ak", lambda r: r["key"])
    s4_ok = len(pairs) == 3 and len(missing) == 0
    print(f"  시나리오4 노이즈 응답 무시: pairs={len(pairs)}, missing={len(missing)} → "
          f"{'OK' if s4_ok else 'FAIL'}")
    all_ok &= s4_ok

    # 시나리오 5: 중복 key 정합성 — 같은 key 3개 요청, 응답도 3개. 모두 매칭되어야 함.
    items = [{"key": "dup", "row": i} for i in range(3)]
    def s5_call(sp, up, ak, timeout=120):
        return ([
            {"key": "dup", "translated": "a"},
            {"key": "dup", "translated": "b"},
            {"key": "dup", "translated": "c"},
        ], {"input": 30, "output": 15, "reasoning": 0, "cached": 0})
    llm_mod.llm_json_call = s5_call
    pairs, missing, usage = helper("sp", items, lambda x: "p", "ak", lambda r: r["key"])
    # 순서대로 row=0,1,2 매칭되는지 확인
    s5_ok = (len(pairs) == 3 and len(missing) == 0
             and [p[0]["row"] for p in pairs] == [0, 1, 2]
             and [p[1]["translated"] for p in pairs] == ["a", "b", "c"])
    print(f"  시나리오5 중복key 정합성: pairs={len(pairs)}, "
          f"row_match={[p[0]['row'] for p in pairs]} → {'OK' if s5_ok else 'FAIL'}")
    all_ok &= s5_ok

    llm_mod.llm_json_call = original
    print(f"  종합: {'OK' if all_ok else 'FAIL'}")
    return all_ok


# ── main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"=== 모델 호출 검증 시작 ({LLM_MODEL}) ===")

    s_ok = smoke_test()
    if not s_ok:
        print("\n>>> Smoke test 실패. 모델/키/네트워크 확인 필요.")
        sys.exit(1)

    results = []
    for size in (25, 50, 100):
        r = chunk_efficiency_test(size)
        results.append(r)
        if not r.get("ok"):
            print(f"\n  >>> size={size} 실패로 다음 사이즈 스킵")
            break

    split_ok = split_retry_test()
    complete_ok = completeness_test()

    print("\n=== 요약 ===")
    print(f"모델: {LLM_MODEL}")
    print(f"CHUNK_SIZE (코드 기본값): {CHUNK_SIZE}")
    for r in results:
        if r.get("ok"):
            print(
                f"  size={r['size']:3d}: {r['elapsed']:6.2f}s "
                f"({r['throughput']:5.1f}행/s), "
                f"누락 {r['missing']}/{r['size']} ({r['miss_rate']*100:4.1f}%), "
                f"태그손실 {r['tag_violations']}, "
                f"비용 ${r['cost_usd']:.5f}"
            )
        else:
            print(f"  size={r['size']}: FAIL ({r.get('error')})")
    print(f"분할 재시도 헬퍼: {'OK' if split_ok else 'FAIL'}")
    print(f"Completeness 헬퍼: {'OK' if complete_ok else 'FAIL'}")
