# 제어 설계 패턴 (C-Block)

buck closed-loop 실작업(fig3_closedloop_v4)에서 검증된 교훈. 이 순서를 지키지 않아
실제로 발산했던 사례들이 근거다.

## C-Block 수정 루프

```
import_circuit                          ← C-Block의 CONTENT(현재 C 코드) 확인
  → C 코드 수정
  → set_parameter(SCB_id, "CONTENT", 새코드)
  → run_simulation → analyze_existing
  → signal_samples로 정착/발산 판정
```

## 교훈 1 — 게인 스케일은 가정하지 말고 chassis에서 읽어라

ADC/PWM 스케일을 관례값(예: 4095/20)으로 가정했다가 발산했다.
올바른 게인은 **회로에 실제 들어있는 값**(해당 회로에서는 2800/3.6)에서 유도해야 한다.
`import_circuit`으로 센서 게인·비교기 진폭 등 실값을 먼저 읽는다.

## 교훈 2 — 제어기 튜닝 중 chassis를 건드리지 않는다

제어 코드를 고치면서 전력단(chassis) 파라미터를 같이 자동 변경했더니 그 행위
자체가 발산 원인이 됐다. 한 번에 한 층만: 제어기 튜닝 중에는 C 코드만 수정.

## 교훈 3 — 정착 시간을 확보하라

closed-loop 판정에는 TOTALTIME 5ms가 부족했고 50ms에서 정착이 확인됐다.
"발산"으로 보이는 것이 실은 관찰 시간 부족일 수 있다 — 늘려서 재확인 후 판정.

## 교훈 4 — 이론보다 시뮬레이션 증거

이론적으로 맞아 보이는 수정(좌표/게인 보정)이 실제 결과를 악화시키면 되돌린다.
판정 기준은 언제나 `analyze_existing`의 실데이터(`signal_samples`)다.
