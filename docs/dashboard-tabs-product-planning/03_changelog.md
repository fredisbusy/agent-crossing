# 대시보드 탭 개선 변경 기록

## 2026-08-26

- 최초 구현은 memory와 관계 evidence를 가렸으나 사용자 결정에 따라 로그인 제한
  없이 memory·reflection·관계 summary/evidence 원문을 공개하도록 변경했다.
- provider 원문·prompt·API key·embedding과 내부 model/governance trace는 계속
  공개 DTO에서 제외한다.
- physical pixel 기준 현재 위치와 문 도착 상태 source를 분리했다.
- state polling을 완료 기반 3초/hidden 15초/backoff로 바꾸고 event cursor polling을
  독립시켰다. 마지막 정상 state는 오류 중에도 보존한다.
- agent/tab/relationship target/rail agent를 URL에 보존하고 탭 ARIA·키보드 이동,
  focus, 44px control, 모바일 runtime summary를 적용했다.
- 기억 검색·유형 필터·total/cursor 계약, 계획 phase와 gap/overlap/replan 상태,
  성찰 진행 상태, 로그 검색·실패 필터와 독립 rail filter를 추가했다.
- 성찰 탭은 최근 일반 기억 목록에 의존하지 않고 `node_type=REFLECTION` cursor로
  원문과 citation을 독립 조회한다.
- network, planning, cognitive runtime 오류를 분리해 표시하고 수동 새로고침과
  freshness 정보를 제공한다.
- 개요 탭에 실제 persona read model 기반 프로필 카드를 추가해 나이·성별,
  traits, 고정 페르소나 문장 전체를 표시한다.

## 의도적으로 남긴 범위

- 장기 diagnostics journal과 SSE
- 관계 evidence의 별도 pagination
