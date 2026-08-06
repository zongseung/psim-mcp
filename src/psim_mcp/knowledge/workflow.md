# PSIM-MCP 워크플로우 가이드

기존 PSIM 회로를 이해·수정·시뮬레이션하는 표준 순서.

## 표준 루프

```
import_circuit(path)          ← 항상 먼저. 소자 + 넷(전기적 연결) + 파라미터 복원
  → (이해/설명)
  → set_parameter(...)        ← 값 변경. 파일에 즉시 저장됨
  → run_simulation()          ← 명시적으로만 실행 (자동 실행 금지)
  → analyze_existing(...)     ← 메트릭 + 파형 PNG + 실제 신호 샘플
```

- `open_project`는 파일을 열기만 한다. 회로 구조(넷 포함)가 필요하면 `import_circuit`.
- 수정 후 구조 재확인이 필요하면 `import_circuit`을 다시 호출한다.

## 타임아웃 우회

`analyze_simulation`(시뮬+분석 일체형)이 타임아웃되면:

1. `run_simulation(simview=false)` — 시뮬만
2. `analyze_existing(graph_file="...")` — 분석만 (5~10초, graph_file 생략 시 최근 결과 자동 사용)

Simview GUI는 Windows에서 뜨는 데 수십 초 걸리므로 `simview`/`open_simview`는 기본 false로 둔다.

## 파형 설명 규칙

파형을 설명할 때는 반드시 응답의 `signal_samples`(실제 시간 시리즈)를 근거로 한다.
스칼라 메트릭(평균/리플/최종값)만으로 파형 모양을 추론해 그리면 실제 PSIM 결과와
동떨어진 가짜 파형이 된다.

## 파라미터 스캔

- 1차원 스캔은 `sweep_parameter` (start/end/step). 단계 수 상한이 있고,
  연속 3회 실패 시 조기 중단된다.
- 어떤 값을 넣을지 판단이 필요한 반복 튜닝은 사람이(또는 모델이) 한 스텝씩
  `set_parameter → run_simulation → analyze_existing`으로 돈다.

## 새 회로가 필요할 때

무에서 생성하지 않는다. `templates.md`(guidelines://templates)의 검증된 회로 파일을
복사한 뒤 `import_circuit`으로 구조를 확인하고 파라미터만 수정한다.
