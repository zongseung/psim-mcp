# Phase 4 라우팅 수정 기획서: PSIM 와이어 연결 문제 해결

## 문서 정보
- 작성일: 2026-03-26
- 상태: 검증 완료, 구현 대기
- 영향 범위: 11개 토폴로지 시뮬레이션 실패 → 성공으로 전환

---

## 1. 문제 정의

### 현상
25개 토폴로지 중 11개가 PSIM 시뮬레이션 시 "The switch X is floating!" 에러 발생.

### 실패 토폴로지
full_bridge, push_pull, thyristor_rectifier, boost_pfc, totem_pole_pfc, three_level_npc, pv_grid_tied, bldc_drive, pmsm_foc_drive, induction_motor_vf, half_bridge

### 성공 토폴로지 (14개)
buck, boost, flyback, buck_boost, sepic, cuk, forward, llc, cc_cv_charger, bidirectional_buck_boost, dab, pv_mppt_boost, ev_obc, diode_bridge_rectifier

---

## 2. 근본 원인 분석

### 2.1 PSIM 와이어 연결 규칙 (검증 완료)

**출처**: PSIM User Manual V9, PsimConvertToPython 출력 분석, Altair Community

1. **끝점 연결만 인식**: PSIM은 와이어의 **끝점(endpoint)** 좌표가 정확히 일치할 때만 전기적 연결로 인식. 와이어 중간점에 다른 와이어가 닿아도 연결 안 됨.

2. **T-접합 미지원**: 와이어 A의 중간점에 와이어 B의 끝점이 닿아도 전기적으로 분리됨. 접합이 필요하면 와이어 A를 해당 지점에서 **분할**해야 함.

3. **암시적 접합**: 별도의 JUNCTION/NODE 요소 없음. 3개 이상의 와이어가 같은 좌표에서 끝나면 자동으로 접합점(검은 점) 표시.

4. **그리드 정렬 필수**: 모든 좌표는 정수, 그리드에 정렬되어야 함.

### 2.2 증거: PsimConvertToPython 출력 분석

`output/converted_buck_main.py`에서 PSIM이 실제로 와이어를 어떻게 배치하는지 확인:

```
접합점 (220,100)에서:
  Wire (200,100) → (220,100)    ← 와이어 A의 끝점
  Wire (220,100) → (250,100)    ← 와이어 B의 시작점
  D1 component pin at (220,100) ← 컴포넌트 핀

→ 세 요소 모두 (220,100)을 "끝점"으로 공유 → 연결됨
```

**핵심**: PSIM은 긴 와이어를 접합점에서 **반드시 분할**함. `(200,100)→(400,100)` 같은 긴 와이어 중간에 핀이 있으면 안 됨.

### 2.3 현재 코드의 문제점

#### 문제 1: 체인 라우팅의 L자 경로가 핀을 빗나감

현재 `nets_to_connections_simple`이 3+ 핀 넷을 체인으로 변환:
```
net_gnd: [V1.negative, GND1.pin1, D1.anode, C1.negative, R1.pin2]
→ V1.negative → GND1.pin1 (와이어 1)
→ GND1.pin1 → D1.anode   (와이어 2)
→ D1.anode → C1.negative  (와이어 3)
→ C1.negative → R1.pin2   (와이어 4)
```

각 와이어는 `_route_wire`에서 L자(수평→수직)로 그려짐. **문제**: L자 꺾임점이 다음 핀의 좌표와 무관하게 결정되므로, 와이어 끝점이 핀에 정확히 닿아도 경로 자체가 다른 와이어와 교차/간섭할 수 있음.

#### 문제 2: 트렁크-브랜치 라우팅에서 트렁크 미분할

`routing/trunk_branch.py`가 올바르게 JunctionPoint를 계산하지만, `to_legacy_segments()`에서 트렁크를 접합점에서 분할하지 않음:

```
현재 (잘못됨):
  트렁크: (100,200) ─────────────────→ (400,200)   [하나의 와이어]
  브랜치:         (250,150) → (250,200)              [끝점이 트렁크 중간 = 연결 안 됨!]

올바른 방식:
  트렁크 1: (100,200) → (250,200)   [접합점에서 분할]
  트렁크 2: (250,200) → (400,200)   [접합점에서 분할]
  브랜치:   (250,150) → (250,200)   [끝점 공유 = 연결됨!]
```

