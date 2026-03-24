# 사용자 의도 기반 회로 합성기로 전환하기 위한 설계 문서
작성일: 2026-03-24

## 목적

현재 `psim-mcp`는 `PSIM reference-derived pattern + parameter retargeting` 성격이 강하다.
이 문서는 이를 `사용자 의도 기반 회로 합성기`로 전환하기 위해 필요한 구조, 데이터 모델,
구현 단계, 리스크를 구체적으로 정의한다.

이 문서의 목표는 다음과 같다.

- 사용자의 자연어 요구를 어떤 내부 표현으로 바꿔야 하는지 정의
- topology 고정 generator 중심 구조를 어떤 계층으로 분해할지 제안
- `graph synthesis -> layout synthesis -> routing synthesis -> bridge emission` 파이프라인을 설계
- 단기/중기/장기 구현 단계를 제시

## 목표 상태 한 줄 정의

목표는 다음 시스템이다.

> 사용자의 요구를 읽고
> 필요한 topology 후보와 제약을 추론한 뒤
> canonical circuit graph를 합성하고
> 그 graph로부터 회로도 layout과 routing을 생성하며
> 마지막에 PSIM bridge가 이를 실행 형식으로 내보내는 구조

즉 핵심은 `예제 패턴 선택`이 아니라 `graph 합성`이어야 한다.

## 현재 구조의 핵심 한계

현재 구조는 대체로 아래 순서다.

1. 자연어 파싱
2. topology 결정
3. topology별 generator 선택
4. generator가 미리 정한 `components + nets` 반환
5. service가 정규화
6. SVG/PSIM 생성

이 구조의 문제는 다음과 같다.

- topology 이후의 회로 구조가 generator 내부에 너무 많이 고정돼 있다
- 사용자의 요구가 topology 선택과 파라미터 치환 이상으로 반영되기 어렵다
- `electrical structure`와 `diagram layout`가 충분히 분리되지 않았다
- example-derived layout가 구조 생성의 사실상 뼈대 역할을 한다

## 목표 아키텍처

전환 후 파이프라인은 아래와 같아야 한다.

1. Intent Understanding
2. Candidate Topology Resolution
3. Canonical Spec Construction
4. Circuit Graph Synthesis
5. Layout Synthesis
6. Routing Synthesis
7. Validation
8. SVG Rendering / PSIM Emission

각 단계는 서로 다른 책임을 가져야 한다.

## 실행 계층 관점에서 추가로 고정해야 할 것

이 문서의 합성 파이프라인은 유지하되, 실제 구현 단계에서는 아래 실행 계층 원칙도 함께 고정해야 한다.

1. tool surface는 high-level capability를 유지한다.
2. preview, confirm, create, simulation은 같은 canonical payload를 소비한다.
3. backend는 교체 가능해야 하지만 service contract는 바뀌지 않아야 한다.
4. preview/session store payload는 versioned contract로 관리한다.
5. low-level draw primitive 확장보다 graph/layout/routing payload 완성도를 우선한다.

즉 목표 구조는 아래처럼 읽어야 한다.

```text
tool surface
  -> canonical synthesis pipeline
  -> backend adapter
  -> preview / PSIM / simulation output
```

## 1. Intent Understanding

### 역할

사용자 자연어에서 아래를 추출한다.

- 목표 기능
- 입력 조건
- 출력 조건
- 전력/주파수/절연 여부
- 제어 요구
- 우선순위
- 명시되지 않은 필수 항목

### 출력 모델

예시:

```json
{
  "intent": {
    "goal": "dc_dc_conversion",
    "input_domain": "dc",
    "output_domain": "dc",
    "requires_isolation": true,
    "target_power_w": 300,
    "input_voltage_v": 380,
    "output_voltage_v": 24,
    "control_mode": "voltage_regulation"
  },
  "confidence": 0.78,
  "missing_fields": ["switching_frequency_hz"]
}
```

### 구현 원칙

- keyword map은 `후보 생성`까지만 담당
- 최종 topology 확정은 별도 결정 계층이 맡음
- ambiguity는 가능한 한 구조적으로 유지
- 부족한 정보는 `missing_fields`로 드러냄

## 2. Candidate Topology Resolution

### 역할

