# PSIM Cloud Service: Product Requirements Document (PRD)

> **버전**: v2.0
> **작성일**: 2026-03-15
> **상태**: Draft

---

## 1. 제품 개요

### 1.1 제품명
**PSIM Cloud Service** — Anthropic API와 Windows PSIM Worker를 연결한 전력전자 시뮬레이션 SaaS

### 1.2 한 줄 요약
사용자가 웹앱 또는 API에서 자연어/구조화 요청을 보내면, 서비스가 Anthropic API로 의도를 해석하고 Windows PSIM Worker에서 실제 시뮬레이션을 실행한 뒤 결과를 반환하는 B2B SaaS

### 1.3 배경 및 동기

문제:
- PSIM은 강력하지만 Windows GUI/로컬 환경 의존성이 크다
- 팀 단위 협업, 결과 공유, 실행 이력 관리, 권한 관리가 어렵다
- 자연어 기반 자동화가 있어도 현재 구조는 로컬 MCP 도구 수준에 머문다

기회:
- Anthropic API 기반으로 자연어 해석을 서버 측에서 일관되게 처리할 수 있다
- Supabase를 활용하면 인증, 멀티테넌트 데이터, 파일/이력 관리 기반을 빠르게 구축할 수 있다
- Windows Worker Pool을 두면 고객은 로컬 PSIM 환경 없이도 시뮬레이션 요청과 결과 조회가 가능하다

### 1.4 목표

| 구분 | 목표 |
|------|------|
| **단기** | 단일 조직(single tenant pilot) 기준 업로드 → 시뮬레이션 → 결과 조회 SaaS 흐름 완성 |
| **중기** | 멀티테넌트 조직/멤버십/권한/감사 로그 포함 B2B 베타 출시 |
| **장기** | 워커 풀 확장, 사용량 과금, 엔터프라이즈 전용 환경 제공 |

### 1.5 비목표

- 브라우저에서 직접 PSIM을 렌더링하는 것
- PSIM 라이선스를 우회하는 것
- 완전 자동 회로 생성기를 1차 목표로 삼는 것
- 초기 버전에서 실시간 공동 편집을 제공하는 것

---

## 2. 대상 사용자

### 2.1 주요 사용자
- 전력전자 엔지니어 팀
- 파워 설계 검증 조직
- 연구소/랩 운영 팀
- 시뮬레이션 자동화가 필요한 컨설팅 조직

### 2.2 구매자/관리자
- 엔지니어링 매니저
- R&D 플랫폼팀
- IT 관리자

### 2.3 사용 환경
- 사용자 클라이언트: 웹앱 또는 고객 내부 도구
- 백엔드: Linux 기반 API/오케스트레이션 서버
- 실행 환경: Windows PSIM Worker
- LLM: Anthropic API
- 데이터 계층: Supabase

---

## 3. 핵심 사용자 시나리오

### US-001: 자연어 시뮬레이션 요청
> "이 buck 회로의 switching frequency를 80kHz로 바꾸고 0.1초 시뮬레이션을 실행해줘"

수락 기준:
1. 사용자가 프로젝트를 선택할 수 있다
2. 자연어 입력이 실행 가능한 작업 명세로 변환된다
3. Worker가 실제 시뮬레이션을 수행한다
4. 결과와 로그가 조직 단위로 저장된다

### US-002: API 기반 배치 실행
> CI 또는 내부 설계 도구가 직접 API로 sweep job을 등록한다

수락 기준:
1. API key 또는 서비스 계정으로 인증 가능
2. 요청이 queue에 적재된다
3. 작업 상태를 polling 또는 realtime으로 조회할 수 있다

### US-003: 결과 공유 및 감사
> 팀 리더가 어떤 프로젝트가 언제 어떤 조건으로 실행됐는지 확인한다

수락 기준:
1. 조직별 실행 이력이 남는다
2. 결과 파일과 메타데이터가 연결된다
3. 누가 실행했는지 추적 가능하다

---

## 4. 기능 요구사항

### 4.1 P0 — Must Have

#### FR-001: 조직/사용자 인증
- Supabase Auth 기반 로그인
- 조직(workspace) 단위 데이터 분리
- 역할: `owner`, `admin`, `member`, `viewer`

