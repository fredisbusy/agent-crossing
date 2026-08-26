# 대시보드 탭 개선 검증

## 자동 검증

- Backend public projection/observability/relationship diagnostics tests: 12 passed
- Frontend Vitest: 27 passed, 6 files
- Shared build, frontend production build, `pnpm -r build`: passed
- Ruff changed-file check: passed
- Full backend suite: 228 passed, 11 skipped, 5 failures

전체 backend의 5개 실패는 이번 dashboard 변경 밖의 기존 dirty
planning/settings 작업(`test_litellm_day_plan_retry`, planning graph 2건, settings
2건)과 일치한다. dashboard targeted suite는 통과했다.

## 공개 runtime 검증

- `GET /dashboard/state?memory_limit=50&event_limit=0`: 117,828 bytes
- 6 agents: 위치 source가 map 또는 arrival이며 null 위치 없음
- public event private field: 0, unredacted memory: 0, relationship evidence: 0
- 공개 브라우저에서 6개 탭, URL 상태, ArrowRight 탭 이동, 기억 redaction 안내,
  계획 진행 상태, 진단 로그 검색/실패 필터를 확인했다.
- 브라우저에 planning/cognitive/network alert가 없고 runtime은 running 상태였다.

현재 앱 브라우저는 viewport capability를 제공하지 않아 390px 실기기 resize는
수행하지 못했다. 반응형 CSS, 44px control, production build로 대체 검증했으며 실제
모바일 기기 확인은 배포 체크리스트에 유지한다.
