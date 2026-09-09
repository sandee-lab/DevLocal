"""게임 로컬라이징 자동화 툴 — Streamlit 메인 앱"""

import uuid

import pandas as pd
import streamlit as st
from langgraph.types import Command

from config.app_config import load_config as _load_config, save_config as _save_config

from agents.graph import build_graph
from config.constants import (
    REQUIRED_COLUMNS,
    SUPPORTED_LANGUAGES,
    Status,
    TOOL_STATUS_COLUMN,
)
from utils.cost import build_cost_summary
from utils.sheets import (
    batch_format_cells,
    batch_update_sheet,
    connect_to_sheet,
    create_backup_csv,
    ensure_tool_status_column,
    get_worksheet_names,
    load_sheet_data,
    save_backup_to_folder,
)
from utils.diff_report import (
    generate_ko_diff_report,
    generate_translation_diff_report,
)
from utils.ui_components import (
    inject_custom_css,
    render_header,
    render_footer,
    render_card_start,
    render_card_end,
    render_done_header,
    render_ko_review_table,
    render_log_terminal,
    render_metric_grid,
    render_overall_progress,
    render_saved_url_inline,
    render_translation_review_table,
)

# ── 페이지 설정 ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="게임 로컬라이징 자동화 툴",
    page_icon="🌐",
    layout="wide",
)

# ── 커스텀 CSS 주입 ──────────────────────────────────────────────────

inject_custom_css()

# ── Session State 초기화 ─────────────────────────────────────────────

_saved_config = _load_config()

_defaults = {
    "thread_id": str(uuid.uuid4()),
    "current_step": "idle",
    "spreadsheet": None,
    "worksheet": None,
    "df": None,
    "backup_csv": None,
    "backup_filename": None,
    "ko_report_df": None,
    "ko_report_csv": None,
    "translation_report_df": None,
    "translation_report_csv": None,
    "logs": [],
    "cost_summary": None,
    "graph_result": None,
    "translations_applied": False,
    # URL 고정 관련 — 로컬 파일에서 복원
    "saved_url": _saved_config.get("saved_url", ""),
    "url_editing": False,
    # 백업 폴더
    "backup_folder": _saved_config.get("backup_folder", "./backups"),
    # 파이프라인 상태
    "pipeline_status": {},
    # 프로그레스바
    "step_progress": {},
}
for key, default in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

if "graph" not in st.session_state:
    graph, checkpointer = build_graph()
    st.session_state.graph = graph


# ── 헬퍼: 번역 phase 스트리밍 실행 ───────────────────────────────────

_PROGRESS_NODES = ["translator", "reviewer", "final_approval"]


def _run_translation_streaming(resume_value: str, config: dict, indicator_slot=None):
    """
    번역 phase를 graph.stream()으로 실행하며 실시간 진행 UI 표시.
    translator → reviewer → final_approval(interrupt) 순서로 진행.
    """
    app_logs = list(st.session_state.logs)
    graph_logs = []
    log_container = st.empty()

    _TRANS_PROGRESS = {
        "translator": {"value": 0.50, "label": "품질 검수 진행중"},
        "reviewer":   {"value": 1.0,  "label": "검수 완료"},
    }

    try:
        for event in st.session_state.graph.stream(
            Command(resume=resume_value), config, stream_mode="updates"
        ):
            if "__interrupt__" in event:
                break

            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # 로그 업데이트 (각 노드는 누적 로그 전체를 반환)
            node_logs = node_output.get("logs", [])
            if node_logs:
                graph_logs = node_logs

            # 파이프라인 상태 업데이트 (내부 추적용)
            if node_name in _PROGRESS_NODES:
                st.session_state.pipeline_status[node_name] = "done"
                st.session_state.pipeline_status[f"{node_name}_text"] = "완료"
                idx = _PROGRESS_NODES.index(node_name)
                if idx + 1 < len(_PROGRESS_NODES):
                    next_node = _PROGRESS_NODES[idx + 1]
                    st.session_state.pipeline_status[next_node] = "active"
                    st.session_state.pipeline_status[f"{next_node}_text"] = "진행중"

            # 인디케이터 내 프로그레스 실시간 업데이트
            if node_name in _TRANS_PROGRESS and indicator_slot:
                p = _TRANS_PROGRESS[node_name]
                st.session_state.step_progress = p
                with indicator_slot.container():
                    render_header("translating", progress=p)

            # 로그 터미널 실시간 갱신
            with log_container.container():
                render_log_terminal(app_logs + graph_logs)

    except Exception as e:
        st.session_state.logs = app_logs + graph_logs
        raise

    # 최종 state 수집
    state_snapshot = st.session_state.graph.get_state(config)
    result = state_snapshot.values

    # 세션 로그 업데이트
    st.session_state.logs = app_logs + graph_logs

    return result


