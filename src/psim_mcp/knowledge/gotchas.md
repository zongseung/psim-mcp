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

## 시뮬레이션 시간 설정

- 정착(settling)을 보려면 TOTALTIME을 충분히: buck 계열은 1ms로는 부족, 50ms에서 정착 확인됨.
- time step은 스위칭 주파수를 해상할 수 있어야 한다. 의심되면 dt를 줄여 결과가 변하는지 확인.
