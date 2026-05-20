"""상수 정의: 금지 시트, 상태값, 태그 패턴 등"""

# 접근 및 노출 절대 금지 시트 목록 (UI 드롭다운에서 필터링)
FORBIDDEN_SHEETS = ["사용법", "Texture", "수정금지_Common"]

# Tool_Status 상태값
class Status:
    WAITING = "대기"
    KO_REVIEWING = "한국어검수중"
    KO_REVIEW_DONE = "한국어검수완료"
    TRANSLATING = "번역중"
    REVIEWING = "검수중"
    REVIEW_FAILED = "검수실패"
    COMPLETED = "최종완료"

# Tool_Status 컬럼명
TOOL_STATUS_COLUMN = "Tool_Status"

# 정규식 태그 검증 패턴 목록
TAG_PATTERNS = [
    r'\{[^}]+\}',           # 변수 태그: {player_name}, {0}, {1}
    r'%[dsf]',              # printf 스타일 변수: %d, %s, %f
    r'<color[^>]*>',        # 색상 시작 태그: <color=#FF0000>
    r'</color>',            # 색상 종료 태그
    r'</?b>',               # 볼드 태그
    r'</?i>',               # 이탤릭 태그
    r'<size=[^>]*>',        # 사이즈 태그
    r'</size>',             # 사이즈 종료 태그
    r'\\n',                 # 줄바꿈
    r'\\t',                 # 탭
]

# 필수 컬럼명
REQUIRED_COLUMNS = {
    "key": "Key",
    "shared_comments": "Shared Comments",
    "korean": "Korean(ko)",
    "english": "English(en)",
    "japanese": "Japanese(ja)",
}

# 지원 언어 목록
SUPPORTED_LANGUAGES = {
    "en": "English(en)",
    "ja": "Japanese(ja)",
}

# LLM 번역 청크 크기 (행 수)
# 50: grok-4.3 + completeness/split 재시도 헬퍼 적용 후 검증된 값
# (25 대비 처리량 +50%, 단가 -16%, 누락률 0% 유지 — 2026-05 측정)
CHUNK_SIZE = 50

# Reviewer 최대 재시도 횟수
MAX_RETRY_COUNT = 3

# LLM 모델 설정
LLM_MODEL = "xai/grok-4.3"
LLM_PRICING = {
    "input": 0.20 / 1_000_000,   # $/token
    "output": 0.50 / 1_000_000,  # $/token
    "cached_input": 0.05 / 1_000_000,
}
