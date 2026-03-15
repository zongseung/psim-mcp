# PSIM Cloud Service: Worker Implementation Spec

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [implementation-phases.md](./implementation-phases.md) | [architecture.md](./architecture.md) | [backend-implementation-spec.md](./backend-implementation-spec.md)

---

## 1. 목적

이 문서는 Windows PSIM Worker를 실제로 구현하기 위한 상세 명세다.

범위:
- worker agent
- polling / claim / execution / complete / fail
- bridge script 호출
- 로컬 파일 경로 관리
- artifact 업로드

비범위:
- backend API 자체 구현
- 웹앱

---

## 2. Worker의 역할

Worker는 아래 역할만 수행한다.

1. control plane에서 job을 가져온다
2. 실행에 필요한 파일을 준비한다
3. PSIM을 호출한다
4. 결과를 export한다
5. artifact를 업로드한다
6. 상태와 로그를 보고한다

Worker는 business rule을 결정하지 않는다.  
실행 결정은 backend가 하고, worker는 이를 수행한다.

---

## 3. 권장 구조

```text
worker/
├── agent/
│   ├── main.py
│   ├── config.py
│   ├── loop.py
│   ├── heartbeat.py
│   ├── claim.py
│   ├── executor.py
│   ├── uploader.py
│   ├── reporter.py
│   └── cleanup.py
├── bridge/
│   ├── bridge_script.py
│   ├── protocol.py
│   └── serializers.py
├── integrations/
│   ├── control_plane_client.py
│   ├── storage_client.py
│   └── psim_runner.py
├── models/
│   ├── job.py
│   ├── results.py
│   └── events.py
├── utils/
│   ├── paths.py
│   ├── time.py
│   └── logging.py
└── tests/
```

---

## 4. Worker 구성요소

### 4.1 `main.py`

역할:
- 설정 로드
- 로깅 초기화
- worker register
- 메인 loop 시작

### 4.2 `loop.py`

역할:
- heartbeat 주기 관리
- claim-next-job polling
- job 없을 때 sleep
- draining/shutdown 처리

### 4.3 `executor.py`

역할:
- job 실행의 중심 orchestrator
- 작업 디렉터리 생성
- 프로젝트 다운로드
- bridge script 호출
- artifact 생성 경로 관리

### 4.4 `reporter.py`

역할:
- progress event 전송
- complete/fail 보고

### 4.5 `cleanup.py`

역할:
- 로컬 임시 파일 정리
- job 완료 후 폴더 제거 또는 아카이브

---

## 5. 설정 설계

### 5.1 필수 환경 변수

```env
WORKER_NAME=win-worker-01
CONTROL_PLANE_URL=https://api.example.com
WORKER_TOKEN=

PSIM_PATH=C:\Altair\Altair_PSIM_2025
PSIM_PYTHON_EXE=C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe
PSIM_PROJECT_ROOT=C:\psim-workers\projects
PSIM_OUTPUT_ROOT=C:\psim-workers\outputs
WORKER_ROOT=C:\psim-workers

WORKER_POLL_INTERVAL_SECONDS=5
WORKER_HEARTBEAT_INTERVAL_SECONDS=15
JOB_TIMEOUT_SECONDS=1800
```

### 5.2 `config.py` 권장 필드

- worker_name
- control_plane_url
- worker_token
- psim_path
- psim_python_exe
- worker_root
- project_root
- output_root
- poll_interval_seconds
- heartbeat_interval_seconds
- job_timeout_seconds

---

## 6. 로컬 파일 시스템 정책

### 6.1 작업 디렉터리 규칙

권장 예시:

```text
C:\psim-workers\
├── jobs\
│   └── org_{org_id}\
│       └── job_{job_id}\
│           ├── source\
│           ├── output\
│           └── logs\
├── cache\
└── temp\
```

### 6.2 원칙

- job마다 완전히 분리된 디렉터리 사용
- org/job 식별자를 경로에 반영
- 완료 후 cleanup 수행
- 실패해도 cleanup가 보장되도록 `finally` 처리

### 6.3 금지

- 여러 job이 같은 output 디렉터리를 공유
- 사용자 입력을 직접 파일 경로로 사용
- cleanup 없는 장기 누적

---

## 7. Worker Control Loop

### 7.1 기본 흐름

1. worker register
2. main loop 진입
3. heartbeat 주기적으로 전송
4. idle이면 claim-next-job 호출
5. job을 받으면 `executor.execute(job)`
6. 완료/실패 보고
7. cleanup 후 다음 loop

### 7.2 pseudo flow

```python
while True:
    maybe_send_heartbeat()
    if current_job is None:
        job = claim_next_job()
        if not job:
            sleep(poll_interval)
            continue
    execute(job)
```

### 7.3 shutdown 처리

권장:
- `draining` 상태 지원
- 현재 job 종료 후 새 claim 중단

---

## 8. Job Execution 단계

### 8.1 준비 단계

- job payload 검증
- 작업 디렉터리 생성
- 프로젝트 파일 다운로드
- 실행 옵션 준비

### 8.2 실행 단계