def _process_translation_result(result: dict):
    """번역 결과를 세션 상태에 저장 (리포트, 비용 등)"""
    st.session_state.graph_result = result

    review_results = result.get("review_results", [])
    if review_results:
        old_trans = []
        new_trans = []
        for r in review_results:
            old_trans.append({
                "Key": r["key"],
                "lang": r["lang"],
                "old": r.get("old_translation", ""),
            })
            new_trans.append({
                "Key": r["key"],
                "lang": r["lang"],
                "new": r["translated"],
                "reason": r.get("reason", ""),
            })
        report_df, report_csv = generate_translation_diff_report(
            old_trans, new_trans
        )
        st.session_state.translation_report_df = report_df
        st.session_state.translation_report_csv = report_csv

    # reasoning/cached 토큰까지 포함해야 실제 과금과 맞음 (utils/cost.py 주석 참조)
    st.session_state.cost_summary = build_cost_summary(
        result.get("total_input_tokens", 0),
        result.get("total_output_tokens", 0),
        result.get("total_reasoning_tokens", 0),
        result.get("total_cached_tokens", 0),
    )


# ── 공통 상태 플래그 ──────────────────────────────────────────────────

is_busy = st.session_state.current_step not in ("idle", "done")

# ── 메인 영역 ────────────────────────────────────────────────────────

# 헤더 바 (로고 + 5단계 스텝 인디케이터)
_header_slot = st.empty()
_step_progress_for_header = st.session_state.get("step_progress", {})
with _header_slot.container():
    render_header(st.session_state.current_step, progress=_step_progress_for_header)

# _indicator_slot은 스트리밍 중 실시간 업데이트에 사용 (_header_slot과 동일)
_indicator_slot = _header_slot

# ── Data Source Configuration (idle 상태에서만 카드 표시, 변수는 항상 정의) ──

# 기본값 초기화 (non-idle 상태 fallback)
selected_sheet = st.session_state.get("_last_sheet", None)
target_langs = list(SUPPORTED_LANGUAGES.keys())
mode = "A"
row_limit = 0
backup_folder = st.session_state.backup_folder
start_button = False
cancel_button = False
sheet_url = st.session_state.saved_url


