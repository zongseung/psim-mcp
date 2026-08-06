# 임의 회로 생성 제거와 기존 회로 중심 로드맵 설계

## 상태와 의존 관계

이 문서는 임의 회로 생성 기능을 제품 경계에서 제거하고, 이미 검증된 PSIM 회로를 안전하게 읽고 수정하고 시뮬레이션하는 방향으로 범위를 좁히는 설계다.

선행 설계인 [기존 회로 안전 편집 및 멀티 클라이언트 설계](./2026-08-04-existing-circuit-editing-multiclient-design.md)가 쓰기 안전성, 공개 도구 계약, 실제 PSIM 수락 조건을 정의한다. 그 설계의 실행 순서는 [기존 회로 안전 편집 구현 계획](../plans/2026-08-04-existing-circuit-editing.md)을 따른다. 이 문서는 두 문서를 재정의하지 않는다. 생성 기능 제거는 지금 독립적으로 수행하고, 후속 편집 기능은 선행 계획의 별도 구현 단계로 남긴다.

## 목표와 현재 근거

목표는 임의 토폴로지를 추론해 새 회로를 만드는 넓고 얕은 인터페이스 대신, 사용자가 제공한 회로에 대해 다음 보장을 제공하는 작고 깊은 모듈을 만드는 것이다.

- 원본은 읽기 전용이며 모든 쓰기는 출처가 기록된 작업 사본에만 일어난다.
- 소자값과 C-block 원문 변경은 저장 후 재가져온 값으로 검증한다.
- 시뮬레이션은 명시적으로만 실행하며 기준 회로와 변경 회로의 근거를 구분해 반환한다.
- 가져오기, 연결망 재구성, 내보내기 후 비교라는 검증 seam은 생성 코드 제거와 무관하게 유지한다.

현재 방향을 뒷받침하는 저장소 근거는 다음과 같다.

- README는 임의 생성 파이프라인을 동결 상태로 설명하고, 새 투자를 기존 회로의 읽기·수정·시뮬레이션에 둔다.
- 생성 파이프라인은 배치와 배선 추측에 의존하며 canonical end-to-end 성공 범위가 제한적이다.
- VER2 가져오기는 PSIM의 `PsimConvertToPython` 결과를 `CircuitGraph`로 재구성한다. DQ Transform과 Interleaving Boost 기준 회로에서 컴포넌트·net 재구성과 roundtrip 비교가 검증되어 있다.
- 선행 설계와 계획은 `prepare_edit`, 전체 C-block 읽기, 값/C-block 저장, 재가져오기 검증, 명시적 시뮬레이션의 구체 계약과 수락 시나리오를 이미 고정했다.

## 접근법 비교

### A. 작은 조합형 도구 유지 — 추천

`import_circuit -> prepare_edit -> set_parameter -> import_circuit -> run_simulation/analyze_existing`를 독립 단계로 유지한다. 각 단계의 입력과 산출물이 관찰 가능하고, 원본 보존·저장 검증·시뮬레이션 실행 여부를 호출자가 통제한다. 여러 번 호출해야 하지만 실패 지점이 분명하고 기존 인터페이스를 재사용하므로 구현과 회귀 위험이 가장 작다.

### B. 일괄 `evaluate_change` 파사드 추가

복사, 변경, 재가져오기, 실행, 비교를 한 호출로 묶으면 단순한 클라이언트 경험을 제공한다. 반면 부분 실패와 재시도 의미가 복잡하고, 기존 조합형 도구의 오케스트레이션을 서버에 중복하며, 긴 PSIM 작업의 상태와 취소 경계가 흐려진다.

### C. 범용 PSIM 워크벤치 확장

구조 편집, batch/AC/다중 엔진, 부품 라이브러리, SimCoder까지 한 제품 표면으로 확장하면 기능 폭은 넓어진다. 그러나 검증되지 않은 PSIM API와 도메인 추론이 다시 핵심 경로에 들어오며, 현재의 신뢰성 근거와 투자 방향을 약화한다.

따라서 A를 채택한다. B와 C를 위한 새 파사드, DSL, 런타임 의존성은 추가하지 않는다.

## 공개 계약 축소

다음 7개 생성 도구를 기본 MCP 등록과 공개 도구 목록에서 제거한다.

1. `design_circuit`
2. `continue_design`
3. `preview_circuit`
4. `confirm_circuit`
5. `create_circuit`
6. `get_component_library`
7. `list_circuit_templates`

