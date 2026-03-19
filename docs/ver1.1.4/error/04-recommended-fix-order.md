# 04. Recommended Fix Order

## 목표

회로도가 "보기 좋게" 그려지는 문제보다 먼저, "잘못된 회로 spec은 그려지지 않게" 만드는 것이 우선이다.

---

## 1단계. Template pin 정합성 복구

대상:

- `src/psim_mcp/data/circuit_templates.py`
- `src/psim_mcp/data/component_library.py`

작업:

1. invalid endpoint 전수 수정
2. IGBT 계열 `drain/source -> collector/emitter` 정규화
3. transformer 계열 pin naming 재정의
4. center-tap transformer의 primary pin 계약 확정

완료 기준:

- 모든 template가 validator에서 `CONN_UNKNOWN_PIN` 없이 통과

현황:

- 완료
- 추가된 `test_circuit_template_validity.py` 기준 template endpoint는 현재 유효

---

## 2단계. Preview hard-fail 적용

대상:

- `src/psim_mcp/services/circuit_design_service.py`

작업:

1. validation error 존재 시 preview 실패 반환
2. warning만 있을 때만 SVG 렌더링 허용
3. 테스트 추가

완료 기준:

- invalid template는 더 이상 "그려지긴 하지만 이상한 그림" 상태로 보이지 않음

현황:

- 완료
- invalid generator/template spec은 `CIRCUIT_VALIDATION_FAILED`로 차단됨

---

## 3단계. Renderer / Bridge pin anchor 통합

대상:

- `src/psim_mcp/utils/svg_renderer.py`
- `src/psim_mcp/bridge/bridge_script.py`
- 신규 공통 registry 모듈

작업:

1. 공통 pin anchor registry 도입
2. renderer, bridge가 같은 anchor 정의 참조
3. 복잡한 부품부터 단계적 통합

완료 기준:

- preview와 PSIM 생성 결과가 동일한 pin contract 위에서 동작

현황:

- 부분 진행
- 2단자 alias 및 일부 transformer anchor는 보강되었지만 공통 registry는 아직 없음

---

## 4단계. 회귀 방지

필수 자동 검사:

1. template endpoint lint
2. preview validation fail test
3. renderer pin mapping test
4. bridge pin mapping test

현황:

- template endpoint lint: 완료
- preview validation fail test: 완료
- renderer pin mapping test: 일부 완료
- bridge pin mapping test: 미완료

---

## 추가 남은 작업

현재 문서 작성 당시보다 더 명확해진 잔여 이슈는 아래와 같다.

1. `boost_pfc` 실제 PSIM flat 원인을 bridge wire routing 또는 다이오드 브리지 구성 기준으로 재검증
2. `forward`, `llc`의 실제 PSIM 시뮬레이션 결과를 최신 코드 기준으로 재검증
3. preview 성공 여부와 실제 PSIM 시뮬레이션 성공 여부를 분리해 추적

---

## 구현 우선순위

| 순서 | 작업 | 우선순위 |
|------|------|----------|
| 1 | template invalid pin 수정 | P0 |
| 2 | preview hard-fail | P0 |
| 3 | bridge / renderer anchor 통합 | P1 |
| 4 | error SVG 시각화 개선 | P2 |

---

## 판단 기준

다음 조건을 만족해야 "회로도 문제 해결"로 볼 수 있다.

1. invalid pin이 있는 spec은 preview 단계에서 실패한다.
2. valid spec은 preview와 PSIM에서 동일한 연결 의미를 가진다.
3. 사용자는 "그림이 이상하다" 대신 구체적인 validation error를 본다.
