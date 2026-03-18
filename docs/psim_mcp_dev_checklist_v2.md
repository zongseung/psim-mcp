# PSIM 없는 Mac 환경에서 개발 후 Windows에서 PSIM 연동하는 방법

> **참고**: 이 문서는 초기 검토용 체크리스트다. 현재 기준의 공식 설계/계약은 `PRD.md`, `architecture.md`, `api-spec.md`, `development-guide.md`를 따른다. 본 문서의 예시 경로, 파일명, 환경 변수명은 최신 설계와 다를 수 있다.

## 1. 목적

이 문서는 다음 상황을 전제로 합니다.

- **Mac에서는 PSIM이 없다**
- **Mac에서 MCP 서버 구조와 공통 로직을 먼저 개발한다**
- **Git 저장소에 올린 뒤 Windows에서 내려받아 PSIM 연동 레이어를 붙인다**
- 최종적으로 **Claude Desktop ↔ MCP 서버 ↔ PSIM** 구조로 사용한다

핵심은 **Mac에서 전체를 다시 짜지 않고**, 처음부터 **PSIM 의존 부분과 비의존 부분을 분리**해서 만드는 것입니다.

---

## 2. 기본 결론

이 방식은 가능하며, 오히려 현재 조건에서는 가장 현실적인 접근입니다.

권장 구조는 다음과 같습니다.

- **Mac 개발 단계**: MCP 서버 골격, tool 인터페이스, 입력 검증, 응답 포맷, mock 테스트 구현
- **Git 저장소 관리**: 공통 코드와 설정 템플릿 업로드
- **Windows 연동 단계**: PSIM 설치, Python API 설치, 실제 PSIM adapter 구현 및 통합 테스트

즉, Windows에서 전체 코드를 다시 만드는 것이 아니라,
**Windows에서는 PSIM 실행 어댑터만 붙이는 방식**으로 가야 합니다.

---

## 3. 해야 하는 사항

### 3.1 아키텍처를 처음부터 분리하기

반드시 다음 레이어를 분리합니다.

1. **MCP 서버 레이어**
   - Claude가 호출하는 tool 정의
   - 예: `open_project`, `set_parameter`, `run_simulation`, `export_results`

2. **서비스/비즈니스 로직 레이어**
   - 입력값 검증
   - 경로 검증
   - 결과 요약 생성
   - 에러 메시지 표준화

3. **PSIM 어댑터 레이어**
   - `MockPsimAdapter` (Mac 개발용)
   - `RealPsimAdapter` (Windows + PSIM 연동용)

이 구조를 지키면 Mac에서는 mock으로 개발하고, Windows에서는 실제 어댑터만 교체하면 됩니다.

---

### 3.2 Mac에서는 mock 기반으로 먼저 개발하기

Mac에서는 실제 PSIM이 없으므로 다음 범위까지 먼저 끝냅니다.

- MCP 서버 실행 확인
- tool 목록 노출 확인
- 각 tool의 입력 스키마 검증
- 예외 처리 구조 작성
- mock 결과 반환
- 로그 저장 방식 정리
- `.env` 또는 설정 파일 구조 확정

예:

- `run_simulation()` 호출 시
  - mock 모드에서는 더미 결과 JSON 반환
  - Windows 실환경에서는 PSIM 실행 결과 반환

---

### 3.3 Git 저장소 구조를 명확히 만들기

권장 예시는 아래와 같습니다.

```text
psim-mcp-server/
├─ src/
│  ├─ server.py
│  ├─ config.py
│  ├─ tools/
│  │  ├─ open_project.py
│  │  ├─ set_parameter.py
│  │  ├─ run_simulation.py
│  │  └─ export_results.py
│  ├─ adapters/
│  │  ├─ base.py
│  │  ├─ mock_psim.py
│  │  └─ real_psim_windows.py
│  └─ services/
│     └─ simulation_service.py
├─ tests/
├─ .env.example
├─ requirements.txt
├─ README.md
└─ .gitignore
```

추가로 아래 파일은 초기에 꼭 정리하는 것이 좋습니다.

