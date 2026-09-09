"""공통 설정 저장소. FastAPI 운영 모드는 공유 DB, 로컬 모드는 파일을 사용한다."""

import json
import os
import tempfile
from pathlib import Path
from threading import RLock

_CONFIG_PATH = Path(__file__).resolve().parent.parent / ".app_config.json"
_LOCK = RLock()
_shared_store = None


def use_shared_store(store):
    global _shared_store
    _shared_store = store


def load_config() -> dict:
    if _shared_store is not None:
        return _shared_store.load_config()
    with _LOCK:
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}


def save_config(data: dict) -> None:
    """동시 변경 유실과 부분 쓰기를 방지하고, 저장 실패는 호출자에게 전달한다."""
    if _shared_store is not None:
        _shared_store.save_config(data)
        return
    with _LOCK:
        existing = load_config()
        existing.update(data)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=_CONFIG_PATH.parent,
                prefix=".app_config-", suffix=".tmp", delete=False,
            ) as output:
                temporary = output.name
                json.dump(existing, output, ensure_ascii=False, indent=2)
            os.replace(temporary, _CONFIG_PATH)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
