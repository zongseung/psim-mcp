# PSIM Cloud Service: Architecture Document

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [supabase-design.md](./supabase-design.md)

---

## 1. 시스템 전체 구조

```text
┌────────────────────────────────────────────────────┐
│                Client (Web / API)                 │
└───────────────────────┬────────────────────────────┘
                        │ HTTPS
                        ▼
┌────────────────────────────────────────────────────┐
│         Control Plane API (Linux backend)         │
│  - Auth context                                    │
│  - Anthropic orchestration                         │
│  - Job validation                                  │
│  - Queue scheduling                                │
└───────────────┬───────────────────┬────────────────┘
                │                   │
                │                   │
                ▼                   ▼
     ┌──────────────────┐   ┌───────────────────────┐
     │  Anthropic API   │   │      Supabase         │
     │  - intent parse  │   │  Auth / Postgres      │
     │  - plan extract  │   │  Storage / Realtime   │
     └──────────────────┘   └───────────────────────┘
                                         │
                                         ▼
                           ┌──────────────────────────┐
                           │ Windows Worker Control   │
                           │  - job polling           │
                           │  - heartbeat             │
                           │  - artifact reporting    │
                           └───────────┬──────────────┘
                                       ▼
                           ┌──────────────────────────┐
                           │ Windows PSIM Worker      │
                           │  - bridge_script.py      │
                           │  - PSIM Python API       │
                           │  - result export         │
                           └──────────────────────────┘
```

---

## 2. 핵심 설계 원칙

1. **Claude Desktop 제거**
- 외부 서비스형 구조에서는 로컬 MCP 클라이언트가 아니라 SaaS API가 중심이다.

2. **Control Plane / Worker Plane 분리**
- API 서버와 Windows PSIM 실행 환경을 분리한다.

3. **Supabase는 시스템 오브 레코드**
- 사용자, 조직, 프로젝트 메타데이터, job 상태, artifact 메타데이터, 감사 로그를 저장한다.

4. **Anthropic API는 의도 해석 전용**
- LLM은 “무엇을 실행할지”를 도와주고, 실제 실행 권한/검증은 backend가 가진다.

5. **Windows Worker는 비신뢰성 환경으로 가정**
- worker 장애, timeout, partial failure를 전제로 재시도/복구를 설계한다.

---

## 3. 컴포넌트 상세

### 3.1 Client Layer

형태:
- 웹앱
- 내부 CLI
- 외부 시스템 연동 API 클라이언트

역할:
- 로그인
- 프로젝트 선택/업로드
- 자연어 요청 또는 구조화 job 등록
- job 상태/결과 조회

### 3.2 Control Plane API

권장 역할:
- 인증 토큰 검증
- 조직/권한 체크
- Anthropic API 호출
- job spec 생성
- validation
- worker 배정
- 결과 요약 API 제공

이 계층은 장시간 시뮬레이션을 직접 실행하지 않는다.

### 3.3 Anthropic Orchestration Layer

역할:
- 자연어 요청을 내부 JSON 실행 계획으로 변환
- 예: 프로젝트 ID, 대상 파라미터, 실행 옵션, export 요구사항

주의:
- LLM 출력은 그대로 실행하지 않는다
- backend validation 후에만 job 생성

### 3.4 Supabase

사용 범위:
- Auth
- Postgres
- Realtime
- Storage

권장 사용 방식:
- **Auth**: 이메일, SSO, service account
- **Postgres**: 조직, 프로젝트, job, worker, usage, audit
- **Storage**: 결과 JSON/CSV/리포트
- **Realtime**: job 상태 업데이트 push

권장하지 않는 역할:
- 장시간 PSIM 실행
- Windows Worker orchestration 자체

### 3.5 Queue / Scheduler

권장 구현:
- Postgres 기반 job table + 상태 전이
- 또는 별도 queue 시스템 도입 가능

초기 버전 권장:
- Supabase Postgres에 `simulation_jobs` 테이블 기반 queue
- worker가 polling 또는 dispatch 기반으로 가져감

### 3.6 Windows Worker

구성:
- worker agent
- PSIM 설치
- PSIM Python API
- bridge script

역할:
- job 수신
- 프로젝트 다운로드/준비
- PSIM 실행
- 결과 export
- artifact 업로드
- heartbeat 전송

---

## 4. 주요 요청 흐름

### 4.1 자연어 실행 요청

1. 사용자 요청 수신
2. backend가 권한 확인
3. Anthropic API 호출
4. 내부 job spec 생성
5. spec validation
6. Supabase에 job row 생성
7. worker가 job pickup
8. PSIM 실행
9. 결과 업로드 및 상태 업데이트
10. client가 polling/realtime으로 상태 확인

### 4.2 구조화 API 실행 요청

1. API key 검증
2. 프로젝트/조직 권한 확인
3. job 생성
4. worker 실행
5. artifact 저장

---

## 5. Supabase 적용 원칙

### 5.1 왜 Supabase를 쓰는가

- 빠른 B2B auth 구성
- 멀티테넌트 Postgres + RLS
- Realtime subscription
- 파일 저장소
- 운영 속도 향상

### 5.2 Supabase에 두는 것

- organizations
- memberships
- projects
- simulation_jobs
- job_events
- artifacts
- workers
- usage_records
- audit_logs

### 5.3 Supabase에 두지 않는 것

- Windows worker 실행 로직
- 장시간 simulation process
- PSIM Python API 직접 호출

---

## 6. 보안 구조

### 6.1 인증/인가

- Supabase JWT 기반 인증
- 조직 단위 role 분리
- RLS로 행 단위 접근 제한

### 6.2 Worker 인증

- worker는 별도 machine token 사용
- 조직 사용자 토큰과 분리

### 6.3 파일 보안

- 원본 프로젝트 파일은 조직별 namespace 분리
- 결과 파일은 signed URL 또는 backend proxy로 다운로드

### 6.4 LLM 보안

- LLM 출력은 실행 spec 초안일 뿐
- backend validation과 allowlist 검증 필수

---

## 7. 권장 디렉터리 구조

```text
psim-cloud/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── services/
│   │   ├── orchestration/
│   │   ├── workers/
│   │   ├── repositories/
│   │   └── models/
│   ├── migrations/
│   └── tests/
├── worker/
│   ├── agent/
│   ├── bridge/
│   └── tests/
├── web/
├── infra/
└── docs/
```

---

## 8. 배포 전략

### 8.1 권장 초기 구조

- Backend: Linux container
- Database/Auth/Storage: Supabase
- Worker: Windows VM 또는 전용 머신

### 8.2 Docker 적용 범위

- backend/web/utility 서비스에는 적합
- Windows PSIM worker에는 기본적으로 부적합 또는 제한적

### 8.3 상용화 전략

1. single-tenant pilot
2. dedicated worker per customer
3. 제한적 multi-tenant

---

## 9. 리스크

| 리스크 | 설명 | 대응 |
|--------|------|------|
| PSIM 라이선스/실행 제약 | hosted worker 운영 가능 범위 불명확 | 계약/법무 확인 |
| Worker 안정성 | Windows 환경 변동성 | heartbeat, retry, draining |
| LLM 오작동 | 잘못된 실행 spec | strict validation |
| 파일 크기 증가 | 결과 파일 누적 | lifecycle 정책 |
| 멀티테넌시 | 데이터 섞임 위험 | RLS + 조직 스코프 강제 |
