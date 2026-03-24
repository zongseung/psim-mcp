# 사용자 의도 기반 회로 생성 vs 예제 패턴 재구성 검토
작성일: 2026-03-24

## 목적

현재 `psim-mcp`가 사용자의 자연어 요구를 받아 회로도를 "새로 설계"하는 구조인지,
아니면 PSIM 튜토리얼/예제에서 가져온 패턴을 바탕으로 회로를 "재구성"하는 구조인지
코드 기준으로 구체적으로 판단한다.

이 문서는 아래 질문에 답한다.

- 지금 시스템을 `사용자 의도 기반 회로 합성기`라고 부를 수 있는가
- 어디까지는 정당한 참고이고, 어디부터는 예제 의존이 과한가
- 왜 사용자 입장에서 "이건 그냥 배낀 것 아닌가"라는 인상이 생기는가
- 진짜 합성 구조로 가려면 무엇이 바뀌어야 하는가

## 결론 요약

현재 구조는 완전한 복사 시스템은 아니다.
사용자 spec으로부터 파라미터를 계산하고, `components + nets`를 코드로 생성하고, 이후 `wire_segments`까지 정규화한다.

하지만 현재의 핵심 생성 로직은 `사용자 요구에서 회로 구조를 새로 합성`한다기보다,
`PSIM 예제에서 검증된 topology/layout/PORTS/DIR 패턴을 코드에 옮겨 놓고, 그 위에 사용자 spec을 입히는 구조`에 더 가깝다.

따라서 현재 시스템을 가장 정확하게 표현하면 다음과 같다.

> `자연어 기반 회로 합성기`라기보다
> `예제 패턴 기반 회로 재구성기 + 파라미터 리타게팅 시스템`에 가깝다.

## 왜 "그냥 배낀 것 같다"는 인상이 생기는가

사용자는 보통 자연어 시스템에 대해 다음을 기대한다.

- 요구사항을 읽고
- 필요한 topology를 판단하고
- 부품 구조와 배선을 새로 만들고
- 그 결과를 회로도로 보여주는 것

그런데 현재 코드는 다음 쪽에 더 가깝다.

- topology별로 미리 굳어진 generator가 있고
- 그 generator 내부 layout, 포트 순서, 방향, 심볼 배치가
  PSIM example 또는 converted reference를 기준으로 고정돼 있고
- 사용자는 주로 그 틀에 파라미터를 제공하는 역할을 한다

즉 사용자가 보기에는 `새로 설계했다`기보다
`검증된 예제 틀에 값을 맞춰 넣었다`는 인상을 받기 쉽다.

이 인상은 단순한 느낌이 아니라, 실제 코드 구조와도 상당 부분 맞아 있다.

## 코드 기준 판단

### 1. 회로 생성 뼈대가 topology별 고정 generator에 강하게 묶여 있음

관련 파일:

- `src/psim_mcp/generators/llc.py`
- `src/psim_mcp/generators/boost_pfc.py`
- `src/psim_mcp/generators/flyback.py`
- `src/psim_mcp/generators/forward.py`
- `src/psim_mcp/generators/layout.py`

확인된 사실:

- 여러 generator 파일 헤더와 주석에 `Layout verified against PSIM reference` 또는
  `converted_...py` reference가 직접 적혀 있다.
- `layout.py`의 공통 helper도 단순 편의 함수가 아니라,
  reference example의 `PORTS`, `DIR`, 좌표 패턴을 재사용하기 위한 factory 역할을 한다.

의미:

- topology 선택 이후의 실질적 회로 형상은 상당 부분 generator 내부 규칙으로 이미 굳어져 있다.
- 사용자는 topology 내부 구조를 새로 설계하게 하는 것이 아니라,
  이미 정해진 구조에 설계값을 공급하는 쪽에 더 가깝다.

### 2. bridge 계층도 PSIM reference 분석 결과를 직접 계약으로 사용함

관련 파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인된 사실:

- 파일 헤더와 내부 설명에 `PsimConvertToPython 출력 기반`이라고 명시돼 있다.
- `_PSIM_TYPE_MAP`, `_PARAM_NAME_MAP`, `_FALLBACK_PORT_PIN_GROUPS`는
  PSIM converted output에서 관찰한 규칙을 코드 계약으로 굳힌 것이다.

