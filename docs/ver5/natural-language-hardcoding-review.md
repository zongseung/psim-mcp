# 자연어 기반 회로 구성에서 하드코딩이 맞는지에 대한 검토

작성일: 2026-03-24

## 질문

`psim-mcp`처럼 자연어로 회로를 구성하는 시스템에서 하드코딩이 들어가는 것이 맞는가?

결론부터 말하면:

- `저수준 규약`과 `도메인 ontology`에 대한 하드코딩은 필요하다.
- `사용자 표현 해석`과 `토폴로지 추천/선택`을 하드코딩에 과도하게 의존하는 것은 맞지 않다.
- 현재 코드는 이 둘이 섞여 있고, 특히 parser/shortcut 계층은 하드코딩 의존도가 높은 편이다.

## 현재 구조를 먼저 정리

현재 자연어 진입 경로는 두 층으로 나뉜다.

1. `LLM 직접 설계 경로`
- `get_component_library() + preview_circuit()`를 사용해 부품/연결을 직접 구성하는 경로
- `src/psim_mcp/parsers/keyword_map.py` 상단 주석에도 이 경로가 primary라고 적혀 있다.

2. `편의용 parser/shortcut 경로`
- `design_circuit()`가 입력 문장에서 topology와 spec을 빠르게 추론하는 경로
- 이 경로는 `keyword_map.py`, `intent_parser.py`, `topology_metadata.py`의 규칙에 강하게 의존한다.

즉, 지금 시스템은 “완전 자유 자연어를 모두 하드코딩으로 해석하는 구조”는 아니다.
하지만 사용자가 `design_circuit()`류 shortcut을 많이 쓸수록 하드코딩의 한계가 바로 드러나는 구조다.

## 하드코딩이 맞는 부분

아래는 자연어 시스템에서도 하드코딩이 정당한 영역이다.

### 1. 회로 도메인의 canonical vocabulary

예:

- topology의 canonical name
- 필드명 alias
- component pin alias
- PSIM element type mapping

관련 파일:

- `src/psim_mcp/data/topology_metadata.py`
- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/data/component_library.py`
- `src/psim_mcp/bridge/bridge_script.py`

이건 하드코딩이라기보다 `제품이 알아야 하는 고정 지식`에 가깝다.
예를 들어 `buck`, `boost`, `flyback` 같은 topology 명칭이나 `vin`, `vout_target` 같은 canonical field는 시스템이 반드시 고정된 내부 언어를 가져야 한다.

이 계층은 오히려 너무 동적으로 만들면 시스템 전체가 불안정해진다.

### 2. 단위/핀/배선/브리지 규약

예:

- 전압/전류/주파수 단위 파싱
- component pin 이름 매핑
- PSIM bridge parameter map
- wire segment schema

이건 자연어 문제가 아니라 `실행 엔진 계약` 문제다.
이 부분은 하드코딩이 아니라 `명세 구현`으로 보는 게 맞다.

### 3. topology-specific design constraints

예:

- buck은 보통 step-down
- LLC는 isolated resonant converter
- half-bridge는 DC-AC 계열

이런 제약은 LLM이 그때그때 추론하게 두기보다 metadata로 고정하는 쪽이 안정적이다.
따라서 `topology_metadata.py` 자체가 존재하는 방향은 맞다.

## 하드코딩이 과한 부분

문제는 아래 영역이다.

### 1. topology 인식을 keyword list에 너무 많이 의존함

관련 파일:

- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/parsers/intent_parser.py`

현재 `TOPOLOGY_KEYWORDS`, `USE_CASE_MAP`, `PRIORITY_OVERRIDES`는 사실상 고정 규칙 기반 router다.

이 방식은 다음 문제가 있다.

- 새로운 표현이 들어오면 코드 수정이 필요하다.
- 한국어/영어/혼합 문장 변형에 취약하다.
- 같은 단어가 여러 topology를 가리키는 경우 문맥 손실이 크다.
- “충전기”, “어댑터”, “전원”, “인버터” 같은 상위 표현은 실제 회로 topology를 1:1로 정하지 못하는데도 shortcut이 너무 일찍 topology로 수렴한다.

자연어 시스템이라면 이 층은 hardcoded routing이 아니라 `candidate generation` 정도까지만 해야 한다.

즉:

- 하드코딩된 keyword map은 `후보군 좁히기`까지만
- 최종 topology 선택은 더 풍부한 reasoning 또는 structured ranking이 맡는 구조

가 맞다.

### 2. 전압 role 추론이 고정 휴리스틱에 크게 의존함

관련 파일:

- `src/psim_mcp/parsers/intent_parser.py`

