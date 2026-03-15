# Step 13: PSIM Element Type Mapping Plan

> 우선순위: P0  
> 환경 제약: **Windows + PSIM + Save as Python Code 필수**  
> 목적: `component_library.py`의 `psim_element_type`를 실제 PSIM element name으로 확정

---

## 1. 배경

현재 `psim_element_type`는 더 이상 빈 문자열은 아니지만, 대부분 canonical component type을 그대로 사용한다.

예:

- `Resistor -> Resistor`
- `DC_Source -> DC_Source`
- `MOSFET -> MOSFET`

이 값이 실제 PSIM 생성 타입과 다르면:

- `PsimCreateNewElement()`가 실패하거나
- 다른 소자가 생성되거나
- 특정 파라미터가 먹지 않을 수 있다

즉 지금 상태는 “빈 값은 아님”이지만, 아직 실측 매핑은 아니다.

---

## 2. 목표

이 단계의 목표는 `COMPONENTS`의 주요 부품에 대해 아래를 확정하는 것이다.

1. logical type
2. 실제 PSIM element type
3. 지원 파라미터 이름
4. 지원 핀 이름
5. 생성 성공 여부

최소 1차 범위:

- `DC_Source`
- `Resistor`
- `Inductor`
- `Capacitor`
- `Diode`
- `MOSFET`

2차 범위:

- `Battery`
- `PV_Panel`
- `Transformer`
- `Current_Probe`
- `Voltage_Probe`

---

## 3. 확인 방법

### 3.1 수동 회로 생성 후 Save as Python Code 분석

각 부품에 대해 아래 절차를 수행한다.

1. PSIM에서 빈 schematic 생성
2. 대상 부품 1개 배치
3. 필요하면 최소 파라미터 1개 수정
4. Save as Python Code 수행
5. 생성된 Python 코드에서 element 생성 라인 확인

기록해야 할 정보:

- PSIM GUI 표시 이름
- Save as Python Code에 나타난 생성 타입 문자열
- 파라미터 이름
- 파라미터 설정 방식

### 3.2 bridge 직접 생성 테스트

가능하면 각 부품을 bridge 경로로도 생성한다.

입력 예시:

```json
{
  "id": "R1",
  "type": "Resistor",
  "psim_element_type": "확인된 실제 타입",
  "parameters": {"resistance": 10.0},
  "position": {"x": 100, "y": 100}
}
```

확인 항목:

- 생성 성공 여부
- 저장 성공 여부
- PSIM에서 파일 오픈 가능 여부

---

## 4. 매핑 테이블 작성 기준

작성 포맷 예시:

| logical type | psim_element_type | status | notes |
|---|---|---|---|
| `Resistor` | `Resistor` | confirmed | Save as Python Code 일치 |
| `DC_Source` | `DCSource` | confirmed | 코드 기준 실명 사용 |
| `MOSFET` | `PowerMOSFET` | pending | GUI 이름과 다를 수 있음 |

상태 규칙:

- `confirmed`: Windows에서 실제 확인 완료
- `assumed`: 아직 실측 전
- `unsupported`: 생성 실패 또는 사용 불가

---

## 5. 코드 반영 원칙

확인 후에는 아래 원칙으로 반영한다.

1. `component_library.py`에 실측값 반영
2. `resolve_psim_element_type()`는 fallback으로만 유지
3. confirmed 부품은 모두 명시값 사용
4. 미확인 부품만 fallback 허용

즉 최종 상태는:

```text
confirmed component -> explicit PSIM type
unknown component -> fallback to logical type
```

---

## 6. 우선 반영 대상

첫 번째 커밋 범위는 아래 6개만으로 제한하는 것이 좋다.

1. `DC_Source`
2. `Resistor`
3. `Inductor`
4. `Capacitor`
5. `Diode`
6. `MOSFET`

이 6개만 정확해도:

- buck
- boost
- buck_boost

자동 생성 경로는 실환경 검증이 가능해진다.

---

## 7. 실패 시 처리 기준

부품별로 아래 중 하나로 분류한다.

1. `confirmed`
2. `assumed`
3. `unsupported`

규칙:

- 생성 실패 시 억지로 매핑하지 않는다
- GUI 이름과 Save as Python Code 이름이 다르면 실측명을 우선한다
- 파라미터 이름도 함께 기록한다

---

## 8. 산출물

이 단계가 끝나면 남아야 할 산출물:

1. 부품별 매핑표
2. Save as Python Code 스크린샷 또는 코드 발췌
3. component library 반영 커밋
4. smoke test 결과

권장 결과 문서:

- `docs/ver1.1.1/13-psim-element-type-results.md`

---

## 9. 완료 기준

- [ ] 1차 대상 6개 부품의 실제 PSIM element type 확인
- [ ] `component_library.py`에 confirmed 값 반영
- [ ] bridge 경로로 1차 대상 생성 확인
- [ ] buck/boost/buck_boost 생성 smoke test 재실행
- [ ] 결과 문서 작성
