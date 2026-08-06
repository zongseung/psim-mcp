# 검증된 회로 템플릿 카탈로그

새 회로가 필요하면 **생성하지 말고 아래 파일을 복사**한 뒤 파라미터만 수정한다.
와이어 좌표·핀 정렬은 사람이 그려서 PSIM이 검증한 상태 그대로 보존된다.

사용 순서:
1. 파일을 작업 위치로 복사 (원본 보존)
2. `import_circuit(복사본)` — 실제 소자 ID·파라미터·넷 확인
3. `set_parameter`로 값 수정 → `run_simulation` → `analyze_existing`

## 카탈로그

| 파일 | 토폴로지 | 용도 / 검증 내용 |
|---|---|---|
| `paper_data/fig2_openloop_buck.psimsch` | Buck open-loop | 기본 벅 컨버터. TOTALTIME 50ms에서 정착 검증됨. 게이팅 소자 `G1` |
| `paper_data/fig2_openloop_v2.psimsch` | Buck open-loop (v2) | fig2 개정판 |
| `paper_data/fig2_openloop_v3.psimsch` | Buck open-loop (v3) | fig2 최신 개정판 |
| `paper_data/fig3_closedloop_v4.psimsch` | Buck closed-loop | C-Block 제어기 포함. 게인은 chassis 실측값(2800/3.6) 기반. TOTALTIME 50ms |
| `paper_data/figa1_divergent.psimsch` | Buck closed-loop (발산 예제) | 잘못된 튜닝의 발산 사례 — 안정성 비교/데모용 |
| `projects/interleaving_demo.psimsch` | Interleaving 컨버터 | 다상 인터리빙 데모. `I(L1)` 등 상전류 관찰 |
| `projects/verify_dq.psimsch` | dq 변환 검증 | dq 변환 블록 동작 확인용 |

주의:
- 위 표의 소자 ID는 참고용. **정확한 ID와 현재 파라미터는 항상 `import_circuit`으로 확인**한다 (.psimsch는 바이너리라 직접 읽을 수 없음).
- closed-loop 회로에서 제어기를 튜닝할 때 chassis(전력단)를 건드리지 않는다 — `control_patterns.md`(guidelines://control-patterns) 참조.
