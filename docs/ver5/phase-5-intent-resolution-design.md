# Phase 5 상세: Intent Resolution 설계 문서
작성일: 2026-03-24

## 목적

Phase 5의 목표는 현재의 `parser shortcut` 중심 흐름을
`intent extraction -> candidate ranking -> clarification -> canonical spec construction`
구조로 바꾸는 것이다.

현재 자연어 해석 관련 핵심 파일은 다음이다.

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/data/topology_metadata.py`

이 문서는 이 계층을 `사용자 의도 기반 합성기`에 맞게 재설계하기 위한 상세 방안을 정의한다.

## 왜 이 단계가 마지막인가

자연어 해석을 먼저 고도화해도,
내부 synthesis 모델이 약하면 결국 결과는 다시 fixed generator path로 수렴한다.

따라서 순서는 다음이 맞다.

1. Phase 1: generator 분해
2. Phase 2: graph 도입
3. Phase 3: layout 분리
4. Phase 4: routing 분리
5. Phase 5: intent resolution 고도화

즉 Phase 5는 parser 개선이 아니라,
앞단 내부 모델이 준비된 뒤에 그 모델로 안전하게 연결하는 단계다.

## 현재 코드 기준 문제점

## 1. keyword map이 후보 생성기보다 확정기에 가깝다

`keyword_map.py`는 원래 fallback layer라고 적혀 있지만,
실제론 topology 선택에 큰 영향을 준다.

문제:

- 특정 단어가 보이면 너무 빨리 topology가 좁혀짐
- use-case와 topology가 거의 1:1로 매핑되는 구간이 있음
- ambiguity를 점수 형태로 유지하지 못함

## 2. `intent_parser.py`가 parsing과 decision을 동시에 수행한다

문제:

- constraint extraction
- topology keyword matching
- use-case matching
- voltage role heuristic
- missing-field 판단

이 한 파일에 과도하게 섞여 있다.

## 3. voltage role mapping이 heuristic에 과하게 의존한다

현재는:

- `vin`, `input`, `source`, `bus`
- `output`, `target`

같은 주변 문맥을 보고 role을 정한다.

문제:

- 실제 사용자 문장은 더 복잡하다
- battery, dc bus, rectified output, auxiliary rail 등은 문맥이 겹친다
- 다전압 시스템에 취약하다

## 4. clarification policy가 구조화돼 있지 않다

현재는 부족한 필드를 묻는 흐름은 있지만,
언제 질문해야 하고 언제 defaulting 해야 하는지가 별도 정책 계층으로 정리돼 있지 않다.

## 5. service 응답 계약이 parser 개편 범위에 명시돼 있지 않다

현재 `CircuitDesignService.design_circuit()`는 단순 parsed dict를 넘기는 것이 아니라,
아래 사용자-facing action contract를 이미 제공한다.

- `confirm_intent`
- `need_specs`
- `suggest_candidates`
- `design_session_token`

Phase 5에서 내부 intent pipeline을 바꿔도,
이 응답 shape를 보존하거나 versioning하는 규칙이 없다면 외부 도구 연동이 깨질 수 있다.

## 목표 구조

Phase 5 이후 흐름은 아래와 같아야 한다.

```text
user text
  -> intent extraction
  -> candidate generation
  -> topology ranking
  -> missing-field analysis
  -> clarification policy
  -> canonical spec builder
  -> synthesis pipeline
```

이때 중요한 점은:

- extraction
- ranking
- questioning
- spec building

이 네 책임이 서로 분리돼야 한다는 것이다.

## 제안 모델

### 1. IntentModel

```python
from dataclasses import dataclass, field

@dataclass
class IntentModel:
    input_domain: str | None = None
    output_domain: str | None = None
    conversion_goal: str | None = None
    use_case: str | None = None
    isolation: bool | None = None
    bidirectional: bool | None = None
    values: dict[str, float] = field(default_factory=dict)
    constraints: dict[str, object] = field(default_factory=dict)
    raw_text: str = ""
```

### 2. TopologyCandidate

```python
@dataclass
class TopologyCandidate:
    topology: str
    score: float
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
```

### 3. ClarificationNeed

```python
@dataclass
class ClarificationNeed:
    kind: str
    field: str | None = None
    message: str | None = None
    priority: str = "normal"
```

### 4. CanonicalIntentSpec

```python
@dataclass
class CanonicalIntentSpec:
    topology: str
    requirements: dict[str, object]
    inferred_values: dict[str, object] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    decision_trace: list[dict[str, object]] = field(default_factory=list)
```

### 5. DesignResolutionResult

```python
@dataclass
class DesignResolutionResult:
    action: str
    selected_topology: str | None = None
    candidates: list[TopologyCandidate] = field(default_factory=list)
    canonical_spec: CanonicalIntentSpec | None = None
    missing_fields: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    design_session_payload: dict[str, object] | None = None