하나의 자연어 요구를 곧바로 topology 하나로 고정하지 않고,
가능한 topology 후보 목록과 점수를 만든다.

예:

- `380V DC를 24V 절연 강하`
  - `flyback`
  - `forward`
  - `llc`
  - `phase_shift_full_bridge`

### 필요한 입력

- intent model
- topology metadata
- feasibility rules
- optional domain heuristics

### 출력 모델

```json
{
  "candidates": [
    {
      "topology": "flyback",
      "score": 0.71,
      "reasons": ["isolated", "medium power", "dc-dc"]
    },
    {
      "topology": "forward",
      "score": 0.62,
      "reasons": ["isolated", "better fit above basic flyback range"]
    }
  ]
}
```

### 구현 원칙

- 현재의 `USE_CASE_MAP`은 여기로 이동
- hardcoded one-shot mapping을 ranking system으로 변경
- 낮은 confidence는 질문 또는 다중 제안으로 처리

## 3. Canonical Spec Construction

### 역할

선정된 topology 후보와 사용자 요구를 바탕으로,
회로 합성에 필요한 표준 스펙 객체를 만든다.

### canonical spec 예시

```json
{
  "topology": "flyback",
  "domains": {
    "input": "dc",
    "output": "dc"
  },
  "requirements": {
    "isolated": true,
    "regulated_output": true,
    "power_w": 300,
    "vin_nominal_v": 380,
    "vout_v": 24,
    "fsw_hz": 100000
  },
  "options": {
    "snubber": "rcd_clamp",
    "rectification": "diode",
    "control": "voltage_mode"
  },
  "layout_preferences": {
    "style": "readable_power_converter",
    "primary_left_secondary_right": true
  }
}
```

### 구현 원칙

- `spec`는 topology generator 입력값이 아니라 synthesis 입력값이어야 함
- 옵션과 기본값의 출처를 기록
- 사용자 명시값과 시스템 추론값을 구분

## 4. Circuit Graph Synthesis

이 단계가 가장 중요하다.

현재 generator가 하던 역할을 `graph synthesis`와 `layout synthesis`로 분리해야 한다.

### 역할

canonical spec을 받아 전기적 구조를 합성한다.

출력은 좌표 없는 구조여야 한다.

- components
- component roles
- nets
- functional blocks
- optional blocks
- feedback / sensing paths

### 예시 출력

```json
{
  "components": [
    {"id": "VIN", "type": "DC_Source", "role": "input_source"},
    {"id": "Q1", "type": "MOSFET", "role": "main_switch"},
    {"id": "T1", "type": "Transformer", "role": "power_transfer"},
    {"id": "D1", "type": "Diode", "role": "output_rectifier"},
    {"id": "COUT", "type": "Capacitor", "role": "output_filter"}
  ],
  "nets": [
    {"id": "n_in_pos", "pins": ["VIN.positive", "Q1.drain", "T1.pri_1"]},
    {"id": "n_out_pos", "pins": ["D1.cathode", "COUT.positive"]}
  ],
  "blocks": [
    {"id": "primary_power_stage", "members": ["VIN", "Q1", "T1"]},
    {"id": "secondary_rectifier", "members": ["T1", "D1", "COUT"]}
  ]
}
```

### 구현 방식

권장 방식은 topology별 `graph assembler`다.

- `buck_graph.py`
- `flyback_graph.py`
- `llc_graph.py`

하지만 이 파일들은 더 이상 좌표를 만들면 안 된다.
오직 구조만 조립해야 한다.

### 반드시 분리해야 할 것

- 구조 결정
- 부품 파라미터 계산
- 좌표 배치
- wire routing

이 네 가지가 한 파일에 섞이면 다시 example-driven 구조로 돌아간다.

## 5. Parameter Sizing Layer

### 역할

구조 합성과 분리된 상태에서 부품 값을 계산한다.

예:

- 인덕턴스
- 커패시턴스
- 턴비
- 공진소자 값
- 스위치 정격 여유

### 이유

현재는 topology generator 안에서 구조와 sizing이 함께 처리되는 경향이 있다.
이걸 분리하면 아래가 좋아진다.

- 동일 구조에 다양한 sizing strategy 적용 가능
- 검증 로직 분리 가능
- 설계 계산식 테스트가 쉬워짐

