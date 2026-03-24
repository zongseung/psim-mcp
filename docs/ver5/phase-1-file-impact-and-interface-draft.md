# Phase 1 상세: 실제 수정 파일 목록과 인터페이스 초안
작성일: 2026-03-24

## 목적

`user-intent-driven-circuit-synthesis-plan.md`의 Phase 1은
기존 generator를 `graph assembler + sizing`으로 분해하는 단계다.

이 문서는 그 Phase 1을 실제 코드베이스에 적용하기 위해,
어떤 파일을 수정해야 하는지와 어떤 인터페이스를 도입해야 하는지를
현재 저장소 구조 기준으로 구체적으로 정리한다.

즉 이 문서는 단순 설계 아이디어가 아니라,
Phase 1 착수 시 바로 참조할 수 있는 실행형 개발 기획 문서다.

## Phase 1의 정확한 목표

Phase 1에서 끝내야 할 것은 다음이다.

- topology generator가 더 이상 회로도 좌표를 직접 만드는 주체가 아니게 만들기
- 기존 `generate()`가 하던 일을 `구조 합성`과 `값 계산`으로 분리하기
- service가 `layout 이전`과 `layout 이후` 데이터를 구분해서 다루게 만들기
- 이후 Phase 2, 3에서 `CircuitGraph`, `LayoutEngine`을 붙일 수 있는 인터페이스를 확보하기

Phase 1에서는 아직 완전한 새 아키텍처를 다 구현하지 않아도 된다.
대신 지금 generator 안에 섞여 있는 `structure + sizing + layout`를 분리 가능한 상태로 만드는 것이 핵심이다.

## 현재 구조에서 가장 먼저 문제 되는 파일

### 직접 수정 대상

- `src/psim_mcp/generators/base.py`
- `src/psim_mcp/generators/__init__.py`
- `src/psim_mcp/generators/buck.py`
- `src/psim_mcp/generators/boost.py`
- `src/psim_mcp/generators/flyback.py`
- `src/psim_mcp/generators/forward.py`
- `src/psim_mcp/generators/llc.py`
- `src/psim_mcp/generators/boost_pfc.py`
- `src/psim_mcp/generators/layout.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/shared/state_store.py`
- `src/psim_mcp/routing/router.py`
- 필요 시 `src/psim_mcp/config.py`

### 1차 신설 권장 대상

- `src/psim_mcp/synthesis/models.py`
- `src/psim_mcp/synthesis/graph_result.py`
- `src/psim_mcp/synthesis/sizing.py`
- `src/psim_mcp/synthesis/__init__.py`
- `src/psim_mcp/synthesis/topologies/buck.py`
- `src/psim_mcp/synthesis/topologies/flyback.py`
- `src/psim_mcp/synthesis/topologies/llc.py`

### Phase 1에서는 수정 보류 가능

- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/adapters/real_adapter.py`

이 파일들은 당장은 기존 `components + wire_segments`를 계속 받아도 된다.
Phase 1에서는 generator와 service 경계만 먼저 분리하는 것이 우선이다.

## Phase 1에서 고정해야 하는 엔트리포인트 범위

Phase 1은 generator만 바꾸는 작업이 아니다.
현재 코드 기준으로 아래 엔트리포인트가 같은 회로 생성 계약을 공유한다.

- `CircuitDesignService.design_circuit()`
- `CircuitDesignService.preview_circuit()`
- `CircuitDesignService.confirm_circuit()`
- `CircuitDesignService.create_circuit_direct()`
- `SimulationService.create_circuit()`

따라서 Phase 1 완료 조건에는 적어도 아래 둘 중 하나가 포함돼야 한다.

1. 새 `synthesis_result`를 위 경로가 공통으로 수용한다
2. 새 경로는 `CircuitDesignService`에만 붙이고, `SimulationService`는 명시적으로 legacy-only로 고정한다

문서상 권장 방향은 1번보다 2번에서 시작하되,
`SimulationService`가 어떤 payload만 받는지 계약을 분명히 적는 것이다.

## 왜 이 파일들이 핵심인가

### `generators/base.py`

현재 `TopologyGenerator.generate()`는
`components, nets, positions`를 한 번에 만든다는 가정을 깔고 있다.

문제:

- 구조 합성과 layout이 인터페이스 단계에서부터 결합돼 있다
- 모든 topology 구현이 이 결합을 그대로 따라간다

Phase 1에서는 이 추상 인터페이스부터 바뀌어야 한다.

### `generators/buck.py`, `llc.py`, `flyback.py` 등

문제:

- 부품 값 계산
- component 생성
- net 생성
- position/direction/ports 지정

이 네 가지가 한 함수 안에 섞여 있다.

예를 들어 `buck.py`는 전형적인 예다.

- duty, inductance, capacitance 계산
- MOSFET, diode, inductor 등 component 생성
- 동시에 `position`, `direction`, `ports`를 고정값으로 넣음

이 구조를 유지하면 layout 분리가 불가능하다.

### `generators/layout.py`

현재는 helper 이름이 layout이지만,
실제론 example-derived PSIM component factory에 가깝다.

문제:

- 구조 합성 계층에서 layout helper를 직접 호출하고 있다
- topology generator가 사실상 layout engine 역할까지 겸한다

Phase 1에서는 이 파일의 책임을 축소하거나,
최소한 generator가 직접 호출하지 않도록 방향을 바꿔야 한다.

### `circuit_design_service.py`

현재 service는 generator 결과를 곧바로 `components/nets`로 받아서 정규화한다.

문제:

- generator 출력이 이미 layout 포함 형태이므로
  service가 `graph 단계`를 개념적으로 다룰 수 없다

Phase 1에서는 service가 최소한 아래 두 경우를 구분할 수 있어야 한다.

- structure-first 결과
- legacy positioned components 결과

## Phase 1에서 새로 도입할 최소 모델

Phase 1은 완전한 `CircuitGraph` 구현 전 단계지만,
아래 정도는 도입해야 분리가 시작된다.

## 1. SizedComponentSpec

역할:

- 좌표 없는 component 정의
- sizing 완료 후의 파라미터 포함

예시:

```python
from dataclasses import dataclass, field

@dataclass
class SizedComponentSpec:
    id: str
    type: str
    role: str | None = None
    parameters: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
```

포인트:

- `position`, `direction`, `ports` 없음
- role을 갖게 해서 이후 layout에서 사용

## 2. NetSpec

```python
@dataclass
class NetSpec:
    name: str
    pins: list[str]
    role: str | None = None
```

포인트:

- 전기적 연결만 표현
- layout 정보 없음

## 3. TopologySynthesisResult

```python
@dataclass
class TopologySynthesisResult:
    topology: str
    components: list[SizedComponentSpec]
    nets: list[NetSpec]
    metadata: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)
    design: dict[str, object] = field(default_factory=dict)
```

포인트:

- generator의 새 기본 출력
- layout 이전 단계의 canonical intermediate

## 4. LegacyRenderableCircuit

Phase 1에서는 하위 호환이 필요하므로,
기존 renderer/bridge가 그대로 받을 수 있는 형태도 유지해야 한다.

```python
@dataclass
class LegacyRenderableCircuit:
    topology: str
    components: list[dict]
    nets: list[dict]
    metadata: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)
```

이 모델은 transition용이다.
장기적으로는 layout engine 산출물로 대체되어야 한다.

## 5. PreviewPayloadV1

Phase 1에서 가장 먼저 버전 고정이 필요한 객체는 preview/store payload다.

```python
@dataclass
class PreviewPayloadV1:
    payload_kind: str = "preview_payload"
    payload_version: str = "v1"
    circuit_type: str
    components: list[dict]
    connections: list[dict]
    nets: list[dict]
    wire_segments: list[dict]
    synthesis_result: dict[str, object] | None = None
    psim_template: dict[str, object] | None = None
