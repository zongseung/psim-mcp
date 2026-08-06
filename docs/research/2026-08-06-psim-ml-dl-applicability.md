# PSIM-MCP 머신러닝·딥러닝 적용 가능성 조사

- 조사일: 2026-08-06
- 범위: 임의 회로 생성은 제거하고 기존 회로의 `import -> edit -> simulate -> analyze`에 집중한다.
- 근거 정책: Altair 공식 문서/API, 원 논문, 저자·프로젝트의 공식 코드와 데이터만 핵심 근거로 사용했다.

## 결론

PSIM-MCP에 ML을 적용할 수는 있지만, 현재 가장 타당한 범위는 **한 회로·소수 파라미터·스칼라 metric에 대한 불확실성 포함 surrogate/후보 순위화**이며 타당성은 **중간(조건부)**이다. PSIM 실행이 충분히 비싸고 같은 회로에서 반복 평가가 많을 때만 규칙·직접 최적화보다 이득이 생긴다. Bayesian optimization은 비싼 black-box 평가를 적게 쓰는 문제를 위해 설계되었고, 공식 BoTorch 설명도 이 조건을 명시한다([BoTorch 2026 개요](https://botorch.org/docs/v0.17.2/overview), [원 논문](https://proceedings.neurips.cc/paper/2020/hash/f5b1b89d98b7286673128a5fb112cb9a-Abstract.html)).

현재 **딥러닝 타당성은 낮음**이다. 독립적인 회로·운전조건·고장 라벨이 없고, 스칼라 metric은 저차원 GP나 응답면으로 충분할 가능성이 크다. 신경 연산자처럼 파형 전체를 대체하는 방법은 실제 연구 분야이지만 별도의 대규모 함수-대-함수 학습 문제다([NeuralOperator 공식 구현](https://github.com/neuraloperator/neuraloperator), [DeepONet 원 논문·코드](https://github.com/lululxvi/deeponet)). 지금 이를 제품에 넣으면 PSIM 검증 seam을 강화하기보다 새 미검증 simulator를 만드는 셈이다.

따라서 첫 투자는 모델 기능이 아니라 **재현 가능한 simulation evidence ledger**여야 한다. 아래의 작은 GP PoC가 엄격한 중단 기준을 통과할 때만 advisory 기능을 검토하며, 모든 최종 판단은 계속 PSIM으로 재검증한다. 현 단계에 **높음**으로 평가할 ML/DL 제품 기능은 없다.

## 현재 제품과 데이터 seam

[기존 회로 중심 로드맵](../superpowers/specs/2026-08-05-generation-removal-existing-circuit-roadmap-design.md)은 `import_circuit -> prepare_edit -> set_parameter -> import_circuit -> run_simulation/analyze_existing`를 조합형 경계로 고정한다. 현재 저장소에도 다음 입출력 seam이 있다.

| 단계 | 현재/승인된 seam | ML 데이터 역할 |
|---|---|---|
| 구조 읽기 | [`ProjectService.import_circuit`](../../src/psim_mcp/services/project_service.py), [`CircuitGraph`](../../src/psim_mcp/synthesis/graph.py) | 회로 SHA-256, graph version, component/net 요약을 dataset provenance로 사용 |
| 안전한 변경 | 승인된 `prepare_edit`, [`ParameterService.set_parameter`](../../src/psim_mcp/services/parameter_service.py) | 입력 `X`: 검증된 작업 사본의 numeric parameter와 단위 |
| ground truth 실행 | [`SimulationService.run_simulation`](../../src/psim_mcp/services/simulation_service.py), [`RealPsimAdapter.run_simulation`](../../src/psim_mcp/adapters/real_adapter.py) | 실행 옵션, 성공/실패, wall time, 결과 artifact |
| 파형 | [`RealPsimAdapter.extract_signals`](../../src/psim_mcp/adapters/real_adapter.py) | 정렬된 시간축과 선택한 전압·전류 파형 |
| label/응답 | [`RealPsimAdapter.compute_metrics`](../../src/psim_mcp/adapters/real_adapter.py) | `Y`: ripple, peak, settling, efficiency 등 버전이 고정된 scalar metric |

Altair의 공식 PSIM/Compose API 표면은 이 seam과 맞는다. 2026 Compose 문서는 `PsimFileOpen/Save`, `PsimSetElmValue`, `PsimSimulate/PsimASimulate`, `PsimReadGraphFile`을 PSIM 명령으로 열거하고([Compose 2026 PSIM 명령 색인](https://help.altair.com/compose/help/en_us/indexTerms.htm)), 최초 공개 릴리스 노트는 단일·복수 simulation에 선택 parameter를 넘기고 graph 파일을 읽고 쓸 수 있다고 명시한다([Compose 2022.3 릴리스 노트](https://2022.help.altair.com/2022.3/compose/Compose_2022.3_ReleaseNotes_English.pdf)). 즉, ML 학습용 입력 변경과 label 수집은 기술적으로 가능하다. 다만 공개 웹 문서가 저장소에서 쓰는 모든 설치형 Python 함수의 정확한 signature를 노출하지는 않으므로, 설치된 PSIM 버전별 contract test가 필요하다.

PSIM 공식 Script Tool tutorial은 blocking `Simulate`, asynchronous `ASimulate`, `.txt`/binary `.smv`, `GraphRead/GraphWrite`를 구분한다([공식 Script Functions tutorial](https://2023.help.altair.com/psim-tut/tutorials/Tutorial%20-%20How%20to%20Use%20Script%20Functions.pdf)). 결과를 즉시 label로 소비하는 기본 수집 경로는 blocking 호출을 사용하고, asynchronous/parallel 실행은 완료·artifact·license를 추적하는 별도 orchestration이 있을 때만 사용해야 한다.

## 실제 적용 후보와 타당성

| 문제 | 입출력 | ML이 이길 조건 | 타당성 |
|---|---|---|---|
| 동일 회로의 scalar metric surrogate와 후보 순위화 | `X`: 2~6개 검증 parameter·운전조건; `Y`: PSIM metric과 성공 여부 | 한 번의 PSIM 실행이 비싸고 동일 domain에서 수십~수백 번 더 물을 때; 비선형 상호작용이 저차원 공식/응답면보다 클 때 | **중간** |
| 측정 파형에 맞춘 파라미터 calibration | `X`: 부품·제어 parameter; `Y`: PSIM 파형과 측정 파형의 정렬된 오차 | 측정 데이터, 시간 정렬, 센서 오차 모델이 있고 직접 least-squares/진화 최적화가 평가 budget을 과소비할 때 | **중간-낮음** |
| 고장/이상 파형 triage | `X`: 다채널 파형과 운전조건; `Y`: 정상/고장 종류·위치 | 다양한 부하·온도·센서·고장 강도의 독립 라벨과 HIL/실측 외부 검증이 있을 때 | **현재 낮음**, 데이터 확보 후 중간 |
| 파형 전체 neural surrogate/operator | `X`: parameter와 초기/경계조건; `Y`: 시간 파형 | 같은 모델군에 수천 회 이상 재사용하고 scalar metric만으로 목적을 표현할 수 없을 때 | **낮음** |
| `CircuitGraph` 기반 교차-topology 추천·GNN | `X`: 여러 회로 graph; `Y`: 정규화된 성능/수정 결과 | 대량의 서로 다른 실제 회로, component ontology, 단위·metric 정규화가 있을 때 | **낮음** |
| C-block/DLL 안의 learned controller 또는 RL policy | 실시간 센서 입력 -> gating/control 출력 | hardware-in-the-loop, worst-case 안정성, 코드 생성·시간 제한 검증이 모두 있을 때 | **낮음/현 범위에서 금지** |

고장 분류가 학술적으로 불가능한 것은 아니다. 2026년 원 연구는 전력변환기 파형의 wavelet 표현과 CNN으로 open-circuit fault를 분류했고([원 논문](https://doi.org/10.1007/s13369-025-10780-z)), 2026년 공개 원 데이터는 2-level VSI의 정상·다중 고장을 HIL에서 라벨링한다([Zenodo 원 데이터](https://zenodo.org/records/20484338)). 그러나 이는 특정 converter/HIL domain의 증거이지 PSIM-MCP 모델의 외삽 근거가 아니다. simulator-only 학습 결과를 현장 진단 성능으로 주장할 수 없다.

## ML/DL이 규칙·최적화보다 이득인 경우

### ML을 고려할 조건

- 목적 함수가 PSIM으로만 평가되는 비싼 black box이고, 같은 회로·같은 parameter domain에서 향후 평가가 반복된다. Bayesian optimization의 장점은 이 평가 budget을 불확실성으로 배분하는 데 있다([BoTorch 개요](https://botorch.org/docs/v0.17.2/overview)).
- 입력이 연속 2~수십 차원 이하이고 확률적 예측 구간이 후보를 어디서 PSIM으로 재검증할지 알려줄 수 있다. scikit-learn의 GPR은 확률적 예측을 제공하지만 feature가 수십 개를 넘으면 효율이 저하된다고 명시한다([GPR 공식 문서](https://scikit-learn.org/stable/modules/gaussian_process.html)).
- 정확한 simulator label은 얻을 수 있지만, 한 번 학습한 surrogate를 trade-off 탐색·민감도 분석·후보 screening에 여러 번 재사용해 학습 비용을 상각할 수 있다.
- 파형 분류에서는 단순 threshold, FFT/wavelet feature + 선형/SVM/tree baseline이 운전조건 변화에서 실패하고, 충분한 독립 라벨로 1-D CNN이 그 baseline을 반복적으로 이길 때만 DL을 고려한다.

### 규칙 또는 기존 최적화를 선택할 조건

- 단위 변환, 허용범위, KCL/KVL, ripple 공식, 안전 한계처럼 이미 정확한 규칙이 있으면 학습하지 않는다.
- 입력이 1~3개이고 PSIM 실행이 짧거나 총 질의가 적으면 grid/space-filling DOE, 보간, least-squares가 더 단순하고 검증 가능하다.
- Altair HyperStudy는 이미 screening DOE, predictive Fit, response-surface optimization과 stochastic 분석을 제공하며([접근법 선택 공식 문서](https://help.altair.com/hwdesktop/hst/topics/design_exploration/hyperstudy_pick_approach_common_use_cases_r.htm)), Fit에는 least squares, RBF, HyperKriging, romAI 등이 있다([Fit methods](https://help.altair.com/hwdesktop/hst/topics/design_exploration/methods_fit_r-2.htm)). 해당 라이선스·연동이 가능한 사용자는 PSIM-MCP가 같은 기능을 재구현하기 전에 HyperStudy와 비교해야 한다.
- 규격 준수, 보호 동작, 안정성 또는 실제 하드웨어 안전 여부는 surrogate가 아니라 규칙·PSIM/HIL·실측으로 판정한다.

## 데이터, 라벨, 검증 기준

### 최소 data contract

한 행은 waveform window가 아니라 **독립적인 PSIM 실행 한 번**이다.

```text
run_id
source_sha256, working_sha256, circuit_graph_hash, graph_version
psim_version, bridge_version, model_schema_version
parameter_values_raw, parameter_values_SI, operating_conditions
simulation_options, signal_names, metric_definitions_version
status, error_code, runtime_seconds, output_artifact_hash
metrics, waveform_artifact, random_seed_or_deterministic_marker
```

PSIM 2025.0 릴리스 노트에는 동일 schematic의 2023.1/2024 결과 불일치가 수정 항목으로 기록되어 있다([PSIM 2025.0 릴리스 노트](https://help.altair.com/powersim/PSIM_2025.0_Release_Notes.pdf)). 이것이 현재 버그라는 뜻은 아니지만, `psim_version`과 artifact hash를 label provenance에서 빼면 안 된다는 직접적인 근거다.

### 규모와 라벨

다음 수치는 보편 법칙이 아니라 PSIM-MCP의 **시작/중단용 engineering budget**이다.

| 모델 | 시작 budget | 필요한 라벨 | 진행 조건 |
|---|---:|---|---|
| 2~4차원 GP scalar surrogate | 48~64개 distinct design + 5개 이상 repeat | versioned deterministic metric, 실패 상태 | learning curve가 아직 개선되고 held-out gate를 통과 |
| 5~10차원 GP/BO | dimension당 최소 10개 수준을 시작점으로 하되 고정하지 않음 | metric + feasibility/constraint | space-filling coverage와 uncertainty calibration이 유지될 때만 추가 수집 |
| fault classifier | 각 class·각 운전영역마다 독립 run/HIL trace; window 수를 표본 수로 세지 않음 | fault injection source, 위치, 시작 시점, severity, load/temperature/sensor 조건 | class/condition group holdout와 HIL/실측 외부 test가 있을 때 |
| neural waveform surrogate | 최소 수천 개 독립 scenario를 탐색 시작점으로 삼음 | 공통 시간축의 파형, 초기조건, parameter, solver 설정 | scalar/GP baseline이 실패하고 학습곡선이 데이터 증가 이득을 보일 때 |

필요 표본 수는 사전 숫자로 확정하지 않고 learning curve로 판단한다. 공식 scikit-learn 지침도 sample 수에 따른 train/validation score를 보고 데이터 추가가 variance를 실제로 줄이는지 확인하라고 설명한다([learning curve 공식 문서](https://scikit-learn.org/stable/modules/learning_curve.html)).

### 누수 방지와 판정 기준

- 같은 simulation에서 잘라낸 waveform window는 같은 group으로 묶는다. train/test를 window 단위로 무작위 분할하지 않는다. 회로 hash, 운전조건 묶음, fault injection run, PSIM version을 group으로 하는 비중첩 분할을 사용한다([GroupKFold 공식 문서](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html)).
- hyperparameter와 threshold를 validation에서 고른 뒤 locked test를 한 번만 사용한다. validation으로 선택한 점수는 일반화 오차의 공정한 추정치가 아니므로 별도 test가 필요하다([scikit-learn validation 지침](https://scikit-learn.org/stable/modules/learning_curve.html)).
- scalar surrogate는 NRMSE/MAE, rank correlation, 90/95% prediction interval coverage, constraint별 false-safe 수를 기록한다. 최종 추천점은 항상 새 PSIM run으로 검증한다.
- classifier는 macro-F1만 보지 않고 class별 recall, false-negative, calibration, 미지 운전조건/OOD rejection을 기록한다. 시계열 anomaly benchmark 자체가 누수와 쉬운 anomaly로 성능을 부풀릴 수 있다는 원 연구가 있으므로([Wu·Keogh 2021](https://doi.org/10.1109/TKDE.2021.3112126)) PSIM-MCP 전용 locked scenario가 필요하다.
- repeat run 분산이 모델 목표 오차와 비슷하면 ML을 멈추고 simulation 설정·metric 계산의 결정성을 먼저 고친다.

## PSIM 연동 가능성과 제약

### 가능한 경로

1. **권장: PSIM 밖의 offline learner.** MCP는 검증된 작업 사본을 만들고 parameter를 바꾸고 PSIM ground truth와 artifact를 수집한다. learner는 별도 연구 환경에서 ledger를 읽고 advisory 후보만 만든다. 새 후보는 기존 seam으로 PSIM 재검증한다.
2. **선택: HyperStudy.** 2026 HyperStudy Python API는 model write/execute와 response extraction을 개별 수행할 수 있고 외부 algorithm 등록도 지원한다([2026 릴리스 노트](https://help.altair.com/hwsolvers/altair_help/topics/release_notes/rn_2026_hyperstudy_r.htm)). 이미 보유한 고객에게는 자체 orchestration보다 먼저 평가할 경로다.
3. **후순위: Twin Activate co-simulation.** 공식 PSIM block은 Link Node로 signal을 주고받고 모든 통신값을 log할 수 있고([공식 co-simulation 문서](https://help.altair.com/twinactivate/help/en_us/topics/math_solutions/psim_cosim_c.htm)), `PyCustomBlock`은 simulation 중 Python 함수를 실행할 수 있다([PyCustomBlock 공식 문서](https://help.altair.com/twinactivate/help/en_us/topics/math_solutions/custom_block_python_define_t.htm)). 하지만 schematic을 interface용으로 바꾸고 Twin Activate/PSIM Interface를 운영해야 하므로 첫 PoC에는 과하다.
4. **비권장 초기 경로: C/DLL 내 inference.** PSIM General DLL block은 C-block 호환 코드와 `psim.h` 기반 API를 제공하지만 compiler·ABI·실시간 실행 검증이 생긴다([공식 DLL tutorial](https://2023.help.altair.com/psim-tut/tutorials/Tutorial%20-%20How%20to%20Use%20General%20DLL%20Block.pdf)). 이는 offline advisory와 별개인 embedded deployment 프로젝트다.

### 제약

- simulation 수집은 PSIM 설치와 solver entitlement에 묶인다. 2025.1 공식 표는 PSIM Solver와 co-simulation Interface를 별도 feature로 구분하고([Altair Units 2025.1](https://help.altair.com/simulation/pdfs/install/altairhyperworks_2025_1_unitslicensing.pdf)), 2026 solver 문서는 HPC unit draw가 core 수에 따라 증가함을 설명한다([PSIM Solver unit draw](https://help.altair.com/hwsolvers/altair_help/topics/getting_started/unit_draw_solvers_r.htm)). 병렬 data generation의 비용·동시성은 배포 전 라이선스로 확인해야 한다.
- `PsimASimulate`가 공식 API에 있어도 현재 제품의 “명시적 simulation” 규칙을 자동 batch로 바꾸는 권한은 아니다. 학습 데이터 수집은 별도 opt-in 연구 run이어야 한다.
- `.smv`는 PSIM graph artifact다. 학습 코드는 proprietary 포맷을 직접 추정하지 말고 `PsimReadGraphFile` 또는 현재 adapter의 `extract_signals/compute_metrics`를 통과해야 한다([Compose 2026 명령 색인](https://help.altair.com/compose/help/en_us/indexTerms.htm)).
- component parameter는 문자열 단위, element type, PSIM 버전에 좌우된다. raw 값과 SI 정규화 값을 함께 보존하고 importer 재읽기로 실제 저장을 검증한다.
- 공식 자료에서 PSIM 내부 ONNX/GPU inference를 현재 MCP 경로의 안정된 API로 확인하지 못했다. 따라서 “PSIM 안에서 Python DL model 실행”을 지원된 것으로 가정하지 않는다.
- 현재 MCP real bridge와 공식 DLL 예시는 Windows process/path/ABI에 결합되어 있다. Twin Activate의 별도 compatibility 표가 PSIM 버전 조합을 열거하더라도([Twin Activate compatibility](https://help.altair.com/twinactivate/twin_activate_compatibility_tables.pdf)) 이것만으로 직접 Python bridge의 교차-platform 동작을 추론하지 않는다. PoC는 현재 검증된 Windows-local runner로 한정한다.

## 가장 작은 PoC: Interleaving Boost metric surrogate

### 질문

고정된 Interleaving Boost 회로에서 2~4개의 검증된 numeric parameter가 `I(L1)` ripple과 출력 제약에 미치는 영향을 GP가 단순 응답면보다 충분히 잘 예측해, 반복 PSIM 평가의 후보 순위를 줄일 수 있는가?

### 범위

- 새 MCP 도구, 자동 edit, 자동 simulation, runtime dependency를 추가하지 않는다.
- `import_circuit`로 실제 ID와 writable parameter를 확인하고 `prepare_edit` 작업 사본만 사용한다.
- 입력은 L1/L2/L3 공통 inductance와 importer에서 확인한 부하·switching parameter 중 최대 3개만 쓴다. topology와 parameter range는 고정한다.
- label은 기존 `compute_metrics`의 `I(L1)` peak-to-peak ripple과 출력전압 constraint다. 파형 전체를 학습하지 않는다.

### 실행

1. 48~64개 space-filling distinct point와 최소 5개 repeat를 사전 등록하고, 각 run의 provenance·실패·wall time·artifact hash를 ledger에 기록한다.
2. quadratic response surface를 필수 baseline으로 두고, 별도 연구 환경의 Gaussian Process를 비교한다. GPR은 예측 평균과 표준편차를 함께 반환할 수 있다([scikit-learn GPR API](https://scikit-learn.org/stable/modules/generated/sklearn.gaussian_process.GaussianProcessRegressor.html)). BoTorch는 PoC가 다목적/제약 BO로 발전할 때만 고려하며 현재 runtime에 추가하지 않는다([공식 코드](https://github.com/meta-pytorch/botorch)).
3. 회로/parameter point가 겹치지 않는 train/validation/locked-test로 평가한다. model 선택 뒤 test는 한 번만 연다.
4. model은 후보를 **추천만** 한다. 최상위 후보와 uncertainty가 큰 후보를 PSIM으로 다시 실행하고 evidence를 나란히 기록한다.

### 사전 중단/통과 기준

- repeat noise가 target range의 1%를 넘거나 동일 설정의 status/metric이 재현되지 않으면 중단한다.
- locked-test NRMSE가 target range의 5% 이하이고, 90% interval의 empirical coverage가 80~100%이며, constraint false-safe가 0이어야 한다.
- GP가 quadratic baseline의 NRMSE를 상대 20% 이상 줄이지 못하면 ML을 채택하지 않는다.
- 추천 후보의 PSIM 검증값이 예측 interval 밖이거나 constraint를 위반하면 제품화하지 않는다.
- 예상 반복 질의에서 절약되는 PSIM wall time이 data collection·학습·검증 시간을 상각하지 못하면 직접 simulation/HyperStudy를 선택한다.

이 수치는 제품 계약이 아니라 한 번의 go/no-go 실험 기준이다. 통과해도 결과는 특정 회로·PSIM 버전·parameter range에만 유효하며 다른 topology로 전이하지 않는다.

## 하지 말아야 할 적용

- 자연어에서 새 topology, layout, routing, component 값을 생성하는 모델을 되살리지 않는다.
- ML 추천으로 원본이나 provenance 없는 문서를 수정하지 않고, import/edit 뒤 simulation을 암묵적으로 실행하지 않는다.
- simulator label만으로 hardware fault 진단, 안정성, 보호, 규격 준수를 승인하지 않는다.
- 학습 범위 밖 extrapolation을 숫자 하나의 confidence로 숨기지 않는다. OOD면 PSIM 실행을 요구한다.
- waveform window를 독립 표본처럼 세거나 같은 run을 train/test에 나누지 않는다.
- 단순 공식·threshold·응답면이 이기는 문제에 CNN/Transformer/GNN을 넣지 않는다.
- `CircuitGraph` 몇 개로 교차-topology 성능 추천을 학습하지 않는다.
- PINN으로 PSIM solver를 대체하지 않는다. PINN 원 연구 이후에도 조금 복잡한 물리에서 최적화가 ill-conditioned해 실패할 수 있음이 실험으로 보고되었다([NeurIPS 2021 원 논문](https://proceedings.neurips.cc/paper_files/paper/2021/hash/df438e5206f31600e6ae4af72f2725f1-Abstract.html)).
- RL/learned controller를 C-block/DLL에 넣거나 hardware로 code-generate하지 않는다. 이는 별도의 HIL, timing, stability, code-generation safety 프로젝트다.
- 모델 artifact를 검증 없이 재학습하거나 PSIM·metric schema가 바뀐 뒤 그대로 사용하지 않는다.

## 권고 결정

1. 기존 회로 편집·재가져오기·명시적 simulation evidence를 먼저 완성한다.
2. 공통 simulation ledger schema만 설계하고 평상시 사용자 요청에서 자동 수집하지 않는다.
3. 실제 반복 최적화 수요와 PSIM wall-time가 확인된 회로 하나에서 위 GP PoC만 수행한다.
4. PoC가 baseline과 상각 기준을 통과하면 내부 advisory seam을 설계하되, public tool과 runtime dependency 추가는 별도 승인한다.
5. fault DL, neural operator, graph model, learned controller는 필요한 독립 데이터/HIL가 생길 때까지 보류한다.

## 출처 품질과 한계

- **공식 제품 근거:** Altair 2026 Compose/HyperStudy/Twin Activate 문서, PSIM 2025.0 릴리스 노트, Altair 2025.1/2026 라이선스 문서를 사용했다. PSIM 설치형 Python API의 모든 signature는 공개 웹 문서에서 확인되지 않아 현재 저장소 adapter와 설치본 contract test를 별도 근거로 요구했다.
- **학술 근거:** NeurIPS 원 논문, 원 저자/프로젝트의 공식 GitHub, peer-reviewed 원 연구, 저자 공개 원 데이터를 사용했다. 리뷰·블로그·vendor 마케팅 수치를 성능 결론에 사용하지 않았다.
- **추론 한계:** 특정 논문의 정확도를 PSIM-MCP로 전이하지 않았다. 표본 수와 PoC threshold는 문헌의 보편 법칙이 아니라 이 저장소의 보수적인 go/no-go 기준으로 명시했다.