```

이 모델은 내부 모델이다.
외부 응답은 기존 action contract와의 호환 계층을 한 번 더 거쳐야 한다.

## 파일 구조 제안

### 신설

- `src/psim_mcp/intent/models.py`
- `src/psim_mcp/intent/extractors.py`
- `src/psim_mcp/intent/ranker.py`
- `src/psim_mcp/intent/clarification.py`
- `src/psim_mcp/intent/spec_builder.py`
- `src/psim_mcp/intent/__init__.py`

### 수정

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/data/topology_metadata.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/shared/state_store.py`

## 책임 재배치

## A. `keyword_map.py`

앞으로의 역할:

- candidate generation용 keyword registry

더 이상 하면 안 되는 역할:

- 최종 topology 확정
- 강한 우선순위 결정

즉 `TOPOLOGY_KEYWORDS`와 `USE_CASE_MAP`는 남아도 되지만,
결정 권한은 `ranker`로 옮겨야 한다.

## B. `intent_parser.py`

앞으로의 역할:

- `IntentModel` 추출
- 숫자/단위/문맥 기반 값 후보 추출

더 이상 하면 안 되는 역할:

- 최종 topology 결정
- use-case shortcut 확정

## C. `topology_metadata.py`

확장되어야 할 항목:

- domain compatibility
- isolation compatibility
- power suitability
- typical use cases
- ambiguity hints
- clarification priority fields

즉 단순 field metadata가 아니라 ranking metadata가 필요하다.

## ranking 설계

### 점수 요소 예시

```text
score =
  domain_match +
  isolation_match +
  conversion_goal_match +
  use_case_match +
  power_range_match +
  bidirectional_match -
  conflict_penalty -
  unsupported_constraint_penalty
```

### 예시

사용자 입력:

`400V DC bus에서 48V 절연 전원 만들고 싶어`

후보:

- `flyback`
  - isolated match
  - dc-dc match
  - medium power unknown
- `forward`
  - isolated match
  - dc-dc match
- `llc`
  - isolated match
  - dc-dc match
  - if power high, score boost

즉 이 단계에선 "하나만 답"이 아니라 ranked list가 맞다.

## clarification policy 설계

질문을 언제 던질지 명확한 정책이 필요하다.

## 질문이 필요한 경우

- 상위 후보 두 개 점수 차가 작음
- power, isolation, output voltage 중 핵심 필드가 빠짐
- topology feasibility가 크게 달라지는 값이 누락됨
- 단일 전압만 주어져 `vin/vout` 역할이 불명확함
- 충전기/어댑터/전원공급기처럼 topology가 여러 개 가능한 use-case

## 질문 없이 진행 가능한 경우

- topology가 명시됨
- 필수 design-ready field가 충분함
- topology 간 점수 차가 큼
- 나머지는 safe default로 보완 가능함

## clarification 인터페이스 초안

```python
def analyze_clarification_needs(
    intent: IntentModel,
    candidates: list[TopologyCandidate],
) -> list[ClarificationNeed]:
    ...
```

## voltage role resolution 설계

현재 가장 취약한 부분 중 하나다.

개선 방향:

### 1. 단순 window heuristic 유지하되 분리

현재 `_VIN_CONTEXT`, `_VOUT_CONTEXT`는 완전히 버릴 필요는 없지만,
이건 `extractor subroutine`이어야 한다.

### 2. single-voltage policy 명시

topology metadata에 이미 `single_voltage_role`이 있다.
이걸 ranking 결과와 결합해 최종 결정에 사용한다.

### 3. multi-rail 대응

향후를 위해 field를 단일 `vin`, `vout_target`만 보지 말고,
아래와 같은 intermediate 표현을 고려한다.

```python
{
    "voltage_candidates": [
        {"value": 400, "role_hint": "input_bus"},
        {"value": 48, "role_hint": "output_target"},
    ]
}
```

이 intermediate를 `spec_builder`가 최종 canonical field로 변환한다.

## spec builder 설계

이 계층은 extraction 결과와 topology decision을 받아
generator/synthesis가 사용할 canonical spec을 만든다.

### 입력

- `IntentModel`
- 선택된 `TopologyCandidate`
- clarification answers 또는 defaults
- topology metadata

### 출력

- `CanonicalIntentSpec`

### spec builder가 해야 하는 것

- alias 정리
- topology-specific required field 채우기
- default 값 삽입
- inference value와 user-provided value 구분
- decision trace 기록

## decision trace 설계

사용자가 나중에 물을 수 있는 질문:

- 왜 buck가 아니라 flyback이 선택됐나
- 왜 vin으로 400V를 잡았나
- 왜 fsw를 100kHz default로 넣었나

