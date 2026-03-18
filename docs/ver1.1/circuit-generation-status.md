# PSIM-MCP Circuit Generation Status

> 작성일: 2026-03-15
> 범위: 현재 `src/psim_mcp` 구현 기준 `create_circuit` 경로 점검
> 목적: MCP 연결 시 "자연어로 회로를 그려주는가"에 대한 현재 구현 상태를 명확히 기록

---

## 1. 결론

현재 구현은 더 이상 "기존 회로를 열고 수정하는 기능만 있는 상태"가 아니다.

지금 코드에는 MCP tool을 통해 새 회로를 생성하는 경로가 실제로 추가되어 있다.

- `create_circuit`
- `list_circuit_templates`

즉, MCP를 통해 Claude가 자연어 요청을 해석한 뒤 `create_circuit` tool을 호출하면, 템플릿 기반 또는 구조화된 입력 기반으로 새 PSIM 회로 생성을 시도하는 구조다.

---

## 2. 현재 구현된 부분

### 2.1 MCP tool 등록

파일:

- `src/psim_mcp/server.py`

확인 내용:

- `register_all_tools()`가 `circuit.register_tools(...)`를 포함한다.
- 따라서 회로 생성 tool은 현재 MCP 서버에 실제 등록된다.

의미:

- MCP 클라이언트는 현재 구현 기준으로 회로 생성 관련 tool을 호출할 수 있다.

---

### 2.2 회로 생성 tool 추가

파일:

- `src/psim_mcp/tools/circuit.py`

확인 내용:

- `create_circuit(...)` tool이 존재한다.
- `list_circuit_templates()` tool도 존재한다.
- 사전 정의 템플릿이 포함되어 있다.

현재 템플릿:

- `buck`
- `boost`
- `half_bridge`
- `full_bridge`

의미:

- "buck 컨버터 만들어줘" 같은 요청은 템플릿 기반 회로 생성 요청으로 연결될 수 있다.

---

### 2.3 service / adapter 경로 연결

파일:

- `src/psim_mcp/services/simulation_service.py`
- `src/psim_mcp/adapters/base.py`
- `src/psim_mcp/adapters/mock_adapter.py`
- `src/psim_mcp/adapters/real_adapter.py`

확인 내용:

- `SimulationService.create_circuit(...)`가 존재한다.
- `BasePsimAdapter`에 `create_circuit(...)` 계약이 추가되어 있다.
- `MockPsimAdapter`, `RealPsimAdapter` 모두 이를 구현한다.

의미:

- 회로 생성은 tool 수준 임시 아이디어가 아니라, 현재 서비스 계약에 포함된 기능이다.

---

### 2.4 real mode bridge 경로 존재

파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인 내용:

- `handle_create_circuit(params)`가 존재한다.
- `psimapipy.PSIM` 기반으로 새 schematic 생성, element 생성, parameter 설정, 저장 흐름이 들어 있다.

의미:

- Windows real mode에서는 실제 PSIM schematic 생성까지 시도하는 구현이 들어와 있다.

---

## 3. 현재 구현의 정확한 해석

현재 구현을 가장 정확하게 표현하면 다음과 같다.

> MCP를 통해 자연어 요청이 들어왔을 때, Claude가 `create_circuit` tool을 호출하여
> 템플릿 기반 또는 구조화된 입력 기반의 PSIM 회로 생성을 시도할 수 있다.

다만 이것을 곧바로 아래처럼 해석하면 과장이다.

- "아무 회로나 자유롭게 자동 설계해준다"
- "실제 PSIM에서 완전한 회로도가 항상 정확하게 그려진다"
- "배선까지 포함해 Windows real mode 동작이 완전히 검증됐다"

즉 현재 단계는:

- 회로 생성 기능이 **있다**
- 하지만 완전 자유형 생성기나 실환경 검증 완료 상태는 **아니다**

---

## 4. 아직 한계가 남아 있는 부분

### 4.1 템플릿 중심 구조

현재 `tools/circuit.py`는 템플릿 회로 또는 명시적 `components` / `connections` 입력을 전제로 한다.

따라서 현재 기능은:

- 템플릿 기반 생성
- 구조화된 회로 정의 기반 생성

에 가깝다.

반면 다음 수준은 아직 별도 문제다.

- 완전 자유형 자연어 회로 설계
- 설계 의도 해석 후 자동 topology 결정
- 임의 회로에 대한 안정적 auto-layout

---

### 4.2 bridge에서 연결선 생성이 명확히 구현되어 있지 않음

파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인 내용:

- `connections` 입력은 받는다.
- 하지만 현재 코드에는 wire 생성 API 호출이 직접 보이지 않는다.
- 응답에도 실제 연결 성공 결과가 아니라 `connection_count`만 기록된다.

의미:

- 현재 bridge는 "부품 생성 및 저장" 경로는 보이지만,
- "연결선까지 실제로 그려진다"는 점은 코드만으로 확정할 수 없다.

---

### 4.3 개별 부품 생성 실패가 조용히 무시됨

파일:

- `src/psim_mcp/bridge/bridge_script.py`

확인 내용:

- 각 컴포넌트 생성 중 예외가 발생해도 `pass`로 넘어간다.

의미:

- 저장은 성공했더라도 일부 소자가 빠진 상태일 수 있다.
- 현재 응답의 `component_count`와 `total_requested` 차이를 반드시 확인해야 한다.

---

### 4.4 테스트는 통과하지만 회로 생성 경로 검증은 아직 약함

재확인 결과:

- `uv run pytest -q` 기준 `221 passed`

하지만 현재 테스트는 주로 아래 경로를 검증한다.

- `open_project`
- `set_parameter`
- `run_simulation`
- `export_results`

현재 부족한 부분:

- `create_circuit` tool 직접 호출 테스트
- 템플릿 생성 통합 테스트
- Windows real mode schematic 생성 smoke test
- 생성 후 실제 열기/실행까지 이어지는 end-to-end 검증

---

## 5. 현재 상태 판단

현재 상태 판단은 아래가 가장 정확하다.

- "회로 생성 기능이 없다"는 설명은 이제 틀리다.
- "자연어 입력으로 회로 생성 시도까지는 가능하다"는 설명은 맞다.
- "실제 PSIM에서 완전한 회로도가 안정적으로 그려진다"는 설명은 아직 이르다.

즉, 이 프로젝트는 현재:

- 기존 회로 자동 조작 도구
- 템플릿 기반 회로 생성 기능

을 함께 가지는 상태로 보는 것이 맞다.

---

## 6. 다음 확인 포인트

가장 중요한 실증 포인트는 Windows real mode다.

권장 확인 순서:

1. `list_circuit_templates` 호출
2. `create_circuit("buck", save_path=...)` 실행
3. 생성된 `.psimsch` 파일이 실제로 열리는지 확인
4. 소자 수가 기대값과 일치하는지 확인
5. 연결선이 실제로 반영됐는지 확인
6. 생성 직후 `run_simulation`까지 이어지는지 확인

---

## 7. 결론

현재 구현 기준으로는 MCP를 통해 회로 생성을 시도하는 기능이 이미 들어와 있다.

따라서 "이 프로젝트는 기존 회로만 수정한다"는 설명은 더 이상 정확하지 않다.
다만 현재 단계는 "템플릿 기반 회로 생성 기능이 구현된 프로토타입"에 가깝고,
Windows real mode에서 실제 PSIM schematic 생성 품질은 별도 실험으로 검증해야 한다.
