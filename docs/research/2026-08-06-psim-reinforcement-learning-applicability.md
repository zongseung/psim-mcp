# PSIM-MCP 강화학습 적용 가능성

- 조사일: 2026-08-06
- 범위: 기존 회로 중심 PSIM-MCP. 구현·의존성·제품 표면은 변경하지 않는다.
- 근거 정책: 현재 공식 프레임워크/Altair 문서와 원 연구 논문, 아래에 연결한 현재 저장소 경로를 사용한다.

## 결론: **현재 제품 RL은 NO-GO, 별도 simulator-only 폐루프 연구 실험만 조건부 GO**

**offline 정적 설계 최적화**에 RL은 기본 선택으로 부적절하다. 한 action이 parameter vector를 고르고 PSIM 한 번으로 점수화되며 다음 trial이 plant state를 이어받지 않으면, 유용한 순차 MDP가 아니라 bounded black-box/DOE 문제다. PSIM-MCP에는 이미 실험적 Optuna/TPE Bayesian-optimization 경로([`OptimizationService`](../../src/psim_mcp/services/optimization_service.py#L15-L18), [`optimize_circuit`](../../src/psim_mcp/tools/analysis.py#L168-L188))와 bounded full-run parameter sweep([`sweep_parameter`](../../src/psim_mcp/tools/parameter.py#L44-L134))가 있다. 기존 [ML/DL 평가](2026-08-06-psim-ml-dl-applicability.md)도 저차원·고비용 scalar search는 먼저 ordinary response-surface/BO와 비교해야 한다고 결론낸다.

RL이 연구 대상이 될 수 있는 경우는 **closed-loop controller learning**이다. policy가 각 control sample에서 변하는 plant를 관측하고, 결과가 누적되는 legal duty/switching action을 선택해야 한다. 이 구분은 state/action/reward control 문제를 구성하고 learned control을 predictive control과 비교한 원 converter-control 연구에도 나타난다([Wan, Xu, and Dragičević, *IEEE TIE*, 2024](https://backend.orbit.dtu.dk/ws/portalfiles/portal/397664915/Reinforcement_Learning-Based_Predictive_Control_for_Power_Electronic_Converters.pdf)).

**online hardware learning은 명시적으로 no-go다.** Converter safety-RL 원 논문은 exploration의 unsafe action이 hardware damage를 일으킬 수 있으며 별도 MPC safety policy가 필요함을 보고한다([원 논문](https://arxiv.org/abs/2312.04158)). Simulator에서 학습한 buck policy도 simulation/real mismatch 때문에 명시적 transfer mechanism이 필요하다([Cui et al., 2021](https://arxiv.org/abs/2110.10490)). Reward penalty는 safety system이 아니다.

## 현재 제품이 지원하는 것과 지원하지 않는 것

| 영역 | 현재 근거 | RL 의미 |
| --- | --- | --- |
| Simulation | [`SimulationService.run_simulation`](../../src/psim_mcp/services/simulation_service.py#L59-L85)는 open project를 요구하고 option을 검증한 뒤 simulation 한 번을 실행한다. Bridge의 [`handle_run_simulation`](../../src/psim_mcp/bridge/bridge_script.py#L378-L454)는 전체 `PsimSimulate`를 호출한다. | 이는 episodic whole-schematic evaluation seam이며 incremental plant `step()` API가 아니다. |
| Parameter change | Sweep은 `set_parameter`와 full run을 반복하고 step을 제한하며 repeated failure 뒤 중단한다([`parameter.py`](../../src/psim_mcp/tools/parameter.py#L44-L134)). | Bounded experiment collection에는 맞지만 active project를 mutate하므로 online exploration에는 안전하지 않다. |
| Real bridge | Adapter는 하나의 subprocess lock으로 request를 serialize한다([`real_adapter.py`](../../src/psim_mcp/adapters/real_adapter.py#L250-L344)). | Process isolation, deterministic parallel rollout, real-time step 보장은 입증되지 않았다. |
| Safety boundary | Project path는 open/import 전 검증된다([`validate_project_path`](../../src/psim_mcp/services/validators.py#L25-L70)); 제품 문서는 `set_parameter`가 original file에 persist한다고 경고한다. | Path validation은 controller safety가 아니다. RL harness는 disposable copy와 독립 electrical limit을 사용해야 한다. |

Altair는 PSIM simulation, asynchronous simulation, graph-file reading, parameter-setting command를 문서화한다([공식 Compose command index](https://help.altair.com/compose/help/en_us/indexTerms.htm)). 이는 유용한 batch primitive의 근거일 뿐 safe generic Python step-level co-simulation contract의 근거는 아니다. Parallel/incremental RL stepping은 설치된 PSIM version에서 입증되기 전까지 **unverified**로 취급한다.

## 세 문제를 분리한다

| 문제 | 권고 | 이유 |
| --- | --- | --- |
| Offline circuit/design 또는 controller-parameter optimization | **No RL.** Constrained DOE/response surface/BO를 쓰고 existing Optuna path와 비교한다. | Stateless candidate-and-score loop은 RL의 temporal-credit-assignment 이득이 없고 rollout/sample cost만 더한다. |
| Simulator-only closed-loop controller learning | **Conditional research GO.** Throughput과 reset semantics가 입증된 뒤 별도 harness를 만든다. | Dynamic policy는 MDP일 수 있지만 현재 MCP interface는 이를 노출하지 않는다. |
| Online hardware control/learning | **No-go.** | Independent interlock, known-safe fallback control, latency verification, calibrated sim-to-real transfer, staged HIL test, hardware ownership이 필요하며 MCP tool call로 해결되지 않는다. |

Converter가 nonlinear이라는 사실만으로 RL이 PI/MPC/ordinary optimization을 이기지는 않는다. Dynamic controller에 반복 closed-loop decision 문제가 있고, matched baseline이 사전 정의된 held-out disturbance에서 실패하며, 추가 simulation cost가 상각될 때만 평가 가치가 있다. Stable-Baselines3는 model-free algorithm이 sample-inefficient하여 유용한 학습에 millions of interactions가 필요할 수 있고, reward engineering이 필요하며, seed에 따라 결과가 달라질 수 있다고 명시한다([SB3 RL tips](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)).

## Training-environment contract (research only)

Gymnasium은 `reset(seed, options) -> (observation, info)`와 `step(action) -> (observation, reward, terminated, truncated, info)`를 요구하며, `terminated`와 `truncated`는 서로 다른 learning semantics를 갖는다([official API](https://gymnasium.farama.org/api/env/)). 미래 harness는 controller sample마다 PSIM subprocess를 새로 시작하는 방식이 아니라, **이미 사용 가능한 incremental/co-simulation interface**를 감싸야 한다.

하나의 fixed, pre-existing DC-DC schematic에서는 다음으로 시작한다.

- **Observation:** normalized `[v_ref, v_out, i_L, v_ref-v_out, previous_action]`; Markov property를 유지하는 데 필요한 measured state만 더한다.
- **Action:** `[-1, 1]`의 normalized continuous duty-ratio increment/command 하나를 circuit-specific safe range로 map하고 clip한다. 또는 known legal switching vector의 finite set을 사용한다. Arbitrary gate pattern은 노출하지 않는다.
- **Reward:** 처음에는 `-(normalized_tracking_error**2)`만 사용한다. Current/voltage/solver constraint violation에서 terminate한다. Loss 또는 switching penalty는 explicit acceptance requirement일 때만 추가한다.
- **Episode:** fixed initial condition과 seeded, bounded reference/load/parameter disturbance를 사용한다. Infeasible/unsafe simulation은 `terminated`, horizon 또는 wall-time limit은 `truncated`다.

이는 인용한 converter 연구의 measured state/error 및 legal-action formulation과 맞지만, 해당 연구의 수치와 reward weight를 transferable product default로 취급하지 않는다. Training 전에 Gymnasium/SB3 environment check와 random-action smoke test를 수행한다. SB3는 custom environment에서 normalized observation 및 symmetric normalized continuous action을 권장한다([SB3 custom-environment guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)).

## Throughput, licensing, reproducibility, safety gate

PSIM은 `PsimSimulate`와 `PsimASimulate`를 제공한다([Altair official index](https://help.altair.com/compose/help/en_us/indexTerms.htm)). 그러나 asynchronous simulation은 result isolation 또는 safe parallel controller step을 입증하지 않는다. 먼저 complete episode 한 번을 측정한다. RL step마다 fresh bridge/process/full schematic simulation이 필요하다면 중단한다. Verified incremental/co-simulation route 없이는 model-free RL environment가 credible하지 않다.

모든 PSIM GUI 또는 standalone Solver execution에는 `PSIMSolver` feature가 필요하고, HPC unit draw는 CPU core당 계산된다([Altair licensing notes](https://2025.help.altair.com/2025.1/hwdesktop/altair_help/topics/release_notes/rn_2025_licensing_r.htm)). 따라서 concurrency는 RL worker-count default가 아니라 측정된 solver throughput과 available license capacity로 제한한다.

결과를 해석하기 전에 다음을 모두 요구한다.

1. PSIM/bridge/package version, circuit checksum, solver option, controller parameter, reward normalization, disturbance set, seed, wall time, artifact hash를 episode마다 기록한다.
2. 최소 세 개 seed를 사용하고 mean/spread를 보고한다. SB3는 seed 변화만으로 outcome이 달라질 수 있으며 separate evaluation environment를 권장한다([SB3 evaluation guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)).
3. Named train/validation/locked-test disturbance scenario를 분리한다. PI/MPC/fixed-controller baseline과 tracking RMSE, peak current/voltage, violation count, switching count, runtime을 비교한다.
4. Hard simulation constraint를 위반한 controller는 채택하지 않는다. Simulator pass는 hardware-safety 또는 sim-to-real claim이 아니다.

## 가장 작은 credible MVP

**PSIM-MCP feature가 아닌 external research harness:** 하나의 fixed existing buck/DC-DC schematic, 하나의 measured tracking target, 하나의 bounded legal control action, seeded load/reference reset만 사용한다. Simulation에서만 train하고 policy/checkpoint와 CSV/JSON episode evidence를 MCP runtime 밖에 저장한다. Held-out scenario에서 pre-existing controller와 비교한다.

다음 precondition이 모두 충족될 때만 시작한다. (a) Licensed PSIM route가 controller sample마다 process를 새로 시작하지 않고 episode를 reset/advance할 수 있다. (b) Working-copy/reset procedure가 episode를 재현할 만큼 deterministic하다. (c) Random legal action도 independently enforced simulation bound 밖으로 나갈 수 없다. (d) PI/MPC/fixed baseline과 acceptance metric을 먼저 freeze한다. 이 MVP는 나중에 external framework를 사용할 수 있으나, 이 평가가 Gymnasium/SB3를 product dependency로 추가하도록 승인하지는 않는다.

### Explicit non-goal

- Static circuit sizing/topology design, natural-language circuit generation, existing optimizer 대체를 위한 RL.
- User schematic의 automatic mutation, arbitrary-gate action space, `sweep_parameter`를 online exploration으로 사용하는 것.
- Multi-circuit/multi-agent learning, hardware-in-the-loop/live training, safety certification, sim-to-real/superiority claim.
- 설치된 version contract test가 deterministic high-throughput stepwise RL을 증명하기 전 PSIM 지원을 주장하는 것.

## Decision record

| 결정 | 상태 | 다음 조건에서만 재검토 |
| --- | --- | --- |
| Product RL tool | **No-go** | Closed-loop environment, safety case, matched baseline evidence가 존재할 때. |
| Offline static optimization via RL | **No-go** | Sequential stateful decision process가 입증될 때. 그렇지 않으면 DOE/BO를 유지한다. |
| Simulator-only closed-loop experiment | **Conditional go** | 위 MVP precondition과 licensing/throughput gate를 통과할 때. |
| Online hardware RL | **No-go** | 별도 hardware-control program이 interlock, fallback, HIL, transfer validation을 제공할 때. |
