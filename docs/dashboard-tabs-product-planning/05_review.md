# 대시보드 탭 기획 리뷰

## 결론

현재 dashboard는 실제 runtime을 한 화면에서 관측한다는 핵심 목적과 6개 탭의 기본 데이터는 갖췄다. 관계 탭은 방향성·정량/정성 근거·관점 전환까지 가장 완성도가 높다. 다음 단계는 새 탭 추가보다 **정확성, 공개 범위, 데이터 전달 구조, 탐색성**을 먼저 개선하는 것이 타당하다.

> 2026-08-26 후속 승인으로 아래 P0/P1 항목을 구현했다. 공개 정책은 인증 없는
> redacted observer view로 확정했으며 private operator view는 별도 후속 범위다.

## 우선순위

### P0 — 정확성·보안·가용성

1. 진단 로그 탭과 우측 rail의 agent filter 결합 버그를 분리한다.
2. dashboard를 운영자 전용으로 할지 공개 관측 화면으로 할지 확정하고 인증/권한을 적용한다.
3. live/persisted diagnostics sanitizer를 단일 allowlist 정책으로 통일한다.
4. 공개 runtime에서 전 agent의 `current_location_path`가 null인 원인을 진단하고 위치 의미를 복구한다.
5. `cognitive_runtime_error`, network offline, planning error를 서로 다른 상태로 표시한다.
6. 1초 fixed interval이 진행 중 요청을 계속 abort하지 않도록 polling을 완료 기반으로 바꾼다.

### P1 — 정보 구조·성능·접근성

1. summary/detail/events를 분리하고 기존 event cursor를 사용한다.
2. 기억·성찰·관계 근거에 total/cursor를 추가한다.
3. 계획 timeline, 현재 marker, 상태와 replan/error metadata를 추가한다.
4. tab semantics, keyboard, focus, alert/status/progress를 보강한다.
5. agent/tab/target/filter를 URL에 보존한다.
6. 8~10px typography와 작은 touch target을 dashboard 전역 기준으로 개선한다.

### P2 — 운영 편의·설명력

1. 기억 검색/필터/정렬과 citation 탐색
2. 진단 로그 필터, 일시정지, gap 안내, JSON 복사
3. 관계 지표 도움말, freshness, 구조화된 `related_agent_ids`
4. 한국어 문구와 내부 용어 정리
5. revision 기반 관계 read-model/cache

## 현재 구현 대비 gap

| 영역        | 현재                                                | 목표                                       |
| ----------- | --------------------------------------------------- | ------------------------------------------ |
| 데이터 갱신 | 전체 payload 1초 polling                            | summary/detail/event cursor 분리와 backoff |
| 일관성      | spatial/runtime/memory/event가 조회 중 섞일 수 있음 | snapshot revision과 생성 시각 명시         |
| 공개 범위   | private memory와 상세 trace가 공개 endpoint에 포함  | 운영자 권한 또는 공개용 redacted view      |
| 개요        | 현재 bubble thought를 최근 생각으로 표시            | 신호 의미 분리와 오류 우선 요약            |
| 기억        | 최근 배열 길이를 건수로 표시                        | total/cursor/search/citation 탐색          |
| 계획        | 카드 목록                                           | 계층 timeline, 상태, replan/error 원인     |
| 성찰        | 최근 memory 중 reflection만 표시                    | 전용 목록, 상태, citation lineage          |
| 로그        | 전역 rail과 상세 중복, filter 결합                  | 요약/상세 역할과 상태 독립                 |
| 접근성      | 관계 탭 일부만 보강                                 | dashboard 전역 표준 패턴                   |

## 확인된 강점

- Phaser를 부팅하지 않는 별도 React 관측 route
- spatial snapshot, planning, memory, reflection, relationship, diagnostics의 실제 데이터 사용
- Brain 결과와 diagnostics buffer의 소유 경계 유지
- raw response/prompt/API key를 제외하려는 public sanitation 경로
- 방향성 관계 5축과 정성 근거를 혼합하지 않는 구조
- client runtime schema validation과 자동 재연결

## 추적성

- `SPEC.md` §9.1: 실제 runtime, bounded diagnostics, public redaction, `/ws/world` 분리
- `TODO.md`: agent inspector와 방향성 관계 탭 완료 항목
- 관계 상세: `docs/dashboard-relationship-redesign/`
- 후속 구현 backlog: `TODO.md`의 "dashboard 탭 관측성·탐색성 개선" 항목

## 구현 후 남은 결정

- 인증된 operator dashboard를 별도로 만들지 여부와 인증 방식
- 관계 evidence 전용 cursor/detail endpoint가 필요한지 여부
- event cursor polling을 SSE로 전환할지 여부
- source of truth를 유지하면서 atomic snapshot을 만드는 방식
- 장기 보존 diagnostics와 bounded live buffer의 역할 분리 여부
