"""Mock 전용 검증 — LLM 호출 없이 헬퍼 단위 동작만 확인 (빠른 회귀용)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from scripts.verify_model import split_retry_test, completeness_test

if __name__ == "__main__":
    a = split_retry_test()
    b = completeness_test()
    print("\n=== Mock 검증 결과 ===")
    print(f"split_retry: {'OK' if a else 'FAIL'}")
    print(f"completeness: {'OK' if b else 'FAIL'}")
    sys.exit(0 if (a and b) else 1)
