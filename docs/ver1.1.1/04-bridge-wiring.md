# Step 4: Bridge 배선 API 확인 및 연결 구현

> 우선순위: P0-P1
> 예상 범위: `src/psim_mcp/bridge/bridge_script.py` 보강
> 의존: Step 1 (CircuitSpec의 nets), Step 2 (Component Catalog의 핀 정의)
> 환경 제약: **Windows + PSIM 설치 환경에서만 확인 가능**

---

## 1. 목적

현재 bridge_script의 `handle_create_circuit`에서 **배선(wire) 생성이 실제로 동작하는지 확인하고, 안정적으로 구현**한다.

중요 원칙:

- bridge는 검증되지 않은 자유형 dict를 직접 판단하는 계층이 아니다
- Step 5 validator를 통과한 `CircuitSpec` 또는 그에 준하는 정규화 결과만 bridge에 전달한다
- bridge의 책임은 "PSIM API 실행"과 "실행 결과 보고"에 한정한다
- bridge는 이상적으로 `connections` 원문이 아니라 `wire plan` 또는 동등한 정규화 배선 입력을 받는다

현재 상태:
- 부품 생성(`PsimCreateNewElement`)은 코드가 있으나, 실환경 검증 미완료
- 배선 생성은 `PsimCreateWire`, `PsimConnect` 등 함수명을 탐색하는 코드가 있으나, 실제 API 존재 여부 미확인
- 부품 생성 실패 시 `failed_components` 목록은 반환하도록 개선됨

---

## 2. 확인해야 할 항목

### 2.1 PSIM Python API 함수 목록 확인

Windows에서 아래 스크립트 실행:

```python
from psimapipy import PSIM

p = PSIM("")
print("Valid:", p.IsValid())
print("Functions:", [x for x in dir(p) if not x.startswith("_")])
```

확인할 핵심 함수:
- 스키매틱 생성: `PsimFileNew`
- 부품 생성: `PsimCreateNewElement` (인자 형식 확인)
- 배선 생성: `PsimCreateWire` / `PsimConnect` / 유사 함수
- 파라미터 설정: `PsimSetElmValue`
- 파일 저장: `PsimFileSave`

### 2.2 "Save as Python Code" 분석

PSIM GUI에서:
1. 간단한 회로(Buck 컨버터) 생성
2. File → Save as Python Code
3. 생성된 Python 코드에서 배선 관련 호출 패턴 확인

이 코드가 **배선 API의 정확한 사용법**을 보여준다.

### 2.3 부품 생성 시 element type 확인

`PsimCreateNewElement`의 첫 번째 인자로 전달해야 할 정확한 type 문자열 확인:
- "V_DC"? "DCSource"? "VDC"?
- "MOSFET"? "Sw_MOSFET"?

---

## 3. 배선 구현 방향

### 3.1 확인 결과에 따른 분기

**Case A: 배선 함수가 존재하는 경우**
```python
# 예상 패턴 (Save as Python Code에서 확인)
p.PsimCreateWire(sch, x1, y1, x2, y2)
# 또는
p.PsimConnect(sch, elem1, pin1, elem2, pin2)
```
→ net 기반으로 핀 좌표 계산 후 배선

**Case B: 배선 함수가 없는 경우**
→ 부품을 핀 좌표가 겹치도록 배치하여 자동 연결 유도
→ 또는 PSIM COM/DDE 인터페이스 탐색

### 3.2 net → wire 변환

CircuitSpec의 net:
```json
{"name": "SW_NODE", "pins": ["SW1.source", "D1.cathode", "L1.input"]}
```

변환 과정:
1. 각 pin의 소속 element와 핀 위치 계산
2. net 내 모든 핀을 star 또는 chain 방식으로 연결
3. wire 좌표 생성 (Manhattan routing)

입력 계약 정리:

- validator/generator 단계까지는 `nets`
- bridge 직전 정규화 단계에서는 `wire_plan`
- bridge는 `wire_plan`을 실행만 함

예:

```json
{
  "net": "SW_NODE",
  "segments": [
    {"from": "SW1.source", "to": "D1.cathode"},
    {"from": "SW1.source", "to": "L1.input"}
  ]
}
```

---

## 4. 실패 처리 강화

### 4.1 부품 생성 실패

현재: `failed_components` 목록 반환 (구현 완료)

추가:
- 전체 요청 대비 성공률 계산
- 성공률 50% 미만 시 전체 실패 처리 (부분 생성된 파일 삭제)

### 4.2 배선 실패

추가:
- `failed_connections` 목록에 실패 사유 포함
- 배선 실패 시에도 부품만 있는 파일은 저장 (사용자가 수동으로 배선 가능)
- 응답에 `wiring_complete: true/false` 플래그 추가

### 4.3 생성 후 검증

저장 후 아래 확인:
- 파일 존재 여부
- 파일 크기 > 0
- (가능하면) reopen 시도하여 element 수 확인

---

## 5. 구현 범위

### 파일 수정
- `src/psim_mcp/bridge/bridge_script.py`
  - `handle_create_circuit`: 배선 로직 보강
  - 부품 type 매핑 추가 (kind → PSIM element type)
  - 생성 후 검증 로직 추가
  - 입력은 정규화된 `CircuitSpec` 변환 결과만 받도록 단순화

### 파일 생성 (선택)
- `src/psim_mcp/bridge/wiring.py`: 배선 좌표 계산 로직 분리

---

## 6. 테스트 계획

### Mac (mock)
- net 기반 배선 의도가 정확히 전달되는지 확인
- failed_connections 반환 형식 확인
- 성공률 기반 전체 실패 로직 확인
- wire_plan 변환 결과가 deterministic 한지 확인

### Windows (real) — 핵심
- buck 컨버터 생성 → PSIM에서 열기 → 부품 존재 확인
- 배선 연결 여부 확인
- 생성 직후 시뮬레이션 실행 가능 여부 확인
- 부품 5개 이상 회로 생성 테스트

---

## 7. 완료 기준

- [x] `bridge/wiring.py` 구조 생성 (nets_to_wire_plan, resolve_pin_position 스텁)
- [ ] PSIM Python API 함수 목록 문서화 (Windows 필요)
- [ ] "Save as Python Code" 패턴 분석 완료 (Windows 필요)
- [ ] 배선 생성 로직 구현 (API 존재 시) (Windows 필요)
- [ ] 배선 실패 시 graceful 처리 (Windows 필요)
- [ ] 생성 후 검증 로직 추가 (Windows 필요)
- [ ] Windows에서 buck 컨버터 생성 + 열기 성공
- [ ] Windows에서 생성 후 시뮬레이션 실행 성공
