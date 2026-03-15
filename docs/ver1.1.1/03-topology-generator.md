# Step 3: Topology Generator 도입

> 우선순위: P0
> 예상 범위: `src/psim_mcp/generators/` 패키지 신규 생성
> 의존: Step 1 (CircuitSpec), Step 2 (Component Catalog)

---

## 1. 목적

현재 템플릿은 **고정된 dict 데이터**다. 이를 **생성 규칙 기반 generator**로 전환한다.

현재 문제:
- 템플릿에서 파라미터를 바꾸면 다른 부품 값도 연쇄적으로 바뀌어야 하지만, 현재는 수동
  - 예: V_in=48V, V_out=12V → duty cycle=0.25 → 인덕터 값 자동 계산 가능
- topology 추가가 data 파일에 dict를 복붙하는 방식이라, 구조적 실수 발생 가능
- 좌표(position)가 하드코딩되어 부품 수 변동에 대응 불가

목표:
- topology별 generator 함수가 `CircuitRequirements` → `CircuitSpec`을 생성
- 설계 공식 기반으로 부품 값 자동 계산
- 좌표는 generator가 자동 배치

---

## 2. Generator 인터페이스

```python
class TopologyGenerator(ABC):
    """Base class for all topology generators."""

    @abstractmethod
    def generate(self, requirements: CircuitRequirements) -> CircuitSpec:
        """Generate a complete CircuitSpec from requirements."""

    @property
    @abstractmethod
    def topology_name(self) -> str:
        """Return the topology identifier (e.g., 'buck')."""

    @property
    @abstractmethod
    def required_fields(self) -> list[str]:
        """List of required fields in CircuitRequirements."""
```

---

## 3. 설계 공식 예시 — Buck Converter

```python
class BuckGenerator(TopologyGenerator):
    topology_name = "buck"
    required_fields = ["vin", "vout_target", "switching_frequency"]

    def generate(self, req: CircuitRequirements) -> CircuitSpec:
        # 설계 공식
        duty = req.vout_target / req.vin

        # 인덕터: L = V_out * (1 - D) / (f_sw * delta_I)
        delta_i = 0.3 * (req.iout_target or 1.0)  # 30% ripple 기준
        L = req.vout_target * (1 - duty) / (req.switching_frequency * delta_i)

        # 캐패시터: C = delta_I / (8 * f_sw * delta_V)
        delta_v = 0.01 * req.vout_target  # 1% ripple 기준
        C = delta_i / (8 * req.switching_frequency * delta_v)

        # 부하 저항
        R_load = req.vout_target / (req.iout_target or 1.0)

        # CircuitSpec 조립
        return CircuitSpec(
            topology="buck",
            metadata=CircuitMetadata(name=f"buck_{req.vin}V_to_{req.vout_target}V"),
            requirements=req,
            components=[...],  # 계산된 값으로 채움
            nets=[...],        # 표준 buck 네트리스트
            simulation=SimulationSettings(...),
        )
```

---

## 4. Auto-Layout 규칙

generator가 좌표를 결정한다. 기본 규칙:

```
전원 → 스위치 → 에너지 저장 → 부하
(좌)                              (우)
```

- 주 경로: 가로 방향, x 간격 160px
- 분기 소자: 세로 방향, y 간격 140px
- GND 라인: 최하단 y 고정

```python
def auto_layout(components: list[ComponentSpec], topology: str) -> None:
    """Assign positions to components based on topology flow."""
    # 1. 주 경로 소자 식별 (source → switch → inductor → load)
    # 2. 분기 소자 배치 (diode, capacitor 등)
    # 3. x/y 좌표 할당
```

---

## 5. Generator Registry

```python
# generators/__init__.py
_GENERATORS: dict[str, TopologyGenerator] = {}

def register(gen: TopologyGenerator):
    _GENERATORS[gen.topology_name] = gen

def get_generator(topology: str) -> TopologyGenerator | None:
    return _GENERATORS.get(topology)

# 초기 등록
register(BuckGenerator())
register(BoostGenerator())
register(BuckBoostGenerator())
# ... 29개 topology 전부
```

---

## 6. 기존 템플릿과의 관계

기존 `circuit_templates.py`의 29개 템플릿은:
- **단기**: generator의 fallback으로 유지 (generator가 없는 topology는 템플릿 사용)
- **중기**: generator로 점진 전환, 전환 완료 시 해당 템플릿 제거
- **장기**: 템플릿은 테스트용 fixture로만 유지

전환 순서:
1. buck, boost, buck_boost (기본 DC-DC)
2. half_bridge, full_bridge (인버터)
3. flyback, forward, LLC (절연 DC-DC)
4. 나머지

---

## 7. 구현 범위

### 파일 생성
- `src/psim_mcp/generators/__init__.py`
- `src/psim_mcp/generators/base.py` (TopologyGenerator ABC)
- `src/psim_mcp/generators/buck.py`
- `src/psim_mcp/generators/boost.py`
- `src/psim_mcp/generators/layout.py` (auto_layout)

### 파일 수정
- `tools/circuit.py`: generator가 있으면 generator 사용, 없으면 템플릿 fallback
- `services/simulation_service.py`: CircuitSpec 기반 create_circuit

---

## 8. 테스트 계획

- BuckGenerator가 유효한 CircuitSpec을 생성하는지
- 설계 공식 계산값이 합리적 범위인지 (L, C, R 값 범위 확인)
- auto_layout이 겹침 없이 좌표를 배치하는지
- generator 출력 → mock adapter → 시뮬레이션 흐름이 통과하는지
- 기존 템플릿 경로가 여전히 동작하는지 (하위 호환)

---

## 9. 완료 기준

- [ ] TopologyGenerator ABC 정의
- [ ] buck, boost, buck_boost generator 구현
- [ ] 설계 공식 기반 부품 값 자동 계산 동작
- [ ] auto_layout 기본 규칙 동작
- [ ] generator registry 동작
- [ ] 기존 템플릿 fallback 유지
- [ ] 기존 테스트 통과