if st.session_state.current_step == "idle":
    # ── 시트 연결 로직 ──
    sheet_names = []
    connected = False

    if st.session_state.saved_url and not st.session_state.url_editing:
        sheet_url = st.session_state.saved_url
        _url_is_saved = True
    else:
        _url_is_saved = False

    if sheet_url:
        try:
            if (
                st.session_state.spreadsheet is None
                or st.session_state.get("_last_url") != sheet_url
            ):
                with st.spinner("시트 연결 중..."):
                    st.session_state.spreadsheet = connect_to_sheet(sheet_url)
                    st.session_state._last_url = sheet_url
            sheet_names = get_worksheet_names(st.session_state.spreadsheet)
            connected = True
        except Exception as e:
            connected = False
            st.error(f"연결 실패: {e}")

    # ── Connection Badge HTML ──
    if connected:
        _badge_html = (
            f'<span class="connection-badge success" style="margin-left:auto;">'
            f'&#9679; Connected &middot; {len(sheet_names)} sheets</span>'
        )
    else:
        _badge_html = (
            '<span class="connection-badge error" style="margin-left:auto;">'
            '&#9679; Not Connected</span>'
        )

    # ── 카드 시작 ──
    render_card_start("&#9881;", "Data Source Configuration", "")
    # Connection badge를 카드 헤더 뒤에 표시
    st.markdown(_badge_html, unsafe_allow_html=True)

    # ── Google Sheet URL ──
    if _url_is_saved:
        render_saved_url_inline(st.session_state.saved_url)
        if st.button("Change URL", use_container_width=False, disabled=is_busy):
            st.session_state.url_editing = True
            st.rerun()
    else:
        sheet_url = st.text_input(
            "Google Sheet URL",
            value=st.session_state.saved_url,
            placeholder="https://docs.google.com/spreadsheets/d/...",
            disabled=is_busy,
        )
        if sheet_url and sheet_url != st.session_state.saved_url:
            st.session_state.saved_url = sheet_url
            st.session_state.url_editing = False
            st.session_state.spreadsheet = None
            _save_config({"saved_url": sheet_url})
            st.rerun()
        elif sheet_url and st.session_state.url_editing:
            st.session_state.url_editing = False

    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

    # ── Sheet Tab + Row Limit (2 columns) ──
    col_sheet, col_mode = st.columns(2)

    with col_sheet:
        selected_sheet = st.selectbox(
            "Sheet Tab",
            options=sheet_names,
            disabled=not sheet_names or is_busy,
        )

    with col_mode:
        mode = st.radio(
            "Mode",
            options=["A", "B"],
            format_func=lambda x: "Full Translation" if x == "A" else "New Only",
            horizontal=True,
            help="A: 기존 번역 유무와 상관없이 전체 재번역\nB: 빈칸만 번역 (비용 절감)",
            disabled=not connected or is_busy,
        )

    # ── Target Languages ──
    target_langs = st.multiselect(
        "Target Languages",
        options=list(SUPPORTED_LANGUAGES.keys()),
        default=list(SUPPORTED_LANGUAGES.keys()),
        format_func=lambda x: f"{x.upper()} ({SUPPORTED_LANGUAGES[x]})",
        disabled=not connected or is_busy,
    )

    # ── Advanced Settings (expander) ──
    with st.expander("Advanced Settings"):
        adv_col1, adv_col2 = st.columns(2)
        with adv_col1:
            row_limit = st.number_input(
                "Row Limit (0 = all)",
                min_value=0,
                max_value=1000,
                value=0,
                disabled=not connected or is_busy,
            )
        with adv_col2:
            backup_folder = st.text_input(
                "Backup Folder",
                value=st.session_state.backup_folder,
                placeholder="./backups",
                disabled=not connected or is_busy,
            )
            if backup_folder and backup_folder != st.session_state.backup_folder:
                st.session_state.backup_folder = backup_folder
                _save_config({"backup_folder": backup_folder})

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

    # ── Start Button ──
    start_button = st.button(
        "Start Translation",
        type="primary",
        disabled=(not sheet_url or not selected_sheet or not target_langs),
        use_container_width=True,
    )

    render_card_end()

elif is_busy:
    # ── 작업 중: Cancel 버튼만 표시 ──
    cancel_button = st.button(
        "Cancel",
        use_container_width=True,
    )

# ── 작업 시작 처리 ────────────────────────────────────────────────────