기본 순서:
1. `open_project`
2. `set_parameter` 반복
3. `run_simulation`
4. `export_results`
5. 결과 파일 확인

### 8.3 종료 단계

- artifact 업로드
- complete/fail 보고
- cleanup

---

## 9. Bridge Script 설계

### 9.1 역할

`bridge_script.py`는 PSIM 번들 Python 환경에서 실행된다.

역할:
- stdin으로 JSON 입력 수신
- PSIM API 호출
- stdout으로 JSON 응답 반환

### 9.2 프로토콜

입력:

```json
{
  "action": "run_simulation",
  "params": {}
}
```

출력:

```json
{
  "success": true,
  "data": {}
}
```

### 9.3 지원 action

- `open_project`
- `set_parameter`
- `run_simulation`
- `export_results`
- `get_status`
- `get_project_info`

### 9.4 원칙

- stderr는 디버그용 로그, 사용자 응답으로 직접 전달하지 않음
- 응답 포맷은 항상 JSON
- bridge 내부 예외는 표준 error envelope로 감싼다

---

## 10. `psim_runner.py` 설계

역할:
- Python 3.8 executable 호출
- bridge script 실행
- timeout 관리
- JSON 파싱

권장 메서드:

```python
class PsimRunner:
    async def open_project(...)
    async def set_parameter(...)
    async def run_simulation(...)
    async def export_results(...)
```

`psim_runner`는 bridge protocol client다.

---

## 11. Control Plane Client 설계

### 11.1 책임

- register
- heartbeat
- claim-next-job
- progress event 전송
- complete
- fail

### 11.2 권장 메서드

```python
class ControlPlaneClient:
    async def register_worker(...)
    async def send_heartbeat(...)
    async def claim_next_job(...)
    async def post_job_event(...)
    async def complete_job(...)
    async def fail_job(...)
```

---

## 12. Artifact Upload 설계

### 12.1 worker 책임

- 결과 파일 path 수집
- backend 또는 signed upload 경로로 업로드
- 업로드 후 artifact metadata 전달

### 12.2 업로드 단위

초기 권장:
- result json
- csv export
- worker log
- bridge stderr log

### 12.3 업로드 실패 처리

- artifact 업로드 실패 시 job 전체를 fail로 둘지
- simulation은 성공했지만 업로드만 실패한 상태를 별도로 둘지

초기 권장:
- artifact 업로드 실패는 `failed` 처리

---

## 13. 상태 전이 규칙

worker 관점 상태:
- `idle`
- `claiming`
- `running`
- `uploading`
- `reporting`
- `draining`
- `offline`

job 관점 상태:
- `queued`
- `claimed`
- `running`
- `completed`
- `failed`
- `cancel_requested`
- `cancelled`

---

## 14. 실패 처리 전략

### 14.1 실패 유형

- control plane 통신 실패
- bridge script 실행 실패
- PSIM import 실패
- PSIM 실행 실패
- timeout
- artifact upload 실패
- cleanup 실패

### 14.2 권장 처리

- recoverable network failure: retry
- PSIM 실행 실패: fail
- timeout: fail + cleanup
- cleanup 실패: warning event + local log

---

## 15. 로그 설계

로그 분리:
- `worker.log`
- `bridge.log`
- `job_{id}.log`

로그 필드 권장:
- timestamp
- worker_name
- job_id
- event_type
- duration_ms
- status

---

## 16. 보안 원칙

1. worker token은 로컬 안전 저장
2. 사용자 경로 입력 직접 사용 금지
3. organization/job 기반 경로만 허용
4. bridge stderr/raw error를 그대로 사용자에게 노출 금지
5. artifact 업로드 전에 허용된 파일만 선택

---

## 17. 테스트 계획

### 17.1 unit
- config parsing
- path builder
- cleanup logic
- bridge protocol parsing

### 17.2 integration
- control plane mock server와 worker 통신
- bridge subprocess 호출
- artifact upload flow

### 17.3 real environment
- Windows + PSIM smoke test
- sample project execution
- parameter update + simulation + export full flow

---

## 18. 우선 구현 순서

1. worker config / logging
2. control plane client
3. polling loop
4. local filesystem layout
5. mock executor
6. bridge script
7. psim_runner
8. artifact uploader
9. full integration

---

## 19. 구현 체크리스트

- [ ] worker config 생성
- [ ] worker register 구현
- [ ] heartbeat 구현
- [ ] claim-next-job 구현
- [ ] local job directory builder 구현
- [ ] mock executor 구현
- [ ] bridge script 구현
- [ ] psim_runner 구현
- [ ] artifact uploader 구현
- [ ] complete/fail reporter 구현
- [ ] cleanup 구현
- [ ] real Windows smoke test

---

## 20. 결론

Worker 구현의 핵심은 “PSIM을 돌리는 코드” 자체보다,

- 안정적으로 job을 가져오고
- 격리된 경로에서 실행하고
- 결과를 업로드하고
- 실패를 일관되게 보고하는

**실행 에이전트로서의 신뢰성**이다.

따라서 구현도 bridge 하나부터가 아니라,

**control plane client → loop → executor → bridge → artifact upload**

순으로 가는 것이 맞다.
