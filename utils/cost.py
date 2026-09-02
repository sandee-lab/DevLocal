"""LLM 토큰 사용량 → 비용 산출 — FastAPI/Streamlit 양쪽의 단일 진실 출처.

주의 (xAI/Grok 특성):
  - reasoning_tokens는 completion_tokens와 별도로 리포트되지만 output 단가로 과금 → 합산 필요
  - cached_tokens는 prompt_tokens에 이미 포함되어 있음 → 차감 후 cached 단가를 별도 적용
"""

from config.constants import LLM_PRICING


def build_cost_summary(
    input_t: int, output_t: int, reasoning_t: int, cached_t: int
) -> dict:
    """토큰 사용량으로 cost summary 생성."""
    non_cached_input = max(input_t - cached_t, 0)
    cost = (
        non_cached_input * LLM_PRICING["input"]
        + cached_t * LLM_PRICING["cached_input"]
        + (output_t + reasoning_t) * LLM_PRICING["output"]
    )
    return {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "reasoning_tokens": reasoning_t,
        "cached_tokens": cached_t,
        "estimated_cost_usd": round(cost, 4),
    }