if start_button:
    # 이전 작업 상태 초기화 (재실행 허용)
    if st.session_state.current_step != "idle":
        for key in [
            "worksheet", "df", "backup_csv", "backup_filename",
            "ko_report_df", "ko_report_csv",
            "translation_report_df", "translation_report_csv",
            "graph_result", "cost_summary", "translations_applied",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        graph, checkpointer = build_graph()
        st.session_state.graph = graph

    st.session_state.current_step = "loading"
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.logs = []
    st.session_state.pipeline_status = {}

    try:
        ws = st.session_state.spreadsheet.worksheet(selected_sheet)
        df = load_sheet_data(ws)
        df = ensure_tool_status_column(ws, df)

        if row_limit > 0:
            df = df.head(row_limit)

        st.session_state.worksheet = ws
        st.session_state.df = df

        # Tool_Status 초기값 '대기' 설정 + 시트에 반영
        status_updates = []
        for idx, row in df.iterrows():
            current_status = row.get(TOOL_STATUS_COLUMN, "")
            if not current_status:
                df.at[idx, TOOL_STATUS_COLUMN] = Status.WAITING
                status_updates.append({
                    "row_index": idx,
                    "column_name": TOOL_STATUS_COLUMN,
                    "value": Status.WAITING,
                })
        if status_updates:
            batch_update_sheet(ws, status_updates, df)

        st.session_state._last_sheet = selected_sheet

        # 백업: 메모리(다운로드용) + 로컬 폴더 자동 저장
        filename, csv_bytes = create_backup_csv(df, selected_sheet)
        st.session_state.backup_filename = filename
        st.session_state.backup_csv = csv_bytes

        save_backup_to_folder(
            df, selected_sheet, st.session_state.backup_folder
        )

        initial_state = {
            "sheet_name": selected_sheet,
            "mode": mode,
            "target_languages": target_langs,
            "original_data": [{**row, "_row_index": i} for i, row in enumerate(df.to_dict("records"))],
            "backup_data": df.to_dict("records"),
            "ko_review_results": [],
            "translation_results": [],
            "review_results": [],
            "failed_rows": [],
            "ko_approval_result": None,
            "final_approval_result": None,
            "retry_count": {},
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "logs": [],
            "_updates": [],
            "_needs_retry": [],
        }

        # 취소 시 복구용으로 initial_state 저장
        st.session_state._initial_state = initial_state

        config = {"configurable": {"thread_id": st.session_state.thread_id}}

        # 파이프라인 상태: data_backup 실행 시작
        st.session_state.pipeline_status = {
            "data_backup": "active",
        }

        # 스트리밍으로 실행 — 노드별 실시간 프로그레스 업데이트
        _INIT_NODES = ["data_backup", "context_glossary", "ko_review", "ko_approval"]
        _INIT_PROGRESS = {
            "data_backup":      {"value": 0.25, "label": "컨텍스트 로드 중"},
            "context_glossary": {"value": 0.50, "label": "한국어 검수 분석 중"},
            "ko_review":        {"value": 0.90, "label": "승인 대기"},
        }
        graph_logs = []
        log_container = st.empty()

        # 초기 프로그레스 표시 (인디케이터 내부에 통합)
        st.session_state.step_progress = {"value": 0, "label": "데이터 확인 중"}
        with _indicator_slot.container():
            render_header("loading", progress=st.session_state.step_progress)

        for event in st.session_state.graph.stream(
            initial_state, config=config, stream_mode="updates"
        ):
            if "__interrupt__" in event:
                break

            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # 로그 수집
            node_logs = node_output.get("logs", [])
            if node_logs:
                graph_logs = node_logs

            # 파이프라인 내부 상태 업데이트 (추적용)
            if node_name in _INIT_NODES:
                st.session_state.pipeline_status[node_name] = "done"
                idx = _INIT_NODES.index(node_name)
                if idx + 1 < len(_INIT_NODES):
                    next_node = _INIT_NODES[idx + 1]
                    st.session_state.pipeline_status[next_node] = "active"

            # 인디케이터 내 프로그레스 실시간 업데이트
            if node_name in _INIT_PROGRESS:
                p = _INIT_PROGRESS[node_name]
                st.session_state.step_progress = p
                with _indicator_slot.container():
                    render_header("loading", progress=p)

            # 로그 터미널 실시간 갱신
            with log_container.container():
                render_log_terminal(graph_logs)

        # 최종 state 수집
        state_snapshot = st.session_state.graph.get_state(config)
        result = state_snapshot.values
        st.session_state.graph_result = result
        st.session_state.logs.extend(graph_logs)

        # ko_approval 승인 대기 상태로 설정
        st.session_state.pipeline_status["ko_approval"] = "active"
        st.session_state.pipeline_status["ko_approval_text"] = "승인 대기"
        st.session_state.step_progress = {}  # 프로그레스바 숨김

        ko_results = result.get("ko_review_results", [])
        if ko_results:
            original_rows = [
                {
                    "Key": r.get(REQUIRED_COLUMNS["key"], ""),
                    "Korean(ko)": r.get(REQUIRED_COLUMNS["korean"], ""),
                }
                for r in df.to_dict("records")
            ]
            revised_rows = [
                {
                    "Key": r["key"],
                    "Korean(ko)": r.get("revised", r.get("original", "")),
                }
                for r in ko_results
            ]
            report_df, report_csv = generate_ko_diff_report(
                original_rows, revised_rows
            )
            st.session_state.ko_report_df = report_df
            st.session_state.ko_report_csv = report_csv

        st.session_state.current_step = "ko_review"

    except Exception as e:
        st.error(f"오류 발생: {e}")
        st.session_state.logs.append(f"오류: {e}")
        st.session_state.current_step = "idle"

    st.rerun()

# ── 작업 취소 처리 ────────────────────────────────────────────────────

if cancel_button:
    for key in [
        "worksheet", "df", "backup_csv", "backup_filename",
        "ko_report_df", "ko_report_csv",
        "translation_report_df", "translation_report_csv",
        "graph_result", "cost_summary", "translations_applied",
    ]:
        if key in st.session_state:
            del st.session_state[key]
    graph, checkpointer = build_graph()
    st.session_state.graph = graph
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.current_step = "idle"
    st.session_state.pipeline_status = {}
    st.session_state.logs.append("사용자가 작업을 취소했습니다.")
    st.rerun()

# ── HITL 1: 한국어 검수 승인 ──────────────────────────────────────────

if st.session_state.current_step == "ko_review":
    ko_count = (
        len(st.session_state.ko_report_df)
        if st.session_state.ko_report_df is not None
        and not st.session_state.ko_report_df.empty
        else 0
    )

    btn_approve = False
    btn_reject = False

    if ko_count > 0:
        # 수정 제안이 있을 때만 카드 표시
        render_card_start(
            "✏️",
            "한국어 사전 검수",
            f"수정 제안 {ko_count}건",
        )
        render_ko_review_table(st.session_state.ko_report_df)

        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="한국어 변경 리포트 (CSV)",
            data=st.session_state.ko_report_csv,
            file_name="ko_review_report.csv",
            mime="text/csv",
        )

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            btn_approve = st.button(
                "변경 사항 승인 및 번역 시작",
                type="primary",
                use_container_width=True,
            )
        with col2:
            btn_reject = st.button(
                "제안 무시하고 원본 그대로 번역",
                use_container_width=True,
            )

        render_card_end()

    # 수정 제안 0건이면 자동 승인 → 바로 번역 시작
    _auto_approve = (ko_count == 0)

    # 버튼 핸들러 — 승인 결과 저장 후 translating 단계로 전환
    if btn_approve or btn_reject or _auto_approve:
        resume_value = "approved" if (btn_approve or _auto_approve) else "rejected"
        st.session_state._ko_resume_value = resume_value

        # 시트 상태 업데이트
        if st.session_state.worksheet and st.session_state.df is not None:
            _df = st.session_state.df
            _ws = st.session_state.worksheet
            if btn_approve or _auto_approve:
                _upd = [
                    {"row_index": i, "column_name": TOOL_STATUS_COLUMN,
                     "value": Status.KO_REVIEW_DONE}
                    for i in range(len(_df))
                ]
                batch_update_sheet(_ws, _upd, _df)
            _upd2 = [
                {"row_index": i, "column_name": TOOL_STATUS_COLUMN,
                 "value": Status.TRANSLATING}
                for i in range(len(_df))
            ]
            batch_update_sheet(_ws, _upd2, _df)

        st.session_state.current_step = "translating"
        st.session_state.pipeline_status.update({
            "ko_approval": "done",
            "ko_approval_text": "승인됨" if (btn_approve or _auto_approve) else "스킵",
            "translator": "active",
            "translator_text": "진행중",
        })
        st.session_state.step_progress = {"value": 0, "label": "AI 번역 진행중"}
        st.rerun()

