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

## 2026-08-26 개요 프로필 후속 검증

- Backend persona/dashboard targeted suite: 22 passed
- Frontend Vitest: 28 passed, 6 files
- Shared build, frontend production build: passed
- Full backend suite: 233 passed, 11 skipped, 6 failures

전체 backend의 실패 중 5개는 위에 기록한 기존 planning/settings 작업과 같고,
추가 1개는 별도로 수정 중인 `briar-cove.tmj` 높이와 기존 world map 테스트 기대값의
불일치다. 개요 프로필 targeted suite는 통과했다.

- 공개 `/dashboard/state`에서 6명 모두 `age`, `gender`, `traits`, `persona`를
  반환하는 것을 확인했다.
- 공개 하은 개요에서 프로필 카드, 30세, 여성, 성격 태그, 고정 페르소나 6개가
  표시되는 것을 확인했다.
- 데스크톱과 390px viewport에서 프로필 카드가 각각 2열과 1열로 표시되며 가로
  overflow가 없었다.
- 공개 브라우저 console warning/error는 없었다.

## 2026-08-26 주민 초상화 후속 검증

- 6개 project asset이 모두 512×512 RGBA PNG이며 실제 alpha channel을 갖는지
  확인했다.
- Frontend Vitest: 35 passed, 7 files
- `pnpm -r build`: passed
- 공개 `/portraits/{agent_id}.png`에서 6개 파일이 모두 512×512 이미지로
  응답하는 것을 브라우저에서 확인했다.
- 현재 공개 dashboard state/events API가 503으로 runtime agent 목록을 제공하지 않아,
  데이터가 결합된 목록·개요 화면의 공개 브라우저 최종 확인은 수행하지 못했다.
  정적 asset 응답, mapping/fallback 테스트와 production build까지 검증했다.
- project backend virtualenv로 skill `quick_validate.py`를 실행해 `Skill is valid!`를
  확인했다. 준비 script는 일반 RGBA와 실제 체크무늬 원본을 각각 512×512 투명
  PNG로 변환했고, 검증 script는 현재 6개 asset을 모두 통과시켰다.
