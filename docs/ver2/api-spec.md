# PSIM Cloud Service: API Specification

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [architecture.md](./architecture.md)

---

## 1. 개요

이 문서는 외부 클라이언트와 Windows Worker가 사용하는 SaaS API를 정의한다.

- Client API: 사용자/조직/프로젝트/job/결과 조회
- Internal Worker API: worker 등록, heartbeat, job claim, job completion

---

## 2. 공통 응답 형식

### 2.1 성공 응답

```json
{
  "success": true,
  "data": {},
  "message": "optional"
}
```

### 2.2 실패 응답

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error",
    "suggestion": "optional"
  }
}
```

### 2.3 공통 에러 코드

| 코드 | 설명 |
|------|------|
| `UNAUTHORIZED` | 인증 실패 |
| `FORBIDDEN` | 권한 없음 |
| `INVALID_INPUT` | 입력 검증 실패 |
| `PROJECT_NOT_FOUND` | 프로젝트 없음 |
| `JOB_NOT_FOUND` | job 없음 |
| `WORKER_OFFLINE` | 사용 가능한 worker 없음 |
| `JOB_FAILED` | job 실행 실패 |
| `RATE_LIMITED` | 요청 제한 초과 |
| `INTERNAL_ERROR` | 내부 오류 |

---

## 3. Auth

인증 방식:
- 사용자: Supabase JWT
- 시스템 간 통신: service token / worker token / API key

---

## 4. Client API

### 4.1 `POST /v1/projects`

설명:
- 프로젝트 등록

입력:

```json
{
  "name": "buck-converter",
  "description": "48V to 12V",
  "storage_path": "projects/org_123/buck.psimsch",
  "default_simulation_options": {
    "time_step": 1e-6,
    "total_time": 0.1
  }
}
```

### 4.2 `GET /v1/projects`

설명:
- 현재 조직의 프로젝트 목록 조회

### 4.3 `POST /v1/jobs`

설명:
- 구조화 실행 job 등록

입력:

```json
{
  "project_id": "proj_123",
  "operation": "run_simulation",
  "parameters": [
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
    "signals": ["Vout", "IL"]
  }
}
```

### 4.4 `POST /v1/assistant/jobs`

설명:
- 자연어 요청 기반 job 생성

입력:

```json
{
  "project_id": "proj_123",
  "prompt": "스위칭 주파수를 80kHz로 바꾸고 0.1초 시뮬레이션 실행해줘"
}
```

출력(`data`):

```json
{
  "job_id": "job_123",
  "parsed_plan": {
    "operation": "run_simulation",
    "parameter_updates": [
      {
        "component_id": "SW1",
        "parameter_name": "switching_frequency",
        "value": 80000
      }
    ]
  }
}
```

### 4.5 `GET /v1/jobs/{job_id}`

설명:
- job 상태 조회

출력(`data`):

```json
{
  "id": "job_123",
  "status": "running",
  "project_id": "proj_123",
  "worker_id": "worker_a",
  "created_at": "2026-03-15T10:00:00Z",
  "started_at": "2026-03-15T10:00:05Z",
  "finished_at": null,
  "summary": null
}
```

### 4.6 `GET /v1/jobs/{job_id}/artifacts`

설명:
- 결과 artifact 목록 조회

### 4.7 `POST /v1/jobs/{job_id}/cancel`

설명:
- 대기 중 또는 실행 중 job 취소 요청

---

## 5. Worker API

### 5.1 `POST /internal/workers/register`

설명:
- worker 등록

입력:

```json
{
  "worker_name": "win-worker-01",
  "capabilities": {
    "psim_version": "2025",
    "max_parallel_jobs": 1
  }
}
```

### 5.2 `POST /internal/workers/heartbeat`

설명:
- worker 상태 heartbeat

### 5.3 `POST /internal/workers/claim-next-job`

설명:
- worker가 다음 job을 가져감

출력(`data`):

```json
{
  "job": {
    "id": "job_123",
    "project_id": "proj_123",
    "operation": "run_simulation",
    "payload": {}
  }
}
```

### 5.4 `POST /internal/workers/{worker_id}/jobs/{job_id}/events`

설명:
- worker가 진행 이벤트를 push

### 5.5 `POST /internal/workers/{worker_id}/jobs/{job_id}/complete`

설명:
- job 완료 처리

입력:

```json
{
  "status": "completed",
  "summary": {
    "output_voltage_avg": 12.01,
    "efficiency": 95.3
  },
  "artifacts": [
    {
      "kind": "result_json",
      "storage_path": "artifacts/org_123/job_123/result.json"
    }
  ]
}
```

### 5.6 `POST /internal/workers/{worker_id}/jobs/{job_id}/fail`

설명:
- job 실패 처리

---

## 6. 상태 모델

### 6.1 Job 상태

- `queued`
- `claimed`
- `running`
- `completed`
- `failed`
- `cancel_requested`
- `cancelled`

### 6.2 Worker 상태

- `online`
- `busy`
- `offline`
- `draining`

---

## 7. 설계 메모

- 외부 API는 사용자/조직 관점
- internal API는 worker 관점
- long-running 작업은 synchronous HTTP 응답으로 처리하지 않음
- realtime 업데이트는 Supabase Realtime 또는 WebSocket 확장 가능