# ── 번역 진행 (translating 단계) ─────────────────────────────────────

if st.session_state.current_step == "translating":
    # 로그 영역 먼저 확보 → 취소 버튼은 로그 아래에 표시
    _streaming_area = st.container()

    btn_cancel_translation = st.button(
        "번역 취소 — 한국어 검수로 돌아가기",
        use_container_width=True,
    )

    if btn_cancel_translation:
        # 그래프 재생성 + 초기 phase 재실행하여 ko_approval interrupt 도달
        graph, _ = build_graph()
        st.session_state.graph = graph
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.logs.append("번역 취소 — 한국어 검수 단계로 복귀 중...")

        _init_state = st.session_state.get("_initial_state")
        if _init_state:
            _cfg = {"configurable": {"thread_id": st.session_state.thread_id}}
            try:
                for _ev in st.session_state.graph.stream(
                    _init_state, config=_cfg, stream_mode="updates"
                ):
                    if "__interrupt__" in _ev:
                        break
                st.session_state.pipeline_status = {
                    "data_backup": "done",
                    "context_glossary": "done",
                    "ko_review": "done",
                    "ko_approval": "active",
                    "ko_approval_text": "승인 대기",
                }
                st.session_state.logs.append("한국어 검수 단계로 복귀 완료")
                st.session_state.current_step = "ko_review"
            except Exception as e:
                st.session_state.logs.append(f"복귀 오류: {e} — 초기화합니다.")
                st.session_state.current_step = "idle"
                st.session_state.pipeline_status = {}
        else:
            st.session_state.current_step = "idle"
            st.session_state.pipeline_status = {}

        st.rerun()

    # 스트리밍 실행 — _streaming_area 안에서 로그 렌더, 취소 버튼은 그 아래
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    resume_value = st.session_state.get("_ko_resume_value", "approved")

    with _streaming_area:
        try:
            result = _run_translation_streaming(resume_value, config, _indicator_slot)
            _process_translation_result(result)
            st.session_state.pipeline_status.update({
                "translator": "done",
                "reviewer": "done",
                "final_approval": "active",
                "final_approval_text": "승인 대기",
            })
            st.session_state.current_step = "final_review"
        except Exception as e:
            st.session_state.logs.append(f"번역 오류: {e}")
            graph, _ = build_graph()
            st.session_state.graph = graph
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.current_step = "idle"

    st.rerun()

