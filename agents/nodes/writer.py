"""최종 승인된 결과에서 실제 변경된 셀의 Batch Update 목록을 만든다."""

from agents.state import LocalizationState
from config.constants import SUPPORTED_LANGUAGES, Status, TOOL_STATUS_COLUMN


def writer_node(state: LocalizationState) -> dict:
    original_data = state.get("original_data", [])
    logs = list(state.get("logs", []))
    updates = []
    statuses = {}
    skipped = 0

    def valid_index(index):
        return type(index) is int and 0 <= index < len(original_data)

    def add_change(index, column, value, change_type):
        if original_data[index].get(column, "") != value:
            updates.append({
                "row_index": index, "column_name": column,
                "value": value, "change_type": change_type,
            })

    for result in state.get("review_results", []):
        index = result.get("row_index")
        column = SUPPORTED_LANGUAGES.get(result["lang"])
        if not valid_index(index) or not column:
            skipped += 1
            continue
        add_change(index, column, result["translated"], "translation")
        statuses[index] = (Status.COMPLETED, "completed")

    # 언어별 실패를 행별로 합치고 성공 상태보다 우선한다.
    for failure in state.get("failed_rows", []):
        index = failure.get("row_index")
        if not valid_index(index):
            skipped += 1
            continue
        statuses[index] = (Status.REVIEW_FAILED, "review_failed")

    for index, (status, change_type) in statuses.items():
        add_change(index, TOOL_STATUS_COLUMN, status, change_type)

    logs.append(f"[Node 5] 변경 셀 {len(updates)}개, 유효하지 않은 항목 {skipped}개 제외")
    return {"_updates": updates, "logs": logs}
