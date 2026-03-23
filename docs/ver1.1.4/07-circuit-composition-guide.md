# PSIM 회로도 구성 방법 기획서

> **Version**: 1.1.4
> **Date**: 2026-03-24
> **목적**: PSIM 네이티브 포맷 기반 회로도 생성의 정확한 방법론 정립 및 현재 문제점 해결 계획

---

## 1. 현재 상태 진단

### 1.1 검증 완료 토폴로지 (8/12)

| 토폴로지 | 입력 | 목표 출력 | 실측 출력 | 상태 |
|----------|------|----------|----------|------|
| buck | 48V | 12V | 11.42V | ✅ 정상 |
| boost | 12V | 24V | 23.36V | ✅ 정상 |
| buck_boost | 24V | 15V | 8.76V | ✅ 정상 |
| cuk | 24V | 12V | 21.11V | ✅ 정상 |
| sepic | 12V | 24V | 23.34V | ✅ 정상 |
| full_bridge | 400V | AC | 94.91V | ✅ 정상 |
| half_bridge | 400V | AC | 92.65V | ✅ 정상 |
| bidirectional | 48V | 12V | 11.94V | ✅ 정상 |

### 1.2 미검증 토폴로지 (4/12)

| 토폴로지 | 제너레이터 | PSIM 검증 | 차단 원인 |
|----------|-----------|----------|----------|
| **flyback** | ✅ 있음 | ❌ 미검증 | `TF_1F_1` 트랜스포머 PORTS 포맷 미확인 |
| **forward** | ✅ 있음 | ❌ 미검증 | `TF_1F_1` 트랜스포머 PORTS 포맷 미확인 |
| **llc** | ✅ 있음 (템플릿) | ❌ 미검증 | PSIM 예제 파일 의존, 커스텀 레이아웃 없음 |
| **boost_pfc** | ✅ 있음 | ❌ 미검증 | VAC + 다이오드 브릿지 레이아웃 미확인 |

### 1.3 핵심 문제점 요약

1. **트랜스포머 PORTS 좌표 미검증** — flyback/forward/llc의 핵심 차단 요인
2. **LLC가 PSIM 예제 파일에 하드코딩** — 자체 회로 생성 불가
3. **AC 소스 + 다이오드 브릿지 레이아웃 없음** — boost_pfc 차단
4. **bridge_script.py의 버그들** — `_try_generate()` 리턴값 불일치, 파라미터 전달 오류
5. **PSIM 타입/파라미터 매핑 중복** — bridge_script.py와 svg_renderer.py에 이중 정의

---

## 2. PSIM 네이티브 포맷 상세

### 2.1 .psimsch 파일 구조

`.psimsch`는 PSIM 2026의 **바이너리 포맷**으로, `psimapipy` Python API를 통해서만 생성 가능.

```
MCP Server (Python 3.12+)
    ↓ JSON IPC
bridge_script.py (Python 3.8/3.9)
    ↓ psimapipy API
PSIM 엔진 → .psimsch 바이너리 파일
```

### 2.2 소자 생성 API

```python
p.PsimCreateNewElement(
    sch,                    # 스키매틱 핸들
    "MULTI_MOSFET",         # PSIM 소자 타입
    "SW1",                  # 이름 (유니크)
    PORTS=[x1,y1, x2,y2, x3,y3],  # 핀 좌표 (Python list, NOT string)
    DIRECTION=0,            # 0=right, 90=down, 180=left, 270=up
    PAGE=0,
    XFLIP=0,
    _OPTIONS_=16,
    SubType="Ideal",        # MULTI_* 타입에 필수
    **parameters            # 소자별 파라미터
)
```

### 2.3 핵심 규칙: PORTS는 반드시 Python list

```python
# ❌ 잘못된 방식 (문자열)
PORTS="{150, 100, 200, 100}"

# ✅ 올바른 방식 (Python list of int)
PORTS=[150, 100, 200, 100]
```

