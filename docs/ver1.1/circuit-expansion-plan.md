# PSIM-MCP Circuit Expansion Plan

> 작성일: 2026-03-15
> 범위: 현재 템플릿 중심 회로 생성 기능을 확장하기 위한 설계 제안
> 목적: "한정적인 회로 생성 및 시뮬레이션" 구조를 더 일반화된 시스템으로 발전시키는 방향 제시

---

## 1. 문제 정의

현재 구현은 다음 범위에서는 의미가 있다.

- 템플릿 기반 회로 생성
- 기존 회로 열기 및 파라미터 수정
- 시뮬레이션 실행 및 결과 export

하지만 아래 요구를 만족하기에는 아직 부족하다.

- 자연어로 다양한 회로를 안정적으로 생성
- 복수 topology를 공통 구조로 표현
- 배선 오류 없이 schematic 생성
- 생성 직후 실행 가능한 수준의 회로 검증

즉 현재 구조는 "회로 생성 기능이 없는 상태"는 아니지만, 아직 "범용 회로 생성 시스템"도 아니다.

---

## 2. 핵심 방향

확장 방향의 핵심은 다음 한 줄로 정리할 수 있다.

> 자연어를 바로 PSIM API로 보내지 말고,  
> `자연어 -> 회로 스펙(DSL) -> 검증 -> PSIM 생성` 구조로 바꿔야 한다.

이 구조가 필요한 이유는 다음과 같다.

- LLM이 좌표, 핀 이름, 연결 규칙을 직접 맞추게 하면 오류가 많다.
- 회로 생성 실패 원인을 추적하기 어렵다.
- 재현성과 테스트 가능성이 떨어진다.
- topology를 늘릴수록 prompt 의존성이 급격히 커진다.

---

## 3. 권장 아키텍처

### 3.1 현재 구조

현재 구조는 사실상 아래에 가깝다.

`자연어 -> tool 선택 -> 템플릿/구조 입력 -> PSIM bridge`

이 구조는 단순하고 빠르지만, 복잡한 회로 생성에는 취약하다.

### 3.2 권장 구조

권장 구조는 아래와 같다.

`자연어 -> intent parser -> CircuitSpec -> validator -> topology generator -> PSIM bridge`

각 단계 역할:

- `intent parser`
  - 자연어에서 topology, 입력 전압, 부하, 스위칭 주파수, 목표 출력 등 추출
- `CircuitSpec`
  - 회로를 표현하는 내부 표준 JSON/DSL
- `validator`
  - 필수 소자, net 연결, 파라미터 범위, 지원 여부 점검
- `topology generator`
  - 검증된 spec을 실제 component/connection/layout으로 전개
- `PSIM bridge`
  - 최종 schematic 생성 및 저장

---

## 4. 우선 도입해야 할 것

### 4.1 CircuitSpec 정의

가장 먼저 필요한 것은 내부 회로 표현이다.

예시 구조:

```json
{
  "topology": "buck",
  "metadata": {
    "name": "buck_48_to_12",
    "version": "1.0"
  },
  "requirements": {
    "vin": 48.0,
    "vout_target": 12.0,
    "switching_frequency": 50000
  },
  "components": [
    {
      "id": "V1",
      "kind": "dc_source",
      "params": {
        "voltage": 48.0
      }
    }
  ],
  "nets": [
    {
      "name": "VIN",
      "pins": ["V1.positive", "SW1.drain"]
    }
  ],
  "simulation": {
    "time_step": 1e-5,
    "total_time": 0.1
  }
}
```

권장 원칙:

- `connections`보다 `nets` 중심 표현을 우선한다.
- topology와 설계 요구사항을 분리한다.
- layout 좌표는 generator 단계에서 계산 가능하게 둔다.
- 사용자 입력과 PSIM API 호출 파라미터를 직접 1:1로 묶지 않는다.

---

### 4.2 Topology Generator 도입

현재 템플릿은 사실상 고정 예제에 가깝다. 이를 "생성 규칙"으로 바꿔야 한다.

예:

- `buck_generator`
- `boost_generator`
- `buck_boost_generator`
- `flyback_generator`
- `half_bridge_generator`
- `full_bridge_generator`

각 generator 책임:

- 필수 소자 구성
- 기본 netlist 생성
- 기본 파라미터 초기화
- 좌표 자동 배치
- simulation 기본값 설정

이렇게 하면 템플릿 추가가 단순 복붙이 아니라 규칙 기반 확장이 된다.

---

### 4.3 Component Catalog 정리

자연어 기반 회로 생성이 안정적이려면 PSIM 부품 카탈로그가 필요하다.

카탈로그에 포함할 항목:

- 내부 표준 부품명
- PSIM 실제 element type
- 필수 파라미터명
- 선택 파라미터명
- 핀 이름 목록
- 기본값
- 지원 topology

예:

- `dc_source`
- `mosfet`
- `diode`
- `inductor`
- `capacitor`
- `resistor`
- `ground`