# ── HITL 2: 최종 번역 승인 ────────────────────────────────────────────

if st.session_state.current_step == "final_review":
    review_count = (
        len(st.session_state.translation_report_df)
        if st.session_state.translation_report_df is not None
        and not st.session_state.translation_report_df.empty
        else 0
    )
    fail_count = (
        len(st.session_state.graph_result.get("failed_rows", []))
        if st.session_state.graph_result
        else 0
    )
    render_card_start(
        "🔍",
        "최종 번역 검토",
        f"변경 {review_count}건 · 실패 {fail_count}건",
    )

    # Overall progress bar (success vs fail ratio)
    # NOTE: review_count = 변경된 행 수, fail_count = 검수실패 행 수 (모집단이 다를 수 있음)
    success_count = max(review_count - fail_count, 0)
    render_overall_progress(success_count, fail_count)

    if review_count > 0:
        # Extract failed_keys for status badges
        failed_keys = set()
        if st.session_state.graph_result:
            for fr in st.session_state.graph_result.get("failed_rows", []):
                if "Key" in fr:
                    failed_keys.add(fr["Key"])

        render_translation_review_table(
            st.session_state.translation_report_df,
            failed_keys=failed_keys,
        )
        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="번역 변경 리포트 (CSV)",
            data=st.session_state.translation_report_csv,
            file_name="translation_diff_report.csv",
            mime="text/csv",
        )
    else:
        st.info("변경 사항 없음")

    if fail_count > 0:
        st.warning(
            f"검수 실패: {fail_count}건 — 아래 행은 검증 통과 실패"
        )
        failed_df = pd.DataFrame(
            st.session_state.graph_result.get("failed_rows", [])
        )
        st.dataframe(failed_df, use_container_width=True)
        failed_csv = failed_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="검수 실패 행 (CSV)",
            data=failed_csv,
            file_name="review_failed_rows.csv",
            mime="text/csv",
        )

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "시트에 최종 업데이트 적용",
            type="primary",
            use_container_width=True,
        ):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            st.session_state.pipeline_status.update({
                "final_approval": "done",
                "final_approval_text": "승인됨",
                "writer": "active",
                "writer_text": "업데이트 중",
            })
            with st.spinner("시트 업데이트 중..."):
                try:
                    result = st.session_state.graph.invoke(
                        Command(resume="approved"), config=config
                    )
                    st.session_state.graph_result = result
                    st.session_state.logs.extend(result.get("logs", []))

                    updates = result.get("_updates", [])
                    if (
                        updates
                        and st.session_state.worksheet
                        and st.session_state.df is not None
                    ):
                        batch_update_sheet(
                            st.session_state.worksheet,
                            updates,
                            st.session_state.df,
                        )
                        # 변경된 셀 하이라이트 적용
                        try:
                            batch_format_cells(
                                st.session_state.worksheet,
                                updates,
                                st.session_state.df,
                            )
                        except Exception:
                            pass  # 포맷팅 실패는 무시 (데이터 업데이트는 이미 완료)
                        st.session_state.logs.append(
                            f"시트 업데이트 완료: {len(updates)}건"
                        )

                    st.session_state.pipeline_status.update({
                        "writer": "done",
                        "writer_text": "완료",
                    })
                    st.session_state.translations_applied = True
                    st.session_state.current_step = "done"
                except Exception as e:
                    st.error(f"시트 업데이트 오류: {e}")
                    st.session_state.logs.append(f"업데이트 오류: {e}")
            st.rerun()

    with col2:
        if st.button("적용 취소 (시트 원복)", use_container_width=True):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            try:
                st.session_state.graph.invoke(
                    Command(resume="rejected"), config=config
                )
            except Exception:
                pass

            # Tool_Status 컬럼을 원래 상태로 복원
            if (
                st.session_state.worksheet is not None
                and st.session_state.df is not None
            ):
                _ws = st.session_state.worksheet
                _df = st.session_state.df
                backup_data = st.session_state.graph_result.get("backup_data", []) if st.session_state.graph_result else []
                revert_updates = []
                for i in range(len(_df)):
                    original_status = ""
                    if i < len(backup_data):
                        original_status = backup_data[i].get(TOOL_STATUS_COLUMN, "")
                    revert_updates.append({
                        "row_index": i,
                        "column_name": TOOL_STATUS_COLUMN,
                        "value": original_status,
                    })
                if revert_updates:
                    try:
                        batch_update_sheet(_ws, revert_updates, _df)
                        st.session_state.logs.append(
                            f"Tool_Status 원복 완료: {len(revert_updates)}건"
                        )
                    except Exception as e:
                        st.session_state.logs.append(f"Tool_Status 원복 오류: {e}")

            st.session_state.translations_applied = False
            st.session_state.current_step = "done"
            st.session_state.logs.append("적용 취소 — 시트가 원래 상태로 복원되었습니다")
            st.rerun()

    render_card_end()

