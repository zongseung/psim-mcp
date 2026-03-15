# Step 5: Validation 계층 추가

> 우선순위: P0-P1
> 예상 범위: `src/psim_mcp/validators/circuit_validator.py`
> 의존: Step 1 (CircuitSpec), Step 2 (Component Catalog)

---

## 1. 목적

회로 생성 요청이 PSIM bridge에 도달하기 **전에** 오류를 잡는다.

현재 문제:
- 잘못된 회로 정의가 bridge까지 가서야 실패함
- 실패 원인이 "PsimCreateNewElement returned None" 같은 불명확한 메시지
- LLM이 생성한 구조적 오류를 사전 차단할 방법이 없음

목표:
- CircuitSpec 수준에서 구조적/전기적 오류를 검출
- 명확한 에러 메시지와 수정 제안 반환
- bridge 호출 전에 "이 회로는 생성 가능한가" 판단

---

## 2. 검증 항목

### 2.1 구조 검증 (Structural)

| 검증 | 설명 | 에러 코드 |
|------|------|-----------|
| component id 중복 | 같은 id를 가진 부품이 2개 이상 | `DUPLICATE_COMPONENT_ID` |
| kind 유효성 | catalog에 없는 kind | `UNKNOWN_COMPONENT_KIND` |
| 필수 파라미터 누락 | catalog의 required_params 미충족 | `MISSING_REQUIRED_PARAM` |
| net 핀 유효성 | net에 참조된 핀이 존재하지 않는 component를 가리킴 | `INVALID_PIN_REFERENCE` |
| 핀 이름 유효성 | component의 핀 목록에 없는 핀 이름 | `UNKNOWN_PIN_NAME` |

### 2.2 전기적 검증 (Electrical)

| 검증 | 설명 | 에러 코드 |
|------|------|-----------|
| 전원 없음 | DC_Source 또는 AC_Source가 없음 | `NO_SOURCE` |
| 부하 없음 | Resistor 또는 Motor 등 부하 소자 없음 | `NO_LOAD` |
| GND 누락 | GND net이 없거나 전원의 negative가 GND에 없음 | `NO_GROUND` |
| floating net | 핀이 1개뿐인 net (연결되지 않은 핀) | `FLOATING_PIN` |
| 단락 가능성 | 전원의 positive와 negative가 같은 net | `SHORT_CIRCUIT` |

### 2.3 파라미터 범위 검증

| 검증 | 설명 | 에러 코드 |
|------|------|-----------|
| 음수 값 | 저항, 인덕턴스, 캐패시턴스 등이 0 이하 | `NEGATIVE_VALUE` |
| 비현실적 값 | 스위칭 주파수 > 10MHz, 인덕턴스 > 1H 등 | `OUT_OF_RANGE` |
| duty cycle 범위 | V_out > V_in (buck) 등 물리적 불가 | `INVALID_OPERATING_POINT` |

---

## 3. 검증 결과 구조

```python
class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

class ValidationError(BaseModel):
    code: str
    message: str
    component_id: str | None = None
    suggestion: str | None = None

class ValidationWarning(BaseModel):
    code: str
    message: str
    component_id: str | None = None
```

---

## 4. 검증 호출 위치

```
사용자 요청
    ↓
preview_circuit / create_circuit (tool)
    ↓
SimulationService.create_circuit
    ↓
★ CircuitValidator.validate(spec)  ←── 여기
    ↓ (통과 시)
adapter.create_circuit
    ↓
bridge_script (PSIM API)
```

검증 실패 시:
- bridge를 호출하지 않음
- 에러 목록 + 수정 제안을 사용자에게 반환
- preview_circuit의 경우 SVG에 에러 표시 (빨간 테두리 등)

---

## 5. 구현 범위

### 파일 생성
- `src/psim_mcp/validators/__init__.py`
- `src/psim_mcp/validators/circuit_validator.py`
- `src/psim_mcp/validators/structural.py` (구조 검증)
- `src/psim_mcp/validators/electrical.py` (전기적 검증)
- `src/psim_mcp/validators/parameter.py` (파라미터 범위)

### 파일 수정
- `services/simulation_service.py`: `create_circuit`에서 validator 호출
- `tools/circuit.py`: preview_circuit에서 validator 호출 (경고만 표시)

---

## 6. 테스트 계획

- component id 중복 시 에러 반환
- 존재하지 않는 kind 사용 시 에러 반환
- GND 없는 회로 시 에러 반환
- 전원 없는 회로 시 에러 반환
- 음수 저항값 시 에러 반환
- 정상 회로(buck 등) 시 검증 통과
- 29개 기존 템플릿 전부 검증 통과

---

## 7. 완료 기준

- [ ] CircuitValidator 구현
- [ ] 구조 검증 5개 항목 동작
- [ ] 전기적 검증 5개 항목 동작
- [ ] 파라미터 범위 검증 3개 항목 동작
- [ ] service 레이어에서 검증 호출
- [ ] 검증 실패 시 명확한 에러 메시지 + 수정 제안 반환
- [ ] 기존 29개 템플릿 검증 통과
- [ ] 기존 테스트 통과
