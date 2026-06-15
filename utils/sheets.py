"""Google Sheets 유틸리티 — gspread Batch Read/Write + Exponential Backoff"""

import io
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from backend.config import get_gcp_credentials
from config.constants import FORBIDDEN_SHEETS, REQUIRED_COLUMNS, TOOL_STATUS_COLUMN

logger = logging.getLogger("devlocal.sheets")

# ── Retry 설정 ────────────────────────────────────────────────────────

MAX_RETRIES = 5
BASE_DELAY = 1  # seconds


def _retry_with_backoff(fn, *args, **kwargs):
    """Exponential backoff wrapper for gspread API calls."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            status = e.response.status_code if hasattr(e, "response") else 0
            if status == 429 or status >= 500:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "API rate limit/error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, MAX_RETRIES, delay, e,
                )
                time.sleep(delay)
            else:
                raise
    return fn(*args, **kwargs)  # final attempt without catch


# ── 인증 및 연결 ──────────────────────────────────────────────────────

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client() -> gspread.Client:
    """GCP 서비스 계정 인증 → gspread Client."""
    creds_dict = get_gcp_credentials()
    credentials = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(credentials)


def connect_to_sheet(url: str) -> gspread.Spreadsheet:
    """스프레드시트 URL로 연결."""
    client = _get_client()
    return _retry_with_backoff(client.open_by_url, url)


def get_bot_email() -> str:
    """서비스 계정 이메일 반환."""
    creds_dict = get_gcp_credentials()
    return creds_dict.get("client_email", "")


def extract_project_name(spreadsheet: gspread.Spreadsheet) -> str:
    """스프레드시트 제목에서 프로젝트명 추출."""
    return spreadsheet.title


def get_worksheet_names(spreadsheet: gspread.Spreadsheet) -> list[str]:
    """시트 이름 목록 반환 (FORBIDDEN_SHEETS 제외)."""
    worksheets = _retry_with_backoff(spreadsheet.worksheets)
    return [
        ws.title
        for ws in worksheets
        if ws.title not in FORBIDDEN_SHEETS
    ]


# ── 데이터 로드 ──────────────────────────────────────────────────────

def load_sheet_data(worksheet: gspread.Worksheet) -> pd.DataFrame:
    """시트 전체를 1회 벌크 로드 → DataFrame 변환."""
    # numericise_ignore=["all"]: 숫자형 셀의 int/float 자동 변환 비활성화.
    # 숫자 Key(예: Etc 시트의 1001, 1002…)가 int가 되면 LLM 응답의 str key와
    # 매칭에 실패해 전건 "응답 누락 → 검수실패"가 됨. 또한 코드 전반이 셀을
    # 문자열로 가정(.replace()/.strip())하므로 숫자 본문은 AttributeError 유발.
    records = _retry_with_backoff(
        worksheet.get_all_records, numericise_ignore=["all"]
    )
    df = pd.DataFrame(records)
    # 빈 문자열 → NaN 변환하지 않음 (원본 보존)
    return df


def ensure_tool_status_column(
    worksheet: gspread.Worksheet, df: pd.DataFrame
) -> pd.DataFrame:
    """Tool_Status 컬럼 없으면 시트+DataFrame 양쪽에 추가."""
    if TOOL_STATUS_COLUMN not in df.columns:
        df[TOOL_STATUS_COLUMN] = ""
        # 시트에도 헤더 추가
        col_idx = len(df.columns)
        _retry_with_backoff(
            worksheet.update_cell, 1, col_idx, TOOL_STATUS_COLUMN
        )
        logger.info("Tool_Status 컬럼 추가 (col %d)", col_idx)
    return df


# ── 백업 ─────────────────────────────────────────────────────────────

def create_backup_csv(df: pd.DataFrame, sheet_name: str) -> tuple[str, bytes]:
    """DataFrame → (파일명, CSV bytes) 반환. UTF-8-SIG 인코딩."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{sheet_name}_{timestamp}.csv"
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return filename, buf.getvalue()


def save_backup_to_folder(
    df: pd.DataFrame, sheet_name: str, folder: str = "./backups"
) -> str:
    """백업 CSV를 로컬 폴더에 저장. 반환: 파일 경로."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{sheet_name}_{timestamp}.csv"
    filepath = os.path.join(folder, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    logger.info("백업 저장: %s", filepath)
    return filepath


# ── Batch Update / Format ────────────────────────────────────────────

def batch_update_sheet(
    worksheet: gspread.Worksheet,
    updates: list[dict],
    df: pd.DataFrame,
) -> None:
    """
    업데이트 목록을 gspread batch_update로 일괄 반영.

    updates 형식: [{"row_index": int, "column_name": str, "value": str}, ...]
    row_index: 0-based DataFrame 인덱스 → 시트 행은 +2 (헤더 + 1-based)
    """
    if not updates:
        return

    cells = []
    columns = list(df.columns)

    for u in updates:
        row_idx = u["row_index"]
        col_name = u["column_name"]

        if col_name not in columns:
            continue

        col_idx = columns.index(col_name) + 1  # 1-based
        sheet_row = row_idx + 2  # 헤더 + 0-based → 1-based

        cells.append(gspread.Cell(sheet_row, col_idx, u["value"]))

    if cells:
        _retry_with_backoff(worksheet.update_cells, cells)
        logger.info("Batch update: %d cells", len(cells))


# 색상 매핑
_COLOR_MAP = {
    "translation": {"red": 0.878, "green": 0.961, "blue": 0.992},  # #E0F5FE (연파랑)
    "review_failed": {"red": 0.996, "green": 0.886, "blue": 0.886},  # #FEE2E2 (연빨강)
    "completed": {"red": 0.863, "green": 0.988, "blue": 0.906},  # #DCFCE7 (연초록)
}


def batch_format_cells(
    worksheet: gspread.Worksheet,
    updates: list[dict],
    df: pd.DataFrame,
) -> None:
    """
    업데이트된 셀에 배경색 적용 (Sheets API batch).

    change_type: "translation" | "review_failed" | "completed"
    """
    if not updates:
        return

    columns = list(df.columns)
    requests = []
    sheet_id = worksheet.id

    for u in updates:
        change_type = u.get("change_type", "")
        color = _COLOR_MAP.get(change_type)
        if not color:
            continue

        row_idx = u["row_index"]
        col_name = u["column_name"]

        if col_name not in columns:
            continue

        col_idx = columns.index(col_name)
        sheet_row = row_idx + 1  # 0-based (헤더 제외, API는 0-based)

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": sheet_row,
                    "endRowIndex": sheet_row + 1,
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color,
                    }
                },
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    if requests:
        _retry_with_backoff(
            worksheet.spreadsheet.batch_update,
            {"requests": requests},
        )
        logger.info("Batch format: %d cells", len(requests))
