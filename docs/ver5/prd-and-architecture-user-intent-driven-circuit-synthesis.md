# VER5 통합 PRD 및 아키텍처 문서
작성일: 2026-03-24

## 문서 목적

이 문서는 `ver5` 문서군을 하나의 제품 문서로 통합한 것이다.

포함 범위:

- 최종 목표
- 제품 정의
- 문제 정의
- 사용자 가치
- 비기능 요구사항
- 시스템 아키텍처
- 핵심 데이터 모델
- 단계별 구현 축
- 구조적으로 추가되어야 할 사항
- 성공 기준

즉 이 문서는 `사용자 의도 기반 회로 합성기` 전환을 위한
최상위 PRD이자 아키텍처 기준 문서이며,
동시에 실제 리팩터링과 단계적 전환을 이끄는 개발 기획 문서다.

## 문서 성격

이 문서는 단순 비전 문서가 아니다.
성격상 아래 세 가지를 함께 가진다.

1. 제품 요구사항 문서(PRD)
- 왜 이 전환이 필요한지
- 최종 목표가 무엇인지
- 사용자와 시스템이 어떤 가치를 얻는지 정의

2. 아키텍처 설계 문서
- 시스템을 어떤 계층으로 분리할지
- 어떤 canonical model을 도입할지
- 어떤 registry와 ownership이 필요한지 정의

3. 개발 기획 문서
- 어떤 phase로 나눌지
- 각 단계에서 무엇을 산출해야 하는지
- 무엇을 먼저 바꾸고 무엇을 나중에 바꿀지 정의

실행 관점의 세부 계획은 별도 문서 `phase-execution-plan.md`를 기준으로 본다.

따라서 이 문서는 `아이디어 설명서`가 아니라,
향후 구현과 리뷰의 기준선 역할을 하는 상위 계획 문서로 취급해야 한다.

## 최종 목표

최종 목표는 다음 한 문장으로 정의한다.

> 사용자의 자연어 요구를 입력으로 받아,
> 시스템이 스스로 적절한 topology 후보를 판단하고,
> canonical circuit graph를 합성하고,
> 사람이 읽기 좋은 schematic layout과 routing을 생성한 뒤,
> 동일한 구조를 SVG preview와 PSIM 회로 생성에 일관되게 반영하는 회로 합성 시스템을 만든다.

이 목표에서 중요한 것은 세 가지다.

- 자연어는 입력 인터페이스일 뿐, 핵심은 내부 합성 엔진이다
- preview와 실제 생성은 같은 canonical 산출물을 써야 한다
- 예제 패턴 재사용은 참고/검증 수준에 머물고, 생성 로직의 중심이 되어선 안 된다

## 벤치마크 관점에서의 보강

최근 CAD/도면 MCP 사례를 참고하면,
`자연어 -> 도면 작업 실행` 자체는 충분히 구현 가능하다는 점은 확인된다.

하지만 이 프로젝트는 일반 CAD 도면 자동화와 성격이 다르다.

- 일반 CAD MCP:
  - 자연어를 적절한 drawing/backend tool 호출로 연결하는 문제가 중심
- psim-mcp:
  - 자연어를 올바른 회로 구조로 해석하고
  - 그 구조를 canonical intermediate로 고정한 뒤
  - preview와 PSIM 생성을 같은 산출물로 일치시키는 문제가 중심

즉 이 프로젝트의 핵심은 `drawing automation`이 아니라
`domain synthesis + deterministic emission`이다.

이 차이 때문에 아래 원칙이 필요하다.

- 저수준 draw command를 MCP 표면의 중심으로 두지 않는다
- LLM이 선/원/좌표를 직접 조합하게 하지 않는다
- 자연어 이후에는 반드시 `spec -> graph -> layout -> routing` 계층을 거친다

## 실행 아키텍처 관점의 최상위 원칙

ver5는 내부 합성 아키텍처만이 아니라
`실행 계층`까지 포함한 구조로 이해해야 한다.

핵심은 아래 네 층이다.

1. Tool Surface
- 사용자가 호출하는 서비스/API 계층
- 예:
  - `design_circuit`
  - `continue_design`
  - `preview_circuit`
  - `confirm_circuit`
  - `create_circuit_direct`

