# PSIM Cloud Service: Go-To-Market Plan

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상위 문서**: [PRD.md](./PRD.md) | [commercialization-strategy.md](./commercialization-strategy.md)

---

## 1. 목적

이 문서는 PSIM Cloud Service를 내부 파일럿에서 외부 고객 유료 도입까지 확장하기 위한 시장 진입 전략을 정리한다.

핵심 원칙:

- 공개 SaaS보다 B2B 전용 모델을 먼저 간다
- 고객이 가장 빨리 체감하는 가치는 “반복 시뮬레이션 자동화”다
- 첫 판매는 기능 수보다 “신뢰 가능한 실행 환경”이 중요하다

---

## 2. 기본 가설

### 2.1 고객이 실제로 사는 것

고객은 “LLM” 자체를 사는 것이 아니라 아래 가치를 산다.

- 반복 시뮬레이션 시간 절감
- 실행 이력 추적 가능성
- 설계 검토/비교 자동화
- 팀 단위 운영성

### 2.2 초기 타깃 고객

우선순위:

1. 전력전자 설계팀
2. PSU / inverter / motor drive 개발 조직
3. 대학/연구소의 반복 시뮬레이션 랩
4. PSIM 기반 검증 자동화가 필요한 컨설팅 팀

### 2.3 초기 도입 환경

가장 적합한 초기 환경:

- 고객 내부 Windows 실행 환경 존재
- 이미 PSIM을 사용 중
- 반복 파라미터 스터디가 많음
- 도입 담당자가 엔지니어 또는 R&D 매니저

---

## 3. 단계별 출시 전략

### Phase 1. Internal Pilot

목표:
- 내부 팀이 실제 업무에 사용할 수 있는 수준 검증

핵심 성공 기준:

- 업로드 → job 실행 → 결과 조회가 안정적으로 동작
- 자연어 요청이 일정 수준 이상 유용함
- Windows worker 운영이 가능함

해야 할 일:

- 내부 사용자 3~10명 테스트
- 실제 프로젝트 기반 반복 작업 사용
- 실패 케이스 로그 수집

출력물:

- 도입 사례 3개 이상
- 시간 절감 사례
- 실패 원인 리스트

### Phase 2. Design Partner Program

목표:
- 첫 외부 고객 후보 1~3곳 확보

권장 대상:

- 이미 PSIM 라이선스를 가진 팀
- 전력전자 자동화 pain point가 분명한 팀
- 베타 제품 사용에 적극적인 팀

제공 방식:

- 무료 또는 저가 PoC
- 전용 구축형 또는 전용 호스팅형

성공 기준:

- 반복 사용 빈도 확보
- 기능 요청 패턴 수집
- 구매 의사 확인

### Phase 3. Paid Pilot

목표:
- 첫 유료 고객 확보

추천 판매 방식:

- 3개월 PoC 계약
- 고객별 전용 worker 환경
- 초기 onboarding/support 포함

포함 기능:

- 프로젝트 등록
- 자연어 실행
- 구조화 API 실행
- 결과 조회
- 감사 로그

### Phase 4. Early Commercial

목표:
- 유료 고객 다수화

권장 모델:

- single-tenant hosted
- customer-dedicated worker
- customer-specific SLA

이 단계에서는 아직 공개 SaaS보다 “고객별 분리 운영”이 적합하다.

---

## 4. 제품 포지셔닝

### 4.1 한 줄 포지셔닝

“PSIM 기반 전력전자 시뮬레이션 자동화를 위한 팀용 실행 플랫폼”

### 4.2 경쟁 회피 포인트

이 서비스는 일반 LLM 앱과 다르다.

- 단순 채팅이 아니라 실제 simulation execution까지 담당
- CAD/EDA 범용 도구가 아니라 PSIM 중심 vertical tool
- 개인 보조도구가 아니라 팀 운영 플랫폼

### 4.3 고객 설득 메시지

- “반복 시뮬레이션을 사람이 클릭하지 않아도 된다”
- “누가 어떤 조건으로 돌렸는지 남는다”
- “자연어 입력을 팀 표준 실행 흐름으로 바꿔준다”

---

## 5. 초기 패키지 전략

### 5.1 추천 판매 패키지

#### Package A: Internal Team Edition
- 고객사 전용 설치
- 1개 worker
- 소수 사용자
- PoC용

#### Package B: Dedicated Hosted Edition
- 고객 전용 worker pool
- API key 제공
- 감사 로그/이력 포함

#### Package C: Enterprise Edition
- 전용 환경
- SSO
- 고급 권한 관리
- 장기 보관/감사 기능

---

## 6. 가격 전략

초기에는 단순 가격 모델이 적합하다.

### 6.1 초기 권장 방식

- 월 고정 구독 + 설치/onboarding fee

예시 축:

- 조직 수
- worker 수
- 월 job 실행량
- 저장 용량

### 6.2 나중에 추가 가능한 사용량 기반 항목

- worker runtime
- Anthropic token usage
- artifact storage
- 고급 리포트/비교 기능

---

## 7. 영업 방식

### 7.1 첫 고객 확보 방식

추천:

- 직접 컨택 기반 B2B
- PSIM 사용자 커뮤니티/네트워크 활용
- 연구실/기업 R&D팀 대상 PoC 제안

비추천:

- 초기부터 셀프서비스 광고 유입
- 일반 대중 대상 마케팅

### 7.2 첫 미팅에서 확인할 질문

1. PSIM 사용 빈도는 얼마나 되는가
2. 가장 반복적인 작업은 무엇인가
3. 파라미터 스터디/비교 작업 비중은 어느 정도인가
4. 현재 결과 공유 방식은 무엇인가
5. 내부 보안 정책상 클라우드 사용이 가능한가

---

## 8. KPI

### 8.1 제품 KPI

- 주간 active organization
- organization당 weekly job 수
- job 성공률
- 평균 대기 시간
- 평균 재실행률

### 8.2 사업 KPI

- design partner 수
- 유료 pilot 전환율
- pilot → 장기 계약 전환율
- 고객당 월 반복 사용량

---

## 9. 리스크

| 리스크 | 설명 | 대응 |
|--------|------|------|
| 라이선스 불확실성 | hosted 실행 권한 불명확 | 계약 우선 확인 |
| 초기 판매 난이도 | vertical B2B라 영업이 느림 | design partner 전략 |
| 과도한 범위 확장 | 처음부터 SaaS를 크게 만들 위험 | dedicated model 우선 |
| 지원 비용 증가 | 고객별 환경 차이 | 표준 배포 템플릿 구축 |

---

## 10. 권장 순서

1. 내부 파일럿 운영
2. design partner 1~3곳 확보
3. dedicated hosted 또는 구축형 paid pilot
4. repeatable deployment 확보
5. enterprise sales motion 정착
6. 이후 multi-tenant 공개 SaaS 검토

---

## 11. 결론

이 서비스의 첫 시장 진입은 공개 SaaS가 아니라 **전용형 B2B 제품**이 맞다.

즉, 가장 현실적인 초기 전략은:

- 내부에서 검증하고
- 첫 고객은 design partner로 받고
- 전용 구축형/전용 호스팅형으로 유료 전환한 뒤
- 반복 가능한 운영 모델이 생기면 그때 multi-tenant SaaS를 검토하는 것이다.