대표적으로 아래가 하드코딩이다.

- `_VIN_CONTEXT`, `_VOUT_CONTEXT`
- `_CONTEXT_WINDOW = 20`
- 큰 전압을 `vin`, 다음 값을 `vout_target`으로 두는 fallback

이건 간단한 문장에는 먹히지만 자연어 다양성이 커질수록 오판 가능성이 높다.

예:

- 배터리 양방향 시스템
- AC 입력 후 정류된 DC bus가 함께 언급되는 문장
- 다출력 전원
- “입력 400V DC bus, 배터리 48V 충전” 같은 복합 서술

이 영역은 하드코딩을 완전히 없애기는 어렵지만, 지금처럼 규칙이 parser 본체 안에 박혀 있는 구조는 확장성이 낮다.

### 3. use-case에서 topology로 바로 점프하는 규칙

예:

- `adapter -> flyback, llc`
- `charger -> cc_cv_charger, ev_obc`
- `motor -> bldc_drive, pmsm_foc_drive, induction_motor_vf`

이건 “도메인 추천”으로는 맞지만, “자연어 해석의 정답”으로 쓰면 과하다.

왜냐하면 사용자는 use-case를 말했지 topology를 확정한 게 아니기 때문이다.

좋은 구조는:

- use-case -> topology 후보군 생성
- 추가 spec/constraints로 ranking
- 부족하면 질문

이다.

지금 구조는 일부 경로에서 이걸 너무 빨리 확정해 버린다.

## 그래서 현재 구조가 맞는가?

부분적으로는 맞고, 부분적으로는 아니다.

### 맞는 점

- topology metadata를 별도로 두는 방향은 맞다.
- field alias를 canonical form으로 정규화하는 것도 맞다.
- low-level bridge/pin/type mapping을 고정하는 것도 맞다.
- keyword map을 “편의 shortcut”로 두는 것 자체는 가능하다.

### 맞지 않는 점

- shortcut parser가 실제 자연어 이해기처럼 동작하려고 하는 부분
- 모호한 use-case를 너무 빨리 topology로 확정하는 부분
- 전압/역할 추론을 고정 window heuristic에 과도하게 맡기는 부분
- 규칙이 코드 상수에 직접 들어 있어 운영 중 보정 비용이 큰 부분

핵심은 이거다.

> 자연어 시스템에서 하드코딩은 “내부 표현과 실행 계약”에는 맞지만,
> “사용자 문장 해석의 주 엔진”이 되면 맞지 않다.

현재 `psim-mcp`는 이 경계가 완전히 분리되어 있지 않다.

## 권장 경계선

이 프로젝트에서 유지해야 할 경계는 아래와 같다.

### A. 하드코딩 유지

- canonical topology 이름
- canonical field 이름과 alias
- component pin alias
- PSIM type/parameter mapping
- topology design constraints
- slot 질문 템플릿의 기본형

이건 제품 지식이므로 유지해도 된다.

### B. 데이터화 또는 설정화

- `TOPOLOGY_KEYWORDS`
- `USE_CASE_MAP`
- `PRIORITY_OVERRIDES`
- topology별 slot questions

이건 파이썬 상수보다 JSON/YAML/registry로 분리하는 편이 낫다.
이유는 운영 중 튜닝 빈도가 높기 때문이다.

### C. 하드코딩 비중을 줄여야 하는 부분

- 문장 전체에서 topology를 최종 확정하는 로직
- `vin/vout` role 추론
- 문맥 기반 후보 우선순위 결정

이건 규칙만으로 버티지 말고 아래 구조로 가는 것이 적절하다.

- 규칙 기반: 후보 생성
- metadata 기반: 후보 필터링
- reasoning 기반: 최종 선택 또는 clarification question

## 현실적인 판단

“자연어니까 하드코딩이 있으면 안 된다”는 건 아니다.
오히려 전력전자 같은 좁은 도메인에서는 어느 정도의 hardcoded ontology가 없으면 시스템이 흔들린다.

문제는 현재 hardcoding의 위치다.

- `실행/모델 계약`에 있는 하드코딩: 대체로 적절함
- `자연어 해석 주 로직`에 있는 하드코딩: 현재는 과한 편

따라서 지금 코드의 방향을 한 줄로 평가하면:

> “도메인 지식의 고정화는 맞지만, 사용자 자연어 해석까지 고정 규칙으로 많이 끌고 간 부분은 재설계 대상이다.”

## 추천 액션