- `README.md`: 설치 순서, 실행 방법, 환경 변수 설명
- `.env.example`: Windows에서 채워야 할 값 예시
- `.gitignore`: 로그, 산출물, 임시파일 제외

---

### 3.4 환경 의존 값을 코드에서 분리하기

다음 값은 하드코딩하지 않습니다.

- PSIM 설치 경로
- Python 실행 파일 경로
- 프로젝트 파일 경로
- 출력 폴더 경로
- 로그 폴더 경로
- Claude Desktop 또는 MCP 관련 설정값

권장 예시:

```env
PSIM_MODE=mock
PSIM_PATH=
PYTHON_EXE=
PSIM_PROJECT_DIR=
PSIM_OUTPUT_DIR=
LOG_DIR=./logs
```

Windows에서는 예를 들어 다음처럼 분리합니다.

```env
PSIM_MODE=real
PSIM_PATH=C:\Altair\Altair_PSIM_2025
PYTHON_EXE=C:\Program Files\Altair\2025\common\python\python3.8\win64\python.exe
PSIM_PROJECT_DIR=C:\work\psim-projects
PSIM_OUTPUT_DIR=C:\work\psim-output
LOG_DIR=C:\work\logs
```

---

### 3.5 인터페이스를 먼저 고정하기

어댑터 교체가 가능하려면 최소 인터페이스를 먼저 확정해야 합니다.

예시:

```python
class BasePsimAdapter:
    def open_project(self, path: str):
        raise NotImplementedError

    def set_parameter(self, name: str, value):
        raise NotImplementedError

    def run_simulation(self):
        raise NotImplementedError

    def export_results(self, output_dir: str):
        raise NotImplementedError
```

그리고 Mac에서는:

```python
adapter = MockPsimAdapter()
```

Windows에서는:

```python
adapter = RealPsimAdapter(...)
```

처럼 주입되게 만드는 것이 좋습니다.

---

### 3.6 Windows에서만 실제 연동 구현하기

Windows에서는 다음 순서로 진행합니다.

1. Git 저장소 clone
2. Python 환경 구성
3. PSIM 설치 확인
4. PSIM Python API 설치 확인
5. `RealPsimAdapter` 구현
6. 작은 샘플 프로젝트로 통합 테스트
7. Claude Desktop에 MCP 서버 등록
8. 실제 대화에서 tool 호출 검증

Windows 단계에서 가장 먼저 확인할 것은 다음입니다.

- PSIM이 실제로 실행되는가
- PSIM Python API가 설치되었는가
- Python에서 샘플 스크립트가 도는가
- 결과 파일 생성 경로에 쓰기 권한이 있는가

---

### 3.7 테스트를 2종류로 분리하기

테스트는 꼭 아래처럼 나누는 것이 좋습니다.

#### A. Mac/공통 테스트

- tool 입력 검증
- 응답 JSON 형식 검증
- 예외 처리 검증
- mock adapter 동작 검증

#### B. Windows/통합 테스트

- 실제 PSIM 호출
- 프로젝트 열기
- 파라미터 변경
- 시뮬레이션 실행
- 결과 파일 생성
- 실패 시 로그 남김

이 둘을 섞어버리면 Mac에서는 테스트가 깨지고, Windows에서는 원인 추적이 어려워집니다.

---

## 4. 주의해야 하는 사항

### 4.1 Mac에서는 끝까지 검증할 수 없다는 점

Mac에는 PSIM이 없으므로, 다음은 검증 불가입니다.

- 실제 PSIM 실행 성공 여부
- 실제 `.smv` 또는 프로젝트 파일 열기
- 실제 결과 파일 생성
- 설치 경로 및 권한 문제
- 라이선스 문제

즉, Mac 단계는 **구조 개발과 인터페이스 검증 단계**이지,
**실제 PSIM 통합 검증 단계가 아닙니다.**

---

### 4.2 경로 문제를 가장 먼저 의심할 것

Windows 연동 시 가장 흔한 문제는 경로입니다.

특히 다음 항목을 주의합니다.

