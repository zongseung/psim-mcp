# 10. Parser Hardcoding Review

> 우선순위: P1
> 대상 범위: `src/psim_mcp/parsers/intent_parser.py`, `src/psim_mcp/parsers/keyword_map.py`
> 연관 문서: `07-nlp-intent-parser.md`, `09-dynamic-circuit-design.md`

---

## 1. 목적

`design_circuit`와 자연어 기반 회로 생성 흐름에서 아직 남아 있는 parser 하드코딩을 정리한다.

이 문서는 parser를 제거하자는 뜻이 아니라:

- 어떤 부분이 임시 규칙인지 명확히 표시하고
- 어떤 규칙은 유지 가능한 fallback인지 구분하고
- 장기적으로 `LLM-as-Designer` 구조와 충돌하는 부분을 분리하는 데 목적이 있다.

---

## 2. 현재 남아 있는 parser 하드코딩

### 2.1 키워드 기반 topology 매칭

현재 상태:

- `keyword_map.py`의 `TOPOLOGY_KEYWORDS`로 topology를 식별한다.
- `"buck"`, `"boost"`, `"full_bridge"` 같은 키워드를 문자열 포함 여부로 찾는다.

문제:

- 표현이 조금만 달라져도 인식이 약해진다.
- 문맥 해석 없이 substring 매칭에 의존한다.
- topology명이 명시되지 않은 설명형 요청에는 한계가 있다.

현재 파일:

- `src/psim_mcp/parsers/keyword_map.py`
- `src/psim_mcp/parsers/intent_parser.py`

### 2.2 use-case → topology 후보 매핑

현재 상태:

- `USE_CASE_MAP`이 `"충전"`, `"인버터"`, `"태양광"`, `"모터"` 같은 단어를 topology 후보 목록에 연결한다.

문제:

- 도메인 지식이 parser 내부 정적 테이블에 박혀 있다.
- 제품군이 늘어날수록 관리 비용이 커진다.
- 후보 우선순위가 고정이라 실제 요구 조건을 반영하지 못할 수 있다.

### 2.3 숫자 값을 spec 필드로 매핑하는 휴리스틱

현재 상태:

- `_map_values_to_specs()`는 전압을 큰 값부터 정렬해 `vin`, `vout_target`으로 넣는다.
- 첫 번째 전류를 `iout`, 첫 번째 주파수를 `fsw`로 넣는다.

문제:

- 다입력/다출력, 배터리/버스/게이트 전압이 함께 나오는 문장에서 쉽게 틀릴 수 있다.
- 값은 추출했지만 역할은 잘못 붙는 경우가 생긴다.

대표 예:

- `"400V DC bus, 15V auxiliary, 48V output"` 같은 문장은 단순 정렬 규칙으로 처리하면 오해 가능성이 높다.

### 2.4 generator 부재 시 기본 필수 필드 fallback

현재 상태:

- `_get_required_fields()`는 generator가 없으면 무조건 `["vin", "vout_target", "iout"]`를 요구한다.

문제:

- 모든 topology가 같은 필수 필드를 갖는다고 가정한다.
- inverter, motor drive, AC-DC, transformer-based converter에는 맞지 않는다.

### 2.5 질문 문구 fallback

현재 상태:

- `SLOT_QUESTIONS`에 없는 필드는 `"{field}을(를) 지정해주세요."` 형식의 일반 문구로 처리한다.

문제:

- 사용자 경험은 유지되지만, domain-aware guidance는 부족하다.
- topology별 질문 맥락이 사라진다.

---

## 3. 분류: 유지 / 축소 / 교체

### 3.1 유지 가능한 fallback

- `TOPOLOGY_KEYWORDS`
- `USE_CASE_MAP`
- `SLOT_QUESTIONS`

조건:

- primary intelligence가 아니라 보조 수단일 것
- parser 실패 시 질문 생성과 candidate 제시에만 사용될 것

### 3.2 빠르게 축소해야 하는 하드코딩

- `_map_values_to_specs()`의 값 역할 추정 규칙
- `_get_required_fields()`의 공통 fallback `["vin", "vout_target", "iout"]`