현재 19개 공개 도구에서 위 7개를 제거하면 계약은 12개가 된다. 후속 계획이 `prepare_edit`를 추가하면 13개가 된다. 도구 수보다 이름 집합을 기준 계약으로 삼아, 위 7개가 없고 기존 회로 작업에 필요한 도구가 남아 있음을 테스트한다. 제거된 이름에 호환 stub이나 숨은 feature flag는 두지 않는다. 복구가 필요하면 아래의 커밋 단위 롤백을 사용한다.

## 내부 코드 정리 경계

공개 계약을 먼저 제거한 뒤 호출 그래프와 테스트에서 도달할 수 없는 생성 전용 구현만 삭제한다. 정리 후보는 다음과 같다.

- `src/psim_mcp/tools/design.py`와 `src/psim_mcp/tools/circuit.py`의 생성 도구 구현
- `src/psim_mcp/services/circuit_design_service.py`, `_circuit_generators.py`, `_circuit_pipeline.py`, `_circuit_render.py`, `preview_store.py`
- `src/psim_mcp/generators/`, `intent/`, `layout/`, `routing/`
- `src/psim_mcp/synthesis/`의 생성 전용 topology, sizing, builder, registry 코드
- 생성 preview에만 쓰이는 helper·renderer·데이터와 그 전용 테스트·fixture·문서
- 보존 경로의 호출자가 없음을 확인한 뒤의 어댑터/브리지 생성 메서드와 `handle_create_circuit`

각 후보는 이름이 아니라 실제 소비자를 기준으로 판정한다. `rg` 호출자 검색과 집중 테스트로 가져오기·분석·결과 표시 경로가 사용하지 않음을 증명한 항목만 삭제한다.

### 반드시 보존할 seam

다음 코드는 겉으로 생성 또는 script 출력처럼 보여도 기존 회로의 충실도 검증에 필요하므로 삭제하지 않는다.

- `src/psim_mcp/synthesis/graph.py`의 `CircuitGraph`: 가져오기 결과를 표현하는 중립 도메인 모델
- `src/psim_mcp/importer/parser.py`: PSIM 변환 script 파싱
- `src/psim_mcp/importer/net_builder.py`: pin과 net 재구성
- `src/psim_mcp/importer/roundtrip.py`의 `emit_script`와 `compare_nets`: 가져온 ground truth의 결정적 재출력과 동등성 검증
- `convert_to_python` 브리지, importer가 소비하는 component/pin mapping과 validator

`emit_script`는 임의 토폴로지 합성이 아니라 가져온 구조의 roundtrip oracle이다. 따라서 생성 코드 삭제의 이름 기반 대상이 아니다.

## 후속 기능 범위

후속 기능은 아래 세 개로 제한한다. 모두 접근법 A의 기존 도구를 깊게 만들며 새 일괄 도구를 추가하지 않는다.

### 1. `prepare_edit` provenance

`prepare_edit` 결과의 `source_path`, `working_path`, `source_sha256`, `status`를 한 편집 세션의 provenance로 유지한다. 값 쓰기 전에 현재 PSIM 문서가 해당 `working_path`인지 확인하고, 원본 경로나 provenance가 없는 임의의 열린 문서에는 쓰지 않는다. 사본 생성 시 덮어쓰기를 거부하며 원본 해시는 작업 전후와 수락 테스트에서 비교한다.

### 2. 검증된 값/C-block 교체

기존 `set_parameter` 하나로 일반 소자값과 `CBLOCK`/`SIMPLECBLOCK`의 `CONTENT`만 교체한다. 길이·NUL·실제 소자 타입 검증과 PSIM 저장 뒤, 같은 `working_path`를 `import_circuit`로 재가져와 요청값과 저장값의 정확한 일치를 확인한다. 컴포넌트 추가·삭제, 배선 변경, 구조적 patch 언어는 포함하지 않는다.

### 3. 명시적 시뮬레이션/비교 근거

읽기나 변경은 시뮬레이션을 자동 실행하지 않는다. 사용자가 `run_simulation`을 명시적으로 호출했을 때만 실행하며 응답에 실행 대상 경로, 출력 artifact 경로, 실행 옵션과 상태를 포함한다. 기준/변경 비교는 각 실행의 provenance와 metric 정의를 함께 보존하고, 한쪽 실행 또는 metric이 없으면 비교 성공으로 표현하지 않는다.

## 아키텍처와 컴포넌트

핵심 호출 경로는 다음 한 방향을 유지한다.

`MCP 도구 -> 도메인 서비스 -> Adapter -> PSIM bridge`

