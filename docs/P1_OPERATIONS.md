# P1 구현 및 운영 적용 안내

작성일: 2026-09-09

리뷰의 P1 두 항목에 대해 PostgreSQL 공유 저장소와 Google IAP 인증을 구현했다. 로컬 통합 검증은 완료했으며 Cloud SQL 생성, 운영 IAM 변경, 실제 Cloud Run 배포는 수행하지 않았다.

## 결정한 접근 권한

IAP 접근 정책에 등록된 팀원은 시트 연결, 번역 실행, 승인·취소, 세션·로그·다운로드 조회를 공유한다. 개인별로 세션을 격리하는 서비스가 아니라 팀 공용 번역 도구로 구성했다. `/api/config`의 설정 변경은 `ADMIN_EMAILS`에 등록한 관리자만 가능하다. 시트 연결 시 최근 URL을 저장하는 기존 동작은 팀원에게 허용한다.

앱은 IAP가 발급한 `X-Goog-IAP-JWT-Assertion`의 ES256 서명, 유효 기간, audience, issuer, 사용자 정보를 검증한다. 서명 없는 이메일 헤더는 신뢰하지 않는다. 인증은 API뿐 아니라 정적 파일과 다운로드에도 적용하며 `/healthz`만 제외한다. 상태를 변경하는 브라우저 요청은 같은 출처의 HTTPS 요청인지 확인한다.