이 답을 시스템이 하려면 decision trace가 필요하다.

예:

```python
[
  {"source": "user", "field": "input_voltage_v", "value": 400},
  {"source": "extractor", "field": "isolation", "value": True, "confidence": 0.91},
  {"source": "ranker", "field": "selected_topology", "value": "flyback"},
  {"source": "default", "field": "fsw", "value": 100000},
]
```

## `circuit_design_service.py` 변경 초안

현재 service는 parser에서 거의 topology-ready 결과를 받는 편이다.

Phase 5 이후 service 흐름:

```python
intent = extract_intent(user_text)
candidates = rank_topologies(intent)
clarifications = analyze_clarification_needs(intent, candidates)
spec = build_canonical_spec(intent, candidates[0], clarifications_resolved)
graph = synthesize_from_spec(spec)
```

중요:

- service는 더 이상 parser shortcut 결과에 직접 의존하지 않음
- intent/candidate/spec를 명시적으로 거침

## 서비스 응답 호환 규칙

Phase 5에서 보존해야 할 외부 계약은 아래와 같다.

### 유지 대상 action

- `confirm_intent`
- `need_specs`
- `suggest_candidates`

### 유지 대상 필드

- `topology`
- `topology_candidates`
- `specs`
- `missing_fields`
- `questions`
- `confidence`
- `design_session_token`

### 허용되는 변경

- 내부적으로 `IntentModel`, `TopologyCandidate`, `CanonicalIntentSpec` 사용
- 응답 data에 `decision_trace`, `candidate_scores`, `resolution_version` 같은 새 필드 추가

### 허용되지 않는 변경

- action 이름 변경
- `design_session_token` 제거
- ambiguity 응답을 기존 action 없이 임의 포맷으로 바꾸는 것

즉 Phase 5는 parser 교체이지만,
동시에 `service compatibility adapter`를 반드시 포함해야 한다.

## design session payload versioning

현재 세션 저장은 단순 dict 저장에 가깝다.
Phase 5 이후에는 최소한 아래 필드를 고정하는 것이 좋다.

```python
{
    "payload_kind": "design_session",
    "payload_version": "v2",
    "selected_topology": "flyback",
    "candidate_topologies": [...],
    "specs": {...},
    "missing_fields": [...],
    "clarification_state": {...},
}
```

주의:

- `continue_design()`는 기존 `design_session_v1`도 읽을 수 있어야 한다
- phase 전환 동안 `v1 -> v2` 상향 변환 shim이 필요할 수 있다

## migration 전략

### Step 1. extractor와 ranker를 별도 도입

- 기존 parser API는 유지
- 내부에서 새 모듈 사용 시작
- `parse_circuit_intent()`는 compatibility wrapper로 남김

### Step 2. keyword_map을 candidate source로 격하

- final decision 제거

### Step 3. clarification policy를 service에 연결

- ambiguity 시 질문 또는 ranked suggestion
- 기존 action contract 유지

### Step 4. canonical spec builder 정식 도입

- `design_session_v1/v2` 호환 저장
- `continue_design()` 경로를 새 spec builder와 연결

## 완료 기준

- `design_circuit()`가 ranked topology candidate를 내부적으로 사용
- ambiguity가 질문 또는 명시적 ranked result로 표현됨
- `vin/vout` 결정이 extractor/ranker/spec builder를 거친 구조로 바뀜
- canonical spec에 trace가 남음
- 기존 action 이름과 `design_session_token` 계약이 유지됨
- `continue_design()`가 `design_session_v1` 또는 `v2`를 안정적으로 처리함

## 테스트 전략

### 단위 테스트

- `tests/unit/test_intent_models.py`
- `tests/unit/test_intent_extractor.py`
- `tests/unit/test_topology_ranker.py`
- `tests/unit/test_clarification_policy.py`
- `tests/unit/test_spec_builder.py`
- `tests/unit/test_design_session_payload.py`

### 시나리오 테스트

- `adapter 48V 5A`
- `400V DC bus to isolated 24V`
- `battery charger`
- `bidirectional 400V to 48V`
- `motor inverter`
- `confirm_intent` 응답 shape 유지
- `need_specs` 응답 shape 유지
- `suggest_candidates` 응답 shape 유지

## 최종 정리

Phase 5의 핵심은 parser를 더 복잡하게 만드는 것이 아니다.

핵심은 이 전환이다.

> `키워드가 보이면 topology를 바로 찍는 shortcut 구조`에서
> `사용자 의도를 추출하고, 후보를 평가하고, 부족한 정보를 식별한 뒤,
> canonical spec으로 합성 파이프라인에 넘기는 구조`로 바꾸는 것

이 단계가 완성돼야 비로소 `자연어 기반 회로 합성기`라는 표현이 구조적으로 맞아진다.
