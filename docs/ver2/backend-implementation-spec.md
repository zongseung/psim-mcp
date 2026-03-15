# PSIM Cloud Service: Backend Implementation Spec

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [implementation-phases.md](./implementation-phases.md) | [api-spec.md](./api-spec.md) | [supabase-design.md](./supabase-design.md)

---

## 1. 목적

이 문서는 Control Plane Backend를 실제로 구현하기 위한 상세 명세다.

범위:
- HTTP API 서버
- 인증/권한
- 프로젝트/잡 관리
- Worker internal API
- Anthropic orchestration
- Supabase 연동

비범위:
- Windows worker 내부 실행 로직
- PSIM bridge 세부 구현
- 웹 프론트엔드

---

## 2. 역할 정의

Backend는 아래 역할만 맡는다.

1. 사용자/조직 인증 컨텍스트 해석
2. 프로젝트/잡 메타데이터 관리
3. 자연어 요청을 구조화 job spec으로 변환
4. job 상태 전이 관리
5. worker와의 제어 plane 통신
6. artifact 메타데이터 및 signed URL 발급

Backend는 직접 PSIM을 실행하지 않는다.

---

## 3. 권장 기술 방향

권장 기본:
- Python 3.12+
- FastAPI
- Pydantic v2
- httpx
- Supabase Python client 또는 Postgres 직접 접근
- SQLAlchemy 또는 query layer 래퍼

권장 이유:
- 타입 기반 API 계약
- 비동기 HTTP 호출
- 구조화된 request/response 모델
- 내부/외부 API 동시 구현 용이

---

## 4. 권장 디렉터리 구조

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── response.py
│   ├── auth/
│   │   ├── jwt.py
│   │   ├── api_keys.py
│   │   ├── worker_tokens.py
│   │   └── permissions.py
│   ├── api/
│   │   ├── routers/
│   │   │   ├── health.py
│   │   │   ├── projects.py
│   │   │   ├── jobs.py
│   │   │   ├── assistant.py
│   │   │   ├── artifacts.py
│   │   │   └── internal_workers.py
│   │   └── schemas/
│   │       ├── common.py
│   │       ├── projects.py
│   │       ├── jobs.py
│   │       ├── assistant.py
│   │       └── workers.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── job_spec.py
│   │   └── models.py
│   ├── repositories/
│   │   ├── organizations.py
│   │   ├── memberships.py
│   │   ├── projects.py
│   │   ├── jobs.py
│   │   ├── job_events.py
│   │   ├── artifacts.py
│   │   ├── workers.py
│   │   ├── api_keys.py
│   │   └── usage.py
│   ├── services/
│   │   ├── project_service.py
│   │   ├── job_service.py
│   │   ├── worker_service.py
│   │   ├── artifact_service.py
│   │   ├── audit_service.py
│   │   └── usage_service.py
│   ├── orchestration/
│   │   ├── anthropic_client.py
│   │   ├── prompts.py
│   │   ├── parser.py
│   │   └── validation.py
│   ├── integrations/
│   │   ├── supabase_auth.py
│   │   ├── supabase_storage.py
│   │   └── postgres.py
│   └── utils/
│       ├── time.py
│       ├── ids.py
│       └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── migrations/
```

---

## 5. 계층 책임

### 5.1 `api/routers`

역할:
- HTTP request parsing
- dependency injection
- service 호출
- HTTP status code 반환

금지:
- DB query 직접 수행
- 권한 판단 로직 직접 구현
- Anthropic prompt 조립

### 5.2 `services`

역할:
- use case orchestration
- repository 조합
- 상태 전이 처리
- 감사 로그 및 usage 기록 트리거

### 5.3 `repositories`

역할:
- DB read/write 캡슐화
- SQL 또는 query object 관리

원칙:
- business rule을 넣지 않는다
- repository는 storage abstraction이다

### 5.4 `orchestration`

역할:
- Anthropic API 호출
- prompt template 관리
- structured output parsing
- job spec validation 전처리

### 5.5 `auth`

역할:
- Supabase JWT 검증
- API key 검증
- worker token 검증
- role check helper

---

## 6. 설정 설계

### 6.1 `config.py`

권장 모델:

```python
class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet"

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    job_claim_timeout_seconds: int = 30
    job_max_runtime_seconds: int = 1800
    signed_url_ttl_seconds: int = 3600
```

원칙:
- settings는 singleton DI로 주입
- 환경별 설정은 `.env`, secret manager, CI env로 관리

---

## 7. 인증/인가 설계

### 7.1 사용자 인증

흐름:
- 클라이언트가 Supabase access token 전송
- backend가 JWT 검증
- user id 추출
- membership 조회
- organization context 계산

### 7.2 API key 인증

용도:
- CI
- 외부 내부도구
- machine-to-machine

흐름:
- `Authorization: Bearer <api_key>`
- hash 비교
- organization scope 확인
- allowed scope 검증

### 7.3 Worker 인증

용도:
- internal worker API

방식:
- worker token 또는 mTLS 대체 가능
- 초기에는 pre-issued worker token 권장

---

## 8. Organization Context 처리

모든 business API는 organization context를 명시적으로 가져야 한다.

권장 dependency:

```python
async def get_org_context(...) -> OrgContext:
    return OrgContext(
        user_id=...,
        organization_id=...,
        role=...,
    )