- 공백이 포함된 경로
- 백슬래시 처리 문제
- 존재하지 않는 폴더
- 상대경로/절대경로 혼용
- 결과 폴더 쓰기 권한 부족

그래서 경로는 실행 전에 항상 검증해야 합니다.

권장 체크:

- 파일 존재 여부
- 디렉터리 존재 여부
- 읽기/쓰기 권한
- 로그 디렉터리 자동 생성

---

### 4.3 라이선스/버전 의존성을 분리해서 봐야 함

PSIM 연동은 단순히 코드만 맞는다고 끝나지 않습니다.

주의할 점:

- 설치된 PSIM 버전과 샘플 경로가 다를 수 있음
- Python API 설치 방식이 버전에 따라 달라질 수 있음
- 일부 커뮤니티 문서는 유지보수 상태를 다시 확인해야 함
- 학생 버전/평가판/기관 라이선스에 따라 제약이 있을 수 있음

따라서 Windows에서 첫 통합 테스트를 할 때는
**“내 코드가 틀렸는지”보다 “설치/버전/라이선스가 맞는지”를 먼저 확인**해야 합니다.

---

### 4.4 실제 연동부를 너무 일찍 Mac에서 흉내 내지 말 것

Mac에서 PSIM이 없는데도 실제 파일 포맷이나 실행 절차를 과하게 추정해서 구현하면,
Windows에서 거의 다시 뜯어고쳐야 할 수 있습니다.

따라서 Mac 단계에서는:

- 인터페이스
- 입력/출력 스키마
- 에러 처리 규칙
- 로그 구조

까지만 확실하게 만들고,
실제 PSIM 호출 세부사항은 Windows에서 맞추는 것이 좋습니다.

---

### 4.5 Claude Desktop 연결 방식은 로컬과 원격을 구분할 것

연결 방식은 크게 두 가지입니다.

#### 로컬 방식

- Windows PC에 Claude Desktop 설치
- 같은 Windows PC에서 MCP 서버 실행
- 같은 PC에 PSIM 설치

장점:

- 가장 단순함
- 경로와 권한 문제를 한 머신에서 해결 가능
- 디버깅이 쉬움

#### 원격 방식

- Windows 서버/워크스테이션에 MCP 서버 + PSIM 설치
- Claude Desktop은 다른 PC에서 원격 커넥터로 연결

장점:

- 사용자 PC와 실행 머신 분리 가능

주의점:

- 배포 및 운영 난도 상승
- 인증/보안/방화벽 고려 필요
- 네트워크 오류와 앱 오류가 섞여 디버깅이 어려움

처음에는 **로컬 방식**으로 검증한 뒤, 필요하면 원격으로 옮기는 것이 좋습니다.

---

### 4.6 로그를 반드시 남길 것

연동 실패 시 원인이 코드인지, PSIM인지, 경로인지, 라이선스인지 구분해야 합니다.

최소한 다음은 남기는 것이 좋습니다.

- 호출된 tool 이름
- 입력 파라미터
- 사용한 경로
- 실행 시작/종료 시각
- 성공/실패 상태
- 예외 메시지
- 가능하면 stderr/stdout

로그 없이는 Windows 통합 디버깅이 매우 어렵습니다.

---

### 4.7 Git에 올리면 안 되는 것 정리하기

반드시 제외할 가능성이 큰 항목:

- 라이선스 파일
- 개인 로컬 경로가 박힌 설정 파일
- 대용량 산출물
- 임시 결과 파일
- 로그 파일
- 비밀키, 토큰
- 개인별 Claude/OS 설정 파일

`.env.example`만 올리고, 실제 `.env`는 올리지 않는 편이 안전합니다.

---

## 5. 권장 개발 순서

### 1단계: Mac

- 저장소 생성
- MCP 서버 기본 실행
- tool 인터페이스 설계
- mock adapter 구현
- 입력/출력 스키마 고정
- 테스트 작성
- README 작성

### 2단계: Git

- 공통 코드 push
- `.env.example` 포함
- `.gitignore` 정리
- 실행 예시 문서화

