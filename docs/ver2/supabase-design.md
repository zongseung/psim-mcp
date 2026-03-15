# PSIM Cloud Service: Supabase Design

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md)

---

## 1. Supabase 적용 목적

Supabase는 이 서비스에서 다음 4가지 역할을 맡는다.

1. Auth
2. 멀티테넌트 Postgres
3. Storage
4. Realtime

이 서비스에서 Supabase는 “부가 서비스”가 아니라 **control plane의 데이터 기반**이다.

---

## 2. 핵심 테이블

### 2.1 `organizations`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | 조직 ID |
| `name` | text | 조직명 |
| `slug` | text | 고유 슬러그 |
| `plan` | text | billing plan |
| `created_at` | timestamptz | 생성일 |

### 2.2 `memberships`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | membership ID |
| `organization_id` | uuid | 조직 ID |
| `user_id` | uuid | auth.users 참조 |
| `role` | text | owner/admin/member/viewer |
| `created_at` | timestamptz | 생성일 |

### 2.3 `projects`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | 프로젝트 ID |
| `organization_id` | uuid | 조직 ID |
| `name` | text | 프로젝트명 |
| `description` | text | 설명 |
| `source_storage_path` | text | 원본 파일 경로 |
| `default_simulation_options` | jsonb | 기본 옵션 |
| `created_by` | uuid | 생성자 |
| `created_at` | timestamptz | 생성일 |

### 2.4 `simulation_jobs`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | job ID |
| `organization_id` | uuid | 조직 ID |
| `project_id` | uuid | 프로젝트 ID |
| `status` | text | queued/running/completed/... |
| `requested_by` | uuid | 요청 사용자 |
| `request_type` | text | api/manual/assistant |
| `prompt` | text | 자연어 입력 원문 |
| `job_spec` | jsonb | 검증된 실행 스펙 |
| `worker_id` | uuid | 담당 worker |
| `error_code` | text | 실패 코드 |
| `error_message` | text | 실패 메시지 |
| `created_at` | timestamptz | 생성일 |
| `started_at` | timestamptz | 시작일 |
| `finished_at` | timestamptz | 종료일 |

### 2.5 `job_events`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | event ID |
| `job_id` | uuid | job ID |
| `event_type` | text | queued/claimed/log/progress/... |
| `payload` | jsonb | 이벤트 상세 |
| `created_at` | timestamptz | 생성일 |

### 2.6 `artifacts`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | artifact ID |
| `job_id` | uuid | job ID |
| `organization_id` | uuid | 조직 ID |
| `kind` | text | result_json/csv/log/report |
| `storage_bucket` | text | bucket |
| `storage_path` | text | 경로 |
| `content_type` | text | MIME |
| `size_bytes` | bigint | 크기 |
| `created_at` | timestamptz | 생성일 |

### 2.7 `workers`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | worker ID |
| `name` | text | worker 이름 |
| `status` | text | online/busy/offline/draining |
| `capabilities` | jsonb | 버전, capacity |
| `last_heartbeat_at` | timestamptz | heartbeat |
| `created_at` | timestamptz | 생성일 |

### 2.8 `api_keys`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | key ID |
| `organization_id` | uuid | 조직 ID |
| `name` | text | key 이름 |
| `key_hash` | text | 해시 |
| `scope` | jsonb | 허용 scope |
| `created_by` | uuid | 생성자 |
| `revoked_at` | timestamptz | 폐기일 |

### 2.9 `usage_records`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | usage ID |
| `organization_id` | uuid | 조직 ID |
| `job_id` | uuid | 연관 job |
| `metric_type` | text | token/worker_seconds/storage_bytes |
| `quantity` | numeric | 수치 |
| `created_at` | timestamptz | 생성일 |

### 2.10 `audit_logs`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | uuid | audit ID |
| `organization_id` | uuid | 조직 ID |
| `actor_type` | text | user/api_key/worker/system |
| `actor_id` | text | 식별자 |
| `action` | text | event name |
| `payload` | jsonb | 상세 |
| `created_at` | timestamptz | 생성일 |

---

## 3. Auth 설계

### 3.1 권장 방식

- 사용자 로그인: Supabase Auth
- 조직 권한: `memberships`
- machine credential: `api_keys`
- worker credential: 별도 worker token 테이블 또는 secure config

### 3.2 역할 모델

- `owner`
- `admin`
- `member`
- `viewer`

---

## 4. RLS 전략

### 4.1 원칙

- 모든 조직 데이터는 `organization_id` 기반으로 제한
- 사용자는 자신이 속한 조직 데이터만 접근
- service role은 backend만 사용

### 4.2 예시 정책 방향

- `projects`: membership 존재 시 select
- `simulation_jobs`: membership 존재 시 select, member 이상이면 insert
- `artifacts`: membership 존재 시 select
- `api_keys`: admin 이상만 관리

---

## 5. Storage 설계

### 5.1 권장 bucket

- `project-sources`
- `job-artifacts`
- `reports`

### 5.2 path 규칙

```text
project-sources/org_{org_id}/project_{project_id}/source.psimsch
job-artifacts/org_{org_id}/job_{job_id}/result.json
job-artifacts/org_{org_id}/job_{job_id}/worker.log
```

### 5.3 다운로드 정책

- public bucket 금지
- signed URL 사용
- 또는 backend proxy로 다운로드 제어

---

## 6. Realtime 설계

Realtime 대상:
- `simulation_jobs`
- `job_events`

사용 예:
- 웹앱에서 job 상태 변화 구독
- 진행률 업데이트 표시

---

## 7. Supabase와 Backend 역할 분리

### 7.1 Backend가 해야 하는 것

- LLM 호출
- job validation
- worker assignment
- signed URL 발급
- API key 검증

### 7.2 Supabase가 해야 하는 것

- 데이터 저장
- 권한 기반 조회
- 인증
- realtime 전달

---

## 8. 권장 SQL/운영 포인트

### 8.1 인덱스

- `simulation_jobs (organization_id, status, created_at desc)`
- `job_events (job_id, created_at asc)`
- `artifacts (job_id)`
- `workers (status, last_heartbeat_at)`

### 8.2 cleanup 정책

- 오래된 job_events 아카이브
- 대용량 artifact lifecycle 관리
- soft delete보다는 상태 전이 + retention 권장

---

## 9. 구현 메모

- 장시간 작업은 Supabase Edge Functions가 아니라 별도 backend/worker에서 처리
- backend는 Supabase service role 남용 금지
- 사용자 요청은 항상 organization context를 명시적으로 계산

---

## 10. 결론

Supabase는 이 서비스에서 “로그인만 담당하는 부가 서비스”가 아니다.  
이 서비스의 멀티테넌트 구조, 감사 로그, 결과 저장, job 메타데이터 운영을 지탱하는 핵심 계층이다.

따라서 초기 설계 단계에서부터:

- 테이블 구조
- RLS 정책
- Storage 경로 규칙
- worker/job 상태 모델

을 함께 고정하는 것이 중요하다.
