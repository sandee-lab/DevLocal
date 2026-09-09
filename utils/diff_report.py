"""Diff 리포트 CSV 생성 — 한국어 교정 / 번역 변경 리포트"""

import io
from collections import defaultdict, deque

import pandas as pd


def generate_ko_diff_report(
    original_rows: list[dict],
    revised_rows: list[dict],
) -> tuple[pd.DataFrame, bytes]:
    """
    한국어 교정 Diff 리포트 생성.

    original_rows: [{"Key": str, "Korean(ko)": str}, ...]
    revised_rows:  [{"Key": str, "Korean(ko)": str}, ...]

    변경된 행만 포함. 반환: (DataFrame, csv_bytes)
    """
    original_map = defaultdict(deque)
    for row in original_rows:
        original_map[row.get("row_index", row["Key"])].append(row.get("Korean(ko)", ""))

    diff_records = []
    for row in revised_rows:
        key = row.get("Key", "")
        revised = row.get("Korean(ko)", "")
        originals = original_map[row.get("row_index", key)]
        original = originals.popleft() if originals else ""

        if original != revised:
            diff_records.append({
                "Key": key,
                "기존 한국어": original,
                "교정 한국어": revised,
            })

    df = pd.DataFrame(diff_records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return df, buf.getvalue()


def generate_translation_diff_report(
    old_trans: list[dict],
    new_trans: list[dict],
) -> tuple[pd.DataFrame, bytes]:
    """
    번역 변경 Diff 리포트 생성.

    old_trans: [{"Key": str, "lang": str, "old": str}, ...]
    new_trans: [{"Key": str, "lang": str, "new": str, "reason": str}, ...]

    반환: (DataFrame, csv_bytes)
    """
    # 행 번호 우선, 없는 레거시 호출은 동일 Key의 등장 순서를 보존한다.
    old_map = defaultdict(deque)
    for row in old_trans:
        old_map[(row.get("row_index", row["Key"]), row["lang"])].append(row.get("old", ""))

    diff_records = []
    for row in new_trans:
        key = row.get("Key", "")
        lang = row.get("lang", "")
        new_val = row.get("new", "")
        reason = row.get("reason", "")
        originals = old_map[(row.get("row_index", key), lang)]
        old_val = originals.popleft() if originals else ""

        diff_records.append({
            "Key": key,
            "언어": lang,
            "기존 번역": old_val,
            "새 번역": new_val,
            "변경 사유/내역": reason,
        })

    df = pd.DataFrame(diff_records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return df, buf.getvalue()