### 3단계: Windows

- repo clone
- Python 환경 준비
- PSIM 설치 확인
- Python API 설치 확인
- 샘플 코드 실행
- real adapter 구현
- 작은 프로젝트로 실험

### 4단계: Claude Desktop 연동

- 로컬 MCP 서버 등록
- tool 인식 확인
- 실제 tool 호출
- 오류 로그 확인
- 성공 후 원격화 여부 검토

---

## 6. 최소 체크리스트

### Mac에서 끝내야 하는 것

- [ ] MCP 서버 실행됨
- [ ] tool 목록이 정상 노출됨
- [ ] mock adapter로 각 tool 호출 가능
- [ ] 설정 파일 구조가 분리됨
- [ ] README에 실행 순서가 있음
- [ ] 테스트가 통과함

### Windows에서 확인해야 하는 것

- [ ] PSIM 실행 가능
- [ ] Python API 설치 확인
- [ ] 샘플 스크립트 실행 가능
- [ ] 프로젝트 파일 접근 가능
- [ ] 결과 폴더 쓰기 가능
- [ ] real adapter 동작 확인
- [ ] Claude Desktop에서 tool 호출 성공

---

## 7. 추천 판단

현재 조건에서는 아래 방식이 가장 안정적입니다.

**추천안**

- Mac: 개발, 테스트, Git 관리
- Windows: PSIM 설치, 실제 연동, 통합 테스트
- Claude Desktop: 처음에는 Windows 로컬 연결로 검증

즉,
**Mac에서 서버 골격을 완성하고, Windows에서는 PSIM 실행 어댑터만 붙이는 전략**이 가장 덜 꼬이고 유지보수도 쉽습니다.

---

## 8. 마지막 메모

이 프로젝트의 핵심 실패 원인은 보통 코드보다 아래에서 많이 나옵니다.

- 경로
- 권한
- 버전
- 라이선스
- 설정 누락

그래서 개발 초기부터
**“구조 분리 + 환경 변수 분리 + 로그 확보 + mock/real 분리”**
이 네 가지를 지키는 것이 가장 중요합니다.

## 10. PSIM 파일 포맷 분석(.psimsch) 관련 리스크와 권장 방향

### 10.1 왜 이 이슈가 중요한가

처음에는 다음과 같은 아이디어가 나올 수 있습니다.

- `.psimsch` 내부 구조를 직접 분석한다
- 부품과 선(Wire)의 표현 규칙을 역으로 찾는다
- 코드로 `.psimsch` 파일을 바로 생성하는 생성기를 만든다

겉보기에는 가장 직접적인 방법처럼 보이지만, 실제로는 이 접근이 **핵심 전략이 되면 위험할 수 있습니다.**

### 10.2 문제가 될 수 있는 이유

#### 기술적 리스크
- `.psimsch`의 **공식 공개 스키마가 확인되지 않은 상태**에서 내부 포맷을 가정하게 됨
- 텍스트처럼 보여도 실제로는 **버전별 숨은 필드, 메타데이터, 좌표 규칙, 연결 규칙**이 있을 수 있음
- 회로가 열리더라도 **PSIM 내부 검증에서 실패**할 수 있음
- 버전이 바뀌면 생성기가 쉽게 깨질 수 있음
- 와이어 연결, 소자 ID, 계층 구조, 라이브러리 참조 방식이 바뀌면 유지보수 비용이 급격히 증가함

#### 운영 리스크
- 공식 지원 경로가 아니면, 오류가 나도 **벤더 지원을 기대하기 어려움**
- 디버깅 기준이 파일 포맷 자체로 내려가므로, 개발 난도가 높아짐
- 자연어 → 회로 생성이라는 상위 목표보다, 파일 포맷 복제 자체에 과도한 시간이 소모될 수 있음

#### 법적·라이선스 리스크
- 독자 포맷을 리버스 엔지니어링해서 생성/변환기를 배포하는 행위는 **EULA나 라이선스 조건**을 반드시 확인해야 함
- 개인 연구용과 팀/상용 배포는 리스크 수준이 다를 수 있음
- 따라서 `.psimsch`를 직접 재현하는 방향은 **법무/계약 확인 전에는 핵심 전략으로 채택하지 않는 것이 안전**함