```

`OrgContext` 필드:
- `user_id`
- `organization_id`
- `role`
- `auth_type` (`user`, `api_key`, `worker`)

---

## 9. 공통 응답 처리

권장 공통 포맷:

```python
def success(data: Any, message: str | None = None) -> dict:
    ...

def failure(code: str, message: str, suggestion: str | None = None) -> dict:
    ...
```

HTTP status는 transport 의미, JSON body는 domain 의미를 표현한다.

예:
- `400`: invalid input
- `401`: unauthorized
- `403`: forbidden
- `404`: not found
- `409`: invalid state transition
- `500`: unexpected internal error

---

## 10. 프로젝트 API 구현 기준

### 10.1 `POST /v1/projects`

체크:
- organization role이 `member` 이상인지
- storage path 규칙이 맞는지
- 프로젝트명 중복 정책 확인

서비스 흐름:
1. 권한 확인
2. payload validation
3. storage path 검증
4. repository create
5. audit log 작성

### 10.2 `GET /v1/projects`

체크:
- organization scope 필수
- soft delete 정책이 있다면 제외

---

## 11. Job API 구현 기준

### 11.1 job spec 구조

job spec은 backend의 핵심 계약이다.

예시:

```json
{
  "operation": "run_simulation",
  "parameter_updates": [],
  "simulation_options": {},
  "export": {}
}
```

### 11.2 `POST /v1/jobs`

서비스 흐름:
1. project 존재/권한 확인
2. job spec validator 실행
3. `simulation_jobs` row 생성
4. `job_events`에 `queued` 기록
5. audit log 작성

### 11.3 상태 전이 규칙

허용 전이:
- `queued -> claimed`
- `claimed -> running`
- `running -> completed`
- `running -> failed`
- `queued -> cancelled`
- `running -> cancel_requested`

금지 전이는 repository 앞단 service에서 차단한다.

---

## 12. Worker API 구현 기준

### 12.1 `register`

작업:
- worker 식별
- capability 저장
- 최초 상태 `online`

### 12.2 `heartbeat`

작업:
- `last_heartbeat_at` 갱신
- `busy` / `online` 상태 갱신 가능

### 12.3 `claim-next-job`

원칙:
- race condition 방지 필요
- 단일 job이 두 worker에 동시에 배정되면 안 됨

권장 방식:
- transaction + row lock
- `queued` 상태 중 oldest eligible job 선택

### 12.4 `complete` / `fail`

작업:
- 상태 전이
- summary 저장
- artifact row 생성
- usage 기록
- audit log 추가

---

## 13. Anthropic Orchestration 구현 기준

### 13.1 모듈 분리

권장 파일:
- `anthropic_client.py`: SDK wrapper
- `prompts.py`: system/user prompt 템플릿
- `parser.py`: structured output parse
- `validation.py`: LLM output safety validation

### 13.2 실행 원칙

1. 사용자 자연어 입력 수신
2. project context 추가
3. Anthropic API 호출
4. structured output 획득
5. backend validator 통과 시에만 job 생성

### 13.3 절대 금지

- LLM 출력 JSON을 검증 없이 실행
- 경로를 LLM이 자유롭게 지정하도록 허용
- 조직 외 프로젝트 식별자를 신뢰

---

## 14. Artifact 처리

### 14.1 backend 책임

- artifact 메타데이터 등록
- signed URL 발급
- 접근 권한 체크

### 14.2 worker 책임

- 결과 파일 생성
- storage 업로드
- storage path 보고

---

## 15. 감사 로그 / 사용량

### 15.1 audit

기록 이벤트:
- project created
- job created
- job cancelled
- worker claimed job
- job failed
- artifact accessed

### 15.2 usage

기록 대상:
- token usage
- worker runtime
- artifact storage size
- job count

---

## 16. 예외 처리 기준

예외 계층:
- `DomainError`
- `PermissionError`
- `ValidationError`
- `NotFoundError`
- `ConflictError`
- `ExternalServiceError`

권장:
- router에서 broad `except` 최소화
- service는 domain exception을 raise
- 공통 exception handler에서 JSON error 생성

---

## 17. 테스트 계획

### 17.1 unit
- validator
- service 상태 전이
- organization permission
- Anthropic output validation

### 17.2 integration
- Supabase/Postgres repository
- job claim race handling
- signed URL flow

### 17.3 contract
- API request/response schema
- worker internal API contract

---

## 18. 우선 구현 순서

1. `config`, `response`, `exceptions`
2. auth dependencies
3. project repository/service/router
4. job repository/service/router
5. worker internal router/service
6. artifact service
7. Anthropic orchestration
8. usage/audit/admin

---

## 19. 구현 체크리스트

- [ ] settings 모델 생성
- [ ] auth dependency 생성
- [ ] org context 생성
- [ ] project CRUD 최소 구현
- [ ] job lifecycle 최소 구현
- [ ] worker internal API 구현
- [ ] artifact metadata 구현
- [ ] Anthropic orchestration 구현
- [ ] audit/usage 기록 구현
- [ ] exception handler 구현

---

## 20. 결론

Backend 구현의 핵심은 “API를 만드는 것”이 아니라,  
**조직 권한, job 상태 전이, worker 제어, LLM 출력 검증**을 안정적인 control plane으로 만드는 것이다.

따라서 구현 순서 역시:

**auth → organization context → job lifecycle → worker control → orchestration**

로 가는 것이 맞다.
