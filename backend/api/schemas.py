"""Pydantic 요청/응답 스키마"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ConnectRequest(BaseModel):
    sheet_url: str


class ConnectResponse(BaseModel):
    sheet_names: list
    bot_email: str
    project_name: str = ""


class StartRequest(BaseModel):
    sheet_url: str
    sheet_name: str
    mode: Literal["A", "B"] = "A"
    target_languages: list[str] = []  # 비어 있으면 시트에 존재하는 모든 지원 언어
    row_start: int = Field(default=0, ge=0)
    row_end: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.row_end and self.row_start > self.row_end:
            raise ValueError("시작 행은 마지막 행보다 클 수 없습니다")
        return self


class StartResponse(BaseModel):
    session_id: str


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    decisions: dict[str, Literal["accepted", "rejected"]] = {}


class SessionStateResponse(BaseModel):
    session_id: str
    current_step: str
    ko_review_count: int = 0
    review_count: int = 0
    fail_count: int = 0
    cost_summary: Optional[dict] = None
    logs: list = []
    # 세션 복원용
    ko_review_results: Optional[list] = None
    review_results: Optional[list] = None
    failed_rows: Optional[list] = None
    original_rows: Optional[list] = None  # [{key, korean}, ...] — 테이블 복원용
    total_rows: int = 0
    translations_applied: bool = False
    updates_count: int = 0