1. `keyword_map.py`의 역할을 `최종 판정`이 아니라 `후보 생성기`로 축소
2. `topology_metadata.py`는 유지하되 JSON/YAML registry로 분리 검토
3. `intent_parser.py`의 전압 role heuristic를 독립 strategy layer로 분리
4. 최종 topology 선택은 `candidate list + constraints + missing fields` 기반으로 재랭킹
5. 모호할 때는 억지 결정 대신 clarification question을 우선

## 최종 결론

자연어 기반 회로 구성 시스템에서 하드코딩은 일부는 맞고 일부는 아니다.

- 맞는 하드코딩: 내부 모델, 도메인 ontology, 브리지 계약, topology 제약
- 맞지 않는 하드코딩: 사용자 문장의 의미를 직접 확정하는 규칙

현재 `psim-mcp`는 이 두 층이 혼합되어 있고, 그중 parser shortcut 계층은 하드코딩 비중이 높다.
따라서 “하드코딩이 있느냐 없느냐”보다, “어느 층에 하드코딩이 있느냐”를 기준으로 리팩터링하는 게 맞다.

## 현재 회로 구성 파이프라인에 대입하면

이 문제를 더 정확히 보려면, 현재 시스템이 실제로 회로를 만드는 흐름 위에 하드코딩을 겹쳐 봐야 한다.

현재 실질적인 파이프라인은 다음에 가깝다.

1. 사용자 자연어 입력
2. `design_circuit()` 또는 `preview_circuit()` 진입
3. parser/shortcut이 topology와 spec 후보를 만든다
4. generator가 `components + nets`를 만든다
5. service가 `connections + wire_segments`로 정규화한다
6. renderer/bridge가 SVG와 PSIM 회로를 만든다

이 구조에서 각 단계별 하드코딩 적합성을 보면 다음과 같다.

### 1. 입력 해석 단계

여기는 하드코딩이 가장 위험한 층이다.

왜냐하면 사용자가 말하는 문장은 다음처럼 매우 다양하기 때문이다.

- 목표 기능만 말하는 경우
- 전압/전류/전력만 말하는 경우
- topology를 직접 말하는 경우
- application과 제약만 말하는 경우
- AC/DC, 절연/비절연, 양방향 여부를 혼합해서 말하는 경우

이 단계에서 hardcoded keyword router가 너무 강하면, 사용자의 의도를 “추정”하는 수준이 아니라 “강제로 확정”해버린다.
자연어 시스템에서 가장 조심해야 하는 하드코딩은 바로 이 층이다.

### 2. topology/spec 정규화 단계

여기는 하드코딩이 비교적 정당하다.

예:

- `buck`은 canonical topology name
- `vout`, `vout_target`은 같은 필드로 정규화
- `switching_frequency`, `fsw`는 같은 spec alias

이건 자연어를 실행 가능한 내부 표현으로 바꾸는 단계이므로, 규칙 기반 정규화가 오히려 필요하다.

### 3. generator 단계

여기는 “자연어 해석용 하드코딩”이 아니라 “설계 템플릿/토폴로지 지식의 하드코딩”이다.

예:

- buck generator의 기본 구조
- LLC generator의 resonant tank 구조
- 각 topology의 기본 부품군, net 구조, 기본 parameter 계산식

이건 어느 정도 하드코딩될 수밖에 없다.
문제는 generator가 topology 지식을 갖는 것 자체가 아니라, 그 generator에 잘못 들어가기 전 단계가 너무 빠르게 topology를 확정하는 경우다.

즉 generator hardcoding보다 parser hardcoding이 더 핵심 문제다.

### 4. rendering/bridge 단계

여기는 자연어 하드코딩과는 성격이 다르다.

예:

- pin alias
- symbol anchor
- PSIM type map
- wire routing helper

이건 실행 계약 계층이라서 hardcoded rule이 존재하는 것이 자연스럽다.
다만 renderer와 bridge가 서로 다른 규칙을 가지면 안 된다.
즉 “하드코딩의 존재”보다 “하드코딩의 중복과 불일치”가 문제다.

## 사용자 관점에서 진짜 문제가 되는 하드코딩

사용자 입장에서 문제는 코드에 상수가 있느냐가 아니다.
실제 문제는 아래처럼 나타난다.

### 1. 내가 말하지 않은 topology로 너무 빨리 굳어진다

예:

- “48V에서 12V 만드는 전원”이라고 했는데 바로 buck으로 결정
- “충전기”라고 했는데 CC/CV charger로 바로 수렴
- “절연 어댑터”라고 했는데 flyback/llc 중 하나로 너무 빨리 굳음

이건 자연어 해석의 유연성을 떨어뜨린다.

### 2. spec의 역할이 잘못 박힌다

예:

- 단일 전압 입력을 `vin`으로 볼지 `vout_target`으로 볼지
- 400V가 AC mains인지 DC bus인지
- 48V가 배터리인지 출력 rail인지

이런 문제는 대부분 parser hardcoding이 너무 앞단에서 확정 결정을 하기 때문에 생긴다.

### 3. clarification 없이 fallback으로 밀어붙인다

자연어 시스템은 모르면 질문하는 것이 맞다.
그런데 하드코딩 기반 shortcut은 대체로 “애매하면 기본값” 또는 “애매하면 대표 topology”로 간다.

이건 짧게는 편하지만, 회로 설계 품질에는 불리하다.

## 엔지니어링 관점에서 봐야 할 기준

자연어 시스템에서 하드코딩을 평가할 때는 “있다/없다”보다 아래 질문으로 봐야 한다.

### 질문 1. 이 규칙은 제품의 내부 계약인가?

예:

- canonical field name
- pin alias
- PSIM type mapping

이런 건 하드코딩이어도 괜찮다.

### 질문 2. 이 규칙은 사용자 언어의 의미를 최종 확정하는가?

예:

- `charger -> cc_cv_charger`
- `adapter -> flyback`
- 큰 전압을 무조건 `vin`

이런 건 hardcoded final decision이면 위험하다.

### 질문 3. 이 규칙은 쉽게 바뀌는 운영 파라미터인가?

예:

- keyword synonym 목록
- use-case to topology 후보 우선순위
- slot question wording

이건 코드 상수보다 데이터/설정으로 분리하는 것이 맞다.

### 질문 4. 이 규칙이 틀리면 시스템이 질문을 해야 하나, 그냥 진행해야 하나?

자연어 계층에서는 이 질문이 중요하다.

- 틀리면 잘못된 회로가 생성되는 규칙: 질문해야 함
- 틀려도 내부 표현만 조금 바뀌는 규칙: 진행 가능

현재 parser hardcoding 중 일부는 첫 번째 성격인데도 질문 없이 진행한다.

## 이 프로젝트에 맞는 목표 구조

지금 프로젝트에 맞는 현실적인 목표 구조는 아래와 같다.

### Layer 1. Candidate extraction

역할:

- keyword
- metadata
- unit parser
- constraints

결과:

- topology 후보군
- 추출된 spec
- 확신도
- 추가로 물어볼 질문 후보

여기까지는 규칙 기반 하드코딩이 가능하다.

### Layer 2. Decision / clarification

역할:

- 후보군 재랭킹
- 충돌 해소
- ambiguity detection
- 질문 필요 여부 결정

이 층은 hardcoded final rule보다 reasoning 중심이어야 한다.

### Layer 3. Canonical circuit spec

역할:

- 최종 topology
- canonical specs
- components/nets/connections

이 층은 generator와 service가 담당한다.
여기는 규칙 기반 구조가 오히려 안정적이다.

### Layer 4. Execution contract

역할:

- wire segments
- SVG renderer
- PSIM bridge

이 층은 deterministic해야 하므로 hardcoded contract가 있어도 된다.

## 지금 문서 기준으로 추가 결론

따라서 “자연어 기반 회로 구성인데 하드코딩이 맞는가?”라는 질문에 더 정밀하게 답하면:

- `회로를 실제로 만들기 위한 내부 명세`는 하드코딩이 맞다.
- `자연어를 해석해 topology를 확정하는 판단`은 하드코딩 비중이 낮아야 맞다.
- `후보 생성`까지는 하드코딩 가능하지만, `최종 선택`까지 하드코딩하는 것은 맞지 않다.

현재 `psim-mcp`는 이 경계에서

- generator/bridge 계층은 비교적 타당한 hardcoding을 하고 있고
- parser/shortcut 계층은 자연어 시스템치고 hardcoding 비중이 높은 편

이라고 보는 것이 가장 정확하다.

## 실무적인 권장안

실제로는 아래 순서로 줄여가는 것이 좋다.

1. `keyword_map.py`는 유지하되 최종 확정 권한을 약하게 만든다
2. `intent_parser.py`는 topology 단정 대신 `candidate + confidence + missing info`를 더 많이 반환하게 바꾼다
3. ambiguity가 높을 때는 generator로 바로 가지 말고 clarification question을 우선한다
4. topology metadata와 keyword set은 코드 상수보다 외부 registry로 이동한다
5. bridge/renderer/component library의 hardcoded contract는 유지하되 중복 정의는 줄인다

이 방향이면 자연어 유연성을 올리면서도, 실행 가능한 회로 생성 엔진의 안정성은 유지할 수 있다.