2. Canonical Synthesis Pipeline
- `intent -> spec -> graph -> layout -> routing`
- 이 계층이 회로 correctness의 source of truth다

3. Registry / Strategy Layer
- topology metadata
- design rule registry
- symbol registry
- layout strategy registry
- routing policy registry
- bridge mapping registry

4. Backend Layer
- preview backend
- real PSIM backend
- 필요 시 headless/export backend

중요:

- 상위 tool surface는 안정적으로 유지한다
- backend는 교체 가능해야 한다
- renderer와 bridge는 추론이 아니라 canonical payload 소비자여야 한다

## 현재 문제 정의

현재 시스템은 다음 성격이 강하다.

- topology를 정하고
- topology별 generator를 선택하고
- generator 내부에 이미 굳어진 회로 구조와 layout 패턴을 사용하고
- 사용자 spec으로 파라미터를 조정한다

이 방식의 장점은 빠르게 PSIM-compatible 결과를 만드는 데 있다.
하지만 한계도 분명하다.

### 현재 구조의 핵심 한계

1. 사용자 요구에서 회로 구조를 새로 합성하기 어렵다
2. topology 이후의 구조가 generator 내부에 고정돼 있다
3. example-derived layout가 실질적인 구조 뼈대 역할을 한다
4. SVG와 실제 생성이 geometry를 재추론하기 쉬운 구조다
5. 자연어 해석이 candidate exploration보다 shortcut 확정에 가깝다

즉 지금 구조는 `사용자 의도 기반 합성기`보다
`예제 패턴 기반 회로 재구성기`에 더 가깝다.

## 제품 정의

### 제품 한 줄 정의

`psim-mcp ver5`는 자연어 요구를 구조화된 intent로 해석하고,
그 intent를 기반으로 회로를 합성하여 preview와 PSIM 생성까지 일관되게 연결하는
회로 합성 플랫폼이다.

### 제품이 해야 하는 일

- 사용자 요구를 해석한다
- topology 후보를 추론한다
- 필요한 추가 정보가 있으면 식별한다
- 회로 구조를 canonical graph로 합성한다
- graph를 readable schematic layout으로 변환한다
- readable routing을 생성한다
- SVG preview를 그린다
- 동일한 구조를 PSIM 회로로 생성한다

### 제품이 하지 말아야 하는 일

- topology를 무리하게 즉시 확정한다
- 예제 좌표를 사실상 정답처럼 복제한다
- preview와 생성이 서로 다른 geometry를 만든다
- 회로 구조를 renderer나 bridge가 제각각 추론하게 둔다

## 사용자와 핵심 사용 시나리오

### 대상 사용자

- 전력전자 엔지니어
- 회로 자동화 도구 사용자
- PSIM 기반 설계/검증 사용자
- 자연어 기반 설계 지원 도구를 원하는 개발자/연구자

### 대표 시나리오

1. 사용자가 자연어로 회로 요구를 입력한다
2. 시스템이 topology 후보와 핵심 누락값을 식별한다
3. 시스템이 합성된 회로를 SVG로 보여준다
4. 사용자는 그 회로가 의도에 맞는지 확인한다
5. 같은 구조가 PSIM 회로로 생성된다

### 대표 입력 예

- `400V DC bus에서 48V 절연 전원 만들고 싶어`
- `48V를 12V로 낮추는 buck converter 그려줘`
- `배터리 충전용 절연형 300W 컨버터 필요해`
- `LLC로 400V에서 24V 1kW 만들고 싶다`

## 핵심 제품 요구사항

## 1. Intent 이해

시스템은 자연어에서 아래를 구조화해야 한다.

- 입력/출력 도메인
- 변환 목적
- 절연 여부
- 전압/전류/전력/주파수
- use case
- control 요구
- topology를 결정하는 제약

## 2. 후보 기반 topology 결정

시스템은 topology를 곧바로 하나로 확정하기보다,
후보 목록과 이유를 내부적으로 유지해야 한다.

필요하면:

- clarification을 요청하거나
- ranked suggestion을 제공해야 한다

## 3. 회로 구조 합성

시스템은 canonical graph를 만들 수 있어야 한다.

graph에는 아래가 포함된다.

- components
- nets
- component roles
- functional blocks
- optional blocks
- design trace

## 4. 레이아웃과 라우팅 분리

