# PSIM Cloud Service: Tenant Strategy

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [architecture.md](./architecture.md) | [supabase-design.md](./supabase-design.md) | [commercialization-strategy.md](./commercialization-strategy.md)

---

## 1. 목적

이 문서는 PSIM Cloud Service를 `single-tenant` 중심 초기 구조에서 `multi-tenant SaaS`로 확장하기 위한 테넌트 전략을 정리한다.

핵심 원칙:

- 처음부터 완전 멀티테넌트로 가지 않는다
- 데이터 격리와 worker 격리를 분리해서 생각한다
- 테넌트 전략은 영업 모델과 함께 움직여야 한다

---

## 2. 테넌트 모델 정의

### 2.1 Single-Tenant

정의:
- 고객 1곳이 전용 환경을 사용

특징:
- 운영 단순
- 보안 설명이 쉬움
- 초기 판매에 적합

### 2.2 Shared Control Plane + Dedicated Worker

정의:
- API/backend/Supabase는 공유하지만 worker는 고객 전용

특징:
- 초기 SaaS와 전용형 사이의 절충안
- 고객 데이터와 실행 환경을 부분적으로 분리 가능

### 2.3 Multi-Tenant Shared Platform

정의:
- control plane과 worker pool을 여러 고객이 공유

특징:
- 가장 높은 확장성
- 가장 높은 격리/보안/운영 난이도

---

## 3. 권장 진화 단계

### Stage 1. Single-Tenant

권장 시점:
- 첫 고객
- PoC
- 유료 pilot

구성:
- 고객별 backend config
- 고객별 Supabase project 또는 별도 DB schema
- 고객별 worker

장점:
- 구현/설득이 가장 쉽다

단점:
- 운영 효율이 낮다

### Stage 2. Shared Control Plane + Org Isolation

권장 시점:
- 고객 수가 3~10개 수준으로 늘 때

구성:
- 하나의 control plane
- 하나의 Supabase
- `organization_id` 기반 격리
- 고객별 dedicated worker 또는 worker group

장점:
- 운영 효율 개선
- 멀티테넌트 운영 연습 가능

단점:
- RLS/권한 실수가 곧 데이터 노출 리스크가 됨

### Stage 3. Shared Worker Pool

권장 시점:
- worker scheduling과 isolation이 충분히 검증된 뒤

구성:
- 여러 조직이 공통 worker pool 사용
- job dispatch 시 조직 context 강제
- artifact 경로/캐시/임시파일 정리 엄격화

장점:
- 비용 효율 증가

단점:
- 실행 환경 혼선, 임시파일 누출, 라이선스 정책 이슈 위험 증가

---

## 4. Supabase 기준 테넌트 전략

### 4.1 필수 원칙

- 모든 business row에 `organization_id` 포함
- RLS는 “조직 멤버십 존재”를 기본 조건으로 사용
- backend service role은 최소 범위로만 사용

### 4.2 조직 경계가 필요한 테이블

- `projects`
- `simulation_jobs`
- `job_events`
- `artifacts`
- `api_keys`
- `usage_records`
- `audit_logs`

### 4.3 조직 경계가 간접적으로 필요한 테이블

- `workers`
  - shared worker일 경우 tenant-agnostic
  - dedicated worker일 경우 `organization_id` 또는 `worker_group_id`로 연결

---

## 5. Worker 격리 전략

### 5.1 초기 권장

- 고객별 dedicated worker

이유:

- 파일 시스템 격리 설명이 쉬움
- PSIM 실행 충돌 리스크 감소
- 라이선스 관리가 단순함

### 5.2 전환 시점

shared worker pool은 아래가 갖춰진 뒤에만 검토한다.

1. job sandboxing
2. 임시 디렉터리 완전 분리
3. artifact 업로드 후 로컬 청소 보장
4. worker reset 정책
5. 라이선스 정책 명확화

---

## 6. 데이터 격리 전략

### 6.1 애플리케이션 레벨

- 모든 API 요청에서 organization context 계산
- project/job 조회는 organization scope 강제

### 6.2 데이터베이스 레벨

- Supabase RLS 정책 적용
- service role은 내부 백엔드에서만 사용

### 6.3 스토리지 레벨

경로 예시:

```text
project-sources/org_{org_id}/project_{project_id}/source.psimsch
job-artifacts/org_{org_id}/job_{job_id}/result.json
```

### 6.4 워커 파일시스템 레벨

로컬 작업 경로 예시:

```text
C:\psim-workers\jobs\org_{org_id}\job_{job_id}\
```

---

## 7. 멀티테넌트 전환 체크포인트

아래가 모두 만족될 때만 shared platform 비중을 높인다.

1. RLS 정책 검증 완료
2. signed URL/다운로드 권한 검증 완료
3. worker 임시파일 청소 자동화 완료
4. worker 장애 복구 정책 완료
5. 감사 로그에서 tenant 경계 추적 가능
6. usage 측정이 tenant 단위로 정확함

---

## 8. 추천 운영 모델

### 8.1 초기

- single-tenant
- 고객별 전용 worker

### 8.2 성장 단계

- shared control plane
- dedicated worker group per customer

### 8.3 후반

- selected shared worker pool
- high-trust low-risk workload만 공유 실행

---

## 9. 안티패턴

초기에 피해야 할 것:

- 처음부터 모든 고객을 shared worker에 태우는 것
- worker 파일시스템을 조직별로 분리하지 않는 것
- RLS 없이 backend만 믿고 tenant 경계를 처리하는 것
- API key와 사용자 권한을 같은 수준으로 취급하는 것

---

## 10. 최종 권장안

가장 현실적인 tenant 전략은 다음과 같다.

1. **Single-Tenant / Dedicated Worker**로 시작
2. **Shared Control Plane + Org-isolated Supabase**로 확장
3. **Dedicated Worker Group** 모델 유지
4. Shared worker pool은 가장 마지막에 일부 고객/일부 workload에만 적용

---

## 11. 결론

이 서비스에서 테넌트 전략의 핵심은 “데이터베이스만 멀티테넌트로 만든다고 끝나는 것”이 아니다.

실제 중요한 경계는 3개다.

- 데이터 경계
- 파일 경계
- 실행 환경 경계

따라서 초기 상업화 단계에서는 **single-tenant 또는 dedicated-worker 구조가 가장 안전하고 현실적**이다.
