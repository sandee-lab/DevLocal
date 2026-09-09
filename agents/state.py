"""LangGraph State 정의 — LocalizationState TypedDict"""

from typing import Optional, TypedDict


class LocalizationState(TypedDict):
    # 작업 설정
    sheet_name: str
    mode: str  # "A" or "B"
    target_languages: list[str]

    # 데이터
    original_data: list[dict]       # 원본 시트 데이터
    backup_data: list[dict]         # 백업용
    ko_review_results: list[dict]   # 한국어 검수 결과
    translation_results: list[dict] # 번역 결과
    review_results: list[dict]      # 검수 결과
    failed_rows: list[dict]         # 검수실패 행 목록

    # HITL 제어
    ko_approval_result: Optional[str]        # "approved" or "rejected"
    final_approval_result: Optional[str]

    # 진행 상태
    retry_count: dict  # {row_key: retry_count}

    # 비용 추적
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    total_cached_tokens: int

    # 로그
    logs: list[str]

    # 사용자 커스텀 지침 (시트별)
    custom_prompt: str

    # 게임 설정 (Settings UI에서 편집)
    game_synopsis: str
    tone_and_manner: str

    # 내부 전달용
    _updates: list[dict]          # writer → app.py 시트 업데이트 목록
    _needs_retry: list[dict]      # reviewer → translator 재번역 필요 항목
    _ko_review_cached: bool      # 취소 복구 시 빈 검수 결과도 재사용
