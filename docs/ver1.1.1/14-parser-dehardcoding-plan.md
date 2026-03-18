# Step 14: Parser De-hardcoding Plan

> 우선순위: P1  
> 목적: `keyword_map.py` 의존도를 낮추고, 자연어를 topology 이름이 아니라 제약조건으로 해석하도록 전환

---

## 1. 문제 정의

현재 parser는 아래 정적 맵에 크게 의존한다.

- `TOPOLOGY_KEYWORDS`
- `USE_CASE_MAP`
- `SLOT_QUESTIONS`

이 구조의 한계:

1. 사전에 없는 표현은 topology를 놓칠 수 있다
2. 표현을 더 많이 넣을수록 사전이 계속 비대해진다
3. 자연어를 “의미”가 아니라 “단어 매칭”으로 해석하게 된다
4. 새로운 도메인 표현이 나올 때마다 코드/데이터를 계속 수정해야 한다

예:

- `"고전압에서 저전압으로 바꿔줘"`
- `"절연된 보조전원 필요"`
- `"태양광 패널에 붙는 승압형 전원"`
- `"벽전원에서 19V 어댑터"`

이런 요청은 topology 이름을 직접 말하지 않아도 의미는 충분히 전달되지만, 현재 구조에서는 keyword hit가 약하면 `NO_MATCH`로 빠질 수 있다.

---

## 2. 목표

parser의 역할을 아래처럼 바꾼다.

### 현재

```text
natural language -> keyword match -> topology guess -> missing fields
```

### 목표

```text
natural language
  -> constraint extraction
  -> capability-based topology ranking
  -> clarification loop
  -> design / preview
```

즉:

- keyword는 topology를 “결정”하는 계층이 아니라
- 후보를 “보조 제안”하는 계층으로 격하한다

---

## 3. 핵심 설계 방향

### 3.1 Topology 이름보다 제약조건을 먼저 뽑기

자연어에서 우선 추출해야 하는 것은 topology명이 아니라 아래 속성이다.

- 입력 도메인: `ac`, `dc`, `battery`, `pv`
- 출력 도메인: `ac`, `dc`
- 절연 여부: `isolated`, `non_isolated`, `unknown`
- 변환 목표: `step_down`, `step_up`, `step_up_down`, `rectification`, `inversion`
- 용도: `power_supply`, `charger`, `drive`, `pfc`, `renewable`
- 방향성: `unidirectional`, `bidirectional`
- 주요 수치: `vin`, `vout_target`, `iout`, `power_rating`, `voc`, `isc`

예:

```json
{
  "input_domain": "dc",
  "output_domain": "dc",
  "isolation": true,
  "conversion_goal": "step_down",
  "use_case": "power_supply",
  "specs": {
    "vout_target": 5.0
  }
}
```

---

## 4. Topology Metadata 확장

`topology_metadata.py`에 현재 있는:

- `isolated`
- `conversion_type`
- `single_voltage_role`

외에 아래 capability 필드를 추가한다.

### 4.1 권장 신규 필드

- `input_domain`
- `output_domain`
- `supports_step_down`
- `supports_step_up`
- `supports_bidirectional`
- `typical_use_cases`
- `power_range`
- `requires_transformer`
- `preferred_for_low_power`
- `preferred_for_high_power`

예:

```python
"flyback": {
    "input_domain": "dc",
    "output_domain": "dc",
    "isolated": True,
    "supports_step_down": True,
    "supports_step_up": True,
    "supports_bidirectional": False,
    "typical_use_cases": ["adapter", "auxiliary_supply", "charger"],
    "preferred_for_low_power": True,
    "requires_transformer": True,
}
```

이렇게 되면 parser는 keyword 없이도 의미 기반으로 후보를 추천할 수 있다.

---

## 5. Candidate Ranking 계층 추가

새 함수 예시:

```python
rank_topology_candidates(constraints: dict, specs: dict) -> list[str]
```

동작 원리:

1. metadata 전체를 순회
2. constraint와 맞지 않는 topology 제거
3. 맞는 topology에 점수 부여
4. score 기준으로 정렬

### 5.1 점수 예시

- input/output domain 일치: `+3`
- isolation 일치: `+3`
- conversion goal 일치: `+3`
- use case 일치: `+2`
- 수치 조건과 잘 맞는 power range: `+1`
- keyword hit: `+1` 보조 가점만 부여

즉 keyword는 ranking의 일부가 될 수는 있어도 주결정 요인이 아니게 한다.

---

## 6. Parser 2단계 구조

### Stage 1: Constraint Extraction

입력 문장에서 아래를 뽑는다.

- 전압/전류/전력
- AC/DC/PV/배터리
- 절연 여부
- 승압/강압/양방향
- 용도

### Stage 2: Topology Ranking

Stage 1 결과를 기반으로 metadata에서 topology 후보를 고른다.

### Stage 3: Clarification

후보가 애매하면:

- `NO_MATCH` 대신
- 후보 몇 개 + 필요한 질문
- 형태로 응답한다

---

## 7. UX 변경 원칙

### 현재의 문제

`NO_MATCH`는 사용자 입장에서 “못 알아들었다”는 인상만 주고 다음 행동을 안내하지 못한다.

### 목표 응답