### 2.4 소자별 PORTS 구조 (레퍼런스 파일 기반 검증)

#### MOSFET (3핀 = 6좌표)
```python
# PORTS = [drain_x, drain_y, source_x, source_y, gate_x, gate_y]

# 수직 MOSFET (DIR=0): drain 위, source 아래, gate 왼쪽
PORTS=[200, 100, 200, 150, 180, 130]
#      drain(200,100)
#          |  50px
#      source(200,150)
#      gate(200-20, 100+30) = (180, 130)

# 수평 MOSFET (DIR=270): drain 왼쪽, source 오른쪽, gate 아래
PORTS=[150, 100, 200, 100, 180, 120]
#      drain(150,100) --50px-- source(200,100)
#                                   |
#                              gate(180,120)
```

#### Diode (2핀 = 4좌표)
```python
# PORTS = [anode_x, anode_y, cathode_x, cathode_y]

# 수직 다이오드 (DIR=270): anode 아래, cathode 위
PORTS=[510, 170, 510, 120]    # 레퍼런스: buck_converted.py
#      anode(510,170)
#          |  50px
#      cathode(510,120)

# 수평 다이오드 (DIR=180): anode 오른쪽, cathode 왼쪽
PORTS=[130, 760, 80, 760]     # 레퍼런스: converted_fullbridge.py
```

#### R / L / C (2핀 = 4좌표)
```python
# PORTS = [pin1_x, pin1_y, pin2_x, pin2_y]

# 수평 인덕터 (DIR=0)
PORTS=[250, 100, 300, 100]    # pin1(250,100) --50px-- pin2(300,100)

# 수직 캐패시터 (DIR=90)
PORTS=[300, 100, 300, 150]    # pin1(300,100) -- pin2(300,150)
```

#### 트랜스포머 TF_1F_1 (4핀 = 8좌표)  ⭐ 핵심 발견
```python
# PORTS = [pri1_x, pri1_y, pri2_x, pri2_y, sec1_x, sec1_y, sec2_x, sec2_y]
# 레퍼런스: converted_Flyback_converter_with_peak_current_mode_control.py

p.PsimCreateNewElement(sch, "TF_1F_1", "T1",
    AREA=[430, -160, 480, -90],
    DIRECTION=0, PAGE=0, XFLIP=0, _OPTIONS_=16,
    PORTS=[430, -150, 430, -100, 480, -100, 480, -150],
    #      pri1(430,-150)  pri2(430,-100)  sec1(480,-100)  sec2(480,-150)
    #
    #      pri1 ──┐    ┌── sec2
    #      (top)  │~~~~│  (top)
    #      pri2 ──┘    └── sec1
    #      (bot)          (bot)
    Lm__magnetizing_="Lm",
    Np__primary_="a_ps",
    Ns__secondary_="1",
    Rp__primary_="Rp",
    Rs__secondary_="Rs",
    Lp__pri__leakage_="L_lk_p",
    Ls__sec__leakage_="L_lk_s",
)
```

#### 트랜스포머 TF_IDEAL (4핀 = 8좌표)
```python
# 레퍼런스: converted_ResonantLLC_CurrentAndVoltageLoop.py

# DIR=0 (수직 배치)
PORTS=[860, 170, 860, 220, 910, 170, 910, 220]
#      pri1(860,170)  pri2(860,220)  sec1(910,170)  sec2(910,220)

# DIR=270 (수평 배치)  - converted_fullbridge.py
PORTS=[90, 100, 140, 100, 90, 50, 140, 50]
#      pri1(90,100)  pri2(140,100)  sec1(90,50)  sec2(140,50)
```

#### 태양전지 SOLAR_CELL_PHY (5핀 = 10좌표)
```python
# 레퍼런스: converted_mppt_inc.py
PORTS=[-50, 120, -50, 180, -130, 120, -130, 180, -90, 100]
#      anode+(−50,120)  cathode−(−50,180)
#      anode+(−130,120) cathode−(−130,180)
#      irradiance(−90,100)
```

