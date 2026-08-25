# Agent Crossing — 아키텍처 분석 (2026-08-25)

`.claude/` 하네스의 도메인 분할(backend-brain / backend-api / frontend-dev / db-prisma)을
따라 코드베이스를 직접 읽고 검증한 분석 문서. 각 절은 실제 소스 file:line을 근거로 한다.
독자: 이 레포에서 작업하는 사람/에이전트. 목적: 현재 구현이 `SPEC.md`/`AGENTS.md`와
실제로 얼마나 일치하는지, 그리고 어디에 손볼 지점이 있는지 파악하는 것.

## 목차

1. [인지 루프 (Brain / Memory / Planning / Reflection / Reaction)](#1-인지-루프)
2. [Backend API / World / Persistence](#2-backend-api--world--persistence)
3. [Frontend (React + Phaser + Zustand)](#3-frontend)
4. [Database (Prisma 스키마 + SQLAlchemy 브릿지)](#4-database)
5. [교차 발견사항 우선순위](#5-교차-발견사항-우선순위)

---

## 1. 인지 루프

`packages/backend/src/agents/{brain,memory,planning,reflection,reaction}/`,
`packages/backend/src/llm/`.

### 1.1 아키텍처

`AgentBrainGraphRunner`(`agents/brain/graph.py`)가 LangGraph 스타일 상태머신으로 한 틱을 처리한다.

```
ensure_plan_context → perceive → persist_observation
  →(조건부)→ [run_reflection] → determine_context → decide_reaction → finalize_action → END
```

- `_ensure_plan_context`(brain/graph.py:129-221): `current_plan_context`가 비어 있으면
  `planner.generate_day_plan(...)`를 호출해 day-plan 앞 2개 항목만 시딩한다.
- `_perceive`(223-262): 한국어 자연어 관측 문자열 생성 후 임베딩.
- `_persist_observation`(264-282): `memory_manager.create_observation` →
  `reflection_graph.record_observation_importance` → `should_reflect()`.
- `_determine_context`(296-325): retrieval query 생성 후 `get_retrieval_memories(top_k=3)`.
- `_decide_reaction`(327-347): `llm_gateway.decide_reaction` → `ReactionDecision`.
- `_finalize_action`(349-402): `talk`/`action_intent`/`silent_reason` 도출, `ActionLoopResult` 반환.

서브모듈:
- **Memory** — `MemoryStream`(append-only + `RLock`), `MemoryManager`(facade).
- **Reflection** — `Reflection`(누적 임계값 게이트), `ReflectionGraphRunner`
  (최근 100개 → 질문 생성 → per-question retrieve → insight 생성 → citation 저장).
- **Planning** — `Planner` → `PlanningGraphRunner`. day/hourly/minute 3개의 파싱/재시도
  그래프, 각 `MAX_PARSE_RETRIES = 2`(planning/graph.py:68).
- **Reaction** — 2단계 그래프: intent 생성 → (반응 시) utterance 생성, semantic
  similarity/n-gram overlap 재시도 루프(≤2회).

### 1.2 SPEC.md 준수 — Retrieval은 정확히 일치, 계획 실행 경로는 미스매치

**Retrieval 스코어링은 SPEC §5와 정확히 일치**(`agents/memory/memory_stream.py:87-181`):
`score = α·norm_rec + β·norm_imp + γ·norm_rel`(α=β=γ=1.0), `recency = 0.995^hours`,
`relevance = cosine_similarity` (오류/차원불일치 시 0 처리), min-max 정규화
(`max==min`→0.5), 정렬은 score desc → `created_at` desc, 반환 시 `last_accessed_at` 갱신.
→ 모두 SPEC §5 그대로 구현됨.

**한 가지 확인된 gap**: SPEC §3이 요구하는 "retrieval 후보가 비어있으면 최근 메모리로
fallback"이 `MemoryStream`/`MemoryManager` 어디에도 없다. 빈 메모리 상태에서
`_calculate_retrieval_scores`는 그냥 `[]`을 반환한다.

**Reflection 트리거는 SPEC §6과 일치**: 임계값 150(`reflection/state.py:6`), 누적→리셋
패턴, 파이프라인 순서, reflection memory도 동일한 `MemoryStream`을 통해 retrieval
후보에 자동 포함됨. `create_reflection`이 알 수 없는 citation id를 조용히 drop하는
지점은 있지만(memory_manager.py:163-170) 진단 로그 없음.

**Plan 계층 구조는 있고, 실행 경로도 존재 — 다만 브레인 루프가 아닌 world 레이어에서
소유**: `AgentBrainGraphRunner`가 의존하는 `PlanningRunner` 프로토콜은
`generate_day_plan`만 선언한다(brain/graph.py:84-88)는 관찰은 맞지만, hourly/minute
JIT 분해는 별도 경로로 실제 호출되고 있다: `world/runtime.py`가
`agents/planning/lifecycle.py`(`generate_hourly_plan`/`generate_minute_plan`,
lifecycle.py:197,213,286,318)를 직접 소유·호출한다. 즉 SPEC §7의 계층형 계획
실행은 구현돼 있다 — 다만 "Brain의 한 틱"이 아니라 world 스케줄러가 별도 주기로
plan lifecycle을 갱신하는 구조다(§2.3 참고). *(2026-08-25 수정: 최초 분석 시
`agents/` 범위만 보고 world 레이어 호출을 놓쳤던 부분을 바로잡음.)*

### 1.3 Governance 경계 위반 — 확인됨

AGENTS.md §9가 명시적으로 금지하는 패턴이 실제로 존재한다:

```python
# packages/backend/src/agents/brain/types.py:48-67
@dataclass(frozen=True)
class ActionLoopResult:
    ...
    reaction_trace: ReactionDecisionTrace | None = None   # raw_response, parse_error,
                                                            # retry_count, threshold 포함
    diagnostics: ActionDiagnostics | None = None           # model_thought, self_critique,
                                                            # decision_process 포함
```

- `ReactionDecisionTrace`(agents/reaction/contracts.py:38-51): `raw_response`,
  `parse_error`, `fallback_reason`, `suppress_reason`, retry 카운터, threshold 필드.
- `ActionDiagnostics`(agents/decision_diagnostics.py:6-13): `model_thought`,
  `self_critique`, `decision_reason`, `action_summary`, `decision_process: dict`.
- `brain/graph.py:395-401`(`_finalize_action`)에서 두 필드 모두 `ActionLoopResult`에
  직접 채워진다.

→ **`ActionLoopResult`는 Brain 도메인 결과 타입인데 governance/diagnostics 필드를
타입 레벨에서 그대로 들고 있다.** API 응답 전에 걸러지는지는 `world/engine.py`
영역(§2에서 확인: `_public_diagnostics()`가 필터링함)이라 외부 유출은 없지만,
타입 자체의 경계 위반은 확정. `.claude/hooks/guard-brain-governance-fields.sh`가
바로 이 패턴을 잡기 위해 만든 훅이다.

### 1.4 한국어 전용 발화 — 이중 레이어로 구현됨

- **소프트 in-flight 교정**: `agents/reaction/graph.py`가
  `llm.language_policy.korean_text_or_fallback`으로 비한국어 thought/reason/critique를
  치환. utterance는 실패 시 빈 문자열로 대체(219-231, 315-330).
- **하드 게이트 (broadcast 직전 차단)**: `llm/governance/policies/reply_policy.py:
  _sanitize_reply`(62-80)가 CJK 비허용 스크립트 검사 + 한글 최소 1자 요구 →
  실패 시 `("", "language_policy_violation")`. `world/engine.py:116`에서 호출됨.

→ 구현은 돼 있으나 **두 계층이 서로 다른 모듈에 분산**돼 있다(reaction/graph.py의
소프트 교정 vs governance/policies의 하드 게이트).

### 1.5 TODO/스텁

`agents/`, `llm/` 전체에서 `TODO`/`FIXME`/`NotImplementedError` 없음. 유일한 구조적
gap은 §1.2의 plan 계층 미배선과 §1.3의 governance 경계 위반.

---

## 2. Backend API / World / Persistence

`packages/backend/src/api/`, `world/`, `persistence/`, `db/`.

### 2.1 API 표면

단일 `FastAPI` 앱(`api/main.py`, 889줄), 라우터 분리 없음. 스키마는 전부
`api/schemas.py`(순수 Pydantic, ORM 미의존) — AGENTS.md §4 요구사항 충족.

주요 엔드포인트: `GET /`(health), `GET/POST /sessions*`(세이브 CRUD, 낙관적 동시성
`expected_save_version` → 충돌 시 409), `GET /world/map`, `GET /dashboard/state`,
`GET /dashboard/events`, `GET/POST /world/spatial/*`, `POST /world/observe`,
`POST /world/path`(A*), `GET /world/state`, `POST /world/step`,
`POST /world/tick/start|stop`.

**WebSocket** `/ws/world`: 단방향 push, 메시지 타입 구분 없음. 구독은
`asyncio.Queue(maxsize=1)`로 backpressure 처리 — 큐가 차면 오래된 프레임을 버리고
최신 것만 유지. 재연결은 클라이언트 전담(서버 세션 토큰 없음), 재연결 시 최신
스냅샷만 다시 시딩(누락 프레임 보정 없음 — push-latest-state 프로토콜로는 허용 가능).

### 2.2 영속성 — "Prisma-backed"의 실제 의미

**Python 백엔드는 Prisma 클라이언트를 전혀 쓰지 않는다.** Prisma는 마이그레이션
권한자일 뿐이고, 런타임 접근은 **SQLAlchemy 2.0 + psycopg + pgvector.sqlalchemy**로
`db/models.py`에 손으로 미러링한 ORM 모델을 통해 이뤄진다(§4.5 참조).

`GameSessionRepository`(persistence/repository.py)가 유일한 read/write 표면:
- `create()`: 단일-ACTIVE 세션 불변식 유지, JSONB `snapshot` 컬럼(복원용) +
  정규화된 테이블(characters/memories/plan_items/dialogue_state) **이중 저장**.
- `save()`: `SELECT ... FOR UPDATE` 기반 낙관적 동시성, 매 저장마다
  `_delete_projection` + `_write_projection`(diff 없는 전체 재작성).
- **자동 저장 없음** — `/sessions/current/save` 명시 호출과 graceful shutdown 시에만
  저장. 비정상 종료(SIGKILL/OOM)는 마지막 저장 이후 진행분을 모두 잃는다.
- `sanitized_diagnostics()`(persistence/contracts.py:138)가 `api_key`/`raw_response`
  등을 DB 저장 전에 제거 — 시크릿 유출 방어는 잘 돼 있음.

### 2.3 World 상태 모델

- **Map**(world/world_map.py): Tiled `.tmj` JSON을 파싱해 불변 `WorldMap` 트리 생성,
  4방향 A* pathfinding.
- **Spatial runtime**(world/spatial.py): LLM과 무관한 순수 이동 시뮬레이션,
  `threading.RLock` 가드, 타일 충돌 회피, `revision` 카운터로 staleness 감지.
- **Cognitive runtime**(world/runtime.py): `WorldRuntime`은 **정확히 2개 에이전트만
  지원**(`len(agents) != 2` → `ValueError`, runtime.py:95) — 논문 프레이밍과 달리
  구조적으로 2인용. 두 시간축 병행: coarse tick(기본 300초 게임시간) vs fine
  cognitive tick(대화 중 30초).
- **Diagnostics 분리**: `world/observability.py`의 `DashboardEventBuffer`(bounded
  ring buffer)가 `SimulationStepResult`와 깔끔히 분리돼 있고, `main.py:545`
  `_public_diagnostics()`가 HTTP 응답 전에 `raw_response`/`prompt`/`api_key`를 추가로
  제거 — API 레이어에서는 AGENTS.md §9 경계가 잘 지켜지고 있다(§1.3의 타입 레벨
  위반과는 별개).

### 2.4 비동기 정합성 — 확인된 위반

**`world/world_map.py:280`(`load_world_map()`)이 동기 파일 읽기 + JSON 파싱을
`asyncio.to_thread` 없이 수행**하고, 이것이 세 개의 async 핸들러에서 매 요청마다
호출된다(캐싱 없음):

- `GET /world/map`(main.py:395)
- `POST /world/observe`(main.py:780)
- `POST /world/path`(main.py:807)

AGENTS.md §4 "차단형 I/O를 동기 루틴으로 남기지 않는다" 위반. 이벤트 루프를
요청마다 블로킹한다. DB 접근(SQLAlchemy 동기 호출)은 모든 지점에서
`asyncio.to_thread`로 잘 감싸져 있어 문제 없음.

**수정 방향**: 정적 파일이라 런타임에 변하지 않으므로 startup 시 1회 파싱해 캐시하는
것이 `asyncio.to_thread`로 감싸는 것보다 나은 해법.

### 2.5 기타 구조적 gap

- `@app.on_event("startup"/"shutdown")`은 FastAPI deprecated API(lifespan
  context manager로 교체 예정).
- 2-에이전트 하드 리밋이 `WorldRuntime.__init__`과 `main.py:70`(`persona_names[:2]`)
  양쪽에 박혀 있음 — 확장하려면 대화 턴제/세션 로직 전체를 건드려야 함.

---

## 3. Frontend

`packages/frontend/src/`, `packages/shared/src/`.

### 3.1 아키텍처

`App.tsx`가 단일 `useEffect`에서 `Phaser.Game`을 생성(Grid Engine을 씬 플러그인으로
등록), `MainScene`(야외, 741줄)과 `InteriorScene`(실내, 413줄) 두 씬을 등록한다.
NPC는 `Phaser.GameObjects.Rectangle` 프리미티브로 조립한 픽셀아트 컨테이너.

**Grid Engine은 서버 권위 이동의 애니메이션 레이어일 뿐**이다.
`game/gridMovement.ts`의 `ServerGridMovement.sync()`가 서버가 준 `tile_position`과
현재 위치의 Manhattan 거리를 `stationary | cardinal-step | resync`로 분류하고,
1칸 이동만 `gridEngine.moveTo`로 애니메이션, 2칸 이상 점프는 `setPosition`으로 즉시
스냅한다. 충돌/경로탐색은 전적으로 백엔드(A*) 소관.

React 트리: `main.tsx`(경로 스위치: `/dashboard` vs 게임) → `App.tsx`(게임 셸 +
`GameTextOverlay` + `SessionMenu`) / `Dashboard.tsx`(독립 라우트, 폴링 기반 인지
관측 도구, WebSocket 미사용).

### 3.2 상태 브릿지 — Phaser ↔ Zustand ↔ React

단일 스토어 `stores/game.store.ts`. **쓰기는 오직 `useWorldStream()`의
`setSnapshot()`만** 담당(백엔드→스토어). Phaser 씬은 `create()` 내부에서
`useGameStore.subscribe(...)`를 직접 호출해(React 훅이 아닌 순수 Zustand 구독)
`state.agents`/`state.followRequestId` 변화를 감지, 씬 정리 시 `SHUTDOWN`/`DESTROY`
이벤트로 구독 해제.

흥미로운 패턴: `GameTextOverlayController`(game/gameText.ts)가 매 프레임 Phaser
좌표를 화면 좌표로 투영해 `setGameTextOverlay()`로 스토어에 쓰고, React가 그 값을
읽어 절대위치 `<span>`으로 렌더링한다 — **Phaser가 DOM 좌표계에서 "그리기"를
스토어를 경유해서 하는 방식**으로, `game/` 내부에서 `document.*`를 직접 만지지
않으면서도 DOM 라벨을 구현한다.

### 3.3 실시간 데이터 흐름

- **World stream**(`useWorldStream.ts`): 순수 `WebSocket`, URL은
  `VITE_WORLD_WS_URL` → prod `/ws/world`(wss) → dev `ws://<host>:8001/ws/world` 순
  결정. 손으로 짠 런타임 검증기(`parseSnapshot` 등)가 매 프레임 shape을 검사,
  잘못된 프레임은 조용히 drop(다음 스냅샷을 기다림). 메시지 타입 구분 없음(항상
  풀 스냅샷, delta 프로토콜 아님). 연결 끊김 시 1.5초 후 자동 재연결.
- **Dashboard**: WebSocket이 아니라 `GET /dashboard/state`를 1초 간격 폴링
  (`AbortController`로 in-flight 요청 취소).
- **Session REST**: `SessionMenu.tsx`의 fetch 래퍼, 동일한 수동 타입가드 패턴.

세 채널 모두 `unknown` → 수동 shape-narrowing(`any` 없음), 항상
`@agent-crossing/shared`의 타입을 대상으로 검증하는 동일한 관용구를 쓴다.

### 3.4 규칙 위반 검사 — 위반 없음

- `game/` 내 `document.querySelector`/`getElementById`: **0건**.
- `src/` 전체 `any`/`as any`/`@ts-ignore`: **0건**.
- 로컬에서 shared DTO를 중복 정의: **0건** — 로컬 타입은 전부 순수 UI-only 형태
  (`AgentView`, `TiledObject` 등)이고 wire-format은 전부 `@agent-crossing/shared`에서
  import.

### 3.5 Shared 패키지

`packages/shared/src/index.ts`(203줄): 공간/월드 DTO, 세션 DTO, 대시보드 DTO.
**`WorldAgentState`/`WorldLocation`/`WorldInteractable`/`WorldSpawn`/
`WorldMapDefinition`(camelCase 필드)이 현재 프론트엔드에서 미사용** — 프론트는
`SpatialAgentState`/`SpatialWorldSnapshot`(snake_case)과 Tiled `.tmj` 원본 파싱을
쓴다. 초기 설계의 잔재로 보이는 죽은 코드 후보(중복 위험은 아님, 아무도 재구현하지
않았으므로).

### 3.6 Mock/스텁 이력

현재 소스에 `TODO|FIXME|mock|stub|placeholder|hardcod` **0건**. 레포 자체의
과거 리뷰(`_workspace/codex-harness/code-reviewer/`)가 지적했던 6개 항목
(하드코딩된 seed-event 패널, InteriorScene에서 죽은 follow 힌트, 스냅샷 고정된
실내 주민 렌더링, 비인터랙티브 notice board/fountain/bench, 모바일 핀치줌 누락,
프론트 회귀 테스트 부재)은 **모두 코드에서 수정 확인됨** — 리뷰 문서는 이제
역사적 기록이고 현재 상태를 반영하지 않는다.

---

## 4. Database

`packages/database/prisma/`, `packages/backend/src/db/`.

### 4.1 스키마 개요

`schema.prisma` — enum 3개(`GameSessionStatus`, `PlanLevel`, `MemoryNodeType`),
모델 8개: `GameSession`, `SessionCharacter`, `SessionMemory`,
`SessionMemoryCitation`, `SessionPlanItem`, `SessionDialogueState`,
`SessionCognitiveLog`, 그리고 세션과 무관한 독립 테이블 `VectorMemory`.

`SessionMemory.embedding`/`VectorMemory.embedding`은 `Unsupported("vector(1024)")`
(pgvector, Prisma 네이티브 미지원). **ANN 인덱스(ivfflat/hnsw) 없음** — 현재는
무해한데, retrieval이 전부 Python 인메모리(§4.3)라 SQL에서 벡터 유사도 검색을
하는 코드가 없기 때문. 나중에 SQL 레벨 검색을 추가하면 그때 문제가 된다.

### 4.2 마이그레이션 이력

`20260825090000_session_persistence` 단 하나 — 오늘 날짜, "Prisma-backed game
saves" 커밋과 일치. 처음부터 전체 스키마를 만드는 마이그레이션이라 drift 가능성
없음(schema.prisma와 필드 단위로 대조 확인, 불일치 없음). CHECK 제약조건
(importance 1-10, 자기인용 금지, 단일 ACTIVE 세션 partial unique index 등)은
**마이그레이션 SQL에만 존재하고 schema.prisma에는 문서화 안 됨** — 향후 스키마
편집자가 놓치기 쉬운 지점.

### 4.3 Retrieval 공식은 SQL이 아니라 Python에서 실행됨

`agents/memory/memory_stream.py`가 `recency`/`importance`/`relevance`(코사인
유사도)와 정규화를 **인메모리 `list[MemoryObject]`에 대해 전부 Python으로**
계산한다(pgvector `<=>`/`<->` 연산자 미사용). 즉 Postgres의 `embedding` 컬럼은
게임플레이 중엔 사실상 write-only이고, 세션 로드 시 통째로 읽어올 때만 쓰인다.

### 4.4 세션 저장 모델 — 전체 재투영, 증분 아님

`save()`는 매번 `_delete_projection` + `_write_projection`으로 캐릭터/메모리/
플랜/대화 상태를 전부 삭제 후 재삽입한다(§2.2와 동일 내용, 여기선 스키마 관점).
`SessionPlanItem.parentId`(day/hourly/minute 자기참조)는 **스키마엔 있지만 항상
`None`으로 쓰임**(`repository.py:245`) — 미완성 기능이거나 죽은 컬럼.

### 4.5 Backend↔DB 브릿지 — 구조적 drift 위험

> **Resolved 2026-08-25**: Prisma를 완전히 제거하고 SQLAlchemy + Alembic로
> 스키마/마이그레이션을 일원화했다. `packages/database`(Prisma) 패키지 삭제,
> `packages/backend/alembic/`이 단일 마이그레이션 소스. CHECK 제약조건은
> `db/models.py`의 `__table_args__`에 명시적으로 선언되고, 임베딩 차원은
> `Vector(EMBEDDING_DIMENSION)`으로 통일해 하드코딩을 제거했다. 아래 원문은
> 문제 진단 당시 스냅샷으로 남겨둔다.

**Python 백엔드는 Prisma 클라이언트를 쓰지 않는다.** `packages/backend/src/db/
models.py`가 `schema.prisma`를 필드 단위로 손으로 미러링한 SQLAlchemy ORM
모델이다. 코드 생성이나 introspection으로 두 정의를 묶어주는 장치가 전혀 없다:

- 임베딩 차원 `1024`가 **4곳에 독립적으로 하드코딩**: `schema.prisma`의
  `vector(1024)` ×2, `settings.py`의 `EMBEDDING_DIMENSION`, `db/models.py`의
  `Vector(1024)`(SessionMemoryRecord) vs `Vector(EMBEDDING_DIMENSION)`
  (VectorMemory) — 하나라도 안 바꾸면 런타임 `validate_embedding_dimension`
  체크가 잡아줄 때까진 조용히 깨진다.
- CHECK 제약조건은 마이그레이션 SQL에만 있어 SQLAlchemy 모델엔 전혀 보이지
  않는다 — 잘못된 값(예: importance 0)으로 row를 만들면 flush 시점에야
  `IntegrityError`로 발견된다.
- `.claude/agents/db-prisma.md`의 house rule("스키마와 packages/shared의 타입이
  어긋나지 않도록")은 `packages/shared`만 언급하고 실제 drift 표면인
  `db/models.py`는 다루지 않는다 — **문서화 gap으로 확인, §5에서 후속 조치 제안**.

### 4.6 기타 발견

- `VectorMemory`/`vector_memories` 테이블은 세션/캐릭터와 FK 관계 없이 고립돼
  있음 — 세션 영속성 이전의 프로토타입 잔재로 추정, 죽은 코드 후보.
- `GameSession.snapshot`(JSONB) vs 정규화된 자식 테이블들 간 중복 저장 여부는
  스키마만으로는 확정 불가 — 후속 확인 필요.

---

## 5. 교차 발견사항 우선순위

코드베이스는 전반적으로 SPEC.md/AGENTS.md와 **높은 일치도**를 보인다(특히
retrieval 공식, DTO 계층 분리, 프론트엔드 규칙 준수는 완벽에 가까움). 아래는
실제로 손볼 가치가 있는 항목을 영향도 순으로 정리한 것.

| 우선순위 | 항목 | 근거 |
|---|---|---|
| 높음 | `ActionLoopResult`에 governance/diagnostics 필드 leak (§1.3) | AGENTS.md §9 명시적 위반, `.claude` 훅이 이미 이 패턴을 감지하도록 준비됨 — `ReactionDecisionTrace`/`ActionDiagnostics`를 별도 채널로 분리 필요 |
| 높음 | `load_world_map()` 미캐싱 blocking I/O (§2.4) | 매 요청마다 이벤트 루프 블로킹, 정적 파일이라 캐싱이 자명한 해법 |
| 중간 | Prisma ↔ SQLAlchemy 이중 스키마 drift (§4.5) | 코드생성 없는 수동 미러링, 임베딩 차원 4곳 하드코딩 |
| 낮음 | Retrieval 빈 후보 시 fallback 없음 (§1.2) | SPEC §3 요구사항이지만 현재 스케일(2 에이전트)에선 실질적 영향 적음 |
| 낮음 | `VectorMemory` 테이블, `SessionPlanItem.parentId`, shared의 `WorldMapDefinition` 계열 | 죽은 코드 후보 — 팀 확인 후 정리 |
| 낮음 | `@app.on_event` deprecated API | FastAPI lifespan으로 교체 예정 항목, 기능상 문제 없음 |

이 문서는 스냅샷이다 — 코드가 바뀌면 갱신 필요. 특히 §1.3(governance 경계)과
§2.4(blocking I/O)는 `.claude/hooks/guard-brain-governance-fields.sh` 및
`/verify` 커맨드로 재발 방지를 걸어둘 수 있는 지점이다.
