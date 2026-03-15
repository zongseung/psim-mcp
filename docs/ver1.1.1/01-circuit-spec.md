# Step 1: CircuitSpec 정의

> 우선순위: P0
> 예상 범위: `src/psim_mcp/models/circuit_spec.py`
> 의존: 없음 (첫 번째 단계)

---

## 1. 목적

회로를 표현하는 **내부 표준 스키마**를 정의한다.

현재 문제:
- 회로 정보가 tool 파라미터 → adapter → bridge로 dict 형태로 흘러가며, 구조가 강제되지 않음
- 같은 회로를 다른 형태의 dict로 표현할 수 있어 일관성이 없음
- 검증이 service 레이어에서 ad-hoc으로만 이루어짐

목표:
- 모든 회로 생성 경로가 `CircuitSpec`을 거치도록 한다
- Pydantic 모델로 정의하여 자동 검증이 가능하게 한다
- 향후 validator, generator, bridge가 모두 이 스키마를 기준으로 동작한다

---

## 2. 스키마 설계

### 2.1 최상위 구조

```python
class CircuitSpec(BaseModel):
    topology: str                    # "buck", "boost", "flyback", ...
    metadata: CircuitMetadata
    requirements: CircuitRequirements
    components: list[ComponentSpec]
    nets: list[NetSpec]
    simulation: SimulationSettings
```

### 2.2 하위 모델

```python
class CircuitMetadata(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    category: str = ""               # "dc_dc", "dc_ac", ...

class CircuitRequirements(BaseModel):
    vin: float | None = None
    vout_target: float | None = None
    iout_target: float | None = None
    switching_frequency: float | None = None
    power_rating: float | None = None

class ComponentSpec(BaseModel):
    id: str                          # "V1", "SW1", ...
    kind: str                        # 내부 표준명 ("dc_source", "mosfet", ...)
    params: dict[str, float | int | str] = {}
    position: Position | None = None  # auto-layout이 채움

class Position(BaseModel):
    x: int = 0
    y: int = 0

class NetSpec(BaseModel):
    name: str                        # "VIN", "SW_NODE", "GND", ...
    pins: list[str]                  # ["V1.positive", "SW1.drain"]

class SimulationSettings(BaseModel):
    time_step: float = 1e-5
    total_time: float = 0.1
    print_step: float | None = None
```

---

## 3. connections → nets 전환 이유

현재 구조:
```json
{"from": "V1.positive", "to": "SW1.drain"}
```

문제점:
- point-to-point 표현이라 3개 이상의 핀이 만나는 노드를 표현하려면 여러 connection이 필요
- 실제 회로는 "노드" 중심이지 "선" 중심이 아님
- 배선 검증 시 노드 단위로 확인하는 것이 자연스러움

net 기반 표현:
```json
{"name": "SW_NODE", "pins": ["SW1.source", "D1.cathode", "L1.input"]}
```

장점:
- 노드에 연결된 모든 핀을 한눈에 파악 가능
- floating net(미연결) 검출이 쉬움
- GND net 존재 여부 검증이 단순함

---

## 4. kind 표준화

현재 component type이 문자열로 자유 입력됨 ("DC_Source", "MOSFET" 등).

`kind` 필드는 `component_library.py`의 키와 1:1 매핑되어야 한다:
- `dc_source` → PSIM DC Voltage Source
- `mosfet` → PSIM MOSFET
- `inductor` → PSIM Inductor
- ...

이렇게 하면:
- 지원하지 않는 부품 종류를 즉시 거부 가능
- 기본 파라미터를 catalog에서 자동 채움 가능
- PSIM API 호출 시 실제 element type으로 변환 가능

---

## 5. 구현 범위

### 파일 생성
- `src/psim_mcp/models/circuit_spec.py`

### 수정 대상
- `tools/circuit.py`: 템플릿 → CircuitSpec 변환 함수 추가
- `services/simulation_service.py`: `create_circuit`이 CircuitSpec을 받도록 변경
- `adapters/base.py`: `create_circuit` 시그니처에 CircuitSpec 반영

### 하위 호환
- 기존 dict 기반 입력도 `CircuitSpec.from_legacy(dict)` 로 변환 가능하게 한다
- 기존 테스트가 깨지지 않도록 점진적 전환

---

## 6. 테스트 계획

- CircuitSpec 생성 및 직렬화 테스트
- 필수 필드 누락 시 ValidationError 발생 확인
- 기존 템플릿 29개를 CircuitSpec으로 변환하는 테스트
- net과 component 간 정합성 기본 테스트 (모든 pin이 유효한 component를 참조하는지)

---

## 7. 완료 기준

- [ ] `CircuitSpec` Pydantic 모델 정의 완료
- [ ] 기존 29개 템플릿이 CircuitSpec으로 변환 가능
- [ ] `from_legacy()` 변환 함수 동작
- [ ] 기본 validation (필수 필드, kind 존재 여부) 통과
- [ ] 기존 221개 테스트 깨지지 않음
