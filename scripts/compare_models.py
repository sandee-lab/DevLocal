"""
grok 모델 A/B 비교 스크립트 — 실제 번역 파이프라인과 동일 조건으로 두 모델을 맞대결.

측정 항목 (모델 × 언어별):
  - 응답 누락률 (요청 key 중 미반환 비율)
  - 태그 손실 (utils.validation.validate_tags — 프로덕션과 동일 검증기)
  - 한글 잔존 (utils.validation.check_hangul_residue)
  - 소요 시간 / 처리량 (행/s)
  - 토큰 사용량 (input/output/reasoning/cached) 및 모델별 단가 기준 비용
  - 1000행 환산 예상 비용

공정성 설계:
  - 두 모델에 완전히 동일한 system/user 프롬프트 투입 (agents.prompts + translator 노드 재사용)
  - conv_id를 모델별로 분리하여 캐시 prefix 공유로 인한 편향 제거
  - 재시도 없는 1회 호출(raw first-pass) 기준 — 재시도 보정 전 실력 비교

사용:
  python scripts/compare_models.py                       # 저장된 시트에서 40행, ja/en 비교
  python scripts/compare_models.py --rows 50 --langs ja,en,zh-CN
  python scripts/compare_models.py --sample              # 시트 접근 없이 내장 샘플로
  python scripts/compare_models.py --models xai/grok-4.3,xai/grok-4.6
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_xai_api_key
from config.constants import REQUIRED_COLUMNS, SUPPORTED_LANGUAGES
from config.glossary import format_glossary_text
from agents.prompts import build_translator_prompt
from agents.nodes.translator import _build_translation_prompt, _normalize_translated
from utils.validation import apply_glossary_postprocess, validate_tags, check_hangul_residue
import utils.llm as llm_mod


# ── 모델별 단가 ($/1M tokens, docs.x.ai/developers/models 2026-09 확인) ──
# 주의: 프롬프트 200k 토큰 초과 시 2배 티어가 적용되나, 청크 호출은 해당 없음.
MODEL_PRICING = {
    "xai/grok-4.3": {"input": 1.25, "cached_input": 0.20, "output": 2.50},
    "xai/grok-4.5": {"input": 2.00, "cached_input": 0.30, "output": 6.00},
    "xai/grok-4.6": {"input": 2.00, "cached_input": 0.50, "output": 6.00},
}


SAMPLE_ROWS = [
    ("skill_fire_01", "화염구", "적에게 {damage}의 화염 피해를 입힙니다."),
    ("skill_fire_02", "지옥불", "<color=#FF4400>지옥의 불길</color>이 {sec}초간 지속됩니다."),
    ("item_potion_01", "체력 회복 물약", "체력을 {amount}만큼 회복한다."),
    ("ui_confirm_01", "", "장비를 강화하시겠습니까?\\n실패 시 재료가 소멸합니다."),
    ("ui_error_01", "", "이미 사용 중인 이름입니다."),
    ("quest_main_03", "잃어버린 유산", "노인의 말에 따르면, 그 검은 <b>폐허의 안쪽</b>에 잠들어 있다고 한다."),
    ("dialog_npc_12", "", "어이쿠, 간이 배 밖으로 나왔군! 그 몸으로 던전에 들어가겠다고?"),
    ("rank_name_01", "", "전설"),
    ("rank_name_02", "", "영웅"),
    ("battle_result", "", "전투 결과: 승리 (%d턴)"),
    ("shop_buy_01", "", "상점에서 {item}을(를) 구매했습니다."),
    ("event_end_01", "", "이벤트가 종료되었습니다. 남은 시간: {time}"),
    ("tip_01", "", "티끌 모아 태산! 매일 접속 보상을 잊지 마세요."),
    ("warn_01", "", "<b>주의</b>: 이 행동은 되돌릴 수 없습니다."),
    ("inven_full", "", "최대 {count}개까지 보관 가능합니다."),
]


def load_rows(args, sheet_name: str | None = None) -> list[dict]:
    """시트에서 실제 행을 로드. --sample이거나 접근 실패 시 내장 샘플 사용."""
    key_col = REQUIRED_COLUMNS["key"]
    ko_col = REQUIRED_COLUMNS["korean"]
    sc_col = REQUIRED_COLUMNS["shared_comments"]

    if not args.sample:
        try:
            from utils.sheets import connect_to_sheet, load_sheet_data
            cfg_path = PROJECT_ROOT / ".app_config.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
            url = args.url or cfg.get("saved_url")
            sheet_name = sheet_name or args.sheet or cfg.get("saved_sheet")
            if not url or not sheet_name:
                raise RuntimeError(".app_config.json에 시트 URL/이름 없음")
            print(f"시트 로드: {sheet_name}")
            ss = connect_to_sheet(url)
            df = load_sheet_data(ss.worksheet(sheet_name))
            rows = []
            for i, rec in enumerate(df.to_dict("records")):
                ko = str(rec.get(ko_col, "") or "").strip()
                if not ko:
                    continue
                rows.append({
                    key_col: str(rec.get(key_col, "") or f"row_{i}"),
                    ko_col: ko,
                    sc_col: str(rec.get(sc_col, "") or ""),
                    "_row_index": i,
                })
                if len(rows) >= args.rows:
                    break
            if rows:
                print(f"  → 실제 시트 {len(rows)}행 확보\n")
                return rows
            raise RuntimeError("한국어 원문이 있는 행 없음")
        except Exception as e:
            print(f"시트 로드 실패 ({type(e).__name__}: {e}) → 내장 샘플로 대체\n")

    rows = []
    for i in range(args.rows):
        k, sc, ko = SAMPLE_ROWS[i % len(SAMPLE_ROWS)]
        rows.append({
            key_col: f"{k}_{i:03d}", ko_col: ko, sc_col: sc, "_row_index": i,
        })
    print(f"내장 샘플 {len(rows)}행 사용\n")
    return rows


def run_one(model: str, lang: str, rows: list[dict], api_key: str,
            effort: str | None = None, timeout: int = 180) -> dict:
    """단일 (모델, 언어) 조합 1회 호출 → 지표 산출.

    effort: reasoning_effort (low/medium/high/xhigh). grok-4.6 기본값은 high로
    reasoning 토큰이 폭증하므로, 낮춘 조건도 비교할 수 있게 주입한다.
    """
    key_col = REQUIRED_COLUMNS["key"]
    ko_col = REQUIRED_COLUMNS["korean"]
    label = f"{model.replace('xai/', '')}" + (f"@{effort}" if effort else "")

    system_prompt = build_translator_prompt(lang, format_glossary_text(lang))

    # 모델 주입 — utils.llm이 모듈 전역 LLM_MODEL을 참조하므로 여기서 교체
    original_model = llm_mod.LLM_MODEL
    original_call = llm_mod.llm_json_call
    call_count = [0]

    def counting_call(*a, **kw):
        call_count[0] += 1
        return original_call(*a, **kw)

    def effort_call(system_prompt, user_prompt, api_key, timeout=120, conv_id=None):
        """llm_json_call과 동일 로직 + reasoning_effort 주입."""
        import litellm
        call_count[0] += 1
        response = litellm.completion(
            model=model, api_key=api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=timeout, reasoning_effort=effort,
            extra_headers={"x-grok-conv-id": conv_id} if conv_id else None,
        )
        content = llm_mod._strip_codeblock(response.choices[0].message.content)
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            parsed = [parsed]
        return parsed, llm_mod._extract_usage(response)

    llm_mod.LLM_MODEL = model
    llm_mod.llm_json_call = effort_call if effort else counting_call
    t0 = time.time()
    try:
        items, usage = llm_mod.llm_json_call_with_split(
            system_prompt=system_prompt,
            items=rows,
            user_prompt_builder=lambda subset: _build_translation_prompt(subset, lang),
            api_key=api_key,
            timeout=timeout,
            # 모델별 캐시 분리 — 한쪽이 상대 캐시에 무임승차하지 않도록
            conv_id=f"cmp-{model.replace('/', '-')}-{effort or 'def'}-{lang}",
        )
    except Exception as e:
        return {"model": model, "label": label, "lang": lang, "ok": False,
                "error": f"{type(e).__name__}: {e}", "elapsed": time.time() - t0}
    finally:
        llm_mod.LLM_MODEL = original_model
        llm_mod.llm_json_call = original_call

    elapsed = time.time() - t0

    # 요청-응답 매칭 (프로덕션과 동일하게 key 문자열 정규화 후 순서 매칭)
    by_key: dict[str, list[dict]] = {}
    for r in rows:
        by_key.setdefault(str(r[key_col]), []).append(r)
    consumed: dict[str, int] = {}
    matched: list[tuple[dict, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        k = str(it.get("key", ""))
        bucket = by_key.get(k)
        if not bucket:
            continue
        idx = consumed.get(k, 0)
        if idx < len(bucket):
            matched.append((bucket[idx], _normalize_translated(str(it.get("translated", "")))))
            consumed[k] = idx + 1

    # 품질 검증 — reviewer 노드와 동일 순서 (glossary 후처리 → 태그 → 한글 잔존)
    tag_fail, hangul_fail, empty = 0, 0, 0
    samples = []
    for src, translated in matched:
        translated = apply_glossary_postprocess(translated, lang)
        if not translated.strip():
            empty += 1
        tag_r = validate_tags(src[ko_col], translated)
        han_r = check_hangul_residue(src[ko_col], translated)
        if not tag_r["valid"]:
            tag_fail += 1
        if not han_r["valid"]:
            hangul_fail += 1
        samples.append({
            "key": str(src[key_col]), "ko": src[ko_col], "translated": translated,
            "tag_ok": tag_r["valid"], "hangul_ok": han_r["valid"],
            "errors": tag_r["errors"] + han_r["errors"],
        })

    n = len(rows)
    missing = n - len(matched)
    price = MODEL_PRICING.get(model, MODEL_PRICING["xai/grok-4.3"])
    non_cached = max(usage["input"] - usage["cached"], 0)
    cost = (
        non_cached * price["input"]
        + usage["cached"] * price["cached_input"]
        + (usage["output"] + usage["reasoning"]) * price["output"]
    ) / 1_000_000

    return {
        "model": model, "label": label, "effort": effort,
        "lang": lang, "ok": True, "rows": n,
        "elapsed": elapsed, "throughput": n / elapsed if elapsed else 0,
        "api_calls": call_count[0],
        "matched": len(matched), "missing": missing, "miss_rate": missing / n,
        "empty": empty, "tag_fail": tag_fail, "hangul_fail": hangul_fail,
        "defect_rate": (missing + tag_fail + hangul_fail + empty) / n,
        "usage": usage, "cost_usd": cost, "cost_per_1k_rows": cost / n * 1000,
        "samples": samples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="xai/grok-4.3,xai/grok-4.6")
    ap.add_argument("--langs", default="ja,en")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--sheets", default=None, help="여러 시트 비교 (쉼표 구분)")
    ap.add_argument("--repeat", type=int, default=1, help="동일 조건 반복 횟수")
    ap.add_argument("--url", default=None)
    ap.add_argument("--sample", action="store_true", help="시트 대신 내장 샘플 사용")
    ap.add_argument("--out", default=None, help="결과 JSON 저장 경로")
    ap.add_argument("--timeout", type=int, default=180, help="호출 타임아웃(초)")
    args = ap.parse_args()

    # "xai/grok-4.6@low" 형태로 reasoning_effort 지정 가능
    specs = []
    for m in args.models.split(","):
        m = m.strip()
        if not m:
            continue
        name, _, eff = m.partition("@")
        specs.append((name, eff or None))
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    for lg in langs:
        if lg not in SUPPORTED_LANGUAGES:
            print(f"지원하지 않는 언어: {lg}")
            sys.exit(1)

    api_key = get_xai_api_key()
    if not api_key:
        print("XAI_API_KEY 없음")
        sys.exit(1)

    sheets = [s.strip() for s in (args.sheets or args.sheet or "").split(",") if s.strip()] or [None]
    labels = [n.replace("xai/", "") + (f"@{e}" if e else "") for n, e in specs]
    out = Path(args.out) if args.out else PROJECT_ROOT / "scripts" / "_compare_result.json"

    # 시트는 1회만 로드 후 반복 재사용 (Sheets API 호출 절약)
    rows_by_sheet = {s: load_rows(args, s) for s in sheets}
    total_calls = len(sheets) * args.repeat * len(langs) * len(specs)
    print(f"=== 모델 비교: {' vs '.join(labels)} | 시트 {', '.join(s or 'default' for s in sheets)} "
          f"| 언어 {', '.join(langs)} | {args.repeat}회 반복 | 총 {total_calls}회 호출 ===")

    results = []
    done = 0
    for sheet in sheets:
        rows = rows_by_sheet[sheet]
        for rep in range(1, args.repeat + 1):
            for lang in langs:
                for model, effort in specs:
                    done += 1
                    tag = f"{model}{'@' + effort if effort else ''}"
                    print(f"\n[{done}/{total_calls}] {sheet or 'default'} rep{rep} {tag} / {lang} 호출 중...")
                    r = run_one(model, lang, rows, api_key, effort=effort, timeout=args.timeout)
                    r["sheet"] = sheet
                    r["rep"] = rep
                    results.append(r)
                    # 장시간 실행 중 중단되어도 결과가 남도록 매 호출마다 저장
                    out.write_text(json.dumps({"rows": len(rows), "results": results},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
                    if not r["ok"]:
                        print(f"  FAIL ({r['elapsed']:.1f}s): {r['error']}")
                        continue
                    u = r["usage"]
                    print(f"  {r['elapsed']:.1f}s ({r['throughput']:.1f}행/s, API {r['api_calls']}회)  "
                          f"누락 {r['missing']}  태그손실 {r['tag_fail']}  "
                          f"한글잔존 {r['hangul_fail']}  빈값 {r['empty']}")
                    print(f"  토큰 in={u['input']}(cached {u['cached']}) out={u['output']} "
                          f"reasoning={u['reasoning']}  →  ${r['cost_usd']:.5f} "
                          f"(1000행 환산 ${r['cost_per_1k_rows']:.3f})")

    # ── 요약 표 ──
    print("\n=== 요약 ===")
    header = (f"{'시트':<10}{'rep':<5}{'모델':<18}{'언어':<8}{'시간':>8}{'행/s':>7}{'누락':>6}"
              f"{'태그':>6}{'한글':>6}{'결함률':>9}{'/1000행$':>11}")
    print(header)
    print("-" * 100)
    for r in results:
        name = r.get("label") or r["model"].replace("xai/", "")
        sh = (r.get("sheet") or "default")[:9]
        if not r["ok"]:
            print(f"{sh:<10}{r.get('rep', 1):<5}{name:<18}{r['lang']:<8}  FAIL: {r['error'][:45]}")
            continue
        print(f"{sh:<10}{r.get('rep', 1):<5}{name:<18}{r['lang']:<8}{r['elapsed']:>7.1f}s"
              f"{r['throughput']:>7.1f}{r['missing']:>6}{r['tag_fail']:>6}{r['hangul_fail']:>6}"
              f"{r['defect_rate'] * 100:>8.1f}%{r['cost_per_1k_rows']:>11.3f}")

    def _agg(rs: list, title: str) -> None:
        for label in labels:
            sel = [r for r in rs if r.get("label") == label]
            ok = [r for r in sel if r["ok"]]
            fails = len(sel) - len(ok)
            if not ok:
                print(f"  {label}: 전건 실패 ({fails}건)")
                continue
            tot_rows = sum(r["rows"] for r in ok)
            defects = sum(r["missing"] + r["tag_fail"] + r["hangul_fail"] + r["empty"] for r in ok)
            cost = sum(r["cost_usd"] for r in ok)
            elapsed = sum(r["elapsed"] for r in ok)
            calls = sum(r["api_calls"] for r in ok)
            print(f"  {label:<16} 결함 {defects:>3}/{tot_rows:<5} ({defects / tot_rows * 100:>4.1f}%)  "
                  f"실패 {fails}  API {calls:>3}회  총 {elapsed:>6.1f}s  "
                  f"1000행 환산 ${cost / tot_rows * 1000:.3f}")

    for sheet in sheets:
        print(f"\n=== 시트별 집계: {sheet or 'default'} ===")
        _agg([r for r in results if r.get("sheet") == sheet], sheet or "default")

    print("\n=== 전체 총계 ===")
    _agg(results, "전체")

    print(f"\n상세 결과 저장: {out}")


if __name__ == "__main__":
    main()