## 6. Layout Synthesis

### 역할

좌표 없는 circuit graph를 사람이 읽기 좋은 schematic layout으로 바꾼다.

이 단계의 출력:

- component positions
- orientation
- symbol variant
- region boundaries
- bus / rail anchors

### layout 입력

- circuit graph
- component roles
- block membership
- layout preferences

### layout 원칙

- primary / secondary 영역 분리
- power flow가 좌에서 우, 상에서 하 등 일관된 방향 유지
- source, switch, magnetic, rectifier, load/filter의 상대적 규칙 정의
- topology 공통 규칙과 topology 특화 규칙 분리

### 왜 필요한가

현재는 example 좌표가 이 역할을 대신하고 있다.
앞으로는 `layout strategy`가 이 일을 해야 한다.

### 구현 제안

`src/psim_mcp/layout/` 계층 신설:

- `models.py`
- `engine.py`
- `strategies/power_converter_common.py`
- `strategies/buck.py`
- `strategies/flyback.py`
- `strategies/llc.py`

## 7. Routing Synthesis

### 역할

layout 결과를 바탕으로 `wire_segments`를 생성한다.

### 요구 사항

- pin anchor 정확성
- multi-pin symbol 대응
- 중복 선 제거
- 교차 최소화
- rail / bus 정렬
- optional obstacle avoidance

### 현재와의 차이

현재 라우팅은 canonical geometry 통일 쪽으로는 개선됐지만,
schematic readability를 적극적으로 만들지는 못한다.

향후에는 단순 L자 규칙이 아니라 아래가 필요하다.

- block-aware routing
- region-aware routing
- trunk-and-branch routing
- symmetry rules

## 8. Validation Layer

검증은 단순 전기적 연결 확인을 넘어 아래까지 포함해야 한다.

### 구조 검증

- topology 필수 블록 존재 여부
- 필수 nets 존재 여부
- role 충돌 여부

### 설계 검증

- 전압/전류/전력 범위 타당성
- topology 적합성
- 절연 요구와 구조 일치 여부

### 도면 검증

- 미연결 핀
- symbol/pin mismatch
- wire overlap / duplicate
- unreadable crossing count threshold

## 9. SVG Renderer와 PSIM Bridge의 역할 재정의

### SVG Renderer

- 절대 구조를 추론하지 않음
- 오직 layout + routing 결과만 소비
- 심볼 렌더링과 시각 표현만 담당

### PSIM Bridge

- 절대 topology를 추론하지 않음
- 오직 canonical graph + layout/routing 결과를 PSIM 형식으로 변환
- low-level PSIM 계약만 책임짐

이렇게 해야 preview와 실제 생성이 같은 시스템의 산출물을 보게 된다.

## 10. 데이터 모델 제안

최소 canonical model은 아래 4개가 필요하다.

### IntentSpec

- 사용자의 요구와 제약

### CircuitGraph

- 좌표 없는 전기적 구조

### SchematicLayout

- component geometry와 orientation

### WireRouting

- `wire_segments`

예시 관계:

```text
IntentSpec
  -> CircuitGraph
  -> SchematicLayout
  -> WireRouting
  -> SVG / PSIM
```

## 11. 하드코딩을 어떻게 줄일 것인가

하드코딩을 전부 제거하는 것이 목표는 아니다.

### 유지할 하드코딩

- topology ontology
- field alias
- pin alias
- PSIM mapping
- topology structural constraints

### 데이터화할 것

- topology 후보 규칙
- optional block catalog
- layout strategy config
- symbol variant registry

### 줄여야 할 것

- example-derived absolute coordinates
- topology별 ad-hoc direction heuristic
- parser 내부 one-shot topology mapping

## 12. 단계별 구현 계획

### Phase 1. Generator 분해

추가 범위:

- preview/session payload에 `payload_version` 추가
- `SimulationService.create_circuit()`도 동일 migration 범위에 포함
- topology 분해와 함께 entrypoint contract 고정

목표:

- 기존 generator를 `graph assembler + sizing`으로 분리

작업:

- topology별 generator에서 좌표 생성 제거
- `components/nets` 생성만 남기기
- sizing 함수 별도 모듈 분리

