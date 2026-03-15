# Step 2: Component Catalog 정비

> 우선순위: P0
> 예상 범위: `src/psim_mcp/data/component_library.py` 리팩터링
> 의존: Step 1 (CircuitSpec의 `kind` 필드가 catalog를 참조)

---

## 1. 목적

PSIM 부품 카탈로그를 **정규화된 레지스트리**로 정비한다.

현재 문제:
- `component_library.py`에 부품 정보가 있지만, 실제 PSIM element type과 매핑이 없음
- 핀 이름이 코드 곳곳에 하드코딩되어 있음 (svg_renderer, ascii_renderer, 템플릿)
- 어떤 부품이 어떤 파라미터를 필수로 가지는지 명시되지 않음

목표:
- 모든 부품의 핀, 파라미터, PSIM 매핑을 한 곳에서 관리
- CircuitSpec의 `kind` 검증에 사용
- topology generator가 부품 조합 시 참조

---

## 2. 카탈로그 엔트리 구조

```python
class ComponentDef(BaseModel):
    kind: str                        # 내부 표준명 ("mosfet", "dc_source")
    psim_element_type: str           # PSIM API에 전달할 실제 타입명
    category: str                    # "switch", "passive", "source", ...
    korean_name: str
    pins: list[PinDef]               # 핀 정의
    required_params: list[ParamDef]  # 필수 파라미터
    optional_params: list[ParamDef]  # 선택 파라미터
    default_values: dict[str, float | int | str]
    symbol: str                      # ASCII 렌더링용 약어

class PinDef(BaseModel):
    name: str                        # "positive", "negative", "drain", ...
    direction: str                   # "input", "output", "bidirectional"

class ParamDef(BaseModel):
    name: str
    unit: str
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""
```

---

## 3. 핀 표준화

현재 핀 이름이 일관되지 않음. 표준화 필요:

| 부품 | 핀 목록 |
|------|---------|
| DC_Source | positive, negative |
| AC_Source | positive, negative |
| MOSFET | drain, source, gate |
| IGBT | collector, emitter, gate |
| Diode | anode, cathode |
| Resistor | pin1, pin2 |
| Inductor | pin1, pin2 |
| Capacitor | positive, negative |
| Transformer | primary_in, primary_out, secondary_in, secondary_out |
| Battery | positive, negative |
| Motor (3상) | phase_a, phase_b, phase_c |

svg_renderer와 ascii_renderer의 핀 매핑도 이 정의를 참조하도록 통일한다.

---

## 4. PSIM Element Type 매핑

카탈로그의 핵심 가치는 **내부 kind → PSIM 실제 타입** 매핑이다.

이 매핑은 Windows 환경에서 `psimapipy`의 `PsimCreateNewElement()` 호출 시 사용된다.

현재는 bridge_script에서 `comp_type`을 그대로 전달하는데, PSIM이 기대하는 정확한 타입명과 다를 수 있다. 카탈로그에서 변환을 보장한다.

확인 방법:
- Windows에서 PSIM GUI로 회로를 만든 후 "Save as Python Code"로 추출
- 추출된 코드에서 `PsimCreateNewElement`의 첫 번째 인자를 기록
- 이 값을 `psim_element_type`에 등록

---

## 5. 구현 범위

### 파일 수정
- `src/psim_mcp/data/component_library.py`: `ComponentDef` 기반으로 재구성
- `src/psim_mcp/utils/svg_renderer.py`: 핀 위치를 catalog에서 참조
- `src/psim_mcp/bridge/bridge_script.py`: `kind` → `psim_element_type` 변환 추가

### 파일 생성
- `src/psim_mcp/data/pin_registry.py` (선택): 핀 이름 상수 정의

---

## 6. 테스트 계획

- 모든 kind에 대해 핀 정의가 존재하는지 확인
- 필수 파라미터 누락 시 검증 실패 확인
- 기존 29개 템플릿의 모든 component type이 catalog에 존재하는지 확인
- svg_renderer가 catalog의 핀 정의와 일관되는지 확인

---

## 7. 완료 기준

- [ ] 모든 부품에 핀 정의 추가
- [ ] 필수/선택 파라미터 분리
- [ ] PSIM element type 필드 추가 (값은 Windows 확인 후 채움)
- [ ] svg_renderer, ascii_renderer가 catalog 핀 정의를 참조
- [ ] bridge_script가 kind → psim_element_type 변환 사용
- [ ] 기존 테스트 통과
