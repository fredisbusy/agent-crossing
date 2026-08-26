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
- public memory placeholder: 0, relationship redacted status: 0,
  relationship evidence: 101, public event private field: 0
- 성찰 cursor는 원문·citation을 반환하며 embedding 필드가 없다.
- 공개 브라우저의 하은 성찰 탭에서 원문 row 45개, 마지막 성찰 시각, 로그인 관련
  문구 없음, placeholder 없음, console error 없음까지 확인했다.
- 공개 브라우저에서 6개 탭, URL 상태, ArrowRight 탭 이동, 계획 진행 상태,
  진단 로그 검색/실패 필터를 확인했다.
- 브라우저에 planning/cognitive/network alert가 없고 runtime은 running 상태였다.

현재 앱 브라우저는 viewport capability를 제공하지 않아 390px 실기기 resize는
수행하지 못했다. 반응형 CSS, 44px control, production build로 대체 검증했으며 실제
모바일 기기 확인은 배포 체크리스트에 유지한다.