완료 조건:

- generator 파일에서 `position`, `direction`, `ports` 하드코딩 비중이 크게 감소

### Phase 2. Canonical Graph 모델 도입

추가 범위:

- preview/store payload에 `graph`를 canonical layer로 저장
- mixed-mode 기간에도 service entrypoint contract는 유지
- `SimulationService`가 graph 또는 legacy projection 경계를 명시적으로 가짐

목표:

- `CircuitGraph` 모델 정식 도입

작업:

- role, block, optional block 메타데이터 추가
- validator와 service를 graph 중심으로 전환

완료 조건:

- service 내부가 raw dict 조립보다 graph 객체 흐름 중심으로 바뀜

### Phase 3. Layout Engine 도입

추가 범위:

- preview/store payload에 `layout` 저장
- renderer는 layout consumer로 축소되고 tool surface는 그대로 유지
- confirm/create/simulation 경로가 같은 layout payload를 읽도록 정리

목표:

- example 좌표 의존 제거

작업:

- topology별 layout strategy 구현
- primary/secondary, source/load, tank/rectifier 영역 규칙 구현

완료 조건:

- 적어도 `buck`, `flyback`, `llc`가 example coordinates 없이 readable layout 생성

### Phase 4. Advanced Routing 도입

추가 범위:

- `WireRouting`을 backend 공통 geometry payload로 승격
- preview와 bridge가 routing 재계산 없이 같은 routing payload를 소비
- backend별 geometry mismatch는 rerouting이 아니라 adapter 차원에서 제어

목표:

- 회로도 가독성 개선

작업:

- block-aware routing
- rail-aware routing
- duplicate/crossing minimization

완료 조건:

- 현재 SVG 대비 우회선, 겹선, 어색한 루프가 의미 있게 감소

### Phase 5. Intent Resolution 개선

추가 범위:

- 기존 action contract와 `design_session_token` 유지
- versioned design-session payload로 continue flow 호환성 보장
- parser 교체와 service contract 보존을 분리해서 관리

목표:

- parser shortcut을 candidate ranking 구조로 교체

작업:

- 후보 topology scoring
- missing-field driven clarification
- user intent traceability 추가

완료 조건:

- `design_circuit()`가 one-shot topology 확정보다 structured resolution을 수행

## 13. 테스트 전략

### 단위 테스트

- intent extraction
- candidate ranking
- graph assembly
- sizing
- layout placement
- routing

### 회귀 테스트

- topology별 golden graph
- topology별 golden SVG
- PSIM emission smoke test

### 품질 지표

- wire crossing 수
- duplicate segment 수
- unconnected pin 수
- symbol-pin mismatch 수
- topology feasibility error rate

## 14. 리스크

### 1. 초기 전환 비용이 큼

generator를 나누는 순간 영향 범위가 넓다.

### 2. topology별 규칙 모델링 난이도가 높음

특히 절연형, 공진형, 다핀 소자는 단순화가 어렵다.

### 3. 자연어 해석보다 구조 모델링이 더 큰 과제일 수 있음

문제의 본질은 parser가 아니라 graph/layout/routing 계층일 가능성이 크다.

## 최종 제안

가장 현실적인 전환 순서는 이렇다.

1. 기존 generator에서 좌표와 구조를 분리
2. `CircuitGraph`를 canonical 중심 모델로 도입
3. `wire_segments` 이전 단계로 `SchematicLayout` 계층을 추가
4. SVG와 bridge를 pure consumer로 제한
5. 마지막에 parser를 candidate-resolution 구조로 개선

즉 parser부터 고치는 것이 아니라,
먼저 `구조를 실제로 합성할 수 있는 내부 모델`을 세우는 것이 우선이다.

## 최종 결론

사용자 의도 기반 합성기로 가려면,
지금의 `topology별 example-driven generator`를 조금 다듬는 수준으로는 부족하다.

핵심 전환은 다음 한 문장으로 요약된다.

> `예제 기반 좌표 조립 시스템`에서
> `canonical graph 기반 회로 합성 시스템`으로 중심축을 옮겨야 한다.

그 전환의 실질적 출발점은 parser가 아니라
`CircuitGraph`, `SchematicLayout`, `WireRouting` 세 계층의 분리다.