#### DC 소스 VDC (2핀 = 4좌표)
```python
# PORTS = [positive_x, positive_y, negative_x, negative_y]
PORTS=[120, 100, 120, 150]    # positive(120,100) -- negative(120,150)
```

#### Ground (1핀 = 2좌표)
```python
PORTS=[120, 150]
```

#### GATING (1핀 = 2좌표)
```python
# 레퍼런스: buck_converted.py
PORTS=[180, 170]              # output 핀 위치

# 듀티 사이클 → 각도 변환
# D=25% → "0 90."   (0°~90°)
# D=50% → "0 180."  (0°~180°)
# D=75% → "0 270."  (0°~270°)
Switching_Points=" 0 180."    # 50% 듀티
```

### 2.5 PSIM 타입 매핑

| 제너레이터 내부명 | PSIM API 타입 | SubType |
|-----------------|--------------|---------|
| MOSFET | `MULTI_MOSFET` | `"Ideal"` |
| IGBT | `MULTI_IGBT` | `"Ideal"` |
| Diode | `MULTI_DIODE` | `"Ideal"` |
| Resistor | `MULTI_RESISTOR` | `"Level 1"` |
| Inductor | `MULTI_INDUCTOR` | `"Level 1"` |
| Capacitor | `MULTI_CAPACITOR` | `"Level 1"` |
| Transformer | `TF_1F_1` | — |
| IdealTransformer | `TF_IDEAL` | — |
| DC_Source | `VDC` | — |
| AC_Source | `VAC` | — |
| PWM_Generator | `GATING` | — |
| Ground | `Ground` | — |

### 2.6 파라미터 이름 매핑

| 제너레이터 파라미터 | PSIM API 이름 |
|------------------|--------------|
| `voltage` | `Amplitude` |
| `resistance` | `Resistance` |
| `inductance` | `Inductance` |
| `capacitance` | `Capacitance` |
| `on_resistance` | `On_Resistance` |
| `forward_voltage` | `Diode_Voltage_Drop` |
| `np_turns` | `Np__primary_` |
| `ns_turns` | `Ns__secondary_` |
| `magnetizing_inductance` | `Lm__magnetizing_` |

### 2.7 와이어 연결

```python
# 직선 와이어
p.PsimCreateNewElement(sch, "WIRE", "",
    X1="200", Y1="130", X2="260", Y2="130", PAGE=0)

# L자형 와이어 (맨하탄 라우팅: 수평 → 수직)
p.PsimCreateNewElement(sch, "WIRE", "",
    X1="200", Y1="100", X2="300", Y2="100", PAGE=0)  # 수평
p.PsimCreateNewElement(sch, "WIRE", "",
    X1="300", Y1="100", X2="300", Y2="150", PAGE=0)  # 수직
```

**규칙**:
- 같은 좌표의 핀은 자동 연결 (0-length wire 불필요)
- X1,Y1,X2,Y2는 **문자열** (PORTS와 다름!)
- 게이트 와이어가 GND 버스와 같은 Y좌표를 공유하면 안 됨

---

## 3. 회로도 구성 파이프라인

### 3.1 전체 흐름

```
사용자 자연어 입력
    ↓
intent_parser → {topology, specs, confidence}
    ↓
TopologyGenerator.generate(specs)
    ↓
┌─────────────────────────────────┐
│ 1. 설계 수식 계산               │
│    D, L, C, R, n 등              │
│ 2. 컴포넌트 배치 (좌표 결정)      │
│    layout.py의 make_*() 헬퍼 사용  │
│ 3. 네트 연결 (핀 매핑)           │
│    nets: [{name, pins}]          │
│ 4. 시뮬레이션 파라미터 설정       │
└─────────────────────────────────┘
    ↓
Validator (구조/전기/파라미터/연결 검증)
    ↓
ASCII + SVG 프리뷰 렌더링
    ↓
PreviewStore에 토큰 저장 (TTL 3600s)
    ↓
사용자 확인 (confirm_circuit)
    ↓
bridge_script.py → PSIM API → .psimsch 파일 생성
    ↓
run_simulation → Simview=1 → PSIM 파형 창 표시
```