### 10.3 더 안전한 이유: 공식/준공식 자동화 경로가 이미 존재함

현재까지 확인된 범위에서는 PSIM 쪽에 다음과 같은 우회가 아니라 **더 적절한 경로**가 이미 있습니다.

1. **Save as Python Code**
   - 회로를 Python 코드 형태로 내보내는 기능을 활용해
   - “어떤 요소가 어떤 코드로 생성되는지”를 학습용 샘플로 수집할 수 있음

2. **Python API 기반 회로 생성/수정**
   - 회로 생성, 요소 추가, 연결, 저장 같은 작업을
   - 파일 포맷 직접 조작이 아니라 **API 호출**로 처리하는 것이 더 안전함

3. **Generate Netlist File (XML)**
   - schematic 자체가 아니라 **중간 표현(XML netlist)** 을 활용하면
   - 내부 독자 포맷에 직접 의존하지 않고도 구조 정보를 다룰 수 있음

즉, `.psimsch` 내부를 직접 찍어내는 생성기를 핵심으로 잡기보다,
**Python 코드 생성 기능 + Python API + XML netlist** 를 우선 활용하는 것이 맞습니다.

### 10.4 권장 아키텍처 방향

가장 권장하는 흐름은 아래와 같습니다.

```text
자연어
  ↓
Claude / MCP
  ↓
내부 DSL 또는 JSON 회로 표현
  ↓
PSIM adapter
  ├─ 템플릿 열기
  ├─ 요소 추가
  ├─ 파라미터 수정
  ├─ 연결 생성
  └─ 저장 / 실행
  ↓
PSIM 프로젝트 / 결과 파일
```

즉 핵심은 **`.psimsch` 생성기**가 아니라,
**“자체 중간 표현(DSL/JSON) → 공식/준공식 자동화 경로로 변환”** 입니다.

이렇게 하면:
- Mac에서도 중간 표현과 로직을 먼저 개발 가능
- Windows에서는 실제 PSIM adapter만 붙이면 됨
- 포맷 변경에 대한 직접 의존도가 줄어듦
- 테스트가 쉬워짐
- 장기 유지보수가 수월해짐

### 10.5 실무 권장 우선순위

#### 1순위
- 템플릿 회로 기반 자동화
- 파라미터 변경
- 시뮬레이션 실행
- 결과 추출

#### 2순위
- Save as Python Code 샘플 수집
- 반복 패턴 분석
- API로 신규 요소 생성 자동화

#### 3순위
- XML netlist를 중간 구조로 활용
- 회로 비교, 검증, 변환 보조 기능 추가

#### 비권장 우선순위
- `.psimsch` 내부 포맷을 직접 리버스 엔지니어링해서
- 최종 파일 생성기를 핵심 제품 기능으로 두는 것

### 10.6 팀 문서에 넣어야 할 결론 문장

다음 문장을 팀 기준 방침으로 두는 것을 권장합니다.

> `.psimsch` 파일 포맷 직접 생성은 연구용 보조 과제로만 다루고, 제품/서비스의 핵심 생성 경로는 PSIM의 공식 또는 준공식 자동화 인터페이스(Python code export, Python API, XML netlist)에 기반한다.

### 10.7 체크리스트

- [ ] `.psimsch` 직접 생성기를 핵심 로드맵으로 두지 않는다
- [ ] PSIM EULA/라이선스에서 역공학 제한 조항을 확인한다
- [ ] Save as Python Code 샘플을 충분히 수집한다
- [ ] 템플릿 기반 생성 전략을 먼저 구현한다
- [ ] 내부 DSL/JSON 회로 표현을 먼저 설계한다
- [ ] Windows용 adapter는 파일 포맷 직접 쓰기보다 API 호출 중심으로 구현한다
- [ ] XML netlist를 활용할 수 있는지 보조 경로로 검토한다