예:

```text
절연형 DC-DC step-down 전원으로 해석했습니다.
가능한 후보:
- flyback
- forward
- llc

더 정확한 추천을 위해 아래 정보가 필요합니다:
- 입력 전압
- 출력 전류 또는 전력
```

즉:

- 실패보다 clarification 우선
- topology guess보다 candidate ranking 우선
- 질문을 통해 설계 가능한 상태로 유도

---

## 8. Keyword Map의 최종 역할

`keyword_map.py`는 제거 대상이 아니라 역할 축소 대상이다.

남겨둘 역할:

- 흔한 표현에 대한 빠른 후보 제안
- UI 메시지용 fallback 질문
- low-cost first-pass hint

빼야 할 역할:

- 최종 topology 결정
- 도메인 의미 해석의 핵심 계층
- priority override의 중심 로직

즉:

```text
keyword map = hint layer
metadata + ranking = decision layer
```

---

## 9. Template / Spec Fallback 축소

현재 parser 문제가 keyword map에만 있는 것은 아니다.

아직 아래 fallback 자산도 남아 있다.

- `_TEMPLATES`
- `_SPEC_MAP`
- `_apply_specs`

현재 구조에서는 parser가 topology를 대충 맞추기만 해도:

1. template를 가져오고
2. `_SPEC_MAP`으로 몇 개 값만 치환하고
3. 나머지는 기본값으로 유지한 채 preview를 만들 수 있다

이 구조의 문제:

- 사용자는 “의도에 맞는 설계”라고 느끼지만
- 실제로는 “정적 template + 일부 파라미터 치환”일 수 있다

즉 parser de-hardcoding은 keyword map만 줄이는 것으로 끝나지 않고,
template/spec fallback을 **주경로에서 보조 경로로 내리는 것**까지 포함해야 한다.

### 9.1 목표 상태

```text
LLM / parser / ranking -> constraints + topology candidates
                         -> design-ready 확인
                         -> generator or explicit design
                         -> preview

template fallback -> only when user explicitly accepts fallback
```

### 9.2 원칙

1. `_TEMPLATES`는 데모/샘플/빠른 시작용으로 유지 가능
2. `_SPEC_MAP`은 단순 convenience layer로만 유지
3. design-ready 정보가 부족하면 template fallback 자동 실행 금지
4. fallback 실행 시 반드시 응답에 명시
   - 예: `generation_mode=template_fallback`
   - 예: `generation_note=기본 template 기반`

### 9.3 구현 방향

- `design_circuit`:
  - design-ready가 아니면 질문
  - template fallback 자동 생성 금지
- `continue_design`:
  - 추가 정보가 design-ready 조건을 만족할 때만 template fallback 허용
- `preview_circuit`:
  - 사용자가 명시적으로 `circuit_type='buck'` 같은 template 호출을 한 경우만 허용

### 9.4 장기 방향

최종적으로는:

- template fallback은 명시적 user choice
- generator는 fast-path
- explicit component/net design은 primary path

이렇게 역할이 분리되어야 한다.

---

## 10. 구현 순서

### Phase 1

- `topology_metadata.py` capability 필드 추가
- topology별 `input_domain`, `output_domain`, `supports_step_*` 정리

### Phase 2

- `intent_parser.py`에 constraint extraction 함수 추가
- `isolated`, `step_up/down`, `domain`, `use_case` 추출 로직 정리

### Phase 3

- `rank_topology_candidates()` 추가
- keyword hit 없이도 후보 추천 가능하게 변경

### Phase 4

- `design_circuit`에서 `NO_MATCH` 분기 축소
- `need_clarification` / `suggest_candidates` 분기 강화

### Phase 5

- parser regression test 확대
- “keyword 없는 표현” 케이스를 회귀 테스트로 고정

---

## 11. 테스트 케이스

아래 요청은 keyword match가 약해도 정상 처리되어야 한다.

1. `"고전압에서 저전압으로 바꿔줘"`
2. `"절연형 5V 보조전원"`
3. `"벽전원에서 19V 어댑터"`
4. `"태양광 패널용 승압 회로"`
5. `"배터리 충방전 양방향 컨버터"`

기대 결과:

- 최소 1개 이상 유효 topology candidate 제시
- 필요한 질문 생성
- 바로 잘못된 template 생성 금지

---

## 12. 완료 기준

- [x] keyword 없이도 constraint 기반 후보 추천 가능 (rank_topology_candidates)
- [x] `NO_MATCH` 빈도 감소 (constraint fallback으로 7개 케이스 모두 후보 제시)
- [x] `suggest_candidates` / `need_clarification` 응답 증가
- [x] keyword map이 최종 판정 계층에서 제외됨 (hint layer로 격하)
- [x] template/spec fallback이 자동 주경로가 아니라 명시적 보조 경로로 내려감 (design_ready_fields 체크)
- [x] “고전압에서 저전압”, “보조전원”, “벽전원 어댑터” 류 회귀 테스트 추가 (20개 테스트)
- [x] topology_metadata에 capability 필드 추가 (input/output_domain, step_up/down, bidirectional, use_cases, power_range)
- [x] _extract_constraints() 함수 추가 (도메인 개념 추출, topology 이름 무참조)
