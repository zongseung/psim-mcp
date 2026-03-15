# PSIM Cloud Service: Implementation Phases

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [development-guide.md](./development-guide.md) | [supabase-design.md](./supabase-design.md) | [architecture.md](./architecture.md)

---

## 1. 목적

이 문서는 실제 구현 착수를 위한 sprint 단위 작업 계획을 정의한다.

범위:
- backend
- Supabase
- Windows worker
- Anthropic API orchestration

원칙:
- 먼저 데이터/권한/잡 상태 모델을 고정한다
- 그 다음 backend API를 만든다
- 그 다음 worker를 붙인다
- Anthropic API는 실행 경로가 안정화된 뒤 붙인다

---

## 2. 전체 구현 순서

권장 순서:

1. Supabase schema + auth foundation
2. Backend API 최소 CRUD + job lifecycle
3. Windows worker polling/claim/complete
4. PSIM bridge + 실제 실행
5. Anthropic API 기반 자연어 실행
6. 운영 기능(usage, audit, admin)

이 순서를 권장하는 이유:
- 데이터 모델이 먼저 고정되어야 API와 worker 계약이 흔들리지 않음
- worker를 붙이기 전에 job 상태 모델이 먼저 있어야 함
- LLM은 마지막에 붙여도 되지만, 실행 경로가 안정화된 뒤 붙이는 편이 안전함

---

## 3. Sprint 계획

### Sprint 1: Supabase Foundation

목표:
- 테넌트/사용자/프로젝트/잡의 최소 데이터 구조 고정

작업:
- Supabase project 생성
- `organizations`, `memberships`, `projects`, `simulation_jobs` 테이블 생성
- 기본 인덱스 생성
- RLS 초안 작성
- 역할 모델(`owner/admin/member/viewer`) 고정
- Storage bucket 생성:
  - `project-sources`
  - `job-artifacts`

완료 기준:
- 조직 생성 가능
- 사용자와 조직 연결 가능
- 프로젝트 row 생성 가능
- job row 생성 가능

산출물:
- SQL migration 초안
- RLS 정책 초안
- 환경 변수 템플릿

---

### Sprint 2: Backend Auth + Project API

목표:
- 로그인 사용자 기준으로 프로젝트를 생성/조회할 수 있는 backend API 구성

작업:
- backend 프로젝트 초기 구조 생성
- Supabase JWT 검증 middleware
- organization context resolver
- `POST /v1/projects`
- `GET /v1/projects`
- `GET /v1/projects/{id}`
- repository 계층 추가
- 공통 응답 포맷 고정

완료 기준:
- 로그인 사용자 기준 프로젝트 CRUD 일부 가능
- 다른 조직 프로젝트 접근 차단

산출물:
- backend API skeleton
- auth middleware
- project repository/service

---

### Sprint 3: Job Lifecycle API

목표:
- 시뮬레이션 job을 등록하고 조회하는 최소 흐름 완성