| 모듈 | 인터페이스와 책임 |
|---|---|
| Project 도구/`ProjectService` | `import_circuit`, `prepare_edit`; 원본 읽기, provenance 생성, 작업 사본 열기 |
| Parameter 도구/`ParameterService` | `set_parameter`; 쓰기 경계와 값/C-block 입력 검증, 저장 요청 |
| Simulation 도구/`SimulationService` | `run_simulation`; 명시적 실행과 artifact 반환 |
| Results/Analysis 모듈 | 기존 출력 읽기, 명시한 metric 계산과 비교 근거 구성 |
| PSIM `Adapter` | 도메인 인터페이스를 mock/real 실행으로 변환하고 bridge 응답을 정규화 |
| PSIM bridge | 문서 열기, 값 설정·저장, 실행, 결과 export, Python 변환 |
| Importer + `CircuitGraph` | 변환 script를 구조화하고 net을 재구성하며 roundtrip 동등성 검증 |

도메인 서비스는 PSIM API 세부사항을 숨기는 깊은 module이어야 한다. 도구 계층은 입력/출력 계약만 노출하고, 저장·재구성·실행의 구현을 복제하지 않는다. `Adapter` seam은 real PSIM과 mock 테스트를 교체하는 유일한 실행 경계로 유지한다.

## 데이터 흐름

1. `import_circuit(source)`가 원본을 PSIM Python script로 변환하고 importer가 `CircuitGraph`와 요청된 C-block 원문을 반환한다. 이 단계는 쓰지 않는다.
2. `prepare_edit(source, destination?)`가 허용 경로와 미존재 목적지를 검증하고, 원본 해시를 계산하고, metadata를 보존해 복사한 뒤 사본만 연다. 결과가 편집 provenance가 된다.
3. `set_parameter(id, name, value)`가 열린 경로와 provenance를 대조하고 입력과 실제 PSIM 소자 타입을 검증한 뒤 사본에 저장한다.
4. `import_circuit(working_path)`가 저장된 값/C-block을 다시 읽는다. 요청값과 일치할 때만 변경을 검증된 것으로 보고한다.
5. 사용자가 요청하면 `run_simulation`이 현재 작업 사본을 실행하고 artifact와 실행 근거를 반환한다. 비교는 별도로 실행된 기준과 변경 결과에 동일 metric 정의를 적용한다.

## 오류 처리

- 경로 오류, 허용 디렉터리 위반, 기존 목적지, 사본 생성/열기 실패는 파일 쓰기 전에 구조화된 오류로 반환한다. 사본을 열지 못하면 새로 만든 불완전 사본만 정리한다.
- provenance 부재 또는 열린 문서와 `working_path` 불일치는 쓰기를 거부한다. 오류에는 기대 경로와 실제 상태를 민감 정보 정제 규칙 안에서 포함한다.
- 지원하지 않는 파라미터, C-block 이외의 `CONTENT`, 길이 초과, NUL은 PSIM 호출 전에 거부한다.
- PSIM이 성공처럼 응답해도 재가져온 값이 다르면 검증 실패다. 원본은 그대로 두고 작업 사본 경로와 기대값/관측값의 안전한 요약을 반환한다.
- 시뮬레이션 실패, 출력 artifact 부재, metric 계산 실패는 서로 다른 단계 오류로 유지한다. 불완전한 두 실행을 성공 비교로 합치지 않는다.
- 내부 예외와 PSIM 메시지는 기존 응답 envelope로 정규화하고 로컬 경로·원문 코드·stack trace의 불필요한 노출을 막는다.

## 테스트 전략

### 계약 및 단위 테스트

- 등록된 공개 도구 이름 집합에서 7개 생성 도구가 사라지고 기존 회로 도구가 유지되는지 검증한다.
- `prepare_edit`의 해시, metadata 보존 복사, 덮어쓰기 거부, 열기 실패 정리, provenance 불일치 쓰기 거부를 검증한다.
- 일반 값과 C-block의 입력 제한, 실제 타입 확인, 저장 후 재가져오기 일치/불일치를 검증한다.
- `CircuitGraph`, parser, net builder, roundtrip 테스트를 생성 코드 삭제 전후 동일하게 실행한다.
- 시뮬레이션이 암묵적으로 호출되지 않고, 명시적 실행만 artifact와 provenance를 반환하는지 검증한다.

### 통합 및 실제 PSIM 수락 테스트

- 세 MCP 클라이언트가 동일한 축소 도구 집합을 발견하고 기존 회로 흐름을 호출하는 smoke test를 수행한다.
- DQ Transform에서 전체 C-block 원문 2,910자를 읽고 사본에 변경·저장·재가져오기하며 원본 SHA-256이 유지되는지 검증한다.
- Interleaving Boost에서 L1/L2/L3의 `125u`를 작업 사본에서 `250u`로 바꾸고 재가져온 값과 명시적 시뮬레이션의 리플 metric을 비교하며 원본 SHA-256이 유지되는지 검증한다.
- 두 기준 회로의 component/net 수와 roundtrip precision/recall 1.0 기준을 유지한다.
- 삭제 후 전체 unit/integration suite와 MCP 초기화 probe를 실행하고, 기존에 문서화된 기준선 실패 외 새 실패가 없음을 확인한다.

