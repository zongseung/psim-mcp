# PSIM 튜토리얼/예제 코드 의존 현황 검토

작성일: 2026-03-24

## 목적

현재 `psim-mcp`가 회로를 구성할 때 PSIM 튜토리얼/예제 코드 또는 예제 `.psimsch` 파일을 얼마나 참고하거나 직접 의존하는지, 현재 코드 기준으로 구체적으로 확인한다.

이 문서는 아래를 구분해서 본다.

- `참고 기반 의존`: 예제에서 추출한 레이아웃/PORTS/DIR 규칙을 코드에 반영한 경우
- `런타임 직접 의존`: 실행 중 예제 `.psimsch` 파일을 실제로 복사하거나 열어 쓰는 경우
- `현재 활성도`: 구현은 있으나 실제 활성 경로로 자주 쓰이는지 여부

## 결론 요약

현재 코드는 분명히 PSIM 튜토리얼/예제 코드에 강하게 영향을 받았다.
다만 현재 주 경로는 `예제 파일을 직접 열어서 쓰는 방식`보다는 `예제에서 추출한 패턴을 generator/layout/bridge에 하드코딩한 방식`에 더 가깝다.

정리하면:

- `generator/layout/bridge`는 PSIM example 또는 `PsimConvertToPython` 결과를 참고해 구현된 흔적이 매우 명확하다.
- `bridge`에는 예제 `.psimsch`를 복사하는 template mode가 아직 남아 있다.
- 하지만 현재 generator 코드들에서 `psim_template`를 직접 반환하는 흔적은 보이지 않아, template-copy 경로가 현재 주 생성 경로라고 보기는 어렵다.

## 1. 참고 기반 의존: 현재도 매우 강함

### 1.1 LLC generator는 예제 변환 코드 기반임이 명시돼 있음

파일:

- `src/psim_mcp/generators/llc.py`

확인 내용:

- 파일 헤더에 `Layout verified against PSIM reference: converted_ResonantLLC_CurrentAndVoltageLoop.py`라고 직접 적혀 있다.
- 본문 주석에도 `Layout based on PSIM reference (converted_ResonantLLC_CurrentAndVoltageLoop.py)`라고 명시돼 있다.
- `TF_IDEAL`, `Lm`의 병렬 배치, `BDIODE1` 사용 방식까지 예제 변환 코드의 좌표/구조를 근거로 설명한다.

판단:

- LLC topology는 단순히 이론식만 구현한 것이 아니라, PSIM reference example에서 레이아웃 패턴을 뽑아와 generator에 반영한 구조다.

### 1.2 Boost PFC도 예제 변환 코드 패턴을 기준으로 함

파일:

- `src/psim_mcp/generators/boost_pfc.py`

확인 내용:

- 파일 헤더에 `Layout verified against PSIM reference`라고 적혀 있고,
  `converted_3-ph_PWM_rectifier_with_PFC.py`, `converted_ResonantLLC`를 명시적으로 언급한다.
- 다이오드 브리지와 `BDIODE1` 사용 패턴이 reference 기반이라고 적혀 있다.

판단:

- Boost PFC 역시 “순수 자작 레이아웃”이라기보다 PSIM 예제의 배치/포트 패턴을 참고한 구현이다.

### 1.3 Flyback / Forward는 TF_1F_1 reference 패턴을 기반으로 함

파일:

- `src/psim_mcp/generators/flyback.py`
- `src/psim_mcp/generators/forward.py`

확인 내용:

- `flyback.py`에 `Layout verified against PSIM reference (converted_Flyback_converter_with_peak_current_mode_control.py)`가 직접 적혀 있다.
- `forward.py`에도 `Layout verified against PSIM TF_1F_1 reference (same base as flyback)`라고 적혀 있다.
- 둘 다 `TF_1F_1 PORTS` 배열 순서와 좌표 패턴을 주석으로 명시하고 그 형식대로 회로를 만든다.

판단:

- 절연형 transformer topology 구현은 PSIM reference의 포트 구조를 직접 참조해 굳혀진 상태다.

### 1.4 layout helper 자체가 예제 기반 factory 역할을 하고 있음

파일:

- `src/psim_mcp/generators/layout.py`

확인 내용:

- `make_capacitor_h()` 주석: `Reference: converted_ResonantLLC Cs ...`
- `make_transformer()` 주석: `converted_Flyback_converter_with_peak_current_mode_control.py`
- `make_ideal_transformer()` 주석: `Reference: converted_ResonantLLC ...`
- `make_diode_bridge()` 주석: `Reference: converted_ResonantLLC BDIODE1 ...`

판단:

- generator 개별 파일뿐 아니라 공통 layout helper도 PSIM converted example을 근거로 만든 재사용 팩토리다.
- 즉 예제 참조가 특정 topology 하나에만 국한되지 않는다.

### 1.5 bridge도 PsimConvertToPython 결과를 기준으로 맵핑함

파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인 내용:

- 헤더 주석에 `PSIM 2026 API 기준 (PsimConvertToPython 출력 기반)`이라고 적혀 있다.
- `_PSIM_TYPE_MAP` 앞에도 `PSIM's PsimConvertToPython output reveals...`라는 설명이 있다.
- `_PARAM_NAME_MAP`, `_FALLBACK_PORT_PIN_GROUPS`도 같은 맥락의 bridge-side 규약 구현이다.

판단:

- bridge는 예제 레이아웃보다 한 단계 더 저수준에서, PSIM API 사용법 자체를 converted output을 기준으로 안정화한 구조다.

## 2. 런타임 직접 의존: template mode는 아직 남아 있음

### 2.1 bridge에는 예제 `.psimsch` 복사 모드가 구현돼 있음

