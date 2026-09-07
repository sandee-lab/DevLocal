"""정규식 태그 검증 + Glossary 후처리"""

import re

from config.constants import TAG_PATTERNS
from config.glossary import get_glossary, get_spelling_fixes


def validate_tags(source_ko: str, translated: str) -> dict:
    """
    원문과 번역문의 포맷팅 태그 일치 여부를 정규식으로 검증.

    Returns: {"valid": bool, "errors": [str]}
    """
    errors = []

    # 리터럴 \\n, \\t 를 통일 (실제 개행/탭이 섞인 경우 보정)
    source_norm = source_ko.replace("\n", "\\n").replace("\t", "\\t")
    trans_norm = translated.replace("\n", "\\n").replace("\t", "\\t")

    for pattern in TAG_PATTERNS:
        source_tags = sorted(re.findall(pattern, source_norm))
        trans_tags = sorted(re.findall(pattern, trans_norm))

        if source_tags != trans_tags:
            errors.append(
                f"태그 불일치 [{pattern}]: "
                f"원문 {source_tags} ≠ 번역 {trans_tags}"
            )

    return {"valid": len(errors) == 0, "errors": errors}


_HANGUL_RUN = re.compile(r"[가-힣]+(?:[\s·,]*[가-힣]+)*")


def check_hangul_residue(source_ko: str, translated: str) -> dict:
    """
    번역문에 한글이 잔존하는지 검증 (Glossary 후처리 이후 호출 전제).

    예외: 번역문이 원문과 완전히 동일하면 의도적 통과로 간주
    (예: 언어 선택 UI의 Local_Lang_KO = "한국어").

    Returns: {"valid": bool, "errors": [str]}
    """
    if translated == source_ko:
        return {"valid": True, "errors": []}

    runs = _HANGUL_RUN.findall(translated)
    if not runs:
        return {"valid": True, "errors": []}

    snippets = ", ".join(f"'{r}'" for r in runs[:5])
    if len(runs) > 5:
        snippets += f" 외 {len(runs) - 5}건"
    return {
        "valid": False,
        "errors": [f"번역문에 한국어 잔존: {snippets} — 관용구 포함 전체를 타겟 언어로 번역해야 함"],
    }


def _fix_spelling(text: str, wrong: str, right: str) -> str:
    """고유명사 오표기를 대소문자 무시로 찾아 정답 표기로 치환.

    원문이 전부 대문자면(제목/강조 스타일) 교정 결과도 대문자로 유지한다.
    """
    def _sub(m: re.Match) -> str:
        matched = m.group(0)
        return right.upper() if matched.isupper() else right

    return re.sub(re.escape(wrong), _sub, text, flags=re.IGNORECASE)


def apply_glossary_postprocess(text: str, lang: str) -> str:
    """
    Glossary 강제 치환 — 번역 결과에서 오역된 Glossary 용어를 교정.
    JA 등급명 등 의역 금지 항목에 대해 str.replace() 적용.

    2단계로 동작한다:
      1) Glossary — 번역문에 한국어 원문 용어가 남아있으면 지정 번역으로 치환
      2) 오표기 교정 — 이미 로마자화됐지만 철자가 다른 고유명사를 정답으로 통일
         (1단계는 한글이 남은 경우만 잡으므로 Kamazon/Kwacha 같은 케이스는 못 막음)
    """
    lang_glossary = get_glossary().get(lang, {})

    # 정방향: source_ko → target (번역문에 한국어가 남아있으면 치환)
    for ko_term, target_term in lang_glossary.items():
        if ko_term in text:
            text = text.replace(ko_term, target_term)

    for wrong, right in get_spelling_fixes(lang).items():
        text = _fix_spelling(text, wrong, right)

    return text


def check_glossary_compliance(
    text: str, lang: str, source_ko: str
) -> dict:
    """
    번역문에 Glossary 용어가 올바르게 반영되었는지 검증.

    원문(source_ko)에 Glossary의 한국어 키가 있으면,
    번역문에 대응하는 타겟 용어가 있어야 함.

    Returns: {"compliant": bool, "violations": [str]}
    """
    glossary = get_glossary()
    lang_glossary = glossary.get(lang, {})
    violations = []

    if not lang_glossary:
        return {"compliant": True, "violations": []}

    for ko_term, target_term in lang_glossary.items():
        if ko_term in source_ko and target_term not in text:
            violations.append(
                f"'{ko_term}' → '{target_term}' 미반영"
            )

    return {"compliant": len(violations) == 0, "violations": violations}
