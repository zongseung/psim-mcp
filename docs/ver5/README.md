# ver5 문서 인덱스
작성일: 2026-03-24

이 폴더는 `사용자 의도 기반 회로 합성기` 전환을 위한
`개발 기획서 + 아키텍처 설계 패키지` 문서 세트다.

즉 이 폴더의 문서들은 단순 아이디어 메모가 아니라 아래 목적을 함께 가진다.

- 무엇을 만들지 정의하는 상위 제품/기술 기획
- 어떤 구조로 만들지 정의하는 아키텍처 설계
- 어떤 단계와 산출물로 옮길지 정의하는 실행 로드맵
- 실제 코드 리팩터링 시 ownership과 책임 경계를 고정하는 기준 문서

추가로 이 문서 세트는 다음 질문에도 답하도록 강화됐다.

- 왜 일반 CAD MCP처럼 저수준 drawing API 중심으로 가면 안 되는가
- 왜 `intent -> spec -> graph -> layout -> routing -> emission` 구조가 필요한가
- backend abstraction과 capability matrix를 왜 문서 상위 개념으로 봐야 하는가

즉 ver5는 단순 설계 패키지가 아니라,
`회로 합성 엔진 + 실행 아키텍처` 패키지로 읽어야 한다.

## 포함 문서

- `natural-language-hardcoding-review.md`
  - 자연어 기반 회로 구성에서 어떤 하드코딩이 맞고 어떤 하드코딩이 과한지 검토

- `psim-tutorial-reference-dependency-review.md`
  - 현재 코드가 PSIM 튜토리얼/예제 코드에 얼마나 의존하는지 검토

- `user-intent-vs-example-pattern-circuit-synthesis-review.md`
  - 현재 구조가 왜 사용자 의도 기반 합성기보다 예제 패턴 재구성기에 가까운지 분석

- `user-intent-driven-circuit-synthesis-plan.md`
  - 사용자 의도 기반 합성기로 전환하기 위한 목표 아키텍처와 단계별 계획

- `phase-1-file-impact-and-interface-draft.md`
  - Phase 1에서 실제 손댈 파일 목록과 인터페이스 초안

- `phase-2-circuit-graph-design.md`
  - CircuitGraph를 canonical intermediate로 도입하기 위한 Phase 2 상세 설계

- `phase-3-to-5-detailed-roadmap.md`
  - Layout Engine, Advanced Routing, Intent Resolution에 대한 Phase 3~5 상세 로드맵

- `phase-3-layout-engine-design.md`
  - Layout Engine의 모델, 전략, 파일 경계, migration 계획에 대한 상세 설계

- `phase-4-advanced-routing-design.md`
  - trunk/branch, rail-aware, region-aware routing으로 가기 위한 상세 설계

- `phase-5-intent-resolution-design.md`
  - intent extraction, candidate ranking, clarification, spec builder 구조의 상세 설계

- `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
  - ver5 전체 방향을 최종 목표, PRD, 아키텍처, 실행 아키텍처, 추가 구조 과제까지 통합한 최상위 기준 문서

- `circuit-metadata-schema.md`
  - 회로를 합성하기 위해 참고해야 하는 기본정보를 topology/component/graph/layout/routing/bridge 기준으로 정리한 스키마 문서

- `metadata-to-code-ownership-map.md`
  - 회로 기본정보 메타데이터를 실제 코드 파일과 어떻게 매핑하고 분리해야 하는지 정리한 ownership 문서

- `phase-execution-plan.md`
  - Phase 1~5의 acceptance, fallback, rollback, PR 단위를 정리한 실행형 개발 계획 문서

## 핵심적으로 먼저 봐야 하는 문서

처음 들어온 사람이 가장 먼저 봐야 하는 문서는 아래 4개다.

1. `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
- 이 폴더의 최상위 기준 문서다.
- 최종 목표, 제품 정의, 아키텍처, 실행 계층, 단계별 방향을 한 번에 본다.
- 전체 문서군 중 가장 먼저 기준선으로 잡아야 하는 문서다.

2. `phase-execution-plan.md`
- 실제 개발 착수 기준 문서다.
- phase별 acceptance, fallback, rollback, PR 단위가 있다.
- payload contract, feature flag, capability matrix 같은 실행 기준도 함께 본다.
- 구현 순서와 병합 기준을 보려면 이 문서를 바로 봐야 한다.

3. `circuit-metadata-schema.md`
- 회로를 합성할 때 참고해야 하는 기본정보가 무엇인지 정의한 문서다.
- 구조화된 메타데이터가 무엇인지 이해하려면 이 문서를 봐야 한다.

4. `metadata-to-code-ownership-map.md`
- 메타데이터가 실제 코드 어디에 있어야 하는지 정리한 문서다.
- 리팩터링과 ownership 분리를 시작할 때 핵심 기준이 된다.

## 문서 성격별 구분

### 1. 상위 기준 문서