# ── 완료 화면 ─────────────────────────────────────────────────────────

if st.session_state.current_step == "done":
    if st.session_state.get("translations_applied"):
        render_card_start("✅", "작업 완료", "번역이 시트에 적용되었습니다")
    else:
        render_card_start("↩️", "작업 완료", "적용 취소 — 시트가 원래 상태로 복원되었습니다")
    render_done_header()

    # 메트릭 그리드
    if st.session_state.cost_summary:
        summary = st.session_state.cost_summary
        input_t = summary.get("input_tokens", 0)
        output_t = summary.get("output_tokens", 0)
        reasoning_t = summary.get("reasoning_tokens", 0)
        cached_t = summary.get("cached_tokens", 0)
        cost = summary.get("estimated_cost_usd", 0)

        review_count = 0
        if (
            st.session_state.translation_report_df is not None
            and not st.session_state.translation_report_df.empty
        ):
            review_count = len(st.session_state.translation_report_df)

        fail_count = 0
        if st.session_state.graph_result:
            fail_count = len(st.session_state.graph_result.get("failed_rows", []))

        render_metric_grid([
            {"label": "번역 건수", "value": str(review_count), "type": "accent"},
            {"label": "실패", "value": str(fail_count),
             "type": "error" if fail_count else "success"},
            {"label": "Input 토큰", "value": f"{input_t:,}", "type": ""},
            # xAI는 reasoning_tokens를 별도 리포트하지만 output 단가로 과금 → 합산 표시
            {"label": "Output 토큰", "value": f"{output_t + reasoning_t:,}", "type": ""},
            {"label": "캐시 적중", "value": f"{cached_t:,}", "type": ""},
            {"label": "예상 비용", "value": f"${cost:.4f}", "type": "warning"},
        ])

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

    # 다운로드 버튼 그리드
    dl_cols = st.columns(4)
    with dl_cols[0]:
        if st.session_state.backup_csv:
            st.download_button(
                label="원본 백업 (CSV)",
                data=st.session_state.backup_csv,
                file_name=st.session_state.backup_filename or "backup.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with dl_cols[1]:
        if st.session_state.translation_report_csv:
            st.download_button(
                label="번역 리포트 (CSV)",
                data=st.session_state.translation_report_csv,
                file_name="translation_diff_report.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with dl_cols[2]:
        _failed = (
            st.session_state.graph_result.get("failed_rows", [])
            if st.session_state.graph_result else []
        )
        if _failed:
            _failed_csv = pd.DataFrame(_failed).to_csv(
                index=False
            ).encode("utf-8")
            st.download_button(
                label="검수 실패 (CSV)",
                data=_failed_csv,
                file_name="review_failed_rows.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with dl_cols[3]:
        if st.session_state.logs:
            log_text = "\n".join(st.session_state.logs)
            st.download_button(
                label="전체 로그 (TXT)",
                data=log_text.encode("utf-8"),
                file_name="execution_log.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

    if st.button("새 작업 시작", use_container_width=True):
        for key in [
            "current_step", "worksheet", "df",
            "backup_csv", "backup_filename", "ko_report_df", "ko_report_csv",
            "translation_report_df", "translation_report_csv",
            "graph_result", "logs", "cost_summary", "translations_applied",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.current_step = "idle"
        st.rerun()

    render_card_end()

# ── 실행 로그 (하단 고정) ──────────────────────────────────────────────

if st.session_state.logs and st.session_state.current_step not in ("idle", "done", "translating"):
    st.markdown(
        '<p style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); '
        'text-transform: uppercase; letter-spacing: 1.2px; margin: 1.5rem 0 0.4rem; '
        "font-family: 'Inter', sans-serif;\">실행 로그</p>",
        unsafe_allow_html=True,
    )
    render_log_terminal(st.session_state.logs)

# ── 하단 Footer ──────────────────────────────────────────────────────

render_footer()
