# Step 6: Windows Real Mode Smoke Test

> 우선순위: P1
> 예상 범위: 테스트 스크립트 + 결과 문서
> 의존: Step 4 (Bridge 배선 구현)
> 환경 제약: **Windows + PSIM 설치 필수**

---

## 1. 목적

Step 1~5에서 구현한 회로 생성 시스템이 **실제 Windows PSIM 환경에서 동작하는지** 검증한다.

이 단계가 전체 프로젝트의 **실증 분기점**이다.
- 통과 → 실제 사용 가능한 시스템
- 실패 → 실패 지점 기반으로 bridge/API 수정

---

## 2. 사전 준비

### 2.1 환경 구성

```
1. PSIM 설치 확인
   - PSIM.exe 경로 확인
   - PSIM 번들 Python 경로 확인
   - psimapipy 설치 확인

2. 프로젝트 설정
   - git clone → uv sync
   - .env 파일 작성 (PSIM_MODE=real, 경로 설정)

3. Claude Desktop 설정
   - claude_desktop_config.json 작성
   - psim MCP 서버 등록
```

### 2.2 환경 검증 스크립트

```python
# test_psim_env.py — PSIM 설치 전 환경 확인
import subprocess, sys, os

print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print(f"PSIM_PATH: {os.environ.get('PSIM_PATH', 'NOT SET')}")

try:
    from psimapipy import PSIM
    p = PSIM("")
    print(f"PSIM Valid: {p.IsValid()}")
    print(f"API Functions: {[x for x in dir(p) if not x.startswith('_')]}")
except ImportError:
    print("ERROR: psimapipy not found")
except Exception as e:
    print(f"ERROR: {e}")
```

---

## 3. 테스트 시나리오

### 3.1 기본 생성 테스트 (필수)

| # | 테스트 | 입력 | 확인 항목 |
|---|--------|------|-----------|
| T1 | API 함수 확인 | 환경 검증 스크립트 | 사용 가능한 함수 목록 |
| T2 | 빈 스키매틱 생성 | `PsimFileNew()` | 파일 생성 성공 |
| T3 | 부품 1개 생성 | DC Source 1개 | element 생성 + 저장 성공 |
| T4 | 부품 생성 type 확인 | 각 부품 type 시도 | 어떤 type 문자열이 유효한지 |
| T5 | 파라미터 설정 | `PsimSetElmValue` | 값 설정 성공 |
| T6 | 배선 함수 확인 | wire 관련 함수 탐색 | 배선 API 존재 여부 |

### 3.2 회로 생성 테스트 (핵심)

| # | 테스트 | 회로 | 확인 항목 |
|---|--------|------|-----------|
| T7 | Buck 생성 | buck 템플릿 | .psimsch 파일 생성, PSIM에서 열림 |
| T8 | Buck 부품 확인 | T7 파일 | 6개 부품 모두 존재 |
| T9 | Buck 배선 확인 | T7 파일 | 배선 연결 여부 |
| T10 | Buck 시뮬 | T7 파일 | 시뮬레이션 실행 성공 |
| T11 | Boost 생성 | boost 템플릿 | 생성 + 열기 + 시뮬 |
| T12 | Full Bridge 생성 | full_bridge 템플릿 | 생성 + 열기 + 시뮬 |

### 3.3 MCP 연동 테스트 (통합)

| # | 테스트 | 방법 | 확인 항목 |
|---|--------|------|-----------|
| T13 | Claude Desktop 연결 | 서버 시작 + 상태 확인 | get_status 성공 |
| T14 | 자연어 생성 | "Buck 컨버터 만들어줘" | preview → confirm 흐름 |
| T15 | 생성 → 시뮬 | "시뮬레이션 돌려줘" | 실제 결과 반환 |
| T16 | 파라미터 스윕 | "저항 10~100Ω 스윕" | 반복 시뮬레이션 결과 |

---

## 4. "Save as Python Code" 분석

이 단계에서 반드시 수행해야 할 작업:

1. PSIM GUI에서 Buck 컨버터를 수동으로 그림
2. File → Save as Python Code
3. 생성된 .py 파일을 분석하여 아래 기록:
   - `PsimCreateNewElement`의 정확한 type 문자열
   - 배선 생성 함수와 인자 형식
   - 파라미터 설정 순서와 키 이름
4. 이 정보를 `component_catalog`의 `psim_element_type`에 반영

---

## 5. 결과 기록 형식

각 테스트 결과를 아래 형식으로 기록:

```markdown
### T1: API 함수 확인
- 결과: PASS / FAIL
- PSIM 버전: ___
- 사용 가능한 함수: [...]
- 비고:

### T7: Buck 생성
- 결과: PASS / FAIL
- 생성된 파일 크기: ___ bytes
- PSIM에서 열기: 성공 / 실패 (에러 메시지)
- 부품 수 확인: 요청 6개 / 실제 ___개
- 스크린샷: (첨부)
```

---

## 6. 실패 시 대응

| 실패 유형 | 대응 |
|-----------|------|
| psimapipy import 실패 | PSIM 번들 Python 경로 확인, pip install 경로 확인 |
| PsimFileNew 실패 | PSIM 라이선스 확인, PSIM.exe 경로 확인 |
| PsimCreateNewElement 실패 | type 문자열 변경, Save as Python Code 참조 |
| 배선 함수 없음 | 좌표 겹침 방식 또는 COM/DDE 대안 탐색 |
| 시뮬레이션 실패 | 회로 연결 오류, simulation settings 확인 |

---

## 7. 완료 기준

- [ ] 환경 검증 스크립트 실행 성공
- [ ] PSIM API 함수 목록 문서화
- [ ] "Save as Python Code" 분석 완료
- [ ] T1~T6 기본 테스트 전부 PASS
- [ ] T7~T10 Buck 회로 테스트 PASS (생성 + 열기 + 시뮬)
- [ ] T13~T15 MCP 연동 테스트 PASS
- [ ] 결과 문서 작성 (`docs/ver1.1.1/06-smoke-test-results.md`)
