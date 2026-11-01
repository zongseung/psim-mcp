# PSIM 함정 사전

모르면 조용히 틀리는 것들. PSIM 2026 / psimapipy 기준, 이 저장소에서 실측 검증된 사실만 기록.

## 파라미터 이름 — 조용한 no-op이 최대 함정

PSIM은 존재하지 않는 파라미터 이름을 받으면 **에러 없이 무시하고 기본값을 유지**한다.

| 소자 | 틀리기 쉬운 이름 | 올바른 PSIM 이름 |
|---|---|---|
| VDC/VAC 소스 | `V1` | `Amplitude` (2026 기준, `V1`은 조용히 무시됨) |
| AC 소스 주파수 | `Frequency` | `Freq` |
| 트랜스포머 권선비 | `Ratio` | **무시됨** — `Np__primary_` / `Ns__secondary_` 사용 |
| 트랜스포머 자화 인덕턴스 | `Lm` | `Lm__magnetizing_` |
| IGBT 온저항 | `On_Resistance` | `R_transistor` (MOSFET은 `On_Resistance`가 맞음) |
| 시뮬 시간 | `TOTALTIME`/`TIMESTEP` | SimControl 소자의 `TotalTime`/`TimeStep` |

**검증 방법**: `set_parameter` 후 `import_circuit`으로 다시 읽어 값이 실제로
바뀌었는지 확인한다. 값이 그대로면 파라미터 이름이 틀린 것.

### 기존 회로 수정(`PsimSetElmValue2`)의 이름 규칙 — 2026.1 실측

- 수정 경로는 `PsimGetElementList`의 **표시 이름**(`On Resistance`, `Init. Cap. Voltage`, `No. of Points`)과
  **실제 Type**(`MOSFET`, `C`, `L`)만 받는다. 생성용 이름(`On_Resistance`)이나 `MULTI_MOSFET`을 넘기면
  **False를 반환**하고 stdout에 `Unable to update element...`를 찍는다(예외 없음).
- `import_circuit` 이름은 표시 이름에서 영문·숫자 외 문자를 `_`로 바꾼 것이다(`Init. Cap. Voltage` → `Init__Cap__Voltage`).
- `set_parameter`는 두 형식을 모두 받아 소자의 실제 이름으로 해석한다. 없으면 `PARAMETER_NOT_FOUND`(실제 이름 목록),
  여러 개와 맞으면 `AMBIGUOUS_PARAMETER`, PSIM이 거부하면 `PARAMETER_REJECTED`(PSIM 출력 포함).
- 위 표의 `On_Resistance` 등은 **새 소자 생성**(`PsimCreateNewElement`) 기준 이름이다.

## C-Block (CBLOCK)

- C 소스 코드는 `CONTENT` 파라미터다: `set_parameter(component_id="SCB1", parameter_name="CONTENT", value="...C코드...")`
- 생성 파라미터가 아니라 별도 설정 경로(`PsimSetElmValue2`)로 들어간다 — 도구가 알아서 처리하므로 파라미터 이름만 `CONTENT`로 주면 된다.

## PSIM 네이티브 소자 규칙

- 소자 타입은 `MULTI_*` (예: `MULTI_MOSFET`, `MULTI_RESISTOR`)
- `PORTS`는 Python 리스트여야 함 (문자열 아님)
- `SubType="Ideal"` 필요

## 저장/실행 동작

- `set_parameter`는 **즉시 파일에 저장**한다 (`PsimFileSave`). 되돌리려면 백업본에서 복원.
- 시뮬 결과 파형은 `.smv` 파일 — 직접 파싱하지 말고 `analyze_existing`/`export_results`를 쓴다.

## simview 플래그 — 2026.1 실측 (2026-11-01)

| 호출 | `Simview` 값 | `.smv` 쓰기 | 메모리 그래프 | Simview 창 |
|---|---|---|---|---|
| `PsimSimulate` | 생략 / 1 / 2 | O | O | **뜸**(호출 ~0.3 s) |
| `PsimSimulate` | 0 | O | O | 안 뜸 |
| `PsimSimulate` | -1 | **안 씀** | O | 안 뜸 |
| `SimulateData` + `PsimASimulate` | 아무 값 | O | O | 안 뜸 |

- `PsimSimulate`에서 `Simview`를 **생략하면 뷰어가 뜬다.** 자동 실행은 반드시 `Simview=0`.
- `SimulateData_from_kwargs`는 `Simview`를 내부 `SimviewFlag`로 바꾼다(-1→5, 0→1, 그 외·생략→0).
  `PsimASimulate` 경로는 플래그와 무관하게 항상 `.smv`를 쓰고 뷰어는 띄우지 않는다(5도 씀, 문서와 다름).
- Simview가 이미 떠 있으면 새 프로세스를 띄우지 않고 기존 창을 쓴다. 프로세스 목록으로 뷰어 실행
  여부를 판정하면 틀릴 수 있다.
- 이 서버의 정책: `run_batch`·병렬 스윕·`vault_edit_and_run`·`optimize_circuit`은 뷰어를 띄우지 않는다.
  파형 창이 필요하면 `open_in_viewer`로 결과 파일 하나만 연다. 기존 `run_simulation`은 기본값
  `simview=true`(뷰어 뜸)이고, 순차 `sweep_parameter`도 이 기본값으로 실행된다.

## 변수 덮어쓰기와 병렬 실행

- `PsimSimulate(..., Lx="0.002")` 같은 kwargs 덮어쓰기는 **회로가 참조하는 변수에만** 효과가 있다.
  `L1` Inductance가 숫자(`0.002`)로 적혀 있으면 덮어쓰기가 조용히 무시된다.
  `run_batch`는 점 없는 키를 변수로 보고 회로가 참조하지 않으면 실행 전에 거부한다.
  숫자 소자 값은 `L1.Inductance` 형식으로 넘기면 run 폴더에 회로 사본을 만들어 수정한다.
- `PSIM()` 생성은 약 17초 걸린다. 병렬 워커는 한 번 띄워 재사용하고, 일정 시간 안 쓰면 종료한다.
- 동시 실행 수는 물리 코어 수가 기준이다. 논리 스레드 수만큼 올리면 실행 1건이 2배 이상 느려져
  처리량이 오히려 낮다(실측: 6코어/12스레드에서 동시 6 = 82.9 runs/min, 12 = 72.6).
- `PsimASimulate`는 한 프로세스 안에서 최대 1.8배에서 포화하고, 끝날 때까지 결과를 주지 않으며,
  짧은 시뮬레이션은 내부 100 ms 폴링에 묶인다. 이 서버는 쓰지 않는다.

## 시뮬레이션 시간 설정

- 정착(settling)을 보려면 TOTALTIME을 충분히: buck 계열은 1ms로는 부족, 50ms에서 정착 확인됨.
- time step은 스위칭 주파수를 해상할 수 있어야 한다. 의심되면 dt를 줄여 결과가 변하는지 확인.
