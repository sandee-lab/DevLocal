"""Node 5: 시트 업데이트 (유틸리티) — HITL 2 승인 후 Batch Update 실행"""

from agents.state import LocalizationState
from config.constants import REQUIRED_COLUMNS, SUPPORTED_LANGUAGES, Status, TOOL_STATUS_COLUMN


def writer_node(state: LocalizationState) -> dict:
    """
    최종 승인된 번역 데이터를 시트에 일괄 업데이트할 업데이트 목록 생성.
    실제 시트 쓰기는 app.py에서 batch_update_sheet()를 호출하여 수행.

    안전성: row_index가 None인 항목은 잘못된 위치에 쓰는 것보다 안전하게 스킵.
    """
    review_results = state.get("review_results", [])
    failed_rows = state.get("failed_rows", [])
    original_data = state.get("original_data", [])
    logs = list(state.get("logs", []))

    # 검수실패 row_index 집합 먼저 수집 (Tool_Status 충돌 방지)
    failed_indices: set = set()
    skipped_failed = 0
    for fail in failed_rows:
        ri = fail.get("row_index")
        if ri is None:
            skipped_failed += 1
            continue
        failed_indices.add(ri)

    # 업데이트 목록 생성
    updates = []
    completed_indices: set = set()  # Tool_Status 중복 방지
    skipped_reviews = 0

    # 성공한 번역 결과 반영 — 실제 변경된 셀만
    for result in review_results:
        key = result["key"]
        lang = result["lang"]
        translated = result["translated"]
        row_idx = result.get("row_index")

        if row_idx is None:
            skipped_reviews += 1
            logs.append(
                f"[Node 5] row_index 결손 — 스킵: key={key} lang={lang}"
            )
            continue

        if row_idx >= len(original_data):
            skipped_reviews += 1
            logs.append(
                f"[Node 5] row_index 범위 초과 — 스킵: key={key} lang={lang} row={row_idx}"
            )
            continue

        lang_col = SUPPORTED_LANGUAGES.get(lang, "")
        if not lang_col:
            continue

        # 원본 값과 비교 — 실제로 변경된 경우만 업데이트 & 컬러링
        original_value = original_data[row_idx].get(lang_col, "")
        if translated != original_value:
            updates.append({
                "row_index": row_idx,
                "column_name": lang_col,
                "value": translated,
                "change_type": "translation",
            })

        # Tool_Status: 실패 row가 아닌 경우만 최종완료
        if row_idx not in completed_indices and row_idx not in failed_indices:
            completed_indices.add(row_idx)
            updates.append({
                "row_index": row_idx,
                "column_name": TOOL_STATUS_COLUMN,
                "value": Status.COMPLETED,
                "change_type": "completed",
            })

    # 검수실패 행 마킹
    for fail in failed_rows:
        row_idx = fail.get("row_index")
        if row_idx is None:
            continue  # 위에서 이미 skipped_failed로 카운트됨
        updates.append({
            "row_index": row_idx,
            "column_name": TOOL_STATUS_COLUMN,
            "value": Status.REVIEW_FAILED,
            "change_type": "review_failed",
        })

    changed_count = sum(1 for u in updates if u.get("change_type") == "translation")
    unchanged_count = len(review_results) - changed_count - skipped_reviews
    fail_count = len(failed_rows) - skipped_failed
    logs.append(
        f"[Node 5] 업데이트 준비: 변경 {changed_count}건, 변경없음 {unchanged_count}건, "
        f"실패 {fail_count}건"
    )
    if skipped_reviews or skipped_failed:
        logs.append(
            f"[Node 5] row_index 결손으로 스킵: 번역 {skipped_reviews}건, 실패행 {skipped_failed}건"
        )

    return {
        "_updates": updates,
        "logs": logs,
    }
