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

원칙:

- validator는 bridge 호출 전에 항상 실행한다
- bridge는 validation 실패를 보완하려는 계층이 아니라, 검증 완료된 spec을 실행하는 계층이다
- tool이나 service에서 임시 dict를 직접 bridge로 보내는 경로는 점진적으로 제거한다
- preview_circuit도 동일한 validator를 사용하되, preview에서는 warning/오류를 UI에 드러내고 create 직전에는 hard fail 정책을 적용한다

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
- preview_circuit 호출 시 validation 결과가 응답에 반영되는지 확인
- confirm_circuit이 validation 실패 spec을 생성 단계로 넘기지 않는지 확인

---

## 7. 완료 기준

- [x] CircuitValidator 구현 (`validators/` 패키지)
- [x] 구조 검증 동작 (빈 리스트, 중복 ID, 미지원 kind)
- [x] 전기적 검증 동작 (소스 없음, 부하 없음, 단락 감지)
- [x] 파라미터 범위 검증 동작 (음수 값, 주파수/전압 범위)
- [x] ValidationResult + ValidationIssue 모델 정의
- [x] 기존 테스트 통과
- [x] service 레이어에서 검증 호출 연동 (create_circuit에서 blocking 검증)
- [x] preview_circuit에서 검증 결과 응답 반영 (validation_warnings + suggestion 포함)
- [x] confirm_circuit에서 검증 실패 시 생성 차단 (service에서 CIRCUIT_VALIDATION_FAILED)
- [x] connection 검증 추가 (핀 이름/부품 존재 확인 + 올바른 핀 목록 제안)
