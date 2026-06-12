"""Pydantic 요청/응답 스키마"""

from typing import Optional
from pydantic import BaseModel


class ConnectRequest(BaseModel):
    sheet_url: str


class ConnectResponse(BaseModel):
    sheet_names: list
    bot_email: str
    project_name: str = ""


class StartRequest(BaseModel):
    sheet_url: str
    sheet_name: str
    mode: str = "A"
    target_languages: list = []  # 비어 있으면 시트에 존재하는 모든 지원 언어로 자동 결정
    row_start: int = 0
    row_end: int = 0


class StartResponse(BaseModel):
    session_id: str


class ApprovalRequest(BaseModel):
    decision: str  # "approved" or "rejected"


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