작업:
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs`
- job status enum 고정
- job spec validator 구현
- `job_events`, `artifacts` 테이블 추가
- job 생성 시 audit log 기록

완료 기준:
- 구조화 요청으로 job 생성 가능
- queued 상태 조회 가능
- job 상세 조회 가능

산출물:
- job validator
- job service/repository
- audit logging 기본 구조

---

### Sprint 4: Worker Control API

목표:
- Windows worker가 job을 claim하고 상태를 업데이트할 수 있게 함

작업:
- `POST /internal/workers/register`
- `POST /internal/workers/heartbeat`
- `POST /internal/workers/claim-next-job`
- `POST /internal/workers/{worker_id}/jobs/{job_id}/events`
- `POST /internal/workers/{worker_id}/jobs/{job_id}/complete`
- `POST /internal/workers/{worker_id}/jobs/{job_id}/fail`
- worker token 인증 추가
- `workers` 테이블 추가

완료 기준:
- worker register 가능
- heartbeat 저장 가능
- queued job을 worker가 claim 가능
- complete/fail로 상태 전이 가능

산출물:
- internal worker API
- worker auth 방식
- 상태 전이 로직

---

### Sprint 5: Windows Worker Agent

목표:
- 실제 Windows worker 프로세스가 control plane과 통신할 수 있도록 함

작업:
- worker agent 프로젝트 생성
- worker token 기반 인증 구현
- polling loop 구현
- claim-next-job 호출
- progress/fail/complete 보고
- 로컬 working directory 정책 구현
- artifact 업로드 client 구현

완료 기준:
- Windows worker가 job을 가져와 상태를 업데이트할 수 있음
- 아직 PSIM 실행이 없어도 mock job 처리 가능

산출물:
- worker agent
- local filesystem layout
- worker logging

---

### Sprint 6: PSIM Bridge Integration

목표:
- Windows worker에서 실제 PSIM 실행 경로 연결

작업:
- `bridge_script.py` 정리
- worker에서 PSIM Python 실행 파일 호출
- 프로젝트 다운로드/배치
- `open_project -> set_parameter -> run_simulation -> export_results` 흐름 연결
- artifact 저장
- timeout / 실패 처리

완료 기준:
- 샘플 `.psimsch` 기준 실제 실행 성공
- 결과 artifact 업로드 성공
- 실패 시 job fail 처리 가능

산출물:
- real worker execution path
- timeout/retry 기본 정책
- 샘플 integration test 시나리오

---

### Sprint 7: Natural Language Orchestration

목표:
- Anthropic API로 자연어를 job spec으로 변환

작업:
- `POST /v1/assistant/jobs`
- prompt template 설계
- structured output schema 정의
- LLM output validator 구현
- 안전 규칙:
  - 허용 가능한 operation만 승인
  - 허용 가능한 parameter만 승인
  - path 직접 입력 제한

완료 기준:
- 자연어 요청으로 구조화 job 등록 가능
- backend validation 이후에만 job 생성

산출물:
- assistant orchestration service
- validation layer
- prompt spec

---

### Sprint 8: Artifact Retrieval + Realtime

목표:
- 결과 조회 경험 개선

작업:
- `GET /v1/jobs/{job_id}/artifacts`
- signed URL 발급
- Supabase Realtime 기반 job status push
- 프론트엔드/클라이언트용 polling + realtime 가이드

완료 기준:
- 결과 파일 접근 가능
- job 상태 변경을 실시간에 가깝게 확인 가능

산출물:
- artifact service
- realtime subscription 흐름

---

### Sprint 9: Usage / Audit / Admin

목표:
- 운영 가능한 제품 수준의 기록/추적 기능 추가

작업:
- `usage_records` 기록
- `audit_logs` 확장
- API key 관리
- admin 조회 API
- worker 상태/실패율 조회

완료 기준:
- 조직별 사용량 추적 가능
- 누가 어떤 job을 실행했는지 추적 가능
- 운영자 관점 진단 가능

산출물:
- admin/reporting query
- API key lifecycle
- 운영 대시보드 데이터 구조

---

### Sprint 10: Paid Pilot Readiness

목표:
- 첫 유료 파일럿 운영 가능한 수준 정리

작업:
- 장애 대응 runbook 작성
- 고객 온보딩 절차 작성
- 전용 worker 배치 템플릿 작성
- 보안/권한 최종 점검
- 계약/운영 체크리스트 정리

완료 기준:
- single-tenant 또는 dedicated hosted 형태로 첫 고객 적용 가능

산출물:
- 운영 문서
- 온보딩 문서
- 배포 체크리스트

---

## 4. 병렬 진행 가능한 항목

아래는 병렬 진행 가능하다.

- Sprint 2 backend auth/project API
- Sprint 5 worker agent mock loop
- Sprint 7 prompt/output schema 설계 초안

단, 아래는 선행 순서를 지키는 것이 좋다.

- Sprint 1 완료 전 job/worker API 상세 구현
- Sprint 4 완료 전 real worker 실행 연결
- Sprint 6 완료 전 자연어 기반 실제 실행 공개

---

## 5. 최소 MVP 경계

가장 작은 상업용 MVP는 Sprint 6까지다.

MVP 포함:
- Supabase auth + org + project + jobs
- backend job API
- Windows worker
- 실제 PSIM 실행
- 결과 저장/조회

MVP 제외 가능:
- Realtime
- API key
- usage billing
- 고급 admin
- compare/sweep 고도화

---

## 6. 팀 역할 분담 예시

### Backend 담당
- Supabase schema
- auth
- project/job API
- orchestration

### Worker 담당
- Windows agent
- PSIM bridge
- artifact handling

### Product/Infra 담당
- 환경 변수/비밀 관리
- 배포 구조
- 운영 문서
- tenant 전략/고객 환경 설계

---

## 7. 리스크 기반 우선순위

가장 먼저 검증해야 하는 리스크:

1. Windows worker에서 실제 PSIM job 수행 가능 여부
2. Supabase 기반 조직 격리/RLS 구현 난이도
3. Anthropic output을 안전하게 구조화 spec으로 제한할 수 있는지

따라서 제품적으로 중요한 기능보다도 아래를 먼저 확인해야 한다.

- real worker execution
- job status consistency
- tenant data isolation

---

## 8. 최종 권장안

실행 순서를 한 줄로 줄이면:

**Supabase → Backend Job API → Worker Control → Windows Worker → PSIM Integration → Anthropic API → 운영 기능**

이 순서를 지키면 가장 적은 재작업으로 제품형 구조를 만들 수 있다.
