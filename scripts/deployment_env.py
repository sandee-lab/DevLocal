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
    # IAP audience는 여기서 조립한다. 셸에서 만들어 환경변수로 넘기면 Git Bash가
    # "/projects/..."를 Windows 경로로 변환해(C:/Program Files/Git/projects/...)
    # 앱의 JWT audience 검증이 전부 실패한다. 슬래시로 시작하는 값을 네이티브
    # 프로그램에 넘기지 않도록 구성 요소만 받아 파이썬에서 만든다.
    audience = "/projects/{}/locations/{}/services/{}".format(
        os.environ["PROJECT_NUMBER"], os.environ["REGION"], os.environ["SERVICE_NAME"],
    )
    if not audience.startswith("/projects/"):
        raise SystemExit(f"IAP audience 형식이 올바르지 않습니다: {audience}")
    env = {
        "XAI_API_KEY": api_key,
        "GCP_SERVICE_ACCOUNT_JSON": json.dumps(credentials),
        "AUTH_MODE": "iap",
        "IAP_AUDIENCE": audience,
        "ADMIN_EMAILS": os.environ["ADMIN_EMAILS"],
    }
    # 공유 저장소 없이 배포할 때만 설정된다. DATABASE_SECRET을 지정하면 deploy.sh가
    # 이 값을 넘기지 않으므로, Postgres 전환 시 별도 정리가 필요 없다.
    session_store = os.environ.get("SESSION_STORE")
    if session_store:
        env["SESSION_STORE"] = session_store
    Path(sys.argv[1]).write_text(
        "\n".join(f"{key}: {json.dumps(value)}" for key, value in env.items()) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
