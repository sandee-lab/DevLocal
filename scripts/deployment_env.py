"""배포 환경 파일을 생성한다. 비밀 값을 셸 코드에 삽입하거나 출력하지 않는다."""

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values


def main():
    values = dotenv_values(".env")
    api_key = values.get("XAI_API_KEY")
    if not api_key:
        raise SystemExit(".env의 XAI_API_KEY가 필요합니다")
    path = Path(values.get("GCP_SERVICE_ACCOUNT_JSON_PATH") or ".gcp_service_account.json")
    credentials = json.loads(path.read_text(encoding="utf-8"))
    env = {
        "XAI_API_KEY": api_key,
        "GCP_SERVICE_ACCOUNT_JSON": json.dumps(credentials),
        "AUTH_MODE": "iap",
        "IAP_AUDIENCE": os.environ["IAP_AUDIENCE"],
        "ADMIN_EMAILS": os.environ["ADMIN_EMAILS"],
    }
    Path(sys.argv[1]).write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in env.items()) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