### 3.2 제너레이터 출력 구조

```python
{
    "topology": "buck",
    "metadata": {
        "duty_cycle": 0.25,
        "inductance": 1.2e-4,
        "capacitance": 4.7e-5,
        ...
    },
    "components": [
        {
            "id": "V1",
            "type": "DC_Source",
            "parameters": {"voltage": 48.0},
            "position": {"x": 120, "y": 100},
            "direction": 0,
            "ports": [120, 100, 120, 150]  # flat list
        },
        ...
    ],
    "nets": [
        {"name": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"]},
        {"name": "net_sw_junc", "pins": ["SW1.source", "D1.cathode", "L1.pin1"]},
        ...
    ],
    "simulation": {
        "time_step": "1E-006",
        "total_time": "0.02"
    }
}
```

### 3.3 레이아웃 헬퍼 함수 (layout.py)

```python
# 그리드 상수
PIN_SPACING = 50   # PSIM 표준 핀 간격
MAIN_Y = 100       # 메인 신호 경로 높이
GND_Y = 150        # GND 버스 높이

# 컴포넌트 팩토리
make_vdc(id, x, y, voltage)                    # DC 소스 (수직)
make_mosfet_h(id, x, y, **params)              # 수평 MOSFET (DIR=270)
make_mosfet_v(id, x, y, **params)              # 수직 MOSFET (DIR=0)
make_diode_h(id, x, y, **params)               # 수평 다이오드
make_diode_v(id, x, y, **params)               # 수직 다이오드
make_inductor(id, x, y, inductance)            # 수평 인덕터
make_capacitor(id, x, y, capacitance)          # 수직 커패시터
make_resistor(id, x, y, resistance)            # 수직 저항
make_gating(id, x, y, fsw, duty_degrees)       # PWM 게이팅
make_transformer(id, p1x,p1y, p2x,p2y,        # 트랜스포머
                 s1x,s1y, s2x,s2y, **params)
```

---

## 4. 검증된 레이아웃 패턴

### 4.1 Buck Converter (검증 완료)

```
        SW1(D=270)        L1(D=0)
  V1 ─→ [D──S] ─→ [pin1──pin2] ─→ C1 ─→ R1
(120,100) (150,100)(200,100)        (300,100) (350,100)
  |                                    |        |
  |        D1(D=270)                   |        |
  └──GND──[A──K]──────────────────────┘────────┘
(120,150)  (220,150-100)            (300,150) (350,150)
```

좌표:
- V1: (120,100)-(120,150), GND: (120,150)
- SW1: drain(150,100), source(200,100), gate(180,120)
- D1: anode(220,150), cathode(220,100)
- L1: (250,100)-(300,100)
- C1: (300,100)-(300,150)
- R1: (350,100)-(350,150)

### 4.2 Boost Converter (검증 완료)

```
       L1(D=0)        D1(D=0)
  V1 ─→ [pin1──pin2] ─→ [A──K] ─→ C1 ─→ R1
(80,100)  (120,100-170,100)         (300,100) (350,100)
  |            |                       |        |
  |        SW1(D=0, 수직)              |        |
  └──GND──[D──S]──────────────────────┘────────┘
(80,150)  (200,100-150)             (300,150) (350,150)
```

### 4.3 Half Bridge (검증 완료)

```
  V1 ────── SW1.drain (상단 스위치)
(80,80)     (200,80)
              |
            SW1.source / SW2.drain = 미드포인트
              (200,130)    (200,160)
              |
  GND ────── SW2.source (하단 스위치)
(80,230)     (200,210)
```

