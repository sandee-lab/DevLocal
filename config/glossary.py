"""게임 설정 로더 — Glossary, 시놉시스, 톤앤매너를 .app_config.json에서 로드 (fallback 내장)"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("devlocal.glossary")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / ".app_config.json"

# ── 하드코딩 fallback (초기 기본값) ──────────────────────────────────

_DEFAULT_GLOSSARY: dict[str, dict[str, str]] = {
    "en": {
        "카마존": "Camazon",
        "콰챠": "Quacha",
    },
    "ja": {
        "카마존": "ニャマゾン",
        "일반": "一般",
        "고급": "高級",
        "희귀": "レア",
        "영웅": "英雄",
        "전설": "伝説",
        "신화": "神話",
        "고대": "古代",
    },
}

# 고유명사 로마자 오표기 교정 — Glossary 후처리만으로는 막을 수 없는 케이스를 처리.
# apply_glossary_postprocess의 Glossary 치환은 "번역문에 한국어가 남은 경우"만
# 동작하므로, LLM이 이미 다른 철자로 로마자화해버리면(Kamazon/Kwacha) 잡지 못한다.
# 모델·실행마다 표기가 갈리는 것이 실측으로 확인되어(4.3=Kamazon/Quacha,
# 4.6=Camazon/Kwacha) 정답 표기로 강제 통일한다.
# 대소문자 무시 매칭이며, 원문이 전부 대문자면 교정 결과도 대문자로 유지한다.
_DEFAULT_SPELLING_FIXES: dict[str, dict[str, str]] = {
    "en": {
        "Kamazon": "Camazon",
        "Kwacha": "Quacha",
    },
}

_DEFAULT_GAME_SYNOPSIS = (
    "상자를 열기 전까지는 내용물을 알 수 없는 우주 최고 가챠 '슈뢰딩거 상자'로 "
    "대박을 터뜨린 우주 기업 카마존. "
    "말단 배달 로봇 404가 배달 사고로 모든 상자를 잃어버리는데, "
    "그 중 하나가 카마존 설립자가 주문한 전 우주에 하나 남은 단종된 한정판 '츄르'였다. "
    "설립자의 전시 프로토콜 가동으로 외딴 행성에 불시착한 로봇 404의 츄르 찾기 대모험. "
    "(외계인들은 상자에 중독되어 카마존 상자를 닥치는 대로 탐내는 상황)"
)

_DEFAULT_TONE_AND_MANNER = (
    "너무 진지하지 않은 유머러스(Humorous)하고 캐주얼(Casual)한 톤을 철저히 유지."
)


# ── Config 로더 (내부) ───────────────────────────────────────────────

def _load_config() -> dict:
    """`.app_config.json` 전체를 파싱하여 반환. 파일 없거나 파싱 실패 시 {}."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Config load failed: %s", e)
        return {}


# ── Public API ───────────────────────────────────────────────────────

def get_glossary() -> dict[str, dict[str, str]]:
    """현재 유효한 glossary 반환 — config 우선, fallback은 하드코딩."""
    cfg = _load_config()
    glossary = cfg.get("glossary")
    if glossary and isinstance(glossary, dict):
        return glossary
    return _DEFAULT_GLOSSARY


def get_spelling_fixes(lang: str) -> dict[str, str]:
    """해당 언어의 고유명사 오표기 교정 맵 반환 — config 우선, fallback은 하드코딩."""
    cfg = _load_config()
    fixes = cfg.get("spelling_fixes")
    if fixes and isinstance(fixes, dict):
        return fixes.get(lang, {})
    return _DEFAULT_SPELLING_FIXES.get(lang, {})


def get_game_synopsis() -> str:
    """게임 시놉시스 반환 — config 우선, fallback은 하드코딩."""
    cfg = _load_config()
    synopsis = cfg.get("game_synopsis")
    if synopsis and isinstance(synopsis, str):
        return synopsis
    return _DEFAULT_GAME_SYNOPSIS


def get_tone_and_manner() -> str:
    """톤앤매너 반환 — config 우선, fallback은 하드코딩."""
    cfg = _load_config()
    tone = cfg.get("tone_and_manner")
    if tone and isinstance(tone, str):
        return tone
    return _DEFAULT_TONE_AND_MANNER


def format_glossary_text(lang: str) -> str:
    """Glossary를 프롬프트용 텍스트로 변환 — 매 호출 시 최신 config 반영."""
    glossary = get_glossary()
    if lang not in glossary or not glossary[lang]:
        return "이 언어에 대한 고정 Glossary 없음. 일관성을 유지하여 자유 번역하세요."
    lines = [f"- {ko} → {target}" for ko, target in glossary[lang].items()]
    return "\n".join(lines)