이유:

- 실제 회로 설계 정확도에 직접 영향을 준다.
- 잘못된 preview/create로 이어질 수 있다.

### 3.3 장기적으로 교체되어야 하는 부분

- 정적 keyword 기반 topology 선택을 주 경로로 쓰는 구조
- parser가 설계 판단까지 대신하는 구조

장기 목표:

- parser는 intent 정리와 slot 수집만 담당
- topology 선택과 설계 판단은 Claude + validator feedback loop가 주도

---

## 4. 권장 개선 방향

### 4.1 parser 역할 축소

parser는 아래만 담당한다.

- 수치/단위 추출
- topology candidate 제시
- 누락 slot 질문 생성

parser가 직접 확정하지 않아야 하는 것:

- 최종 topology 결정
- derived parameter 계산
- 회로 설계 규칙 적용

### 4.2 spec mapping을 context-aware로 변경

현재:

- 값 크기 순서로 `vin`, `vout_target`를 추정

개선:

- `"input"`, `"출력"`, `"bus"`, `"battery"`, `"gate"` 같은 주변 단어를 함께 본다.
- 불확실하면 강제 추정하지 말고 clarification으로 전환한다.

### 4.3 topology별 required fields를 metadata로 분리

현재:

- generator가 없으면 공통 fallback 사용

개선:

- `topology metadata` 또는 `template metadata`에 required fields를 둔다.
- parser는 generator 존재 여부와 무관하게 topology별 필수값을 참조한다.

### 4.4 질문 생성도 topology-aware로 분리

예:

- `buck`: 입력 전압, 목표 출력 전압, 출력 전류
- `full_bridge inverter`: DC bus voltage, output frequency, load type
- `flyback`: 입력 범위, 출력 전압, 출력 전류, 절연 여부

---

## 5. 구현 영향 범위

수정 대상:

- `src/psim_mcp/parsers/intent_parser.py`
- `src/psim_mcp/parsers/keyword_map.py`

추가 후보:

- `src/psim_mcp/data/topology_metadata.py`
- `src/psim_mcp/parsers/spec_mapper.py`

연계 영향:

- `tools/design.py`
- generator selection 로직
- preview 전 clarification 응답 구조

---

## 6. 테스트 기준

### 6.1 유지해야 하는 테스트

- `"buck 컨버터 48V 입력 12V 출력"` → topology=buck
- `"태양광 MPPT"` → candidate 제시
- 단위 파서의 SI prefix 동작

### 6.2 추가해야 하는 테스트

- `"400V bus, 48V output, 15V auxiliary"`에서 값 역할이 잘못 확정되지 않는지
- generator가 없는 topology에서 공통 fallback 대신 metadata 기반 required fields를 쓰는지
- ambiguity가 높을 때 잘못된 확정 대신 clarification 질문으로 내려가는지

---

## 7. 현재 자연어 입력에서 실제로 놓칠 수 있는 부분

### 7.1 필드명 불일치로 인한 반영 누락

현재 상태:

- parser는 `iout`, `fsw`, `r_load`를 채운다.
- 일부 metadata와 질문 로직은 `iout_target`, `switching_frequency`, `load_resistance`, `output_frequency` 같은 이름을 사용한다.

영향:

- 자연어에서 값은 추출됐는데 required field 비교나 후속 로직에서 누락으로 보일 수 있다.
- 질문이 불필요하게 다시 나올 수 있다.

대표 예:

- `"출력 5A"`는 `iout`로만 잡히고 `iout_target` 기준 로직과 어긋날 수 있음
- `"스위칭 주파수 100kHz"`는 `fsw`로만 잡히고 `switching_frequency` 기반 로직과 분리될 수 있음
- `"부하저항 10옴"`은 `r_load`로만 잡히고 inverter metadata의 `load_resistance`와 연결되지 않을 수 있음

### 7.2 다중 전압 문장의 역할 오해

현재 상태:

- `vin` / `vout_target`은 주변 단어 매칭 또는 큰 값 순 정렬로 결정된다.

영향:

- auxiliary rail, battery voltage, DC bus가 함께 나오면 잘못 매핑될 수 있다.

대표 예:

- `"400V bus, 48V battery, 15V auxiliary"`
- `"입력 220Vac, 정류 후 310Vdc, 출력 19V"`
- `"1차 400V, 2차 48V, 보조 12V"`

### 7.3 다중 주파수 문장 처리 한계

현재 상태:

- frequency category는 첫 번째 값만 `fsw`로 사용한다.

영향:

- 출력 주파수와 스위칭 주파수가 함께 있는 문장에서 잘못 해석될 수 있다.

대표 예:

- `"출력 60Hz, 스위칭 100kHz 인버터"`
- `"20kHz PWM, 400Hz 출력"`

### 7.4 topology를 직접 말하지 않는 설명형 요청

현재 상태:

- topology 인식은 keyword map 또는 use-case map에 크게 의존한다.

영향:

- topology명이 없는 설명형 자연어는 쉽게 놓친다.

대표 예:

- `"정류 후 mains에서 19V 노트북 어댑터"`
- `"절연형 5V 보조전원"`
- `"배터리와 DC 링크를 양방향으로 연결하는 회로"`

### 7.5 topology-specific slot 미지원

현재 상태:

- parser는 공통 필드 중심으로 값을 매핑한다.
- `voc`, `isc`, `vmp`, `imp`, `output_frequency`, `grid_voltage` 같은 topology 전용 slot은 직접 매핑하지 않는다.

영향:

- 태양광, 계통연계, 인버터 계열 자연어가 일부만 반영된다.

대표 예:

- `"Voc 40V, Isc 10A 태양광 MPPT"`
- `"계통 220V 연계 인버터"`
- `"출력 60Hz 3상 인버터"`

### 7.6 generator fast-path에 필요한 값 부족

현재 상태:

- `buck`, `boost`, `buck_boost` generator는 `vin`, `vout_target`, `iout`를 모두 요구한다.

영향:

- 흔한 짧은 요청도 parser가 topology는 알아도 자동 설계로 바로 못 넘어갈 수 있다.

대표 예:

- `"48V 입력 12V buck"`
- `"12V to 48V boost"`

---

## 8. 우선 수정 항목

1. parser/metadata/generator의 필드명을 단일 canonical schema로 통일
2. `output_frequency`, `switching_frequency`, `load_resistance`, `voc/isc/vmp/imp` 매핑 추가
3. 다중 전압 문장에서 잘못 확정하지 않고 clarification으로 내리는 기준 강화
4. 설명형 자연어에 대한 synonym/use-case map 보강
5. generator fast-path와 질문 생성 기준을 분리

---

## 9. 완료 기준

- [x] parser가 topology 확정과 설계 판단을 분리한다 (parser는 intent 정리 + slot 수집만 담당)
- [x] `_map_values_to_specs()`의 단순 정렬 기반 규칙을 축소하거나 대체한다 (context-aware 매핑, 주변 단어 탐색)
- [x] generator 없는 topology도 metadata 기반 required fields를 사용한다 (`topology_metadata.py` 30개 topology)
- [x] 질문 생성이 topology-aware 구조를 갖는다 (topology별 slot_questions 참조)
- [x] keyword/use-case map은 fallback 계층으로만 남는다
- [x] 3+ 전압 시 강제 할당 대신 unassigned_voltages 반환 + confidence 하향
- [x] parser 관련 회귀 테스트 보강 (13개 회귀 테스트, 5개 클래스)
- [x] 필드명 alias 통일 (iout↔iout_target, fsw↔switching_frequency, r_load↔load_resistance)
- [x] 다중 주파수 context-aware 처리 (switching vs output frequency)
- [x] topology-specific slot 매핑 (voc, isc, vmp, imp, grid_voltage)
- [x] generator iout 옵션화 (buck/boost/buck_boost에서 기본값 1.0A)
- [x] USE_CASE_MAP 33개 항목 추가 (설명형 요청 지원)
- [x] TOPOLOGY_KEYWORDS 확장 (resonant, cc/cv, on-board charger, v2h 등)