#### 문제 3: 두 경로의 불일치

| 항목 | Legacy 경로 (connections) | Canonical 경로 (wire_segments) |
|------|--------------------------|-------------------------------|
| 와이어 데이터 | `{from, to}` 핀 이름 | `{x1,y1,x2,y2}` 좌표 |
| 다중 핀 전략 | 체인 (A→B→C) | 트렁크+브랜치 |
| 라우팅 | bridge에서 L자 | routing 엔진에서 사전 계산 |
| 접합 처리 | 없음 (암시적) | JunctionPoint 계산은 하지만 미활용 |

---

## 3. 해결 방안

### 3.1 핵심 원칙

**"모든 와이어 끝점은 컴포넌트 핀 또는 다른 와이어 끝점과 정확히 같은 좌표를 공유해야 한다"**

### 3.2 구현 전략: 스타형 라우팅 + 트렁크 분할

#### 방안 A: Legacy 경로 수정 (connections → 스타형)

`bridge_script.py`의 `_route_wire` 로직을 수정하여, 3+ 핀 넷에 대해 **스타형 라우팅**을 적용:

```
Before (체인):
  A ──L──> B ──L──> C ──L──> D

After (스타):
         B
         │
  A ─────J─────── C
         │
         D

J = 접합점 (모든 핀의 중앙 좌표)
```

**구현 위치**: `bridge_script.py`의 connections 처리 브랜치 (line 996-1022)

**변경 내용**:
1. connections를 넷 단위로 재그룹화 (같은 넷의 connections를 하나로 묶기)
2. 2핀 넷: 기존 L자 라우팅 유지
3. 3+ 핀 넷: 접합점 계산 → 각 핀에서 접합점까지 개별 와이어 생성

```python
def _route_net_star(p, sch, pin_positions: list[tuple[int,int]]):
    """Route a multi-pin net using star topology with junction point."""
    if len(pin_positions) < 2:
        return 0
    if len(pin_positions) == 2:
        _route_wire(p, sch, *pin_positions[0], *pin_positions[1])
        return 1

    # Calculate junction point (median of all pin positions)
    xs = [pos[0] for pos in pin_positions]
    ys = [pos[1] for pos in pin_positions]
    jx = sorted(xs)[len(xs) // 2]  # median X
    jy = sorted(ys)[len(ys) // 2]  # median Y

    # Grid snap
    jx = round(jx / 10) * 10
    jy = round(jy / 10) * 10

    # Route each pin to junction
    count = 0
    for px, py in pin_positions:
        _route_wire(p, sch, px, py, jx, jy)
        count += 1
    return count
```

#### 방안 B: Canonical 경로 수정 (트렁크 분할)

`routing/trunk_branch.py` 또는 `WireRouting.to_legacy_segments()`에서 트렁크를 접합점에서 분할:

**구현 위치**: `routing/models.py`의 `to_legacy_segments()` 또는 새 함수 `split_at_junctions()`

**변경 내용**:
1. `WireRouting.junctions`에서 접합점 좌표 수집
2. 각 트렁크 세그먼트를 접합점에서 분할
3. 분할된 세그먼트를 legacy 포맷으로 반환

```python
def to_legacy_segments_split(self) -> list[dict]:
    """Convert to legacy wire segments, splitting trunks at junctions."""
    junction_coords = {(j.x, j.y) for j in self.junctions}
    segments = []

    for seg in self.segments:
        splits = _find_junction_splits(seg, junction_coords)
        if splits:
            segments.extend(splits)
        else:
            segments.append({"x1": seg.x1, "y1": seg.y1,
                           "x2": seg.x2, "y2": seg.y2})
    return segments

def _find_junction_splits(seg, junction_coords):
    """Split a segment at any junction points that lie on it."""
    # For horizontal segments: check junctions with same Y, X between x1 and x2
    # For vertical segments: check junctions with same X, Y between y1 and y2
    ...
```

### 3.3 권장 구현 순서