파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인 내용:

- `_handle_template_circuit(psim_template, save_path)`가 존재한다.
- 이 함수는 `psim_template["source"]`를 읽고, `PSIM_PATH` 아래의 example 파일을 실제로 찾아 `save_path`로 복사한다.
- 이후 `PsimSetElmValue2`, `PsimSetElmValue`로 parameter와 simulation override를 적용한다.
- `handle_create_circuit()` 안에서도 `psim_template`가 오면 일반 create path 대신 바로 template mode로 빠진다.

판단:

- 구현 차원에서는 “예제 `.psimsch`를 직접 복사해 회로를 만드는 모드”가 분명히 존재한다.
- 즉 런타임 직접 의존 경로는 제거되지 않았다.

### 2.2 service / adapter도 template mode를 통과시킬 수 있게 되어 있음

파일:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/adapters/real_adapter.py`

확인 내용:

- `_try_generate()`는 `gen_result.get("psim_template")`를 반환하도록 되어 있다.
- preview 저장 시에도 `psim_template`를 store에 넣는다.
- confirm/create 시 real adapter가 `psim_template`를 bridge로 전달할 수 있다.

판단:

- application service 계층도 template-copy mode를 공식 경로로 지원한다.

## 3. 그런데 현재 “주 경로”는 무엇인가

### 3.1 현재 generator 코드들에서 `psim_template` 반환 흔적은 보이지 않음

확인 방법:

- `src/psim_mcp/generators`
- `src/psim_mcp/data`

확인 내용:

- 현재 코드 검색 기준으로 generator/data 쪽에서 `psim_template`를 직접 정의하거나 반환하는 코드는 보이지 않았다.

판단:

- template mode 인프라는 남아 있지만, 지금 활성 generator들이 그 경로를 기본적으로 쓰고 있다고 보기는 어렵다.
- 현재 자주 쓰이는 topology들은 대체로 `components + nets`를 직접 생성하는 generator 경로를 사용한다.

### 3.2 현재 preview/create의 일반 경로는 generator -> routing -> renderer/bridge 구조임

파일:

- `src/psim_mcp/services/circuit_design_service.py`
- `src/psim_mcp/routing/router.py`
- `src/psim_mcp/utils/svg_renderer.py`

확인 내용:

- generator가 `components + nets`를 반환
- service가 `connections + wire_segments`로 정규화
- SVG renderer와 bridge가 그 결과를 소비

판단:

- 현재 시스템의 중심은 “예제 파일 복사”보다 “예제에서 추출한 규칙으로 회로를 재구성하는 코드 생성”이다.

## 4. 현재 구조를 어떻게 봐야 하나

이 프로젝트는 지금 아래 두 모델이 공존한다.

### 모델 A. Example-derived code generation

특징:

- 예제 튜토리얼/converted output에서 PORTS, DIR, 배치 패턴을 추출
- 그 패턴을 generator/layout/bridge 코드에 내재화
- 실행 시에는 그 규칙으로 새 회로를 구성

현재 활성도:

- 높음

대표 파일:

- `llc.py`
- `flyback.py`
- `forward.py`
- `boost_pfc.py`
- `layout.py`
- `bridge_script.py`

### 모델 B. Template-copy generation

특징:

- PSIM 설치 경로 아래 example `.psimsch`를 직접 복사
- 일부 parameter만 override

현재 활성도:

- 구현은 존재
- 현재 generator 코드 기준으로 적극적으로 사용되는 흔적은 약함

대표 파일:

- `bridge_script.py`
- `circuit_design_service.py`
- `real_adapter.py`

## 5. 리스크 평가

### 5.1 장점

- PSIM이 실제로 받아들이는 PORTS/DIR/element type 패턴을 그대로 학습해서 쓸 수 있다.
- 이론적으로 맞는 회로보다 “PSIM에서 실제로 열리고 동작하는 회로”를 만드는 데 유리하다.
- bridge 구현의 안정성을 높인다.

### 5.2 단점

- 예제의 배치 감각과 한계를 그대로 끌고 오기 쉽다.
- generator가 특정 example layout에 과도하게 묶이면 일반화가 어렵다.
- 예제에서 가져온 좌표/포트 패턴이 늘 “가독성 좋은 회로도”를 보장하지는 않는다.
- template mode가 다시 활성화되면 PSIM 설치 경로/예제 파일 구조 변화에 취약하다.

## 6. 최종 판단

질문에 대한 가장 정확한 답은 다음이다.

> 현재 코드는 PSIM 튜토리얼/예제 코드를 분명히 참고하고 있으며,
> 그 영향은 generator/layout/bridge 전반에 남아 있다.
> 다만 현재의 주 생성 경로는 예제 `.psimsch`를 직접 복사하는 방식보다는,
> 예제에서 추출한 레이아웃/PORTS/API 패턴을 코드로 재구성하는 방식이다.

즉:

- `예제 참고`: 맞다
- `예제 파일 직접 의존`: 경로는 남아 있다
- `현재 주 경로가 예제 복사냐`: 그렇다고 보기는 어렵다

## 7. 권장 후속 작업

1. topology별로 `reference-derived pattern`과 `runtime template dependency`를 명시적으로 분리한다
2. generator가 어떤 example에서 어떤 PORTS/DIR 규칙을 가져왔는지 메타데이터로 남긴다
3. template-copy mode가 실제로 안 쓰인다면 deprecated 여부를 결정한다
4. example 기반 좌표 패턴과 “회로도 가독성용 레이아웃 규칙”을 분리한다
5. bridge의 API 매핑은 유지하되, generator 좌표/배치 hardcoding은 점진적으로 일반화한다