의미:

- low-level bridge mapping 자체는 참고 기반 구현이 맞다.
- 이 계층은 원래부터 예제/레퍼런스 기반일 수밖에 없는 부분이므로,
  이것만으로 문제라고 보긴 어렵다.
- 다만 generator까지 같은 성격으로 reference에 강하게 묶이면,
  전체 시스템이 `새 설계`보다 `reference 재현`으로 기울게 된다.

### 3. 서비스 계층은 generator 출력을 조립하고 전달하는 구조이지, 구조 합성 엔진은 아님

관련 파일:

- `src/psim_mcp/services/circuit_design_service.py`

확인된 사실:

- `parse_circuit_intent()`로 topology/spec를 정리한 뒤
  `get_generator(circuit_type)`를 통해 topology별 generator를 선택한다.
- 이후 service는 generator 결과를 `components`, `nets`, `wire_segments`로 정규화하고
  preview/bridge로 전달한다.

의미:

- service는 파이프라인 조정자다.
- `사용자 요구 -> 새로운 회로 그래프 합성`을 일반 규칙으로 수행하는 핵심 엔진은 아니다.
- 실제 회로 구조의 상당 부분은 이미 generator 안에서 결정돼 있다.

### 4. 템플릿 복사 모드는 남아 있지만, 현재 주 경로는 아닌 것으로 보임

관련 파일:

- `src/psim_mcp/bridge/bridge_script.py`
- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/adapters/real_adapter.py`

확인된 사실:

- `psim_template`가 있으면 예제 `.psimsch`를 복사하고 override하는 경로가 구현돼 있다.
- 하지만 현재 generator/data 코드 검색 기준으로 `psim_template`를 직접 반환하는 흔적은 보이지 않는다.

의미:

- "예제 파일을 그대로 복사하는 시스템"이 현재 주 경로라고 보긴 어렵다.
- 그러나 "예제에서 추출한 패턴으로 generator를 짜 놓은 시스템"이라는 평가는 여전히 유효하다.

## 그래서 이건 복붙인가, 아닌가

정확히 말하면 `완전 복붙`은 아니다.

이유:

- 사용자 spec에서 `vin`, `vout_target`, `power`, `fsw` 등을 읽고
  필요한 파라미터를 계산한다.
- generator가 실제 `components + nets`를 다시 만든다.
- 이후 routing과 SVG/bridge 생성도 현재 입력 기준으로 다시 수행한다.

하지만 `진짜 합성`이라고 보기 어려운 이유도 분명하다.

- topology 내부 구조가 generator에 미리 고정돼 있다.
- 부품의 공간 배치와 포트 구조가 reference 예제를 많이 따른다.
- topology 결정 이후에는 `구조적 자유도`가 크지 않다.
- 사용자가 원하는 회로도를 넓게 탐색하기보다,
  미리 준비된 topology skeleton 중 하나를 구체화하는 구조다.

따라서 가장 정확한 표현은 이렇다.

> 복사본 그대로를 내는 시스템은 아니지만,
> 사용자의 요구에서 회로 구조를 새로 발명하는 시스템도 아니다.
> 현재는 reference-derived skeleton을 사용자 spec으로 구체화하는 시스템에 가깝다.

## 어떤 참고는 정당하고, 어떤 참고는 과한가

### 정당한 참고

아래는 오히려 reference를 참고하는 것이 맞다.

- PSIM element type mapping
- PSIM parameter name mapping
- 부품별 pin group / port contract
- low-level bridge API 사용법

이 영역은 `도메인/도구 계약`에 해당한다.
정확히 동작하려면 reference나 공식 동작을 기반으로 고정하는 것이 맞다.

### 과한 참고

아래는 reference 의존이 과하면 사용자 맞춤 생성기로 보기 어렵다.

- topology별 좌표 배치가 특정 example layout를 거의 따라가는 것
- transformer, bridge, resonant tank 등의 구조 배치가 reference 예제 중심으로 굳는 것
- topology 내부 연결과 도면 형상을 예제 패턴에 기대는 것
- 자연어 해석 결과가 결국 특정 skeleton 선택으로만 귀결되는 것

이 영역은 `사용자 요구 기반 synthesis`가 일어나야 하는 층이다.
여기까지 example이 지배하면 설계 엔진이 아니라 example reconstruction 엔진이 된다.

## 현재 구조의 한계

### 1. 사용자 요구를 topology 이후 구조 차이로 충분히 반영하기 어렵다

예:

- 같은 `flyback`이라도 보조권선 유무, clamp 구조, rectifier 배치, sensing 위치는 달라질 수 있다.
- 같은 `llc`라도 정류부 배치, 공진소자 배치, 구동부/탱크 상대 위치는 달라질 수 있다.

현재 구조에서는 이런 차이를 topology 내부 generator variant로 미리 만들어 두지 않으면 다루기 어렵다.

### 2. 새로운 topology 또는 변형을 수용할 때 코드 수정 비용이 크다

- 새 topology를 추가하려면 generator, layout, bridge 검증까지 새로 넣어야 한다.
- 구조를 메타데이터나 graph rule로 조합하는 비중이 낮아서 확장성이 떨어진다.

### 3. 회로도 가독성과 회로 합성이 분리돼 있지 않다

- reference 기반 좌표 패턴이 곧 회로 구조처럼 취급되기 쉽다.
- `electrical graph`와 `diagram layout`가 분리되지 않으면,
  예제 배치가 사실상 구조 자체를 결정하게 된다.

## 진짜 사용자 의도 기반 합성기로 가려면

핵심은 `예제`를 없애는 것이 아니라,
예제를 `근거`와 `검증 데이터`로 낮추고
실제 생성은 별도의 canonical synthesis model에서 하도록 바꾸는 것이다.

### 목표 구조

1. 사용자 요구 해석
- topology 후보
- constraints
- 필수 설계 파라미터

2. canonical circuit graph 생성
- components
- nets
- functional blocks
- roles

3. structural synthesis
- topology rule로 그래프를 조립
- optional block 포함 여부 결정
- variant 선택

4. layout synthesis
- graph를 기준으로 부품 배치
- rail, bus, isolation boundary, primary/secondary 영역 배치

5. routing synthesis
- `wire_segments` 생성
- diagram readability 규칙 적용

6. bridge emission
- PSIM 계약에 맞게 실제 회로 생성

이 구조에서는 example이 아래 용도로만 쓰인다.

- 특정 topology에서 PSIM이 요구하는 핀/파라미터 계약 확인
- reference layout와 비교한 회귀 검증
- generator/renderer 테스트 fixture

즉 example은 `정답의 출처`가 아니라 `검증용 참고자료`가 되어야 한다.

## 단기/중기 권장 방향

### 단기

- generator 주석/메타데이터에 `reference-derived` 여부를 명시
- topology별로 무엇이 고정 skeleton이고 무엇이 사용자 spec으로 바뀌는지 분리
- `electrical graph`와 `diagram layout`를 문서/코드에서 명확히 구분

### 중기

- generator를 `example-coordinates producer`에서 `graph assembler`로 축소
- layout.py를 example factory가 아니라 layout strategy 계층으로 전환
- topology 내부 optional block을 metadata/rule 기반 variant로 분리

### 장기

- `user intent -> canonical graph -> layout -> routing -> bridge` 파이프라인 완성
- example는 regression corpus와 PSIM contract validation 용도로만 유지

## 최종 결론

현재 `psim-mcp`는 사용자의 요구를 전혀 반영하지 않는 단순 복사 시스템은 아니다.
하지만 아직 `사용자 요구 기반으로 회로 구조를 새로 합성하는 시스템`이라고 보기도 어렵다.

더 정확한 평가는 다음과 같다.

> 현재 시스템은
> `PSIM 예제에서 추출한 회로 패턴을 코드화해 두고,
> 사용자 spec으로 그 패턴을 구체화하는 구조`에 가깝다.

사용자가 "이건 그냥 배낀 것 아니냐"라고 느끼는 이유는 타당하다.
다만 엄밀히는 `예제 파일 복사`보다 `예제 패턴의 코드화와 재조립`에 더 가깝다.

앞으로의 핵심 과제는 예제를 제거하는 것이 아니라,
예제가 생성 로직의 중심이 아니라 검증 근거가 되도록 구조의 무게중심을 옮기는 것이다.
