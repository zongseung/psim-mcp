# PSIM-MCP v1.1.4 Error Review

> 작성일: 2026-03-19
> 범위: 회로 preview SVG와 실제 PSIM 회로 생성 경로에서 확인된 "회로도 엉망" 현상 분석
> 대상 코드:
> - `src/psim_mcp/data/circuit_templates.py`
> - `src/psim_mcp/data/component_library.py`
> - `src/psim_mcp/utils/svg_renderer.py`
> - `src/psim_mcp/services/circuit_design_service.py`
> - `src/psim_mcp/bridge/bridge_script.py`

---

## 요약

회로도가 엉망으로 보이는 이유는 단일 버그가 아니라 아래 세 층의 불일치가 겹친 결과다.

1. 템플릿 connection endpoint가 component library의 pin 정의와 맞지 않는다.
2. preview 단계가 validation error를 감지해도 렌더링을 계속 진행한다.
3. SVG renderer와 PSIM bridge가 동일한 pin/anchor 규약을 완전히 공유하지 않는다.

즉, "자연어 -> 회로 spec -> preview -> PSIM" 파이프라인에서 공통 계약(contract)이 약하다.

---

## 2026-03-19 코드 반영 현황

아래 항목은 현재 코드에 이미 반영되었다.

- template 기반 invalid pin 정리
- IGBT template의 `drain/source -> collector/emitter` 정규화
- 일부 transformer template의 pin 계약 보정
- generator(`forward`, `flyback`, `llc`)의 transformer pin alias 정규화
- preview 단계의 validation hard-fail
- template endpoint 유효성 테스트 추가

아래 항목은 아직 남아 있다.

- renderer/bridge 공통 anchor registry 부재
- 실제 PSIM 시뮬레이션에서 `boost_pfc`의 flat 현상 추가 확인 필요
- 실제 PSIM 시뮬레이션에서 `forward`, `llc`의 동작 결과 재검증 필요

---

## 확인된 핵심 증상

- 일부 회로에서 선이 빠진다.
- 일부 회로에서 선이 부품 단자와 어긋난 위치에 붙는다.
- 복잡한 토폴로지에서 부품은 보이는데 연결이 비정상적이다.
- preview는 그려지지만 confirm/create 단계에서 다른 배선 결과가 나올 수 있다.

---

## 원인 분류

| 구분 | 심각도 | 설명 |
|------|--------|------|
| Pin 계약 불일치 | P0 | template 또는 generator가 존재하지 않는 pin 이름을 사용 |
| Validation 무시 | P0 | preview가 CONN_UNKNOWN_PIN error를 띄우고도 SVG 생성 |
| Renderer/Bridge 좌표 규약 분리 | P1 | 같은 spec이라도 preview와 PSIM 배선이 다르게 보일 수 있음 |
| Alias pin 중복 배치 | P1 | 2단자 부품 alias pin이 서로 다른 좌표로 처리되던 문제 |

---

## 세부 문서

- [01-pin-contract-mismatch.md](./01-pin-contract-mismatch.md)
- [02-preview-validation-gap.md](./02-preview-validation-gap.md)
- [03-renderer-bridge-divergence.md](./03-renderer-bridge-divergence.md)
- [04-recommended-fix-order.md](./04-recommended-fix-order.md)

---

## 결론

현재 문제의 본질은 "그림을 못 그린다"가 아니라 "회로 spec의 pin 계약이 통일되지 않았다"는 점이다.

따라서 우선순위는 아래가 맞다.

1. template endpoint를 component library 정의에 맞게 정규화
2. preview에서 validation error 회로 렌더링 차단
3. SVG renderer와 PSIM bridge가 같은 pin anchor source를 참조하도록 통합
