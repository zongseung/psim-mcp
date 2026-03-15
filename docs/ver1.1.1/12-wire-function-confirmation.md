# Step 12: Windows Wire Function Confirmation

> 우선순위: P0  
> 환경 제약: **Windows + PSIM + psimapipy 필수**  
> 목적: `bridge_script.py`의 배선 함수 추측 로직을 실제 PSIM 계약으로 교체

---

## 1. 배경

현재 bridge는 배선 함수명을 아래 후보로 탐색한다.

- `PsimCreateWire`
- `PsimConnect`
- `PsimCreateNewWire`

이 구조는 개발 단계에서는 유용하지만, 운영 기준으로는 아직 계약이 닫히지 않은 상태다.  
Windows 실환경에서 실제 함수명과 시그니처를 확인해 기본 경로를 확정해야 한다.

---

## 2. 목표

이 단계의 목표는 두 가지다.

1. **실제 배선 함수명을 확정**
2. **필요한 인자 형식과 호출 순서를 문서화**

최종적으로는:

- bridge의 기본 wire function을 1개로 고정하거나
- PSIM 버전별 분기 규칙을 문서화하고
- `PSIM_WIRE_FUNCTION`은 예외 대응용 override로만 남긴다

---

## 3. 확인 대상

반드시 확인할 항목:

1. 함수명
2. 호출 주체
3. 인자 개수
4. 인자 의미
5. element handle 기반인지, pin/좌표 기반인지
6. 호출 성공 시 반환값
7. 실패 시 예외/반환 패턴

예시 확인 포맷:

```text
Function name: PsimConnect
Call shape: PsimConnect(schematic, from_element, to_element)
Pin support: no / yes
Return value: bool / handle / None
Failure mode: exception / False / silent no-op
```

---

## 4. 수행 절차

### 4.1 psimapipy 함수 목록 덤프

Windows에서 아래를 먼저 실행한다.

```python
from psimapipy import PSIM

p = PSIM("")
print("IsValid:", p.IsValid())
for name in dir(p):
    if "wire" in name.lower() or "connect" in name.lower():
        print(name)
```

기록할 것:

- wire/connect 관련 함수 전체 목록
- 이름 패턴
- 후보 외 함수 존재 여부

### 4.2 Save as Python Code 분석

PSIM GUI에서 아래 회로를 직접 만든다.

1. DC Source 1개
2. Resistor 1개
3. 두 소자 연결

그 후 `Save as Python Code`를 수행해 생성 코드를 확인한다.

반드시 기록:

- 실제 wire 생성 함수명
- 함수 호출 순서
- element 생성 후 어떤 값이 wire 호출로 전달되는지
- pin 개념이 코드에 드러나는지 여부

### 4.3 bridge 단독 확인

다음 3개를 각각 테스트한다.

1. 함수 후보 자동 탐색
2. `PSIM_WIRE_FUNCTION` 강제 지정
3. 잘못된 override 지정

기대 결과:

- 올바른 함수는 연결 성공
- 잘못된 override는 명확한 에러/실패 정보 반환

---

## 5. 테스트 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| W1 | 후보 함수 목록 조회 | 관련 함수명 확보 |
| W2 | 수동 회로 Save as Python Code 분석 | 실제 함수명 확인 |
| W3 | bridge 자동 탐색으로 연결 | 연결 성공 |
| W4 | `PSIM_WIRE_FUNCTION`으로 동일 함수 지정 | 연결 성공 |
| W5 | 잘못된 override 지정 | 실패 사유에 `configured wire function not found` 포함 |
| W6 | 생성된 `.psimsch`를 PSIM에서 열기 | 회로 파일 정상 오픈 |

---

## 6. 코드 반영 원칙

확인 후 코드에 반영할 원칙:

1. 기본 함수명은 상수 1개로 고정
2. 후보 탐색은 필요 시 보조 fallback로만 유지
3. `PSIM_WIRE_FUNCTION`은 운영/디버깅 override로 유지
4. 결과 payload에 `wire_function`을 계속 포함

권장 상태:

```text
기본 경로: 확정 함수 1개
보조 경로: optional fallback
예외 경로: env override
```

---

## 7. 산출물

이 단계가 끝나면 남아야 할 산출물:

1. 확인된 함수명 기록
2. 호출 예제 코드
3. 성공/실패 스크린샷
4. PSIM 버전 정보
5. bridge 기본 함수명 변경 커밋

권장 파일:

- `docs/ver1.1.1/12-wire-function-results.md`

---

## 8. 완료 기준

- [ ] Windows에서 wire/connect 관련 함수 목록 확보
- [ ] Save as Python Code에서 실제 배선 함수 확인
- [ ] `PSIM_WIRE_FUNCTION` override 동작 확인
- [ ] 잘못된 override 실패 경로 확인
- [ ] 기본 wire function 고정 여부 결정
- [ ] 결과 문서 작성

