"""
영문 번역 비교표(Markdown) 생성 — 담당자 검수용.

compare_models.py가 남긴 결과 JSON에서 EN 번역을 뽑아
모델별로 나란히 놓은 검수 문서를 만든다.

레이아웃:
  - 짧은 텍스트(기본 60자 미만): 표 형식
  - 긴 텍스트: Key별 블록 형식 (표 셀에 넣으면 읽기 불가)
  - 두 모델 번역이 동일한 행은 검수 대상에서 제외하고 건수만 집계

사용:
  python scripts/make_en_report.py scripts/_compare_full3.json -o docs/model-comparison-en.md
  python scripts/make_en_report.py scripts/_compare_mail50.json scripts/_compare_result.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SHORT_LIMIT = 60  # 이 길이 미만이면 표, 이상이면 블록


def esc(text: str) -> str:
    """마크다운 표 셀 안전 처리 — 파이프/개행 이스케이프."""
    return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def collect(paths: list[Path], lang: str) -> tuple[dict, list[str], dict]:
    """
    결과 JSON들에서 (sheet, key) → {label: {translated, tag_ok, hangul_ok}} 수집.
    같은 (sheet, key, label)이 여러 번(반복 실행) 나오면 첫 결과를 대표로 쓰고,
    반복 간 번역이 흔들린 경우 variants에 기록한다.
    """
    data: dict = {}
    labels: list[str] = []
    variants: dict = {}

    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for r in doc.get("results", []):
            if not r.get("ok") or r.get("lang") != lang:
                continue
            label = r.get("label") or r["model"].replace("xai/", "")
            if label not in labels:
                labels.append(label)
            sheet = r.get("sheet") or "default"
            for s in r.get("samples", []):
                slot = data.setdefault((sheet, s["key"]), {"ko": s["ko"], "by": {}})
                prev = slot["by"].get(label)
                if prev is None:
                    slot["by"][label] = {
                        "translated": s["translated"],
                        "tag_ok": s["tag_ok"], "hangul_ok": s["hangul_ok"],
                        "errors": s.get("errors", []),
                    }
                else:
                    # 반복 실행 간 번역이 달라진 경우 — 재현성 참고용으로 수집
                    if prev["translated"] != s["translated"]:
                        variants.setdefault((sheet, s["key"], label), set()).add(s["translated"])
                    # 결함은 한 번이라도 발생하면 결함으로 표시 (보수적 집계)
                    prev["tag_ok"] &= s["tag_ok"]
                    prev["hangul_ok"] &= s["hangul_ok"]
                    if s.get("errors"):
                        prev["errors"] = list({*prev["errors"], *s["errors"]})
    return data, labels, variants


def flag(entry: dict) -> str:
    """자동 검증 결과 표기."""
    if entry is None:
        return "—"
    bad = []
    if not entry["tag_ok"]:
        bad.append("태그")
    if not entry["hangul_ok"]:
        bad.append("한글잔존")
    return "⚠️ " + "/".join(bad) if bad else "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="compare_models.py 결과 JSON 경로")
    ap.add_argument("-o", "--out", default="docs/model-comparison-en.md")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--limit-per-sheet", type=int, default=0, help="시트별 최대 표기 건수 (0=전체)")
    args = ap.parse_args()

    paths = [Path(p) for p in args.inputs]
    for p in paths:
        if not p.exists():
            print(f"입력 파일 없음: {p}")
            sys.exit(1)

    data, labels, variants = collect(paths, args.lang)
    if len(labels) < 2:
        print(f"비교할 모델이 2개 미만입니다: {labels}")
        sys.exit(1)
    a_label, b_label = labels[0], labels[1]

    sheets: dict = {}
    for (sheet, key), slot in data.items():
        sheets.setdefault(sheet, []).append((key, slot))

    out_lines: list[str] = []
    W = out_lines.append

    W(f"# 번역 모델 비교 검수표 — 영문(EN)")
    W("")
    W(f"- 작성일: {date.today().isoformat()}")
    W(f"- 비교 모델: **{a_label}** (현행) vs **{b_label}** (검토 대상)")
    W(f"- 대상 시트: {', '.join(sorted(sheets))}")
    W(f"- 원문·번역은 실제 시트 데이터이며, 동일 프롬프트·동일 조건에서 각 모델이 생성한 결과입니다.")
    W("")
    W("## 검수 방법")
    W("")
    W("1. 두 모델의 번역이 **다른 항목만** 아래에 실었습니다 (동일한 항목은 판단이 필요 없으므로 제외).")
    W("2. 각 항목의 `선택` 칸에 더 나은 쪽을 표기해 주세요 — `A`(현행) / `B`(검토 대상) / `둘다OK` / `둘다NG`.")
    W("3. `자동검증` 칸은 툴이 정규식으로 잡아낸 결함입니다. 태그(`{변수}`, `\\n`, `<color>` 등) 누락과 "
      "한국어 잔존만 기계적으로 검사한 것이라, **문체·의미의 적절성은 사람 판단이 필요합니다**.")
    W("")

    # ── 전체 요약 ──
    total = same = 0
    for rows in sheets.values():
        for _k, slot in rows:
            if a_label in slot["by"] and b_label in slot["by"]:
                total += 1
                if slot["by"][a_label]["translated"] == slot["by"][b_label]["translated"]:
                    same += 1
    diff = total - same
    W("## 요약")
    W("")
    W(f"| 항목 | 값 |")
    W(f"|---|---|")
    W(f"| 비교 대상 행 | {total}행 |")
    W(f"| 두 모델 번역 동일 | {same}행 ({same / total * 100:.0f}%) |")
    W(f"| **번역 상이 (검수 대상)** | **{diff}행 ({diff / total * 100:.0f}%)** |")
    a_bad = sum(1 for rows in sheets.values() for _k, s in rows
                if a_label in s["by"] and flag(s["by"][a_label]) != "OK")
    b_bad = sum(1 for rows in sheets.values() for _k, s in rows
                if b_label in s["by"] and flag(s["by"][b_label]) != "OK")
    W(f"| 자동검증 결함 — {a_label} | {a_bad}행 |")
    W(f"| 자동검증 결함 — {b_label} | {b_bad}행 |")
    W("")

    # ── 시트별 본문 ──
    for sheet in sorted(sheets):
        rows = sheets[sheet]
        pairs = [(k, s) for k, s in rows
                 if a_label in s["by"] and b_label in s["by"]
                 and s["by"][a_label]["translated"] != s["by"][b_label]["translated"]]
        pairs.sort(key=lambda x: x[0])
        if args.limit_per_sheet:
            pairs = pairs[:args.limit_per_sheet]
        if not pairs:
            continue

        short = [(k, s) for k, s in pairs if len(s["ko"]) < SHORT_LIMIT]
        long_ = [(k, s) for k, s in pairs if len(s["ko"]) >= SHORT_LIMIT]

        W(f"## {sheet} 시트 — 상이 {len(pairs)}건")
        W("")

        if short:
            W(f"### 단문 ({len(short)}건)")
            W("")
            W(f"| Key | 원문(KO) | A. {a_label} | B. {b_label} | 자동검증 | 선택 |")
            W("|---|---|---|---|---|---|")
            for k, s in short:
                ea, eb = s["by"][a_label], s["by"][b_label]
                fa, fb = flag(ea), flag(eb)
                chk = "OK" if fa == "OK" and fb == "OK" else f"A:{fa} / B:{fb}"
                W(f"| `{k}` | {esc(s['ko'])} | {esc(ea['translated'])} | "
                  f"{esc(eb['translated'])} | {chk} | |")
            W("")

        if long_:
            W(f"### 장문 ({len(long_)}건)")
            W("")
            for k, s in long_:
                ea, eb = s["by"][a_label], s["by"][b_label]
                W(f"#### `{k}`")
                W("")
                W("**원문(KO)**")
                W("")
                W("```")
                W(s["ko"])
                W("```")
                W("")
                W(f"**A. {a_label}** — 자동검증: {flag(ea)}")
                W("")
                W("```")
                W(ea["translated"])
                W("```")
                W("")
                if not ea["tag_ok"] or not ea["hangul_ok"]:
                    for e in ea["errors"]:
                        W(f"> ⚠️ {e}")
                    W("")
                W(f"**B. {b_label}** — 자동검증: {flag(eb)}")
                W("")
                W("```")
                W(eb["translated"])
                W("```")
                W("")
                if not eb["tag_ok"] or not eb["hangul_ok"]:
                    for e in eb["errors"]:
                        W(f"> ⚠️ {e}")
                    W("")
                W("**선택:** ( ) A  ( ) B  ( ) 둘다OK  ( ) 둘다NG   **의견:**")
                W("")
                W("---")
                W("")

    if variants:
        W("## 참고 — 반복 실행 간 번역이 달라진 항목")
        W("")
        W("같은 모델·같은 원문인데 실행마다 결과가 달랐던 항목입니다. "
          "번역 일관성 참고용이며, 위 표에는 첫 실행 결과를 실었습니다.")
        W("")
        W("| Key | 모델 | 변형 |")
        W("|---|---|---|")
        for (sheet, key, label), vs in sorted(variants.items())[:40]:
            W(f"| `{key}` | {label} | {esc(' / '.join(sorted(vs))[:300])} |")
        W("")

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"작성 완료: {out_path}")
    print(f"  비교 {total}행 / 동일 {same}행 / 상이 {diff}행")
    print(f"  자동검증 결함 — {a_label}: {a_bad}행, {b_label}: {b_bad}행")


if __name__ == "__main__":
    main()
