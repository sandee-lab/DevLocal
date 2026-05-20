"""SSE 청크 emit 유틸 — 청크 결과를 단일 이벤트로 즉시 전송."""


def drip_feed_emit(
    emitter,
    event_name: str,
    items: list,
    progress_base: int,
    total: int,
    lang: str = "",
) -> None:
    """
    청크 결과 전체를 단일 SSE 이벤트로 즉시 전송.

    과거에는 항목 간 150ms sleep으로 드립피드 효과를 줬으나,
    큰 시트에서 워커 스레드를 점유하며 진행 정체를 일으켜 제거함
    (1000행 기준 누적 150초+ 지연). 부드러운 진행 표시는 프론트 CSS가 담당.

    Args:
        emitter: SSE emit callback (event_name, data_dict)
        event_name: SSE 이벤트명 ("ko_review_chunk", "translation_chunk", "review_chunk")
        items: 전송할 결과 리스트 (전체를 chunk_results에 그대로 포함)
        progress_base: 이 배치 시작 시점의 누적 완료 수
        total: 전체 예상 항목 수
        lang: 언어 코드 (translation_chunk용, 선택)
    """
    if not items:
        return

    data = {
        "chunk_results": items,
        "progress": {
            "done": progress_base + len(items),
            "total": total,
        },
    }

    if lang:
        data["lang"] = lang

    emitter(event_name, data)