### 4.4 Flyback Converter (레퍼런스 발견, 미적용)

레퍼런스 파일 `converted_Flyback_converter_with_peak_current_mode_control.py`에서 확인된 정확한 구조:

```python
# TF_1F_1 트랜스포머 (핵심!)
PORTS=[430, -150, 430, -100, 480, -100, 480, -150]
#      pri_top     pri_bot     sec_bot     sec_top
DIRECTION=0

# 레이아웃 패턴:
#   pri1(430,-150)      sec2(480,-150)
#        |     ~~~~        |
#   pri2(430,-100)      sec1(480,-100)
```

### 4.5 LLC Resonant Converter (레퍼런스 발견, 미적용)

레퍼런스 파일 `converted_ResonantLLC_CurrentAndVoltageLoop.py`에서 확인:

```python
# TF_IDEAL (이상 변압기)
PORTS=[860, 170, 860, 220, 910, 170, 910, 220]
DIRECTION=0

# LLC 구조:
# V+ → SW_high → mid → Cr → Lr → TF_IDEAL → D_rect → Cout → R_load
#       SW_low → GND            Lm (병렬)
```

---

## 5. 해결 계획

### Phase 1: 긴급 버그 수정 (1-2일)

#### 1-1. `_try_generate()` 리턴값 불일치 수정
```
문제: 정상 경로 → 7개 값 리턴, 에러 경로 → 6개 값 리턴
위치: services/circuit_design_service.py
해결: 에러 경로에도 동일한 7개 값 리턴하도록 수정
```

#### 1-2. `create_circuit_direct()` 파라미터 전달 오류
```
문제: simulation_settings를 specs 자리에 전달
위치: services/circuit_design_service.py
해결: specs와 simulation_settings를 올바르게 분리하여 전달
```

#### 1-3. Bridge subprocess stderr 미처리
```
문제: stderr 버퍼 가득 차면 데드락 발생 가능
위치: adapters/real_adapter.py
해결: stderr를 비동기로 소비하거나 PIPE 대신 DEVNULL로
```

### Phase 2: 트랜스포머 기반 토폴로지 완성 (3-5일)

#### 2-1. Flyback PSIM 검증 및 수정

**작업 내용**:
1. `converted_Flyback_...py`에서 TF_1F_1의 정확한 PORTS/AREA/파라미터 추출
2. `generators/flyback.py`의 `make_transformer()` 호출을 레퍼런스에 맞게 수정
3. `layout.py`의 `make_transformer()` 헬퍼 함수 좌표 검증
4. PSIM에서 실제 시뮬레이션 돌려서 출력 전압 확인

**레퍼런스 데이터** (이미 확보):
```python
# TF_1F_1 검증된 호출
PORTS=[430, -150, 430, -100, 480, -100, 480, -150]
DIRECTION=0, XFLIP=0, _OPTIONS_=16
Lm__magnetizing_="Lm"
Np__primary_="a_ps"
Ns__secondary_="1"
```

#### 2-2. Forward 컨버터 검증

**작업 내용**:
1. Flyback과 동일한 TF_1F_1 기반이므로 flyback 완료 후 진행
2. Forward 특유의 리셋 와인딩/클램프 회로 추가 검증
3. `generators/forward.py` 레이아웃 수정

#### 2-3. LLC 레조넌트 자체 생성 구현

**작업 내용**:
1. `converted_ResonantLLC_...py`에서 전체 레이아웃 패턴 추출
2. Half-bridge + Cr + Lr + Lm(shunt) + TF_IDEAL + 정류기 구조 구현
3. PSIM 예제 파일 의존 제거
4. `generators/llc.py`를 완전한 formula-based generator로 리팩토링