#### FR-002: 프로젝트 등록
- 프로젝트 메타데이터 등록
- 원본 `.psimsch` 파일 업로드/참조
- 프로젝트별 기본 실행 옵션 저장

#### FR-003: 자연어 실행 요청
- 사용자가 자연어 또는 구조화 요청 제출
- Anthropic API가 요청을 내부 실행 스펙으로 변환
- 변환 결과 검증 후 queue에 등록

#### FR-004: Worker 기반 시뮬레이션 실행
- Windows Worker가 queue에서 job을 가져와 PSIM 실행
- 실행 상태/로그/오류 저장
- 성공 시 결과 artifact 저장

#### FR-005: 결과 조회
- job 상태 조회
- 결과 메타데이터/요약/다운로드 URL 조회
- 최근 실행 히스토리 조회

#### FR-006: 감사 로그
- 누가 어떤 프로젝트에 어떤 요청을 보냈는지 기록
- API key 사용 이력, 실패 이력 저장

### 4.2 P1 — Should Have

#### FR-007: 파라미터 스윕
- 범위 지정 실행
- 결과 비교 테이블 제공

#### FR-008: Worker Pool 관리
- 워커 heartbeat
- 워커 상태(online, busy, offline, draining)
- 워커별 실행 capacity 관리

#### FR-009: API Key / Service Account
- CI 또는 외부 도구 연결용 machine credential
- 조직 단위 scope 제한

#### FR-010: 사용량 측정
- job 수, 시뮬레이션 시간, 토큰 사용량, 저장소 사용량 기록

### 4.3 P2 — Nice to Have

#### FR-011: Realtime 상태 스트리밍
- job 진행률 push 업데이트

#### FR-012: 엔터프라이즈 전용 환경
- 고객별 전용 worker pool
- VPC 또는 온프레미스 배치

#### FR-013: 비용/과금
- 플랜별 quota
- 과금 연동

---

## 5. 비기능 요구사항

### 5.1 보안
- 조직별 데이터 격리
- Supabase RLS 필수
- Worker와 control plane 간 토큰 인증
- 프로젝트 경로/파일 접근 제한
- 결과 다운로드는 signed URL 또는 권한 검증 후 발급

### 5.2 안정성
- job 재시도 정책 필요
- worker 장애 감지 필요
- API 서버/queue/worker 장애가 분리되어야 함

### 5.3 성능
- API 요청 응답: 1~3초 이내
- job 등록: 1초 이내
- 시뮬레이션 실행 시간은 queue/worker 상태에 따라 비동기 처리

### 5.4 운영성
- job/event/audit/worker 상태 추적 가능
- 운영자가 실패 원인을 확인할 수 있어야 함

### 5.5 상업성
- 내부 파일럿 → 고객 전용 환경 → 멀티테넌트 SaaS 순으로 확장 가능해야 함

---

## 6. 기술 제약

| 항목 | 제약 |
|------|------|
| PSIM 실행 | Windows Worker 필요 |
| PSIM API | 번들 Python 기반 제약 존재 |
| LLM | Anthropic API 상업용 조건 준수 필요 |
| 멀티테넌트 | 데이터베이스 레벨 격리 필요 |
| 장시간 작업 | Edge Function보다 별도 backend/worker 구조 필요 |

---

## 7. 제품 전략

### 7.1 권장 상용화 순서
1. 내부 파일럿
2. single-tenant hosted deployment
3. customer-dedicated worker pool
4. multi-tenant SaaS

### 7.2 초기 판매 모델
- 조직별 subscription
- 실행량/저장량/토큰 사용량 기반 추가 과금 가능

---

## 8. 성공 지표

- 활성 조직 수
- 주간 시뮬레이션 job 수
- 성공률
- 평균 실행 대기 시간
- 사용자당 반복 사용률
- 수동 PSIM 작업 시간 절감률

---

## 9. 마일스톤

### Phase 1: Internal Pilot
- Auth / workspace / project / job / worker / results 최소 흐름
- Anthropic API 기반 자연어 → 실행 스펙 변환
- 단일 Windows Worker

### Phase 2: Private Beta
- 조직 권한
- API key
- worker pool
- 감사 로그

### Phase 3: Commercial Beta
- 멀티테넌트 안정화
- 사용량 측정
- 운영 대시보드

### Phase 4: GA
- 엔터프라이즈 계약 지원
- 전용 환경 배포 옵션
- 과금 체계
