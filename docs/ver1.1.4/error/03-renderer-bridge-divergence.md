# 03. Renderer / Bridge Divergence

## 문제 정의

SVG preview renderer와 PSIM bridge는 둘 다 같은 회로 spec을 사용하지만, pin 위치 계산 규칙이 완전히 동일하지 않다.

즉, 논리적으로는 같은 회로라도:

- preview에서 보이는 wire 종점
- 실제 PSIM에서 생성되는 wire 종점

이 다를 수 있다.

---

## 현재 구조

### SVG renderer

파일: `src/psim_mcp/utils/svg_renderer.py`

역할:

- component type별 symbol 배치
- pin 이름 -> preview 좌표 변환
- connection / net을 SVG polyline으로 렌더링

### PSIM bridge

파일: `src/psim_mcp/bridge/bridge_script.py`

역할:

- component를 실제 PSIM element로 생성
- `ports` 또는 `position` 기반으로 pin 좌표 계산
- 좌표로 wire 생성

---

## 현재 확인된 구체 문제

### 1. 2단자 부품 alias pin 분리

이전 renderer는 `Inductor`, `Resistor` 등에서:

- `pin1`
- `input`

을 서로 다른 y 좌표로 계산했다.

즉, 하나의 물리 단자에 대한 alias가 서로 다른 좌표를 갖고 있었다.

이 문제는 이번에 `svg_renderer.py`에서 수정했다.

---

### 2. 복잡한 부품은 아직 공통 anchor source가 없음

예:

- `IGBT`
- `Transformer`
- `Center_Tap_Transformer`
- `Three_Phase_Transformer`

이 부품들은 preview symbol의 anchor와 bridge 측 pin map이 서로 다른 로직을 사용한다.

이 상태에서는 한쪽을 수정해도 다른 쪽이 자동으로 따라오지 않는다.

---

## 왜 반복적으로 깨지는가

renderer와 bridge가 같은 component metadata를 공유하지 않고 각자 pin 위치를 계산하기 때문이다.

즉, 현재 구조는:

- component library: pin 이름
- svg renderer: pin 좌표 규칙
- bridge script: pin 좌표 규칙

이 분리되어 있다.

pin 이름이 늘어나거나 바뀔 때 회귀가 생기기 쉽다.

---

## 권장 구조

공통 `pin anchor registry`를 도입하는 것이 맞다.

예시 책임:

- component library: valid pin 목록
- anchor registry: pin별 preview/bridge 기준 anchor 정의
- renderer: registry 참조
- bridge: registry 참조

이렇게 해야 preview와 PSIM이 같은 회로를 본다.

---

## 우선 적용 범위

다음 부품부터 공통화 우선순위가 높다.

1. `IGBT`
2. `Transformer`
3. `Center_Tap_Transformer`
4. `Three_Phase_Transformer`
5. `DiodeBridge`

---

## 테스트 필요 항목

- 같은 circuit spec에 대해 preview pin endpoint와 bridge pin endpoint가 일치하는지
- alias pin이 동일 좌표를 갖는지
- 3핀, 4핀, center-tap 계열이 의도한 위치에 배치되는지
