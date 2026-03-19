# 02. Preview Validation Gap

## 문제 정의

`preview_circuit()`는 validation error를 계산하지만, error가 있어도 SVG 렌더링을 계속 진행한다.

이 때문에 사용자 관점에서는:

- 틀린 회로가 정상 preview처럼 보인다.
- 나중에 confirm/create에서만 문제를 인지하게 된다.
- "왜 그림이 이상한지" 즉시 알 수 없다.

---

## 현재 동작

파일: `src/psim_mcp/services/circuit_design_service.py`

현재 순서는 아래와 같다.

1. template 또는 generator로 component / connection / net 구성
2. `validate_circuit()` 호출
3. `validation_issues` 수집
4. `_render_and_store()` 호출
5. 성공 응답 반환

핵심 문제는 `_has_errors`가 계산되지만 preview 차단에 사용되지 않는다는 점이다.

---

## 실제 영향

예를 들어 endpoint가 invalid pin이면 validator는 `CONN_UNKNOWN_PIN`을 만든다.
하지만 preview는 계속 진행되어:

- 어떤 선은 안 보이고
- 어떤 부품만 남고
- 사용자는 renderer bug처럼 오해한다

실제로는 invalid circuit spec인데, UI 상 정상 흐름처럼 보이는 것이다.

---

## 왜 위험한가

preview는 사용자가 가장 먼저 접하는 품질 게이트다.

여기서 error circuit를 막지 않으면:

- 잘못된 템플릿이 계속 재사용된다
- NLP parsing 문제와 template 문제를 분리해서 진단하기 어렵다
- PSIM bridge 문제로 오인하게 된다

---

## 권장 정책

### P0

validation error가 하나라도 있으면 성공 preview를 만들지 않는다.

권장 응답:

- `success: false`
- `error.code: CIRCUIT_VALIDATION_FAILED`
- invalid endpoint 목록
- 수정 suggestion

### P1

대안으로 "error preview"를 허용할 수는 있다. 단, 이 경우에도:

- 일반 preview와 명확히 구분
- SVG 상에 invalid endpoint를 강조
- confirm/create는 반드시 차단

현재 상태에서는 차라리 hard fail이 더 안전하다.

---

## 수정 포인트

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/validators/structural.py`

필요 작업:

1. `preview_circuit()`에서 `_has_errors` true면 early return
2. `validation_issues`를 사용자 메시지에 포함
3. 테스트 추가:
   - invalid pin template preview 실패
   - warning만 있는 경우 preview 성공

---

## 기대 효과

- broken template가 즉시 드러남
- renderer 문제와 spec 문제를 분리 가능
- 사용자에게 "회로가 이상하게 그려진다" 대신 "pin 정의가 틀렸다"를 명확히 전달 가능