Cloud Run의 직접 IAP 활성화와 JWT audience 형식은 [Google Cloud의 IAP 설정 문서](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)와 [서명 헤더 검증 문서](https://docs.cloud.google.com/iap/docs/signed-headers-howto)를 기준으로 했다.

## 공유 저장소와 실행 방식

| 대상 | 저장·복구 방식 |
|---|---|
| 세션 데이터 | PostgreSQL `devlocal_sessions`: 원본 행과 DataFrame 인덱스, 승인 결과, 토큰·로그, 다운로드 CSV, 작업 예약 |
| LangGraph | 공식 `PostgresSaver`: 노드 체크포인트와 HITL interrupt 유지 |
| SSE | `devlocal_events`: 실행 서버와 연결 서버가 달라도 이벤트 전달. 새 연결에는 현재 완료·승인 상태를 먼저 전달 |
| 설정 | `devlocal_config`: JSONB 원자적 병합으로 다른 서버의 설정 변경 보존 |
| 동시 승인 | 세션별 PostgreSQL advisory lock. 겹친 요청은 409, 완료 응답은 재사용 |
| 작업 실행 | 프로세스당 최대 4개 worker. DB 작업 목록 조회 후 세션별 실행 lock을 획득한 worker만 실행 |
| 취소·실행 인계 | 새 `thread_id`와 세션 revision 사용. 실행을 인계할 때 최신 체크포인트와 pending writes를 복사해 이전 실행의 늦은 체크포인트 쓰기도 격리 |

체크포인터 초기화 방식은 [LangGraph PostgreSQL 체크포인터 문서](https://reference.langchain.com/python/langgraph.checkpoint.postgres/PostgresSaver/setup)를 따랐다. 애플리케이션 시작 시 전역 DB lock 아래에서 스키마를 준비한다. 설정·세션 저장 오류가 발생해도 메모리나 로컬 파일로 자동 전환하지 않는다.

## 재시작 시 동작

- `/start` 응답 전에 작업을 DB에 저장한다. SSE 연결이 없어도 작업이 시작된다.
- 한국어·최종 승인 대기 상태는 새 프로세스에서도 복구한다.
- 처리 중 서버가 종료되면 다른 worker가 마지막 체크포인트부터 재개한다. 체크포인트에 반영되지 않은 노드의 LLM 호출은 다시 발생할 수 있다. 외부 API 호출의 정확히 한 번 실행까지 보장하는 구조는 아니다.
- 취소 복원도 DB 작업으로 남겨 복원 도중 서버가 종료되어도 한국어 승인 대기로 복구한다.
- 최종 승인 결정과 개별 Reject를 먼저 저장한다. 이후 오류가 나면 같은 결정으로만 재시도한다.
- 시트에 적용할 셀·값을 외부 쓰기 전에 저장한다. 쓰기 직후 서버 종료로 성공 여부가 불명확한 경우, 사용자가 재시도하면 저장해 둔 동일한 값으로 다시 batch update한다. 완료 응답이 저장된 이후에는 중복 승인으로 다시 쓰지 않는다.
- 백업 다운로드 CSV는 DB에 남는다. `backup_folder`에 생성하는 별도 파일은 Cloud Run 로컬 파일이므로 인스턴스 교체 후 보존 대상이 아니다.

기존 메모리 세션은 새 버전으로 자동 이전되지 않는다. 최초 운영 전환 전에 진행 중인 작업을 완료해야 한다. DB에는 세션과 실행별 체크포인트가 계속 남으므로 운영 보관 기간과 DB 백업 정책을 설정해야 한다. 자동 세션 삭제는 도입하지 않았다.

## 과도기 구성 — 인증만 먼저 적용 (현재 선택)

Cloud SQL 준비 전에 인증부터 적용하기로 했다. 두 P1 중 공개 배포 쪽이 더 급하다고 판단했다.
인증 없는 상태에서는 URL을 아는 누구나 `GET /api/config`로 Glossary·게임 시놉시스를 읽고
`PUT /api/config`로 덮어쓸 수 있으며, 시트가 연결된 인스턴스에서는 시트 URL까지 노출된다.
반면 세션 공유 문제는 이미 지금 운영에도 존재하므로, 이 구성으로 새로 나빠지는 것은 없다.

`DATABASE_SECRET`과 `CLOUD_SQL_INSTANCE`를 지정하지 않으면 `deploy.sh`가 이 구성으로 배포한다.

| 항목 | 과도기 구성 | 공유 저장소 구성 |
|---|---|---|
| 인증 | IAP (동일) | IAP |
| 세션·설정 저장 | 프로세스 메모리와 `.app_config.json` | PostgreSQL |
| `max-instances` | 1 | 5 |
| 인스턴스 교체 시 | 진행 중 세션과 UI 설정 변경 유실 | 복구 |
| Cloud SQL 비용 | 없음 | 발생 |

앱은 `SESSION_STORE=memory`가 있을 때만 공유 저장소 없이 기동한다. 이 선언이 없는데
`DATABASE_URL`도 없으면 기동에 실패한다. `DATABASE_URL` 설정을 빠뜨린 사고와 의도적인
단일 인스턴스 운영을 구분하기 위한 것이며, 조용히 메모리로 폴백하지 않는다.

공유 저장소로 넘어갈 판단 기준은 다음과 같다.

- 동시에 번역을 돌리는 사람이 늘어 한 인스턴스로 부족해질 때
- 인스턴스 교체로 진행 중 작업이 끊기는 일이 실제로 발생할 때
- UI에서 바꾼 설정이 사라지는 것이 문제가 될 때

전환은 준비를 마친 뒤 `DATABASE_SECRET`과 `CLOUD_SQL_INSTANCE`를 지정해 다시 배포하면 된다.
`deploy.sh`가 `SESSION_STORE`를 넘기지 않고 DB 연결을 추가하므로 코드 변경은 필요 없다.

## 운영 적용 전 준비

1. Cloud Run 서비스의 IAP 접근 정책에 팀의 Google 그룹 또는 사용자를 등록한다. 필요한 역할은 `roles/iap.httpsResourceAccessor`이다. 조직이 없는 프로젝트나 외부 계정은 최초 OAuth 설정이 필요할 수 있으므로 Cloud Console에서 확인한다.
2. 설정 관리자의 실제 이메일 목록을 정한다. IAP 접근 권한과 관리자 이메일 등록은 별개다.
3. 런타임 서비스 계정을 정한다. 공유 저장소를 함께 적용한다면 아래 4번의 권한이 필요하다.
4. (공유 저장소 구성일 때만) Cloud SQL PostgreSQL에 앱 전용 데이터베이스·사용자를 준비한다. 앱 사용자는 해당 DB의 애플리케이션 테이블과 체크포인터 스키마를 만들고 읽고 쓸 수 있어야 한다. DB 접속 문자열은 Secret Manager에 저장하고, 런타임 서비스 계정에 해당 Secret의 `roles/secretmanager.secretAccessor`와 Cloud SQL 연결을 위한 `roles/cloudsql.client` 권한을 부여한다.
5. 아래 배포 변수를 지정하고 변경 내용을 검토한 뒤 `deploy.sh`를 실행한다.

| 배포 변수 | 필수 | 의미 |
|---|---|---|
| `RUNTIME_SERVICE_ACCOUNT` | 필수 | 런타임 서비스 계정 이메일 |
| `ADMIN_EMAILS` | 필수 | 설정 관리자 이메일, 쉼표 구분 |
| `DATABASE_SECRET` | 선택 | DB 접속 문자열 Secret의 `이름:버전` |
| `CLOUD_SQL_INSTANCE` | 선택 | `project:region:instance` 연결 이름 |

선택 변수 두 개를 **함께** 지정하면 공유 저장소 구성으로, 지정하지 않으면 과도기 구성으로 배포한다.

DB 접속 문자열의 예시 형식은 `postgresql://USER:ENCODED_PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE`이다. 비밀번호의 특수문자는 URL 인코딩한다. 연결 문자열이나 비밀 값을 저장소에 커밋하지 않는다.

`deploy.sh`는 `AUTH_MODE=iap`와 `/projects/PROJECT_NUMBER/locations/REGION/services/SERVICE_NAME` 형식의 `IAP_AUDIENCE`를 설정한다. 익명 접근을 허용하지 않고 IAP를 활성화하며, IAP 서비스 에이전트에 해당 서비스의 `roles/run.invoker`를 부여한다. 팀 사용자·그룹의 접근 권한은 임의로 추가하지 않는다.

백그라운드 작업 실행을 위해 최소 인스턴스 1개와 상시 CPU 할당을 사용한다. Cloud SQL과 함께 기존 요청 기반 실행보다 유휴 비용이 늘어난다. 최대 인스턴스 수는 기존 5개를 유지한다.

Cloud Run에서 IAP audience나 관리자 목록이 빠지거나 로컬 인증 모드를 사용하면 앱 시작이 실패한다. DB 주소는 `SESSION_STORE=memory`를 명시한 과도기 구성에서만 생략할 수 있고, 선언 없이 빠지면 마찬가지로 기동에 실패한다. IAP 접근 정책 준비가 끝나기 전에 기존 운영 서비스에 이 버전을 배포하지 않는다.

## 기존 설정 이전과 로컬 실행

DB 설정 저장소는 처음에는 비어 있다. 로컬 `.app_config.json`을 운영 DB로 자동 복사하지 않는다. 특히 `backup_folder`의 로컬 경로를 검토한 뒤 필요한 설정만 이전한다.

```powershell
# DATABASE_URL을 안전한 환경 변수로 지정한 상태에서 실행한다.
python scripts/import_shared_config.py .app_config.json
```

이 명령은 같은 키의 기존 공유 설정을 덮어쓴다. UI에서 관리자가 새로 저장하는 방법도 사용할 수 있다.

FastAPI는 `DATABASE_URL`이 설정되면 로컬에서도 공유 저장소를 사용한다. DB가 없는 로컬 개발은 기존 메모리 세션과 `.app_config.json` 방식을 유지한다. `AUTH_MODE=local`은 로컬 개발용이며 인터넷 공개용 설정이 아니다. 레거시 Streamlit 진입점은 기존 로컬 설정·메모리 방식으로 별도 실행한다.

## 검증

- Python 44건: 기존 회귀 26건, 실제 ES256 서명 인증 6건, PostgreSQL 통합 12건.
- PostgreSQL 통합은 임시 DB와 독립 연결을 사용했다. 별도 Python 프로세스의 승인 체크포인트 복원도 확인했다.
- 한국어·번역 체크포인트 직후 중단, 취소 도중 중단, 최종 승인 후 업데이트 목록 저장 전 중단, 다른 서버에서의 저장 재시도를 검증했다.
- 프론트엔드 회귀 9건: 늦은 SSE 연결과 다른 연결에서 수행한 취소 반영 포함.
- 프론트엔드 TypeScript·프로덕션 빌드 및 ESLint 통과.

이번 검증의 Grok·Google Sheets 호출은 모의 처리했다. 실제 PostgreSQL 엔진과 ES256 서명 검증을 사용했지만 운영 IAP 로그인 화면, 실제 팀 IAM 정책, Cloud SQL 접속, Cloud Run 재배포는 검증하지 않았다.

```powershell
# TEST_DATABASE_URL은 테스트용 PostgreSQL 서버를 가리켜야 한다.
# 테스트가 고유한 devlocal_test_* DB를 생성하고 종료 시 그 DB만 제거한다.
python -X utf8 -m unittest discover -s tests -v
```

`TEST_DATABASE_URL`이 없으면 PostgreSQL 통합 12건은 skip된다. 연결·스키마 문제를 숨기기 위해 성공으로 처리하지 않는다.
