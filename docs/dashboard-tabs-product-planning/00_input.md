# 대시보드 탭 제품 기획 입력

> 상태: 기획·구현·공개 runtime 검증 완료 (2026-08-26)

## 사용자 요청

> dashboard의 각 탭들에 대해 기획문서를 작성하고, 개선할점이 있는지 파악해서 정리해봐

## 목적

- 현재 `/dashboard`의 6개 탭이 답해야 하는 사용자 질문과 정보 우선순위를 정의한다.
- 화면 구현, shared 계약, FastAPI read model, 실제 공개 runtime을 함께 확인해 개선점을 찾는다.
- 후속 구현이 바로 티켓으로 분해될 수 있도록 우선순위와 수용 기준을 남긴다.

## 대상 독자와 사용자

- 1차 사용자: 에이전트의 인지 상태와 장애 원인을 확인하는 개발자·운영자
- 2차 독자: dashboard 기능을 구현·검증하는 frontend/backend/QA 담당자
- 결정: 현재 공개 route에는 로그인이나 접근 제한을 두지 않는다. memory,
  reflection, 관계 summary/evidence 원문은 일반 관람객에게도 표시한다. provider
  원문·prompt·API key·embedding·내부 model trace는 제품 데이터가 아니므로 제외한다.

## 범위

- 공통 shell: 세계 상태, 연결 상태, 에이전트 선택, 전역 로그 rail
- 탭: 개요, 관계, 기억, 계획, 성찰, 진단 로그
- 상태: 초기 로딩, 정상, stale, 부분 데이터, empty, 오류, 재연결
- 데이터 경계: `/dashboard/state`, `/dashboard/events`, shared DTO, diagnostics redaction
- 접근성, 모바일, 한국어 문구, URL 상태, 성능과 테스트

## 비목표

- 기획 단계에서는 source code나 API를 구현하지 않는다. 후속 승인에 따라 본
  문서의 P0/P1 개선은 같은 주제 기록 아래 구현한다.
- mock 데이터나 추정 지표를 새로 만들지 않는다.
- React/Vite/FastAPI/Phaser 경계를 변경하지 않는다.
- Brain 결과 객체에 dashboard 전용 diagnostics 필드를 추가하지 않는다.

## 기준 문서와 구현

- `SPEC.md` §9.1 운영 관측 대시보드 계약
- `TODO.md`의 agent inspector 및 방향성 관계 항목
- `packages/frontend/src/dashboard/Dashboard.tsx`
- `packages/frontend/src/hooks/useDashboardState.ts`
- `packages/shared/src/index.ts`의 `Dashboard*` 계약
- `packages/backend/src/api/main.py`의 dashboard read model
- `docs/dashboard-relationship-redesign/`의 관계 탭 상세 기획

## 2026-08-26 공개 runtime 표본

`https://agentcrossing.byfred.io/dashboard/state`를 읽기 전용으로 확인했다.

- 정상 상태: scheduler running, planning error 없음, agent 6명
- 응답 크기: 280,413 bytes
- 포함 데이터: memory 350개, 방향성 관계 30쌍, diagnostics event 64개
- 위치: 6명 모두 `current_location_path=null`이지만 action과 destination에는 장소가 있음
- 성찰: 6명 중 5명은 최근 memory 100개 안에 reflection이 0개

표본은 특정 시점의 운영 상태이며 제품 계약 자체로 간주하지 않는다. 다만 위치 의미, pagination, payload 분리, empty state의 필요성을 확인하는 실증 자료로 사용한다.

## 2026-08-26 구현 후 공개 runtime 표본

- 응답 크기: 117,828 bytes (`memory_limit=50`, `event_limit=0`)
- agent 6명 모두 physical map 또는 명시적인 arrival source로 위치 해석
- memory 원문과 관계 evidence를 표시하며 public diagnostics 내부 trace field는 0개
- scheduler running, planning/cognitive runtime error 없음
- 탭 URL·키보드 이동과 기억/계획/로그 화면을 공개 브라우저에서 확인
