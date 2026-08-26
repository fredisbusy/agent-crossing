# 대시보드 탭 개선 변경 기록

## 2026-08-26

- 공개 dashboard를 metadata-only memory와 allowlisted event를 사용하는 redacted
  observer view로 확정했다.
- physical pixel 기준 현재 위치와 문 도착 상태 source를 분리했다.
- state polling을 완료 기반 3초/hidden 15초/backoff로 바꾸고 event cursor polling을
  독립시켰다. 마지막 정상 state는 오류 중에도 보존한다.
- agent/tab/relationship target/rail agent를 URL에 보존하고 탭 ARIA·키보드 이동,
  focus, 44px control, 모바일 runtime summary를 적용했다.
- 기억 검색·유형 필터·total/cursor 계약, 계획 phase와 gap/overlap/replan 상태,
  성찰 진행 상태, 로그 검색·실패 필터와 독립 rail filter를 추가했다.
- network, planning, cognitive runtime 오류를 분리해 표시하고 수동 새로고침과
  freshness 정보를 제공한다.

## 의도적으로 남긴 범위

- private memory와 내부 모델 추론을 보는 인증 operator surface
- 장기 diagnostics journal과 SSE
- 관계 private evidence의 별도 pagination