현재처럼 문자열 타입을 바로 bridge에 넘기는 구조는 확장 시 위험하다.

---

### 4.4 Validator 계층 추가

회로 생성 전에 아래 검증이 필요하다.

- 필수 소자 누락
- duplicate component id
- unsupported component type
- net 미연결
- ground 누락
- source/load 누락
- 파라미터 범위 오류
- topology별 필수 구조 위반

이 검증 계층이 있어야 LLM 출력이 바로 PSIM 오류로 이어지지 않는다.

---

### 4.5 Auto-layout 규칙 도입

회로 생성 시스템은 좌표 배치도 deterministic 해야 한다.

권장 접근:

- 초기에는 topology별 grid layout
- 이후 branch 수에 따른 spacing 조절
- 입력/스위치/에너지 저장/부하 순서의 좌우 흐름 유지

중요한 점:

- layout은 LLM이 정하지 말고 generator가 정해야 한다.

---

## 5. PSIM Bridge 보강 포인트

현재 bridge는 회로 생성 시도 경로는 있지만, 확장형 시스템으로 보기엔 아직 부족하다.

필수 보강 항목:

### 5.1 실제 wire 생성 API 확인

현재 코드상 `connections`는 응답에 숫자만 반영될 뿐, 배선 생성 호출이 명확하지 않다.

필요 작업:

- `psimapipy` 또는 PSIM Python API에서 wire/connect 관련 함수 확인
- pin-to-pin 연결 구현
- net 단위 배선 생성 로직 추가

### 5.2 실패를 `pass`로 삼키지 않기

현재 개별 부품 생성 실패가 무시된다.

필요 작업:

- 실패한 컴포넌트 목록 반환
- 실패 이유 기록
- 부분 성공 상태를 명시
- 특정 임계치 이상 실패 시 전체 실패 처리

### 5.3 생성 후 검증

저장 직후 아래를 확인해야 한다.

- 파일 생성 성공
- component 수 일치 여부
- net 수 일치 여부
- schematic reopen 가능 여부
- simulation precheck 통과 여부

---

## 6. 자연어 처리 전략

자연어 처리도 한 번에 완전 자유형으로 가면 실패 가능성이 크다.

권장 단계:

### 6.1 1단계: constrained intent

예:

- "48V 입력 buck 컨버터 만들어줘"
- "출력 12V 목표로 boost 회로 생성해줘"
- "half bridge inverter 회로 만들어줘"

이 단계에서는 topology와 주요 파라미터만 추출한다.

### 6.2 2단계: guided slot filling

누락된 필수 값이 있으면 질문을 되묻는다.

예:

- 입력 전압
- 목표 출력 전압
- 스위칭 주파수
- 부하 조건

### 6.3 3단계: free-form to spec

충분한 catalog/validator/generator가 생긴 뒤에만 더 자유로운 자연어를 허용한다.

---

## 7. 구현 우선순위

### P0

- `CircuitSpec` 스키마 정의
- topology generator 계층 추가
- component catalog 도입
- bridge의 component 생성 실패 가시화
- `create_circuit` mock/real 경로 테스트 추가

### P1

- net 기반 연결 모델 도입
- wire 생성 API 연동
- topology별 auto-layout
- 생성 후 reopen 검증

### P2

- guided natural language parsing
- 더 많은 topology 추가
- 설계 규칙 기반 추천값 생성
- 결과 기반 회로 수정 loop

---

## 8. 최소 성공 기준

이 기능이 "확장되었다"고 말하려면 최소 아래가 되어야 한다.

1. `buck`, `boost`, `half_bridge`, `full_bridge` 생성이 Windows real mode에서 성공
2. 생성된 schematic이 실제 PSIM에서 열림
3. 배선이 실제로 연결됨
4. 생성 직후 simulation 실행 가능
5. 실패 시 어느 소자/배선이 실패했는지 응답에 포함됨
6. topology 추가가 템플릿 복붙이 아니라 generator 추가로 가능

---

## 9. 권장 실행 순서

실행 순서는 아래가 가장 안전하다.

1. `CircuitSpec` 정의
2. component catalog 정의
3. topology generator 도입
4. bridge 배선 API 확인 및 연결 구현
5. validation 계층 추가
6. Windows real mode smoke test
7. 자연어 intent parser 정교화

---

## 10. 결론

현재 한정적인 회로 생성 구조를 해결하려면, 템플릿 개수를 늘리는 것만으로는 부족하다.

핵심은 다음 세 가지다.

- 회로를 표현하는 내부 표준 스펙 도입
- topology generator와 validator로 생성 과정을 deterministic 하게 분리
- PSIM bridge를 실제 배선/검증 가능한 실행 엔진으로 강화

즉 이 프로젝트를 다음 단계로 올리려면,
`템플릿 기반 자동화 도구`에서 `검증 가능한 회로 생성 시스템`으로 구조를 바꿔야 한다.