## 두 커밋 리팩터링 경계

### 커밋 1: 공개 생성 계약 제거

7개 도구의 등록과 공개 도구 함수를 제거하고, 도구 이름 계약 테스트와 사용자 문서를 축소된 제품 표면에 맞춘다. 내부 생성 구현은 이 커밋에서 삭제하지 않는다. 따라서 실패 시 이 커밋 하나를 되돌려 공개 계약을 복원할 수 있다.

### 커밋 2: 도달 불가능한 생성 구현 정리

커밋 1 이후 `rg`와 테스트로 소비자가 없다고 확인된 생성 전용 서비스·pipeline·layout·routing·synthesis 구현과 전용 테스트/데이터만 삭제한다. 보존 seam과 기존 회로 테스트는 수정 없이 통과해야 한다. 이 커밋은 외부 동작을 바꾸지 않으며, 실패 시 커밋 2만 되돌려 내부 구현을 복원할 수 있다.

두 커밋에는 선행 기존 회로 편집 구현을 섞지 않는다. 현재 importer/roundtrip과 MCP 도구 계약을 기준선으로 삼아 삭제 전후 회귀 여부를 판별한다.

## 현재 리팩터링 성공 기준

- 기본 MCP 공개 목록에서 정확히 7개 생성 도구가 제거되고 기존 회로 읽기·편집·실행·분석 도구는 유지된다.
- 공개 도구 계약은 현재 19개에서 12개가 되며 이름 집합 테스트로 고정된다.
- `CircuitGraph`/importer/roundtrip 기준과 전체 회귀 suite에 새 실패가 없다.
- 생성 전용 내부 코드는 남은 소비자가 없다는 증거가 있는 항목만 제거된다.

## 후속 로드맵 성공 기준

- 원본 문서는 어떤 쓰기 경로에서도 열리지 않으며, 작업 전후 SHA-256이 같다.
- 모든 변경에는 `prepare_edit` provenance가 있고, provenance가 없는 문서 쓰기는 거부된다.
- 값과 C-block 변경은 작업 사본 재가져오기 결과가 요청값과 정확히 일치해야 성공한다.
- 읽기와 변경은 시뮬레이션을 실행하지 않으며, 명시적 실행 결과에는 대상·옵션·artifact·metric 근거가 있다.
- DQ Transform 및 Interleaving Boost 실제 수락 시나리오가 통과한다.

## 비목표

- 임의 회로 생성의 복구 또는 새 topology/template 추가
- 컴포넌트 추가·삭제, 배선·layout·routing 변경, 구조 편집 DSL
- 서버 측 자연어 해석이나 LLM 호출
- 변경 뒤 자동 시뮬레이션 또는 C 코드 자동 수정
- batch/병렬 sweep, DOE, Monte Carlo, fault injection
- AC sweep, 다중 시뮬레이션 엔진, SimCoder
- subcircuit·부품 라이브러리 관리
- sidecar 자동 발견과 복사
- 새 GUI, 클라우드 동기화, 계정·권한 시스템

## 롤아웃과 롤백

1. 현재 unit/integration, importer/roundtrip, MCP 도구 계약 기준선을 기록한다.
2. 커밋 1을 적용해 공개 도구 계약을 축소하고 MCP 초기화와 기존 회로 smoke test를 실행한다.
3. 커밋 2를 적용해 도달 불가능한 생성 구현을 정리하고 importer/roundtrip 집중 테스트와 전체 회귀 suite를 다시 실행한다.
4. 선행 설계의 편집 기능은 별도 구현 계획으로 진행하고 두 실제 PSIM 수락 시나리오로 검증한다.
5. 릴리스 노트에 제거된 7개 이름, 대체하지 않는다는 결정, 기존 회로 권장 흐름과 선행 설계 링크를 명시한다.

문제가 공개 계약에서 발생하면 커밋 1을 되돌린다. 문제가 내부 정리에서만 발생하면 커밋 2만 되돌려 공개 표면은 좁게 유지한다. 작업 사본의 저장 또는 비교가 의심스러우면 원본을 수정하지 말고 해당 사본을 폐기한 뒤 같은 원본에서 새 `prepare_edit` 흐름을 시작한다. 별도 feature flag나 이중 구현은 운영 복잡도를 늘리므로 두지 않는다.
