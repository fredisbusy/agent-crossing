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
- 6명의 게임풍 픽셀 초상화를 추가하고 주민 목록 썸네일과 개요 프로필에
  연결했다. 알 수 없는 `agent_id`는 기존 이니셜로 대체한다.
- 추가 페르소나 4명(우식·용준·병용·원준)의 초상화를 생성해 실제 게임 주민
  10명 모두가 고유 초상화를 갖도록 확장했다.
- 같은 화풍을 재사용하도록 `agent-crossing-portraits` project skill과 prompt
  template, 초상화 준비·검증 script를 추가했다.

## 의도적으로 남긴 범위

- 장기 diagnostics journal과 SSE
- 관계 evidence의 별도 pagination