- `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
- `phase-execution-plan.md`

이 두 문서는 가장 핵심적으로 봐야 하는 문서다.
하나는 방향과 구조를 정의하고, 다른 하나는 실제 실행 기준을 정의한다.
특히 전자는 `왜 이 프로젝트가 일반 CAD 자동화 MCP와 다른지`,
후자는 `그 차이를 구현할 때 어떤 계약을 지켜야 하는지`를 설명한다.

### 2. 문제 정의 / 배경 분석 문서

- `psim-tutorial-reference-dependency-review.md`
- `user-intent-vs-example-pattern-circuit-synthesis-review.md`
- `natural-language-hardcoding-review.md`

이 문서들은 왜 지금 구조를 바꿔야 하는지 설명하는 배경 문서다.

### 3. 아키텍처 설계 문서

- `user-intent-driven-circuit-synthesis-plan.md`
- `phase-1-file-impact-and-interface-draft.md`
- `phase-2-circuit-graph-design.md`
- `phase-3-layout-engine-design.md`
- `phase-4-advanced-routing-design.md`
- `phase-5-intent-resolution-design.md`
- `phase-3-to-5-detailed-roadmap.md`

이 문서들은 각 계층과 phase의 구조 설계를 담고 있다.

### 4. 메타데이터 / ownership 기준 문서

- `circuit-metadata-schema.md`
- `metadata-to-code-ownership-map.md`

이 문서들은 회로 기본정보를 어떤 형태로 저장하고,
코드 어디가 owner가 되어야 하는지 정리한 기준 문서다.

## 문서별 핵심도

### 반드시 봐야 하는 문서

- `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
- `phase-execution-plan.md`
- `circuit-metadata-schema.md`
- `metadata-to-code-ownership-map.md`

### 구조 이해를 위해 강하게 권장되는 문서

- `phase-1-file-impact-and-interface-draft.md`
- `phase-2-circuit-graph-design.md`
- `phase-3-layout-engine-design.md`
- `phase-4-advanced-routing-design.md`
- `phase-5-intent-resolution-design.md`

### 배경 이해용 문서

- `psim-tutorial-reference-dependency-review.md`
- `user-intent-vs-example-pattern-circuit-synthesis-review.md`
- `natural-language-hardcoding-review.md`

## 목적별 읽기 순서

### 1. 전체 방향만 빨리 파악하고 싶을 때

1. `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
2. `phase-execution-plan.md`

### 2. 실제 개발 착수를 준비할 때

1. `phase-execution-plan.md`
2. `phase-1-file-impact-and-interface-draft.md`
3. `phase-2-circuit-graph-design.md`
4. `metadata-to-code-ownership-map.md`

### 3. 왜 구조를 바꾸는지 배경부터 이해하고 싶을 때

1. `psim-tutorial-reference-dependency-review.md`
2. `user-intent-vs-example-pattern-circuit-synthesis-review.md`
3. `prd-and-architecture-user-intent-driven-circuit-synthesis.md`

### 4. 메타데이터 체계부터 보고 싶을 때

1. `circuit-metadata-schema.md`
2. `metadata-to-code-ownership-map.md`
3. `phase-2-circuit-graph-design.md`
4. `phase-3-layout-engine-design.md`

## 패키지 성격

이 문서 세트는 성격상 아래 둘을 함께 가진다.

- 개발 기획서
  - 최종 목표, 범위, 단계, 산출물, migration 방향을 정의
- 아키텍처 설계 패키지
  - canonical model, 계층 분리, registry ownership, 인터페이스 초안, backend abstraction을 정의

추가로 다음 성격도 가진다.

- 실행 아키텍처 기준 문서
  - tool surface
  - payload contract
  - capability matrix
  - mixed-mode migration
  - backend boundary

즉 이 문서들은 내부 합성 로직만 설명하지 않고,
실제 서비스가 어떤 표면과 계약으로 운영돼야 하는지도 함께 정의한다.

따라서 `ver5`는 한 장짜리 PRD가 아니라,
실행 가능한 리팩터링과 구조 전환을 뒷받침하는 설계 패키지로 보는 것이 맞다.

## 권장 읽기 순서

1. `prd-and-architecture-user-intent-driven-circuit-synthesis.md`
2. `phase-execution-plan.md`
3. `psim-tutorial-reference-dependency-review.md`
4. `user-intent-vs-example-pattern-circuit-synthesis-review.md`
5. `circuit-metadata-schema.md`
6. `metadata-to-code-ownership-map.md`
7. `phase-1-file-impact-and-interface-draft.md`
8. `phase-2-circuit-graph-design.md`
9. `phase-3-to-5-detailed-roadmap.md`
10. `phase-3-layout-engine-design.md`
11. `phase-4-advanced-routing-design.md`
12. `phase-5-intent-resolution-design.md`
13. `user-intent-driven-circuit-synthesis-plan.md`

## 비고

기존 `docs/ver2`에 있던 관련 문서 중,
사용자 의도 기반 합성기 전환 논의에 직접 연결되는 문서만 이 폴더로 이동했다.