```

포인트:

- confirm/create가 이 payload를 그대로 다시 읽는다
- 이후 Phase 2~4에서 `graph`, `layout`, `routing` 필드를 늘릴 수 있어야 한다
- `payload_version` 없이 필드를 늘리면 confirm 경로 회귀가 생기기 쉽다

## 6. DesignSessionV1

Phase 5 이전에도 설계 세션 payload는 하위 호환 대상이다.

```python
@dataclass
class DesignSessionV1:
    payload_kind: str = "design_session"
    payload_version: str = "v1"
    topology: str
    specs: dict[str, object]
    missing_fields: list[str]
```

## 인터페이스 초안

## A. `TopologyGenerator` 인터페이스 변경 초안

현재:

```python
class TopologyGenerator(ABC):
    @abstractmethod
    def generate(self, requirements: dict) -> dict:
        ...
```

Phase 1 초안:

```python
class TopologyGenerator(ABC):
    @abstractmethod
    def synthesize(self, requirements: dict) -> TopologySynthesisResult:
        """Build topology structure and sized component parameters only."""

    def generate(self, requirements: dict) -> dict:
        """Legacy adapter. Temporary compatibility path."""
```

의도:

- 새 경로는 `synthesize()`
- 기존 `generate()`는 legacy compatibility wrapper로 남김

## B. `sizing` 분리 함수 초안

신설 파일:

- `src/psim_mcp/synthesis/sizing.py`

예시:

```python
def size_buck(requirements: dict) -> dict[str, float]:
    ...

def size_flyback(requirements: dict) -> dict[str, float]:
    ...

def size_llc(requirements: dict) -> dict[str, float]:
    ...
```

반환 예:

```python
{
    "duty": 0.25,
    "inductance": 0.00012,
    "capacitance": 0.000047,
    "r_load": 4.8,
}
```

의도:

- 계산 로직 테스트 분리
- topology structure와 sizing 독립성 확보

## C. topology assembler 함수 초안

신설 파일 예:

- `src/psim_mcp/synthesis/topologies/buck.py`

```python
def synthesize_buck(requirements: dict) -> TopologySynthesisResult:
    sized = size_buck(requirements)
    components = [...]
    nets = [...]
    return TopologySynthesisResult(
        topology="buck",
        components=components,
        nets=nets,
        design=sized,
        simulation=...,
        metadata=...,
    )
```

중요:

- 여기서 `position`, `direction`, `ports`를 만들면 안 된다
- role과 net 구조만 만든다

## D. legacy layout adapter 초안

Phase 1에서는 renderer/bridge를 바로 바꾸지 않으므로,
구조-only 결과를 기존 positioned component 형식으로 내리는 임시 adapter가 필요하다.

권장 신설:

- `src/psim_mcp/synthesis/legacy_layout_adapter.py`

```python
def materialize_legacy_layout(
    result: TopologySynthesisResult,
) -> LegacyRenderableCircuit:
    """Temporary adapter for existing SVG/bridge pipeline."""
```

역할:

- topology별 간단한 기본 좌표를 부여
- 기존 `components` dict 포맷으로 변환
- 이후 Phase 3에서 제거 대상

주의:

- 이 adapter는 "새 표준"이 아니라 migration shim이어야 한다
- `layout.py` helper를 내부에서 호출하더라도, generator 본체는 그 파일을 직접 보지 않게 해야 한다

## E. `get_generator()` 확장 초안

현재:

- generator registry는 legacy `generate()` 기반

Phase 1 초안:

```python
def get_generator(name: str) -> TopologyGenerator:
    ...

def synthesize_topology(name: str, requirements: dict) -> TopologySynthesisResult:
    return get_generator(name).synthesize(requirements)