시스템은 구조와 회로도 배치를 분리해야 한다.

- graph는 electrical structure
- layout는 component geometry
- routing은 wire geometry

이 셋은 서로 다른 계층이어야 한다.

## 5. preview와 PSIM 생성의 일치

SVG preview와 PSIM 생성은 같은 canonical 산출물을 소비해야 한다.

즉:

- 같은 graph
- 같은 layout
- 같은 routing

을 써야 한다.

## 비기능 요구사항

### 1. 결정성

같은 canonical spec에 대해서는 동일하거나 거의 동일한 결과가 나와야 한다.

### 2. 추적 가능성

왜 특정 topology가 선택됐는지,
왜 특정 값이 들어갔는지,
왜 특정 layout/routing이 나왔는지 추적 가능해야 한다.

### 3. 테스트 가능성

다음 계층별로 테스트 가능해야 한다.

- intent extraction
- candidate ranking
- graph synthesis
- sizing
- layout
- routing
- bridge emission

### 4. 하위 호환성

기존 generator 기반 경로를 한 번에 모두 제거하지 않고,
transition 기간 동안 mixed mode를 허용해야 한다.

### 5. 확장성

새 topology를 추가할 때
예제 좌표 복붙이 아니라
graph rule + layout strategy + routing policy를 추가하는 방식이 되어야 한다.

### 6. 실행 계층 안정성

도구 표면과 런타임 payload 계약은
내부 리팩터링과 별도로 안정적으로 유지돼야 한다.

특히 아래는 버전 관리 대상이다.

- preview payload
- design session payload
- service action/response shape
- backend input contract

## 목표 아키텍처

전체 시스템은 아래 8단계로 구성된다.

1. Intent Understanding
2. Candidate Topology Resolution
3. Canonical Spec Construction
4. Circuit Graph Synthesis
5. Layout Synthesis
6. Routing Synthesis
7. Validation
8. SVG / PSIM Emission

## 실행 아키텍처

위 8단계 합성 구조와 별개로,
실제 제품은 아래 실행 아키텍처를 함께 가진다.

```text
user / tool call
  -> Tool Surface
  -> Canonical Synthesis Pipeline
  -> Backend Adapter
  -> Preview / PSIM / Simulation result
```

### 1. Tool Surface

역할:

- 사용자-facing action 제공
- session 관리
- compatibility contract 유지

원칙:

- 고수준 capability 중심으로 설계
- 저수준 draw primitive 중심 API로 가지 않음

### 2. Backend Adapter Layer

역할:

- 같은 canonical payload를 서로 다른 실행 backend에 전달

예:

- SVG preview backend
- PSIM bridge backend
- mock/headless backend

이 구조는 CAD MCP 계열에서 검증된 방식이지만,
psim-mcp에서는 그 앞단에 canonical synthesis pipeline이 반드시 존재해야 한다.

### 3. Capability Matrix

지원 상태는 topology별만이 아니라,
tool surface와 backend 조합별로 추적해야 한다.

예:

- `buck`는 graph/layout/routing 지원
- `flyback`는 graph 지원, layout partial
- `preview_circuit()`는 new path 사용 가능
- `SimulationService.create_circuit()`는 legacy-only

따라서 capability matrix는 제품 문서의 부록이 아니라
실행 아키텍처의 일부다.

## 아키텍처 상세

### 1. Intent Layer

역할:

- 자연어 입력 해석
- 값 추출
- 제약 추출
- ambiguity 유지

출력:

- `IntentModel`

### 2. Decision Layer

역할:

- topology 후보 생성
- 후보 점수화
- clarification 필요 여부 판단
- canonical spec 확정

출력:

- `TopologyCandidate[]`
- `CanonicalIntentSpec`

### 3. Synthesis Layer

역할:

- topology와 spec를 받아 회로 구조를 합성
- sized component와 net을 graph로 구성

출력:

- `CircuitGraph`

### 4. Layout Layer

역할:

- graph를 schematic geometry로 변환
- component position, direction, symbol variant 결정

출력:

- `SchematicLayout`

### 5. Routing Layer

역할:

- layout를 기반으로 readable wire geometry 생성
- trunk/branch, rail, region-aware routing 수행

출력:

- `WireRouting`

### 6. Validation Layer