**핵심 구조**:
```
V+ ─── SW_high ─── midpoint ─── Cr ─── Lr ─── TF_IDEAL ─── D_rect ─── Cout ─── R
        SW_low ─── GND                  Lm (병렬)
```

### Phase 3: AC 기반 토폴로지 (2-3일)

#### 3-1. Boost PFC 레이아웃 구현

**작업 내용**:
1. `converted_3-ph_PWM_rectifier_with_PFC.py`에서 VAC + 다이오드 브릿지 패턴 추출
2. VAC → 4x MULTI_DIODE 브릿지 → Boost 스테이지 레이아웃 구현
3. `generators/boost_pfc.py` 수정

**레이아웃 구조**:
```
VAC ─── D_bridge (4x MULTI_DIODE) ─── L_boost ─── SW ─── D_boost ─── Cout ─── R
                                                    |
                                                   GND
```

### Phase 4: 코드 품질 개선 (2-3일)

#### 4-1. PSIM 매핑 통합
```
문제: _PSIM_TYPE_MAP, _PARAM_NAME_MAP이 bridge_script.py와 svg_renderer.py에 중복
해결: shared/psim_mappings.py로 통합 (bridge는 인라인 유지, 단 원본 소스 명시)
```

#### 4-2. 시뮬레이션 기본값 통합
```
문제: _SIMULATION_DEFAULTS가 bridge_script.py와 simulation_defaults.py에 중복
해결: bridge_script.py가 MCP 서버에서 전달받은 값을 우선 사용하도록 수정
```

#### 4-3. SIMCONTROL 위치 개선
```
현재: max_x + 100, min_y - 50 (고정 오프셋)
개선: 컴포넌트 바운딩 박스 계산 후 우측 상단에 자동 배치
```

---

## 6. 레퍼런스 파일 활용 전략

### 6.1 보유 중인 PSIM 변환 파일

| 파일 | 용도 | 추출 대상 |
|------|------|----------|
| `buck_converted.py` | 기본 DC-DC 레퍼런스 | MOSFET, Diode, R/L/C 좌표 패턴 |
| `converted_Flyback_...py` | **Flyback TF_1F_1** | 트랜스포머 PORTS, 파라미터 이름 |
| `converted_ResonantLLC_...py` | **LLC TF_IDEAL** | 이상변압기, 공진탱크 레이아웃 |
| `converted_fullbridge.py` | Full Bridge TF_IDEAL | DIR=270 트랜스포머 패턴 |
| `converted_3-ph_PWM_rectifier_with_PFC.py` | **PFC 다이오드 브릿지** | VAC + 4x Diode 패턴 |
| `converted_mppt_inc.py` | PV MPPT | SOLAR_CELL_PHY 핀 구조 |
| `converted_mppt_po.py` | PV P&O | MPPT 제어 블록 패턴 |
| `converted_pv_grid.py` | 계통연계 PV | 인버터 + 그리드 연결 |

### 6.2 활용 방법

```
1. 레퍼런스 파일에서 PsimCreateNewElement 호출 추출
2. PORTS, DIRECTION, AREA, 파라미터 이름 정리
3. layout.py의 make_*() 헬퍼에 반영
4. 제너레이터에서 헬퍼 호출
5. PSIM에서 실제 시뮬 돌려서 검증
6. 검증 결과를 topology-status에 업데이트
```

---

## 7. 좌표 시스템 및 레이아웃 규칙

### 7.1 그리드 규칙

- **핀 간격**: 50px (PSIM 표준)
- **컴포넌트 간 수평 간격**: 80-160px (토폴로지에 따라)
- **메인 신호 경로**: Y=100 (수평 라인)
- **GND 버스**: Y=150 또는 Y=230 (토폴로지에 따라)
- **게이트 핀**: GND 버스보다 위에 위치해야 함 (단락 방지)

### 7.2 DIRECTION에 따른 핀 위치 변화

