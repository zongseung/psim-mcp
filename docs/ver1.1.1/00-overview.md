# PSIM-MCP v1.1.1 구현 기획 개요

> 작성일: 2026-03-15
> 기반 문서: `docs/ver1.1/circuit-expansion-plan.md`
> 목표: 템플릿 기반 회로 생성 → 검증 가능한 회로 생성 시스템으로 전환

---

## 아키텍처 전환

```
[현재]
자연어 → tool 선택 → 템플릿/dict → PSIM bridge

[목표]
자연어 → intent parser → CircuitSpec → validator → topology generator → PSIM bridge
```

---

## 단계별 기획서

| 단계 | 문서 | 우선순위 | 핵심 산출물 |
|------|------|----------|------------|
| Step 1 | [01-circuit-spec.md](./01-circuit-spec.md) | P0 | CircuitSpec Pydantic 모델 |
| Step 2 | [02-component-catalog.md](./02-component-catalog.md) | P0 | 정규화된 부품 카탈로그 (핀, 파라미터, PSIM 매핑) |
| Step 3 | [03-topology-generator.md](./03-topology-generator.md) | P0 | 설계 공식 기반 회로 생성기 |
| Step 4 | [04-bridge-wiring.md](./04-bridge-wiring.md) | P0-P1 | PSIM 배선 API 확인 및 구현 |
| Step 5 | [05-validation-layer.md](./05-validation-layer.md) | P0-P1 | 구조/전기/파라미터 검증 |
| Step 6 | [06-windows-smoke-test.md](./06-windows-smoke-test.md) | P1 | Windows 실환경 검증 |
| Step 7 | [07-nlp-intent-parser.md](./07-nlp-intent-parser.md) | P2 | 자연어 → CircuitSpec 변환 |

---

## 실행 순서

```
Step 1 ──→ Step 2 ──→ Step 3 ──→ Step 5
                         │
                         └──→ Step 4 ──→ Step 6 ──→ Step 7
```

- Step 1~3: Mac에서 구현 가능 (코드 구조 작업)
- Step 4, 6: Windows PSIM 환경 필요
- Step 5: Mac에서 대부분 구현, Windows에서 통합 검증
- Step 7: Step 1~6 안정화 후 진행

---

## 누락 보완 항목

현재 코드 기준으로, 아래 2개는 별도 단계 문서까지는 아니더라도 P0 성격으로 함께 반영해야 한다.

### 1. Preview 상태 관리

현재 `preview_circuit` / `confirm_circuit` 흐름은 전역 in-memory 상태에 의존하고 있다.

필요 보완:

- preview 결과를 전역 변수 1개가 아니라 `preview_token` 기준으로 저장
- 요청 단위 또는 세션 단위로 분리
- `confirm_circuit(preview_token=...)` 형식으로 확정
- preview 만료 시간(TTL)과 정리 정책 정의

예상 변경 대상:

- `src/psim_mcp/tools/circuit.py`
- `src/psim_mcp/services/preview_store.py` 신규

완료 기준:

- [x] `preview_token` 발급 및 조회 가능
- [x] token별 preview가 서로 덮어쓰지 않음
- [x] `confirm_circuit(preview_token=...)` 형식으로 확정 가능
- [x] confirm 성공 시 token 삭제
- [x] 만료/없는 token 요청 시 명시적 에러 반환

### 2. Legacy → CircuitSpec 마이그레이션

현재 구현은 템플릿 dict, `components` / `connections`, `specs` dict가 섞여 있다.

필요 보완:

- 기존 dict 입력은 당장 제거하지 않음
- 모든 입력을 먼저 `CircuitSpec.from_legacy(...)` 또는 동등한 adapter로 변환
- 이후 validator / generator / bridge는 `CircuitSpec`만 받도록 고정
- generator가 없는 topology만 기존 템플릿 fallback 허용

즉 전환 순서는 아래가 맞다.

`legacy input 유지 -> CircuitSpec adapter 추가 -> generator 우선 사용 -> legacy 경로 축소`

정리 기준:

- Step 1 완료 후 모든 신규 로직은 내부적으로 `CircuitSpec`으로 정규화
- Step 3 완료 후 generator 지원 topology는 legacy dict 경로를 기본 경로로 사용하지 않음
- Step 5 완료 후 validator를 거치지 않는 직접 bridge 호출 경로는 deprecated 처리
- Step 6 완료 후 Windows smoke test 통과 topology부터 legacy 직접 처리 경로 제거 검토

---

## 최소 성공 기준

1. buck, boost, full_bridge가 Windows real mode에서 생성 + 열기 + 시뮬 성공
2. 배선이 실제로 연결됨
3. 실패 시 어느 소자/배선이 실패했는지 응답에 포함
4. topology 추가가 generator 추가로 가능 (dict 복붙이 아닌)
5. "48V to 12V buck" 자연어 입력 → 회로 생성까지 연결
6. preview token 흐름이 세션 간 충돌 없이 동작

---

## 현재 코드 기준 변경 대상

| 파일/패키지 | 변경 유형 |
|-------------|-----------|
| `src/psim_mcp/models/circuit_spec.py` | 신규 |
| `src/psim_mcp/generators/` | 신규 패키지 |
| `src/psim_mcp/validators/` | 신규 패키지 |
| `src/psim_mcp/parsers/` | 신규 패키지 |
| `src/psim_mcp/services/preview_store.py` | 신규 |
| `src/psim_mcp/data/component_library.py` | 리팩터링 |
| `src/psim_mcp/data/circuit_templates.py` | 점진적 대체 (generator fallback) |
| `src/psim_mcp/tools/circuit.py` | 수정 (generator/validator 연동) |
| `src/psim_mcp/services/simulation_service.py` | 수정 (CircuitSpec 수용) |
| `src/psim_mcp/adapters/base.py` | 수정 (CircuitSpec 시그니처) |
| `src/psim_mcp/bridge/bridge_script.py` | 보강 (배선, 검증) |