역할:

- 구조 검증
- 설계 제약 검증
- renderability 검증
- routing 품질 검증

### 7. Emission Layer

역할:

- SVG preview 생성
- PSIM bridge로 실제 회로 생성

중요:

이 계층은 추론하지 않고 소비만 해야 한다.

즉 emission layer는
`draw_line`, `draw_circle` 수준의 자유 조합기가 아니라,
이미 확정된 canonical payload를 반영하는 backend여야 한다.

## 핵심 데이터 모델

## 1. IntentModel

자연어에서 추출한 사용자의 요구와 제약.

## 2. CanonicalIntentSpec

topology 결정과 필수 값이 정리된 합성 입력.

## 3. CircuitGraph

회로의 전기적 구조를 표현하는 canonical intermediate.

포함 항목:

- GraphComponent
- GraphNet
- FunctionalBlock
- DesignDecisionTrace

## 4. SchematicLayout

component geometry와 region 배치를 표현하는 intermediate.

## 5. WireRouting

wire_segments와 junction을 표현하는 geometry intermediate.

## 6. EmissionPayload

SVG renderer와 PSIM bridge가 소비하는 최종 전달 모델.

## 구조적으로 추가되어야 할 사항

이 부분은 기존 ver5 문서에 흩어져 있었지만,
최상위 아키텍처 기준으로는 명시가 필요하다.

### 1. Canonical Model Versioning

필요성:

- graph/layout/routing 모델이 진화할 때 호환성 관리가 필요하다
- preview store와 bridge payload에도 버전이 필요하다

권장:

- `schema_version`
- `graph_version`
- `layout_version`
- `routing_version`

을 canonical payload에 포함

### 2. Symbol Registry

필요성:

- multi-pin component
- orientation별 symbol variant
- pin anchor policy

를 renderer 내부 hardcoding이 아니라 registry로 관리해야 한다.

포함 항목:

- symbol_variant id
- supported component types
- bounding box
- pin anchor map
- preferred orientations

### 3. Layout Strategy Registry

필요성:

- topology별 layout rule를 code if-else가 아니라 strategy registry로 관리

포함 항목:

- topology name
- default flow direction
- region template
- rail policy
- preferred block ordering

### 4. Routing Policy Registry

필요성:

- topology마다 routing 특성이 다르다

예:

- buck는 ground rail 중심
- flyback는 isolation boundary 중심
- llc는 resonant trunk 중심

따라서 topology별 routing policy registry가 필요하다.

### 5. Design Traceability

필요성:

- 왜 특정 topology가 선택됐는지
- 왜 특정 default가 들어갔는지
- 왜 특정 layout/routing이 나왔는지

사용자와 개발자가 모두 추적할 수 있어야 한다.

필수 trace source:

- user
- extractor
- ranker
- default
- topology rule
- layout strategy
- routing strategy

### 6. Quality Gate Metrics

필요성:

회로도 품질을 주관적으로만 보지 않고 측정해야 한다.

필수 메트릭:

- duplicate segment count
- crossing count
- unconnected pin count
- symbol-pin mismatch count
- orphan component count
- orphan net count
- routing detour length
- topology feasibility issue count

### 7. Mixed-Mode Migration Layer

필요성:

모든 topology를 한 번에 새 구조로 옮기기 어렵다.

따라서 아래 두 경로를 한동안 공존시켜야 한다.

- new path: `Intent -> Graph -> Layout -> Routing`
- legacy path: `generator -> positioned components`

중요:

mixed-mode는 영구 구조가 아니라 migration 장치여야 한다.

### 8. Preview Store Payload Rework

필요성:

현재 preview store는 mostly renderable payload에 가깝다.

앞으로는 적어도 아래를 함께 저장해야 한다.

- canonical spec
- graph
- layout
- routing
- emitted preview metadata

그래야 confirm/create에서 재계산 불일치가 줄어든다.

### 9. Capability Matrix

필요성:

topology별 지원 상태를 명확히 구분해야 한다.

예:

- graph synthesis 지원 여부
- layout strategy 지원 여부
- advanced routing 지원 여부
- bridge emission 검증 여부

이 matrix가 없으면 일부 topology만 새 구조로 옮겨져도 추적이 어렵다.

### 10. Stable Tool Contract

필요성:

- 내부 intent/synthesis/layout 구조가 바뀌어도
  사용자-facing tool contract가 자주 바뀌면 실제 운영이 어렵다

최소 안정 대상:

- `design_circuit()` action 이름
- `continue_design()` session token contract
- `preview_circuit()` preview payload contract
- `confirm_circuit()` confirm path contract

즉 ver5는 아키텍처 refactor이면서도
`runtime contract preservation`을 함께 요구한다.

## 단계별 구현 계획

이 절은 단순 로드맵이 아니라,
실제 개발 시 순서를 고정하기 위한 실행 기준이다.

## Phase 1. Generator 분해

목표:

- generator에서 structure, sizing, layout 결합을 푼다

산출물:

- `synthesize()` 경로
- topology synthesis result
- legacy compatibility adapter

## Phase 2. CircuitGraph 도입

목표:

- graph를 canonical source로 만든다

산출물:

- graph 모델
- graph validator
- graph 기반 service 흐름

## Phase 3. Layout Engine 도입

목표:

- graph로부터 readable component geometry를 만든다

산출물:

- layout engine
- topology별 layout strategy
- renderer geometry 추론 제거

## Phase 4. Advanced Routing 도입

목표:

- readable wire geometry를 합성한다

산출물:

- trunk/branch routing
- rail-aware routing
- region-aware routing
- routing metrics

## Phase 5. Intent Resolution 개선

목표:

- parser shortcut을 intent/candidate/spec 구조로 교체한다

산출물:

- extractor
- ranker
- clarification policy
- spec builder

## 단계별 완료 정의

이 완료 정의는 문서상의 목표가 아니라,
각 phase를 종료해도 되는지 판단하는 개발 기획 기준으로 사용한다.

실제 acceptance, fallback, rollback, PR 단위는
`phase-execution-plan.md`에서 더 구체적으로 관리한다.

### Phase 1 완료

- `buck`이 generator 내부 좌표 하드코딩 없이 synthesize 가능

### Phase 2 완료

- `buck` preview/create가 graph를 canonical source로 사용

### Phase 3 완료

- `buck`, `flyback`, `llc`가 new layout engine으로 layout 생성

### Phase 4 완료

- 같은 topology에서 preview geometry 품질이 눈에 띄게 개선

### Phase 5 완료

- intent resolution이 ranked candidate + clarification 기반으로 동작

## 성공 지표

이 항목은 단순 참고 지표가 아니라,
개발 완료와 구조 전환 성공 여부를 판단하는 검증 지표다.

### 제품 지표

- 사용자의 자연어 요청에서 설계 가능 회로 비율 증가
- preview와 실제 생성 간 불일치 감소
- topology 선택 오류 감소
- 신규 topology 추가 비용 감소

### 기술 지표

- duplicate segment 감소
- crossing count 감소
- graph validation coverage 증가
- layout strategy coverage 증가
- advanced routing coverage 증가
- backend 간 canonical payload mismatch 감소
- tool contract 호환성 회귀 0건

## 범위 밖 항목

현재 문서 기준으로 아래는 1차 범위 밖이다.

- 완전 자유형 아날로그 회로 합성
- PCB 자동 배치/배선
- 폐루프 제어 블록 자동 설계 전부
- 모든 PSIM example을 일반화하는 범용 역합성

즉 범위는 우선 `전력전자 중심 topology 합성`이다.

## 최종 판단

ver5의 본질은 단순히 parser를 고치거나 SVG를 예쁘게 만드는 것이 아니다.

핵심은 다음 구조 전환이다.

> `예제 기반 generator가 회로와 좌표를 한 번에 내는 구조`에서
> `사용자 의도를 canonical spec으로 바꾸고,
> 그 spec으로 circuit graph, layout, routing을 순차 합성하는 구조`로 바꾸는 것

그리고 이 구조는 일반 CAD MCP처럼
`자연어 -> 저수준 draw command`로 가는 구조가 아니라,
`자연어 -> canonical synthesis -> backend emission`으로 가야 한다.

그리고 이 전환이 완료되면 제품은 다음 상태가 된다.

> 자연어 입력을 받지만 내부는 결정적이고 검증 가능한 회로 합성 엔진으로 동작하는 시스템

이것이 ver5의 최종 목표다.
