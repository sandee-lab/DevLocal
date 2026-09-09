"""검토한 로컬 설정을 공유 DB로 명시적으로 옮긴다. 같은 키는 덮어쓴다."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.storage import PostgresStorage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    data = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        parser.error("설정 파일 루트는 JSON 객체여야 합니다")
    store = PostgresStorage(os.environ["DATABASE_URL"])
    try:
        store.setup()
        store.save_config(data)
        print(f"설정 {len(data)}개를 공유 DB에 반영했습니다")
    finally:
        store.close()


if __name__ == "__main__":
    main()