**Phase A (즉시 효과, Legacy 경로)**:
1. `bridge_script.py`에 `_route_net_star()` 함수 추가
2. connections 처리를 넷 단위 재그룹화 + 스타 라우팅으로 변경
3. 14개 → 25개 시뮬레이션 성공 목표

**Phase B (구조적 개선, Canonical 경로)**:
1. `WireRouting.to_legacy_segments()`에 트렁크 분할 로직 추가
2. `routing/trunk_branch.py`에서 JunctionPoint를 활용한 세그먼트 분할
3. Canonical 경로(buck, flyback, llc)의 라우팅 품질 향상

**Phase C (고급 기능)**:
1. `routing/costs.py` 비용 함수 도입
2. Region-aware 라우팅
3. Symmetry-aware 라우팅 (half_bridge, full_bridge, 3상 토폴로지)

---

## 4. 파일 영향 분석

### 수정 파일

| 파일 | 변경 내용 | 우선순위 |
|------|----------|---------|
| `bridge/bridge_script.py` | `_route_net_star()` 추가, connections 처리 변경 | Phase A |
| `services/_circuit_render.py` | `nets_to_connections_grouped()` 추가 | Phase A |
| `routing/models.py` | `to_legacy_segments_split()` 추가 | Phase B |
| `routing/trunk_branch.py` | 트렁크 분할 로직 | Phase B |
| `routing/costs.py` | 새 파일: 비용 함수 정의 | Phase C |

### 신규 파일

| 파일 | 내용 | 우선순위 |
|------|------|---------|
| `routing/costs.py` | 비용 함수 (`crossing_penalty`, `detour_penalty`, `bend_penalty`) | Phase C |
| `routing/region_router.py` | Region-aware 라우팅 | Phase C |

### 테스트 파일

| 파일 | 내용 |
|------|------|
| `tests/unit/test_star_routing.py` | 스타형 라우팅 단위 테스트 |
| `tests/unit/test_trunk_split.py` | 트렁크 분할 단위 테스트 |
| `tests/integration/test_all_topologies_sim.py` | 25개 토폴로지 PSIM 시뮬레이션 통합 테스트 |

---

## 5. 성공 기준

### Phase A 완료 기준
- [ ] 25개 토폴로지 중 20개 이상 PSIM 시뮬레이션 성공
- [ ] 기존 14개 성공 토폴로지 퇴행 없음
- [ ] 1002+ 단위 테스트 통과

### Phase B 완료 기준
- [ ] Canonical 경로(buck, flyback, llc) 트렁크-브랜치 라우팅에서 접합점 분할 동작
- [ ] routing_quality_report의 unconnected_pins = 0

### Phase C 완료 기준
- [ ] 25개 토폴로지 전체 시뮬레이션 성공
- [ ] routing_quality_report의 detour_ratio < 1.5
- [ ] crossing_count 30% 감소 (Phase A 대비)

---

## 6. 리스크

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| 스타형 라우팅이 시각적으로 지저분할 수 있음 | 낮음 | 접합점 좌표 최적화 (핀들의 median 사용) |
| 트렁크 분할 시 기존 라우팅 퇴행 | 중간 | Phase B를 feature flag로 제어 |
| PSIM 그리드 정렬 미스매치 | 높음 | 모든 좌표에 `round(x/10)*10` 적용 |
| 복잡한 토폴로지(NPC, FOC)의 특수 컴포넌트 | 중간 | 핀 매핑 테이블 지속 보강 |

---

## 7. 부록: PSIM PsimConvertToPython 와이어 패턴

### 검증된 PSIM 와이어 API 호출
```python
# 직선 와이어
p.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="200", Y1="100", X2="220", Y2="100")

# L자 와이어 (3점, 2세그먼트)
p.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="530", Y1="230", X2="570", Y2="230", X3="570", Y3="250")

# Z자 와이어 (4점, 3세그먼트)
p.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="870", Y1="-120", X2="870", Y2="-150", X3="1010", Y3="-150", X4="1010", Y4="150")
```

### PSIM 다점 와이어 지원
현재 `_route_wire`는 2점 와이어만 생성. PSIM API는 X3/Y3, X4/Y4를 지원하여 단일 와이어 요소에 L자/Z자 경로를 포함할 수 있음. 이를 활용하면 와이어 수를 줄이고 라우팅 품질을 높일 수 있음.
