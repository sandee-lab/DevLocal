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

# 필수 컬럼명 — 타겟 언어 컬럼은 필수가 아님 (시트에 존재하는 언어만 번역 대상)
REQUIRED_COLUMNS = {
    "key": "Key",
    "shared_comments": "Shared Comments",
    "korean": "Korean(ko)",
}

# 지원 언어 목록 (언어코드 → 시트 컬럼 헤더명 — 시트 컬럼명과 정확히 일치해야 함)
SUPPORTED_LANGUAGES = {
    "en": "English(en)",
    "ja": "Japanese(ja)",
    "zh-CN": "Chinese_CN(zh-CN)",
    "zh-TW": "Chinese_TW(zh-TW)",
}

# 프롬프트용 언어 표기 — LLM이 간체/번체 문자 체계를 혼동하지 않도록 명시
LANGUAGE_PROMPT_LABELS = {
    "en": "English (en)",
    "ja": "日本語 / Japanese (ja)",
    "zh-CN": "简体中文 / Simplified Chinese (zh-CN) — 반드시 간체자만 사용",
    "zh-TW": "繁體中文 / Traditional Chinese (zh-TW) — 반드시 번체자만 사용",
}

# LLM 번역 청크 크기 (행 수)
# 50: grok-4.3 + completeness/split 재시도 헬퍼 적용 후 검증된 값
# (25 대비 처리량 +50%, 단가 -16%, 누락률 0% 유지 — 2026-05 측정)
CHUNK_SIZE = 50

# 한 단계(ko_review/translator/reviewer) 내에서 동시에 실행하는 LLM chunk 수
# 4: xAI Grok rate limit 안전 + 큰 시트(1000행+) 체감 4배 단축
LLM_CHUNK_PARALLELISM = 4

# Reviewer 최대 재시도 횟수
MAX_RETRY_COUNT = 3

# LLM 모델 설정
LLM_MODEL = "xai/grok-4.3"
# 단가 출처: xAI 공식 모델 페이지 docs.x.ai/developers/models/grok-4.3 (2026-07 확인)
LLM_PRICING = {
    "input": 1.25 / 1_000_000,        # $/token
    "output": 2.50 / 1_000_000,       # $/token  (reasoning_tokens 포함 합산)
    "cached_input": 0.20 / 1_000_000,  # 공식 문서 명시값
}