```
DIR=0   (기본, 오른쪽): 심볼 그대로
DIR=90  (아래):         90° 시계방향 회전
DIR=180 (왼쪽):         180° 회전
DIR=270 (위):           270° 시계방향 (= 90° 반시계) 회전
```

### 7.3 배치 패턴

**DC-DC Non-isolated (수평 흐름)**:
```
V+ → [Switch] → [Inductor] → [Capacitor] → [Load]
 |                                |            |
GND ←←←←←←← [Diode] ←←←←←←←←←←┘←←←←←←←←←←←┘
```

**DC-DC Isolated (2단 구성)**:
```
1차측:  V+ → [Switch] → [Transformer Pri]
2차측:  [Transformer Sec] → [Rectifier] → [Filter] → [Load]
GND:    각 측에 별도 GND
```

**Half/Full Bridge (수직 스택)**:
```
V+ ─── SW_high.drain
        SW_high.source ── midpoint ── 출력
        SW_low.drain
GND ── SW_low.source
```

---

## 8. 테스트 전략

### 8.1 단위 테스트 (mock 모드)

```bash
# 전체 테스트
uv run pytest tests/unit -q

# 제너레이터별 테스트
uv run pytest tests/unit/test_generators.py -k "flyback" -v

# 브릿지 헬퍼 테스트
uv run pytest tests/unit/test_bridge_helpers.py -v
```

### 8.2 PSIM 실물 검증 (real 모드)

```bash
# 1. 회로 생성
# Claude Desktop에서: "flyback 48V→5V 2A 만들어줘"

# 2. 시뮬레이션 실행
# Claude Desktop에서: "시뮬레이션 돌려줘"

# 3. Simview에서 파형 확인
# - Vout이 목표값 ±10% 이내인지
# - 정상상태 도달 여부
# - 오실레이션/불안정 여부
```

### 8.3 검증 체크리스트

각 토폴로지 검증 시:
- [ ] 제너레이터가 components + nets 정상 생성
- [ ] bridge_script에서 PSIM 소자 정상 생성
- [ ] 와이어 연결 정상 (단락/개방 없음)
- [ ] SIMCONTROL 위치 정상
- [ ] 시뮬레이션 실행 성공
- [ ] 출력값 목표 대비 ±10% 이내
- [ ] Simview에서 파형 정상 표시

---

## 9. 우선순위 요약

| 순서 | 작업 | 예상 소요 | 임팩트 |
|------|------|----------|--------|
| **P0-1** | `_try_generate()` 버그 수정 | 1h | 에러 핸들링 정상화 |
| **P0-2** | Flyback TF_1F_1 검증/수정 | 3h | +1 토폴로지 |
| **P0-3** | Forward TF_1F_1 검증/수정 | 2h | +1 토폴로지 |
| **P0-4** | LLC 자체 생성 구현 | 5h | +1 토폴로지, 템플릿 의존 제거 |
| **P0-5** | Boost PFC AC+브릿지 구현 | 4h | +1 토폴로지 |
| **P1-1** | PSIM 매핑 통합 | 2h | 유지보수성 향상 |
| **P1-2** | 시뮬 기본값 통합 | 1h | 불일치 위험 제거 |
| **P2** | 3상 인버터/PV/모터 | 2-3주 | 토폴로지 확장 |

---

## 부록: 주요 파일 위치

| 파일 | 역할 |
|------|------|
| `src/psim_mcp/generators/*.py` | 토폴로지별 회로 생성 |
| `src/psim_mcp/generators/layout.py` | 컴포넌트 배치 헬퍼 |
| `src/psim_mcp/data/component_library.py` | 소자 정의 + 핀 매핑 |
| `src/psim_mcp/bridge/bridge_script.py` | PSIM API 브릿지 |
| `src/psim_mcp/services/circuit_design_service.py` | 설계 파이프라인 |
| `src/psim_mcp/validators/` | 회로 검증 |
| `output/converted_*.py` | PSIM 레퍼런스 파일 |
