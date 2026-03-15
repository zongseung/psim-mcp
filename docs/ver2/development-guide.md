# PSIM Cloud Service: Development Guide

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md) | [supabase-design.md](./supabase-design.md)

---

## 1. 개발 원칙

이 버전은 더 이상 로컬 Claude Desktop 중심 프로젝트가 아니다.  
핵심은 아래 3개다.

- Anthropic API 기반 orchestration
- Supabase 기반 auth/data/storage
- Windows PSIM Worker 기반 실행

---

## 2. 추천 저장소 구조

```text
repo/
├── backend/          # control plane API
├── worker/           # Windows worker + bridge
├── web/              # 사용자 웹앱
├── infra/            # 배포 설정
└── docs/ver2/        # 서비스 문서
```

---

## 3. 단계별 구현 순서

### Phase 1: Control Plane 최소 구현

목표:
- Supabase 연결
- 조직/프로젝트/job CRUD
- 구조화 job 등록 API

필수 작업:
1. Supabase project 생성
2. DB schema/migration 작성
3. backend auth middleware 작성
4. 프로젝트 등록 API 작성
5. job 생성 API 작성

### Phase 2: Worker Plane 구현

목표:
- Windows worker에서 queue pickup 후 PSIM 실행

필수 작업:
1. worker register/heartbeat 구현
2. claim-next-job 구현
3. bridge script 연결
4. 결과 업로드 구현

### Phase 3: Anthropic API 연결

목표:
- 자연어 요청을 job spec으로 변환

필수 작업:
1. prompt template 작성
2. structured output schema 정의
3. backend validation 추가
4. assistant job API 구현

### Phase 4: 운영/상용화 기능

목표:
- 감사 로그, 사용량, 조직 권한, API key

필수 작업:
1. usage tracking
2. API key 발급/회수
3. audit logs
4. worker draining / retry / timeout 정책

---

## 4. 환경 변수 설계

### 4.1 Backend

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=

JOB_CLAIM_TIMEOUT_SECONDS=30
JOB_MAX_RUNTIME_SECONDS=1800
SIGNED_URL_TTL_SECONDS=3600
```

### 4.2 Windows Worker

```env
WORKER_NAME=win-worker-01
CONTROL_PLANE_URL=
WORKER_TOKEN=

PSIM_PATH=
PSIM_PYTHON_EXE=
PSIM_PROJECT_ROOT=
PSIM_OUTPUT_ROOT=
WORKER_POLL_INTERVAL_SECONDS=5
```

---

## 5. Supabase 적용 지침

### 5.1 Supabase를 반드시 쓰는 영역

- 사용자 인증
- 조직/멤버십 저장
- 프로젝트/잡/아티팩트 메타데이터 저장
- 감사 로그 저장
- 결과 다운로드 권한 제어

### 5.2 Supabase에 넣지 말아야 하는 영역

- 장시간 simulation 실행 로직
- PSIM subprocess lifecycle
- worker 스케줄링의 핵심 로직

### 5.3 구현 방식

- backend는 `service role key`를 제한적으로 사용
- 일반 사용자 요청은 Supabase JWT로 조직 context 확인
- DB 접근은 repository 계층으로 감싼다

---

## 6. Anthropic API 적용 지침

목표:
- 자연어를 그대로 실행하지 않고, 구조화된 실행 spec으로 변환

권장 출력 스키마 예:

```json
{
  "operation": "run_simulation",
  "project_id": "proj_123",
  "parameter_updates": [
    {
      "component_id": "SW1",
      "parameter_name": "switching_frequency",
      "value": 80000
    }
  ],
  "simulation_options": {
    "time_step": 1e-6,
    "total_time": 0.1
  },
  "export": {
    "format": "json",
    "signals": ["Vout"]
  }
}
```

주의:
- LLM 출력은 backend validator를 반드시 거친다
- 허용되지 않은 경로, 파라미터, 과도한 실행 길이는 차단한다

---

## 7. 구현 권장 우선순위

1. Supabase schema
2. backend auth + project/job API
3. Windows worker claim/complete API
4. bridge script + PSIM execution
5. Anthropic API orchestration
6. artifacts + signed URL
7. audit + usage + admin views

---

## 8. 테스트 전략

### 8.1 Backend
- auth / org permission test
- job lifecycle test
- Anthropic output validation test

### 8.2 Worker
- job claim test
- timeout / retry test
- artifact upload test

### 8.3 Integration
- backend ↔ Supabase
- backend ↔ worker
- worker ↔ PSIM

---

## 9. 상용화 전 체크리스트

- Altair/PSIM 라이선스 정책 확인
- Anthropic 상업용 API 계약 확인
- 조직별 데이터 격리 검증
- worker token 보안 검증
- 운영 로그/감사 로그 검증
- 결과 다운로드 권한 검증
