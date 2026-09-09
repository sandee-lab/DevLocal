"""행 식별자를 보존하는 한국어 검수 결과 매핑."""

from collections import Counter

from config.constants import REQUIRED_COLUMNS


def merge_ko_reviews(original_data: list[dict], reviews: list[dict]) -> list[dict]:
    """모든 원본 행에 검수 결과를 대응시킨다. 중복 Key는 행 번호로만 매칭한다."""
    by_index = {r["row_index"]: r for r in reviews if r.get("row_index") is not None}
    key_counts = Counter(row.get(REQUIRED_COLUMNS["key"], "") for row in original_data)
    by_key = {r["key"]: r for r in reviews if r.get("row_index") is None}
    results = []
    for index, row in enumerate(original_data):
        key = row.get(REQUIRED_COLUMNS["key"], "")
        original = row.get(REQUIRED_COLUMNS["korean"], "")
        row_index = row.get("_row_index", index)
        review = by_index.get(row_index)
        if review is None and key_counts[key] == 1:
            review = by_key.get(key)
        results.append({
            "key": key, "original": original, "revised": original,
            "comment": "", "has_issue": False,
            **(review or {}), "row_index": row_index,
        })
    return results


def reviewed_source_rows(state: dict) -> list[dict]:
    """승인된 한국어 교정을 Translator와 Reviewer에 동일하게 적용한다."""
    rows = state.get("original_data", [])
    if state.get("ko_approval_result") != "approved":
        return rows
    reviews = merge_ko_reviews(rows, state.get("ko_review_results", []))
    return [
        {**row, REQUIRED_COLUMNS["korean"]: review["revised"]}
        for row, review in zip(rows, reviews)
    ]