```

의도:

- service가 명시적으로 synthesis 경로를 호출하게 만듦

## F. `CircuitDesignService` 변경 초안

현재 `_try_generate()`는 사실상 legacy generator 결과를 받는다.

Phase 1 초안:

```python
def _try_generate(...):
    synthesis = generator.synthesize(req)
    legacy = materialize_legacy_layout(synthesis)
    return (
        legacy.components,
        [],
        legacy.nets,
        "generator",
        None,
        constraint_validation,
        None,
        synthesis,
    )
```

또는 더 명확하게:

```python
{
    "legacy_renderable": ...,
    "synthesis_result": ...,
}
```

권장 방향:

- preview store에 `synthesis_result` 원본도 저장
- 현재 SVG/bridge는 `legacy_renderable` 소비
- 다음 Phase에서 layout engine 붙일 때 `synthesis_result`를 재사용
- `_try_generate()`의 반환 타입은 tuple보다 named payload로 정리하는 쪽이 안전

## G. `SimulationService` 영향 범위

현재 `SimulationService.create_circuit()`도 `circuit_spec` 내부의
`components`, `nets`, `wire_segments`를 직접 소비한다.

따라서 Phase 1에서 선택지는 두 가지다.

1. `SimulationService`도 `preview_payload_v1` 또는 이에 준하는 공통 payload를 읽게 만든다
2. `SimulationService`는 legacy `circuit_spec`만 유지하고, 새 경로는 `CircuitDesignService`로 한정한다

Phase 1에서는 2번이 더 안전하다.
대신 아래를 명시해야 한다.

- `SimulationService`는 `TopologySynthesisResult`를 직접 받지 않는다
- 필요 시 `legacy_renderable`에서 다시 `circuit_spec`을 구성한다
- Phase 2 이후 graph payload를 받기 전까지는 compatibility shim으로 남긴다

## 파일별 구체 작업안

## 1. `src/psim_mcp/generators/base.py`

작업:

- `TopologySynthesisResult` import
- `synthesize()` abstract method 추가
- `generate()`를 optional legacy adapter method로 변경

예상 수정 범위:

- 중간

리스크:

- 모든 generator 구현 클래스가 영향을 받음

## 2. `src/psim_mcp/generators/buck.py`

작업:

- sizing 계산을 함수로 분리
- 구조-only component/net 생성으로 분리
- legacy positioned output은 adapter 또는 compatibility wrapper에서 생성

초기 목표:

- buck를 first migration target으로 사용

이유:

- 회로 구조가 단순함
- 현재 preview 문제 사례가 이미 많아 기준점으로 좋음

## 3. `src/psim_mcp/generators/llc.py`

작업:

- reference-derived layout 주석과 구조-only 생성 부분 분리
- `Lm`, `TF_IDEAL`, `BDIODE1` 관계를 role 기반 graph로 표현

주의:

- LLC는 복잡하므로 Phase 1에서는 완전 migration보다 skeleton 분리 우선

## 4. `src/psim_mcp/generators/layout.py`

작업:

- 직접 generator import 경로에서 빠지게 조정
- transition 기간 동안 only `legacy_layout_adapter` 내부에서 호출되도록 제한

목표:

- generator 계층이 layout helper에 직접 의존하지 않게 만들기

## 5. `src/psim_mcp/generators/__init__.py`

작업:

- `synthesize_topology()` 추가
- 필요하면 legacy registry와 synthesis registry를 같은 객체로 운영

## 6. `src/psim_mcp/services/circuit_design_service.py`

작업:

- `_try_generate()`가 synthesis result와 legacy renderable을 함께 다루도록 변경
- preview store에 `synthesis_result` 저장
- 이후 phase에서 layout/routing 교체 가능하게 준비
- `preview_payload_v1` 버전 필드 저장
- confirm/create가 payload version을 보고 복구 가능하도록 준비

주의:

- 현재 public response shape는 크게 깨지지 않게 유지

## 7. `src/psim_mcp/routing/router.py`

Phase 1에서의 역할:

- 큰 구조 변경은 아님
- 다만 `structure-only` 단계와 `layouted-components` 단계를 구분하는 주석/함수 경계 정리 필요

작업:

- `resolve_wire_segments()`는 positioned component input이 필요함을 명시
- synthesis result에서 직접 호출되지 않도록 경로 정리

## 8. `src/psim_mcp/services/simulation_service.py`

작업:

- Phase 1 기간에는 legacy `circuit_spec` consumer임을 문서/주석/테스트로 고정
- `CircuitDesignService`와 다른 payload 계약을 쓰는 경우 명시적으로 구분
- Phase 2 이후 graph payload 전환 전까지는 compatibility boundary로 취급

리스크:

- 이 경계를 문서화하지 않으면 create path 회귀를 뒤늦게 발견할 가능성이 크다

## 9. `src/psim_mcp/synthesis/models.py`

신설:

- `SizedComponentSpec`
- `NetSpec`
- `TopologySynthesisResult`
- transition용 type helpers

이 파일은 Phase 1의 중심 모델이다.

## 10. `src/psim_mcp/synthesis/sizing.py`

신설:

- topology별 sizing 함수
- 공통 계산 helper

초기 범위:

- buck
- flyback
- llc

## 11. `src/psim_mcp/synthesis/topologies/*.py`

신설:

- topology별 structure assembler

Phase 1 우선순위:

1. `buck.py`
2. `flyback.py`
3. `llc.py`

나머지는 이후 순차 전환

## Phase 1 권장 구현 순서

1. `synthesis/models.py` 신설
2. `generators/base.py`에 `synthesize()` 도입
3. `synthesis/sizing.py`에 buck sizing 분리
4. `synthesis/topologies/buck.py` 작성
5. `legacy_layout_adapter.py` 작성
6. `shared/state_store.py`와 preview payload version 고정
7. `circuit_design_service.py`가 synthesis + legacy dual path 저장
8. `simulation_service.py` compatibility boundary 고정
9. buck 회귀 테스트 추가
10. 같은 패턴으로 flyback, llc 확장

## Phase 1 완료 기준

아래가 만족되면 Phase 1 완료로 본다.

- `buck`은 generator 본체에서 좌표 하드코딩 없이 합성 가능
- service가 `synthesis_result`와 `legacy_renderable`을 모두 다룸
- 기존 preview/create 경로가 계속 동작함
- 향후 layout engine이 붙을 자리가 인터페이스상 분리됨
- preview/store payload에 `payload_version`이 존재
- `SimulationService.create_circuit()`의 입력 계약이 문서와 테스트에서 고정됨

## 권장 테스트 추가

### 단위 테스트

- `tests/unit/test_synthesis_models.py`
- `tests/unit/test_sizing_buck.py`
- `tests/unit/test_synthesize_buck.py`
- `tests/unit/test_legacy_layout_adapter.py`
- `tests/unit/test_preview_payload_schema.py`

### 서비스 회귀

- `tests/unit/test_circuit_design_service.py`
  - preview store에 `synthesis_result` 저장 확인
  - 기존 SVG preview 생성 유지 확인
- `tests/unit/test_simulation_service.py`
  - legacy `circuit_spec` 경로 유지 확인
  - Phase 1 payload 변경이 create path를 깨지 않음 확인

## 최종 제안

Phase 1은 모든 topology를 한 번에 옮기는 작업으로 잡으면 실패할 가능성이 크다.
가장 현실적인 전략은 이렇다.

1. `buck`을 기준 topology로 먼저 분해
2. `flyback`, `llc`를 복잡도 순으로 추적 전환
3. 나머지 topology는 legacy generator를 유지한 채 점진 이관

즉 Phase 1의 성공 조건은 "전부 새 구조로 갈아엎기"가 아니라,
`새 합성 인터페이스가 실제 코드에 뿌리내리기 시작하는 것`이다.
