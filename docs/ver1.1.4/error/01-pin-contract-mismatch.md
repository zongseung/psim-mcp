# 01. Pin Contract Mismatch

## 문제 정의

`circuit_templates.py` 또는 generator 출력의 connection endpoint와 `component_library.py`의 pin 정의가 불일치할 수 있다.

이 문제는 가장 치명적이다. endpoint가 잘못되면:

- validator는 `CONN_UNKNOWN_PIN`을 발생시킨다.
- SVG renderer는 pin 좌표를 찾지 못해 일부 wire를 생략한다.
- PSIM bridge도 pin position map을 만들지 못해 일부 wire 생성에 실패한다.

---

## 계약의 기준점

회로 연결의 기준 데이터는 component library의 `pins` 배열이어야 한다.

예시:

- `IGBT`: `collector`, `emitter`, `gate`
- `Transformer`: `primary_in`, `primary_out`, `secondary_in`, `secondary_out`
- `Center_Tap_Transformer`: `primary_in`, `primary_out`, `secondary_top`, `secondary_center`, `secondary_bottom`

관련 파일:

- `src/psim_mcp/data/component_library.py`
- `src/psim_mcp/validators/structural.py`

---

## 실제 확인된 불일치

### 1. IGBT를 MOSFET처럼 사용

아래 template들은 `IGBT`인데도 `drain/source` pin을 사용한다.

- `three_phase_inverter`
- `three_level_npc`
- `pv_grid_tied`
- `pmsm_foc_drive`
- `induction_motor_vf`

이 경우 library 기준 valid pin은 `collector/emitter/gate`뿐이다.

상태:

- 2026-03-19 기준 template는 수정 완료

영향:

- upper/lower switch bus connection이 누락되거나 잘못 연결됨
- inverter leg가 끊겨 보임

---

### 2. Transformer pin naming 불일치

일반 `Transformer`에 대해 template가 존재하지 않는 pin을 참조한다.

문제 예:

- `llc`
- `phase_shifted_full_bridge`
- `ev_obc`

잘못된 예:

- `secondary_top`
- `secondary_bottom`
- `secondary_center`

하지만 일반 `Transformer` 정의는:

- `secondary_in`
- `secondary_out`

뿐이다.

상태:

- template의 일부 사례(`llc`, `phase_shifted_full_bridge`, `ev_obc`)는 수정 완료
- generator(`forward`, `flyback`, `llc`)의 `primary1/primary2/secondary1/secondary2` alias도 정규화 완료

영향:

- secondary rectifier/load path wire 누락
- 절연형 토폴로지에서 출력측이 붕괴

---

### 3. Center-Tap Transformer primary pin naming 불일치

`push_pull` template는 `Center_Tap_Transformer`에 대해 다음 pin을 사용한다.

- `primary_center`
- `primary_top`
- `primary_bottom`

하지만 library 정의에는 없다.

현재 정의는:

- `primary_in`
- `primary_out`
- `secondary_top`
- `secondary_center`
- `secondary_bottom`

상태:

- 2026-03-19 기준 library/template 계약 보정 완료

영향:

- push-pull 1차측 구성이 잘못됨
- preview/PSIM 모두 primary routing 실패 가능

---

## 왜 구조적으로 위험한가

지금 구조에서는 pin 이름을 다음 세 군데가 각자 알고 있다.

1. template
2. renderer / bridge
3. component library

이 셋 중 하나라도 어긋나면 회로도가 깨진다.

---

## 권장 조치

1. `component_library.py`를 pin 계약의 단일 source of truth로 고정
2. `circuit_templates.py` 전수 검사 스크립트 추가
3. 잘못된 template endpoint를 전부 library 기준으로 수정
4. validator를 CI 필수 단계로 포함

---

## 전수 검사 결과 요약

초기 점검 당시 다음 template에서 invalid pin이 확인되었다.

- `push_pull`
- `llc`
- `phase_shifted_full_bridge`
- `three_phase_inverter`
- `three_level_npc`
- `pv_grid_tied`
- `pmsm_foc_drive`
- `induction_motor_vf`
- `ev_obc`

즉, 문제는 일부 edge case가 아니라 template 세트 전반에 퍼져 있다.

현재는 template endpoint lint 기준 invalid pin 0건이다.
또한 `forward`, `flyback`, `llc` generator 경로의 transformer alias mismatch도 정리되었다.
