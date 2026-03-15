# Step 7: 자연어 Intent Parser 정교화

> 우선순위: P2
> 예상 범위: `src/psim_mcp/parsers/intent_parser.py`
> 의존: Step 1~6 전부 (안정적인 생성 파이프라인이 선행되어야 함)

---

## 1. 목적

사용자의 자연어 요청을 **CircuitRequirements**로 정확하게 변환한다.

현재 상태:
- Claude(LLM)가 자연어를 해석하여 tool 파라미터로 변환
- 이 과정이 LLM prompt 의존적이라 불안정
- "48V 입력 buck 컨버터"는 잘 되지만, "배터리 충전용 회로 추천해줘"는 처리 불가

목표:
- 3단계 점진적 자연어 처리 구현
- topology 자동 선택 및 파라미터 추출
- 누락 정보에 대한 가이드 질문 생성

---

## 2. 3단계 구현 전략

### 2.1 Stage 1: Constrained Intent (제약 기반)

사용자가 topology를 명시하는 경우:

```
입력: "48V 입력 12V 출력 buck 컨버터 만들어줘"
추출: topology=buck, vin=48, vout=12
```

구현:
- topology 키워드 매칭 (한/영 모두)
- 숫자 + 단위 패턴 추출 (V, A, Hz, Ω, μH, μF)
- 추출 결과 → CircuitRequirements

키워드 매핑 예시:
```python
TOPOLOGY_KEYWORDS = {
    "buck": ["buck", "벅", "강압", "step-down", "step down", "스텝다운"],
    "boost": ["boost", "부스트", "승압", "step-up", "step up", "스텝업"],
    "flyback": ["flyback", "플라이백"],
    "llc": ["llc", "공진"],
    "full_bridge": ["full bridge", "풀브리지", "h-bridge", "h브리지"],
    # ...
}
```

### 2.2 Stage 2: Guided Slot Filling (가이드 질문)

topology는 식별됐지만 필수 파라미터가 부족한 경우:

```
입력: "buck 컨버터 만들어줘"
응답: "입력 전압과 출력 전압을 알려주세요.
       예: 48V 입력, 12V 출력, 부하 5A"
```

구현:
- generator의 `required_fields`와 사용자 입력 비교
- 누락 필드에 대한 질문 템플릿 생성
- 기본값 제안 포함

```python
SLOT_QUESTIONS = {
    "vin": "입력 전압은 몇 V인가요?",
    "vout_target": "목표 출력 전압은 몇 V인가요?",
    "iout_target": "출력 전류(부하)는 몇 A인가요?",
    "switching_frequency": "스위칭 주파수를 지정하시겠어요? (기본: 50kHz)",
}
```

### 2.3 Stage 3: Free-form to Spec (자유 형식)

topology를 명시하지 않는 경우:

```
입력: "배터리 충전 회로 만들어줘, 12V 배터리"
추론: topology=cc_cv_charger, battery_voltage=12
```

구현:
- 용도 키워드 → 적합 topology 매핑
- 복수 후보 시 추천 목록 제시

```python
USE_CASE_MAP = {
    "충전": ["cc_cv_charger", "ev_obc"],
    "인버터": ["half_bridge", "full_bridge", "three_phase_inverter"],
    "태양광": ["pv_mppt_boost", "pv_grid_tied"],
    "모터": ["bldc_drive", "pmsm_foc_drive", "induction_motor_vf"],
    "역률": ["boost_pfc", "totem_pole_pfc"],
    "LED": ["buck", "flyback"],
    "전원": ["buck", "boost", "flyback"],
}
```

---

## 3. MCP Tool 설계

### 3.1 새 tool: `design_circuit`

기존 `preview_circuit`의 상위 레벨 도구:

```python
@mcp.tool(description="자연어로 회로를 설계합니다. 사양을 분석하여 적절한 회로를 추천하고 생성합니다.")
async def design_circuit(description: str) -> str:
    """Parse natural language and generate a circuit.

    Examples:
      - "48V to 12V buck 컨버터"
      - "태양광 패널용 MPPT 회로"
      - "BLDC 모터 드라이브 회로"
    """
```

흐름:
```
description → intent_parser.parse()
    ↓
topology + requirements 추출
    ↓
generator.generate(requirements)
    ↓
validator.validate(spec)
    ↓
preview (ASCII + SVG)
    ↓
사용자 확인 대기
```

### 3.2 누락 정보 처리

intent parser가 필수 정보를 추출하지 못하면:
- 부족한 항목 목록 + 질문을 응답에 포함
- 사용자가 추가 정보를 제공하면 다시 parse

---

## 4. 단위 파서

자연어에서 숫자+단위를 추출하는 파서:

```python
UNIT_PATTERNS = {
    "voltage": r"(\d+\.?\d*)\s*(V|볼트|volt)",
    "current": r"(\d+\.?\d*)\s*(A|암페어|amp)",
    "frequency": r"(\d+\.?\d*)\s*(Hz|kHz|MHz|헤르츠)",
    "resistance": r"(\d+\.?\d*)\s*(Ω|옴|ohm)",
    "inductance": r"(\d+\.?\d*)\s*(H|mH|μH|uH|헨리)",
    "capacitance": r"(\d+\.?\d*)\s*(F|mF|μF|uF|패럿)",
    "power": r"(\d+\.?\d*)\s*(W|kW|와트|watt)",
}
```

SI 접두어 변환:
- k → ×1e3, M → ×1e6
- m → ×1e-3, μ/u → ×1e-6, n → ×1e-9, p → ×1e-12

---

## 5. 구현 범위

### 파일 생성
- `src/psim_mcp/parsers/__init__.py`
- `src/psim_mcp/parsers/intent_parser.py` (메인 파서)
- `src/psim_mcp/parsers/unit_parser.py` (단위 추출)
- `src/psim_mcp/parsers/keyword_map.py` (키워드 매핑 데이터)

### 파일 수정
- `tools/circuit.py`: `design_circuit` tool 추가
- `server.py`: tool 등록

---

## 6. 테스트 계획

### 단위 파서
- "48V" → 48.0
- "100kHz" → 100000.0
- "47μH" → 47e-6
- "10옴" → 10.0

### Intent 파서
- "buck 컨버터 48V 입력 12V 출력" → topology=buck, vin=48, vout=12
- "부스트 승압 회로" → topology=boost
- "LLC 공진 컨버터 400V" → topology=llc, vin=400
- "태양광 MPPT" → topology=pv_mppt_boost
- "BLDC 모터 드라이브 48V" → topology=bldc_drive, vin=48

### 가이드 질문
- "buck 컨버터 만들어줘" → vin, vout 질문 생성
- "회로 만들어줘" → topology 선택 질문 생성

---

## 7. 완료 기준

- [ ] 단위 파서 구현 (V, A, Hz, Ω, H, F 지원)
- [ ] topology 키워드 매핑 (한/영 29개 topology)
- [ ] Stage 1 constrained intent 동작
- [ ] Stage 2 guided slot filling 동작
- [ ] Stage 3 use-case 기반 추천 동작
- [ ] `design_circuit` tool 등록 및 동작
- [ ] 기존 preview_circuit / create_circuit과 공존
- [ ] 기존 테스트 통과
