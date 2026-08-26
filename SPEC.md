# Agent Crossing Technical Specification

이 문서는 Agent Crossing 구현의 단일 기술 기준입니다.
개발자는 이 문서만 보고도 backend 핵심 루프를 구현할 수 있어야 합니다.

## 0. 문서 역할

- 목적: Generative Agents 논문 아키텍처를 프로젝트 코드로 재현
- 범위: backend 중심 인지 루프(memory/retrieval/reflection/planning/react)
- 우선순위: 구현 수식/상수/계약은 이 문서를 기준으로 함

---

## 1. 프로젝트 목표

Agent Crossing은 NPC가 기억과 계획을 기반으로 자율 행동하는 2D 사회 시뮬레이션입니다.

핵심 가치:

- 자율성: 스크립트 없이 스스로 계획하고 행동
- 연속성: 기억이 미래 행동/대화에 누적 영향
- 창발성: 에이전트 상호작용으로 정보 확산/관계 형성

---

## 2. 시스템 아키텍처

```text
Frontend (React 19 + Phaser 3)
  - map rendering, inspector, user intervention
        <-> WebSocket
Backend (FastAPI)
  - AgentBrain (tick loop)
  - Memory (PostgreSQL + pgvector)
  - World clock/scheduler
Database package (Prisma)
  - schema and PostgreSQL migrations
```

Backend 레이어 책임:

- API 레이어: 요청/응답, websocket 브로드캐스트
- Service/UseCase: 인지 루프 오케스트레이션
- Domain: MemoryObject, plan/reflection/ranking 규칙
- Repository: PostgreSQL + pgvector I/O

---

## 3. 인지 루프 계약 (Perceive -> Store -> Plan -> Act -> React)

매 tick에서 아래 순서를 유지합니다.

1. Perceive: 현재 위치/주변 상태를 자연어 관찰로 변환
2. Store: observation 메모리 저장 + importance 평가
3. Retrieve: 현재 의사결정에 필요한 기억 top-k 조회
4. Plan/Update: 필요 시 minute plan 갱신
5. Act: 이동/대화/행동 실행
6. Reflect Trigger Check: 누적 중요도 임계치 검사

실패 처리 원칙:

- 중요도 파싱 실패: fallback 값 사용(기본 3)
- 임베딩 오류/차원 불일치: 해당 memory relevance를 0으로 처리하고 진행
- retrieval 후보가 비어있으면 최근 메모리 fallback 사용

---

## 4. Memory Stream 계약

### 4.1 MemoryObject 스키마

메모리 도메인 모델의 canonical 필드:

- `id: int`
- `node_type: OBSERVATION | REFLECTION | PLAN`
- `citations: list[int] | None`
- `content: str`
- `created_at: datetime`
- `last_accessed_at: datetime`
- `importance: int` (1~10)
- `embedding: np.ndarray`

추가 예정 필드:

- `location_path: str` (예: `Town > House > Kitchen > Stove`)

무결성 규칙:

- importance는 저장 시 1~10으로 clamp
- OBSERVATION은 `citations=None`
- REFLECTION/PLAN은 citations 허용

### 4.2 Storage

- 영속 저장소: PostgreSQL + pgvector
- DB 스키마와 migration의 단일 기준은 `packages/backend/src/db/models.py`(SQLAlchemy)와
  `packages/backend/alembic/`(migration)이다.
- Python runtime은 해당 SQLAlchemy repository로 스키마를 직접 읽고 쓴다.
- 메모리 조회 기본 정렬: score 내림차순, 동점 시 최신 생성 우선

### 4.3 게임 세션 저장 계약

- 한 시점에 `ACTIVE` 세션은 하나이며 나머지 저장 슬롯은 `SAVED` 상태다.
- 저장 snapshot은 schema version과 낙관적 `save_version`을 포함한다.
- 세션은 world clock, turn/revision, scheduler 상태, planning error, 조우 cooldown,
  대화 큐/history, 공개 가능한 diagnostics를 저장한다.
- 캐릭터는 persona/profile, tile/goal/route/destination, 현재 행동, memory/citation,
  reflection 누적값과 day/hourly/minute planning cache를 저장한다.
- provider 원문 응답, prompt, API key는 cognitive log에 저장하지 않는다.
- 로드 전에 map/agent roster, embedding 차원, walkable 좌표와 연속 route를 검증한다.
- 저장 또는 로드 중 실패하면 기존 runtime, spatial stream, 활성 세션을 함께 유지한다.

---

## 5. Retrieval Scorer 계약

### 5.1 점수 공식

이 프로젝트의 retrieval 공식:

`score = alpha * recency + beta * importance + gamma * relevance`

기본값:

- `alpha = 1.0`
- `beta = 1.0`
- `gamma = 1.0`

### 5.2 각 항목 정의

- `recency = 0.995 ** hours_since_last_access`
- `importance = stored_importance` (1~10)
- `relevance = cosine_similarity(query_embedding, memory_embedding)`

### 5.3 정규화

최종 score 계산 전 `recency/importance/relevance`를 각각 Min-Max로 `[0,1]` 정규화합니다.

정규화 edge case:

- max == min 이면 전 항목을 `0.5`로 처리

### 5.4 출력 계약

- 입력: `query_embedding`, `current_time`, `top_k`
- 출력: `list[MemoryObject]` (길이 `<= top_k`)
- 부작용: 반환된 memory의 `last_accessed`를 `current_time`으로 업데이트

---

## 6. Reflection 계약

트리거 조건:

- 최근 이벤트 누적 중요도 `>= 150`

실행 파이프라인:

1. 최근 memory 100개 수집
2. salient questions 3개 생성
3. 질문별 retrieval 수행
4. high-level insight 5개 생성
5. 각 insight를 REFLECTION 메모리로 저장(citations 포함)
6. 누적 중요도 카운터 리셋

규칙:

- reflection memory도 retrieval 후보에 포함
- insight는 반드시 근거 memory id를 citations에 보존

---

## 7. Planning / Re-planning 계약

계획 계층:

1. Day plan: 하루 거시 일정(5~16 broad strokes)
2. Hourly plan: **현재 시점이 속한 day plan 항목**을 시간 단위로 세분화한 근미래 계획
3. Minute plan: **현재 시점이 속한 hourly plan 항목**을 기본 5~15분 단위로 세분화한 실행 액션

Minute decomposition은 Park et al.의 Generative Agents 구현처럼 상위 task의
고정 duration을 5분 단위 하위 행동으로 분해한다. LLM은
`duration_minutes`와 `action_content`만 생성하고, authoritative
`start_time`, `end_time`, `location`은 runtime이 연속적으로 조립한다.

제품 runtime의 day plan은 생성 시점부터 다음 자정까지를 고정 planning window로
사용하며 5~16개 항목이 빈틈·겹침 없이 전체 구간을 덮어야 한다. hourly plan도
active day-plan 종료까지 연속으로 덮어야 하며, 위치는 모델이 재작성하지 않고
authoritative day-plan 위치를 상속한다. 시간창 불일치는 parsing governance의
semantic error로 재시도하고, retry 소진 시 명시적 planning error로 중단한다.

각 액션 필수 필드:

- `start_time`
- `end_time`
- `location`
- `action_content`

시간 표현 규칙:

- canonical 저장 필드는 `start_time`, `end_time`
- `end_time`는 항상 `start_time`보다 이후여야 함
- `duration_minutes`는 저장 필드가 아니라 `end_time - start_time`으로부터 계산되는 파생값으로 취급
- day/hourly/minute plan 모두 초 단위 없이 minute precision 사용
- day/hourly plan은 exact-hour 정렬을 강제하지 않으며 `5:30 pm` 같은 자연스러운 broad-strokes 시간을 허용
- day-plan의 개별 항목은 최대 180분으로 제한한다. 장시간 업무·학습·휴식은 활동 또는 장소 전환이 드러나는 연속 블록으로 나누며, 이 상한은 prompt와 semantic parsing/초안 병합에 모두 적용한다.
- hourly plan의 개별 항목은 최대 180분으로 제한해 minute decomposition이 과도하게 길어지지 않게 함
- LLM이 생성하는 minute duration은 5~15분이며 5분 단위여야 함. 다만 runtime이
  현재 시점부터 상위 계획 종료까지 정확히 덮도록 조립하는 마지막 항목은 1~4분의
  짧은 tail action 또는 5분 단위가 아닌 연장 구간일 수 있다.
- 고정 시간창보다 총합이 짧을 때는 논문 구현처럼 마지막 항목을 종료 시각까지 늘릴 수 있어 최종 canonical 항목은 15분을 초과할 수 있음
- minute decomposition의 duration 합계는 현재 시각부터 active hourly 종료까지의 남은 시간과 정확히 같아야 함
- day/hourly plan은 고정 planning window의 시작과 끝을 모두 덮고 항목 사이에 gap/overlap이 없어야 함
- hourly location은 active day-plan의 canonical location을 runtime이 상속함
- duration 합계가 고정 시간창보다 길면 끝부분을 잘라내고, 짧으면 마지막 항목을 늘려 authoritative 종료 시각에 맞춤
- JSON/schema/필수 행동/duration 단위 자체가 잘못된 경우에는 보정하지 않고 semantic parse error로 재시도함
- 계획 JSON은 Pydantic 모델에서 생성한 JSON Schema를 provider의 constrained decoding에 전달하고 동일 모델로 응답을 재검증함
- day/hourly/minute `action_content`는 각각 최대 50/50/30자로 제한하고 프롬프트와 JSON Schema에 같은 제한을 명시함
- day `location`은 최대 120자로 제한하며 schema에 선언되지 않은 추가 필드는 허용하지 않음
- active day/hourly/minute 항목은 모두 현재 world clock을 포함해야 하며, 미래 항목을 현재 항목처럼 선택하지 않는다
- day plan만 하루 전체를 미리 생성하고, hourly/minute plan은 near future만 just-in-time으로 재귀 분해한다
- day-plan provider 초안은 최대 16개까지 제한적으로 수용할 수 있다. 8개를 초과하면
  전체 시간창의 연속성을 먼저 검증한 뒤 가장 짧은 인접 항목을 결정론적으로 병합해
  5~8 broad strokes로 canonicalize한다. gap/overlap이나 비-canonical 장소는 병합하지 않는다.
- 자정까지 남은 시간이 25분 미만이면 가능한 5분 슬롯 수에 맞춰 1~4개의 tail plan을
  생성하고, 자정 전환 뒤 새 날짜의 정상 5~8개 day plan을 생성한다.
- hourly plan은 현재 시점의 active day-plan item(필요 시 다음 전이 1개 포함) 범위를 벗어나지 않는다
- minute plan은 현재 시점의 active hourly-plan item(필요 시 다음 전이 1개 포함) 범위를 벗어나지 않는다

라이브 하루 실행 규칙:

- 시뮬레이션은 매 tick마다 5분씩 진행하며, 서비스 시작 시 당일 06:00에서 시작한다.
- 평상시에는 real 1초당 game 5분을 진행하되, dialogue session 또는 cognitive task가 활성화되면 tick당 game 1분으로 감속한다. 이 감속치는 논문 구현의 minute-level action loop와 minute-precision 계획 경계를 함께 지키며, 아래 게이팅과는 독립적인 결정이다.
- world clock은 논문 §3.1.1("agents output a natural language statement... sandbox server parses... moves the agents")과 동일하게, **해당 tick에 아직 진행 중인 agent 행동 결정이 모두 끝난 뒤에만** 다음 tick으로 진행한다. 구체적으로 `_run_scheduler`는 매 tick마다 `_advance_world_tick` 실행 이후, 그 tick에서 새로 시작되었거나 이미 진행 중이던 in-flight `_cognitive_task`(대화 턴 생성)와 백그라운드 plan-disruption 스레드(`_dispatch_tick_plan_disruption_check`가 기동한 react 판정, `react_replan`으로 계획을 변형할 수 있음)를 모두 `await`/`join`한 뒤에야 다음 tick의 `_advance_world_tick`으로 넘어간다. `tick_interval_seconds`의 `asyncio.sleep`은 이 gate 뒤에 오는 순수 real-time pacing이며, 더 이상 "행동 완료를 기다리지 않고 시간이 흘러가는" 자유 실행 타이머가 아니다.
- cognitive 구간에는 참여 agent의 현재 공간 계획과 목적지를 유지하고, 대화 완료 또는 실패 후 최신 game clock에 맞춰 계획 실행을 재개한다.
- `WorldRuntime.step()`(수동 `tick()` 진입점, 테스트에서 주로 사용)은 원래부터 동기적으로 `engine.step()` 완료까지 반환하지 않으므로 이미 이 gating 규칙을 만족한다. 별도 조정이 필요했던 대상은 `_run_scheduler`/`_advance_world_tick` 뿐이다.
- day/hourly/minute 계획은 모두 planner가 생성한 authoritative 결과만 실행한다. 고정 문구나 상위 문장 복사로 계획을 대체하지 않는다.
- 서비스 시작과 active parent 전환 시 필요한 계획 계층이 준비될 때까지 world clock을 진행하지 않는다.
- 같은 tick에서 필요한 모든 agent 계획을 먼저 검증한 뒤 spatial schedule과 world clock을 원자적으로 갱신한다.
- 계획 생성·파싱·장소/시간 검증이 실패하면 scheduler를 중단하고 `planning_error`를 WebSocket과 dashboard에 노출한다.
- 로컬 27B planner 호출은 생성 시간 제한을 두지 않고 완료될 때까지 기다린다. 연결·파싱·검증 실패는 fallback 없이 `planning_error`로 노출한다.
- 로컬 Qwen의 structured JSON 생성은 thinking을 끄고 출력 토큰을 최종 JSON 본문에 사용한다.
- structured JSON의 출력 토큰 수는 응답 길이 조절 수단이 아닌 안전 상한으로 사용한다. 상한 도달 종료 사유는 일반 parse error와 구분하고, 한 번 증액 재시도한 뒤에도 잘리면 명시적 오류로 중단한다.
- reflection/reaction/importance를 포함한 모든 JSON LLM 호출은 JSON Schema constrained decoding과 필드별 길이 제한을 사용한다.
- day plan은 날짜가 바뀔 때 한 번 선택하고, hourly/minute plan은 active parent가 바뀔 때 JIT 생성한다.
- active minute plan의 canonical `location`과 `action_content`가 공간 runtime의 목적지와 현재 행동에 직접 반영된다.
- canonical 마을·건물·장소 경로와 사용자 노출 지도 라벨은 한국어 이름을 사용한다.
- hourly/minute plan은 canonical 한국어 장소 경로를 축약하거나 일반화하지 않고 그대로 유지한다.
- minute plan의 시각과 장소는 모델 출력에서 받지 않고 검증된 hourly window와 canonical location에서 파생한다.
- 두 agent가 같은 canonical 목적지에서 인접했을 때만 대화 세션을 열고, 종료 뒤 30분 동안 재조우 대화를 억제한다.
- Jiho의 Sujin에 대한 호감은 Jiho만 가진 private seed memory다. Sujin은 이를 선험적으로 알지 못하며 독립된 일정, 판단, 경계를 유지한다.

react 정책:

- 매 tick마다 “현재 계획 유지 vs 반응” 판정 (§4.3.1). `agents/planning/react_gate.py`의
  `PlanDisruptionGate`가 `[Agent's Summary Description]` + 현재 시각 + agent status +
  observation을 입력으로 continue/react와 근거를 반환한다. 이는 이미 진행 중인 대화를
  이어갈지 판단하는 `agents/reaction/graph.py`의 dialogue-level `should_react`와는
  범위가 다른 상위 게이트다.
- 반응 필요 시, 하루 전체를 재생성하지 않고 **현재 시점 이후 계획만** 재수립한다.
  `PlanningCoordinator.react_replan`이 day plan(과 canonical 위치/시간창)은 그대로
  두고 hourly/minute plan만 현재 시점 기준으로 다시 생성한다.

---

## 8. 공간/사회 상호작용 계약

공간 컨텍스트:

- 위치 표현은 `Town -> Building -> Room -> Object` 트리
- canonical world map은 `packages/shared/assets/briar-cove.tmj`의 Tiled JSON이다.
- `locations`, `paths`, `collision`, `interactables`, `spawns`, `decorations`를
  독립 object layer로 관리한다.
- 프런트엔드는 맵을 렌더링하지만 위치 유효성, 충돌, 경로 탐색 판정은
  backend world 계층이 소유한다.
- 프런트엔드는 semantic object layer를 32px pixel tile grid로 투영하고,
  전체 월드 축소가 아닌 local follow camera를 기본 관찰 시점으로 사용한다.
- pixel texture는 nearest-neighbor로 렌더링하며 terrain/building/decor/agent의
  depth는 tile y 좌표를 기준으로 정렬한다.
- `home` kind는 Smallville Figure 2처럼 지붕 없는 dollhouse 평면도로 메인 맵에
  침실, 주방, 공용실, 욕실과 핵심 가구를 항상 노출한다.
- cafe/library/market도 지붕 없는 kind별 dollhouse interior를 메인 맵에 항상
  노출한다. 문 portal은 같은 semantic `kind`의 확대 interior scene template에
  연결하고 출구 portal로 outdoor scene에 복귀한다.
- agent는 backend 상태가 해당 building/home의 문 또는 문 앞 대기 tile에 도착한
  경우에만 outdoor avatar 대신 dollhouse의 충돌하지 않는 activity slot에 표시한다.
  `current_action`과 `plan`의 행동 키워드는 관찰용 실내 위치와 말풍선에만 사용하며
  canonical tile/navigation 상태를 변경하지 않는다.
- React text overlay는 카메라 투영 후 캐릭터 말풍선/nameplate의 screen-space
  bounds를 계산하고, 겹치는 박스를 위로 쌓아 서로 가리지 않게 한다.
- interactable은 `location_path`와 쉼표로 구분된 `affordances`를 가져야 한다.
- React HUD와 Phaser scene은 Zustand의 `world/interior` scene context를 공유하고,
  주민 선택 요청은 어느 scene에서도 outdoor follow camera로 연결한다.
- `오늘의 메인이벤트`는 선택 주민의 authoritative active minute와 게임 시각으로
  계산하며, 구현되지 않은 정보 확산률을 임의 수치로 표시하지 않는다.
- 사용자에게 노출하는 interactable 안내는 Tiled의 agent affordance를 설명할 뿐,
  canonical world mutation이나 God mode 입력으로 취급하지 않는다.
- touch 환경은 한 손가락 pan과 두 손가락 pinch zoom을 제공한다.

월드 API:

- `GET /sessions`: 현재 슬롯과 저장된 세션 목록 반환
- `POST /sessions`: 06:00 초기 상태의 새 세션 생성 및 활성화
- `POST /sessions/current/save`: 현재 runtime을 저장하며 선택적으로 save version 충돌 검사
- `POST /sessions/{session_id}/load`: 저장 snapshot 검증 후 해당 세션 활성화
- `GET /world/map`: 장소, 충돌, 상호작용 물체, 스폰의 canonical snapshot
- `POST /world/observe`: 좌표와 반경을 입력받아 현재 위치와 주변 affordance 반환
- `POST /world/path`: tile 좌표 입력을 받아 충돌을 우회하는 4방향 A\* 경로 반환
- `GET /world/spatial/state`: 현재 공간 revision, 게임 시각, scheduler 상태, 좌표, 목적지, 활성 계층 계획과 하루 계획을 반환
- `POST /world/spatial/step`: 결정론적 공간 tick을 한 번 진행
- `POST /world/god-mode/perception`: 자연어 문장을 특정 agent의 observation memory로
  주입한다(§3.2, §8.1). 환경 상태 변경 입력이며 "inner voice"/directive 입력(§3.1.2)과는
  분리된 별도 경로다. `plan_react_gate`가 구성된 경우 주입 직후 §4.3.1 continue-vs-react
  판정을 실행하고, react 판정 시 현재 시점 이후 계획만 재수립한다.
- `WS /ws/world`: `session_id`를 포함한 최신 공간 snapshot을 약 650ms 간격으로 전달
- 목적지가 막혔거나 도달 불가능하면 `reachable=false`, `path=[]`를 반환
- `/ws/world` handler는 snapshot 송신과 client disconnect 수신을 동시에 감시한다.
  한쪽이 종료되면 반대 task와 stream 구독을 즉시 취소해 reload/shutdown이 열린
  WebSocket 때문에 지연되지 않게 한다.

공간 실행 규칙:

- live planning이 있으면 active minute plan의 canonical location을 우선하고, 초기 상태에서는 persona의 `current_plan_context`에서 canonical location 또는 alias를 찾는다.
- 건물 목적지는 Tiled에 선언한 `entrance_tile_x/y` 문으로만 진입한다. 문이 다른
  agent에게 점유된 경우 `entrance_dx/dy` 방향의 walkable 대기 tile을 선택한다.
- 건물·물·간판·분수·벤치·나무·가로등 collision은 통과할 수 없고, agent tile도
  tick 동안 동적 collision으로 취급해 같은 tile 점유와 자리 맞바꾸기를 금지한다.
- backend 4방향 A\*는 authored path/광장/공원의 이동 비용을 `1`, 그 밖의
  walkable 지형 비용을 `4`로 계산해 가능한 경우 길을 우선하며 한 tick에 한 tile씩
  route를 소비한다.
- 프런트엔드 tile motion은 `grid-engine@2.48.2`에 위임하고 전역/character
  방향 수를 모두 `NumberOfDirections.FOUR`로 고정한다.
- 연속 snapshot은 Manhattan distance 1인 경우에만 한 tile 이동으로
  애니메이션한다. 누락 frame으로 두 tile 이상 차이가 나면 backend 좌표로
  즉시 재동기화하며 client-side 우회 경로를 만들지 않는다.
- plan이 바뀌면 기존 route를 폐기하고 현재 tile에서 다시 탐색한다.
- 공간 runtime/stream은 DB/LLM 인지 runtime의 실패와 독립적으로 부팅한다.

대화/정보 확산:

- 조우 시 pass-by vs converse 결정. `agents/reaction/encounter.py`의 `EncounterGate`가
  관계 요약(relationship_summary) + 상황 요약(context_summary) 두 프롬프트 패턴(§4.3
  예시)으로 판단하고 근거를 로그로 남긴다. converse 결정 시 기존 짧은 대화 아크
  세션(§2-D)으로 연결한다. `encounter_gate`가 구성되지 않으면 기존 동작(항상 대화)을
  유지한다.
- 대화 중 핵심 정보를 상대 메모리에 주입 가능. `WorldConversationSession.broadcast_reply`가
  발화를 상대 agent의 observation memory로 저장하며, day plan 생성이
  `PlanningCoordinator._generate_day_plan`을 통해 최근 관련 기억을 retrieval 후보로
  포함해 실제 계획에 반영한다(§3.4.3 coordination 패턴, 특정 시나리오에 하드코딩하지 않음).
- 논문 원문의 관계 영향에는 별도 수치 가중치 공식이 없다. 논문 원문(§4.3.1)은 관계/맥락 영향을
  "What is [observer]'s relationship with the [observed entity]?" /
  "[Observed entity] is [action status of the observed entity]" 두 retrieval
  질의의 답을 요약해 프롬프트에 넣는 방식으로만 정의한다("The context summary is
  generated through two prompts that retrieve memories via the queries ... and
  their answers summarized together."). §7.1.1/§7.1.2의 네트워크 밀도 `eta`는 평가
  지표일 뿐 계획 우선순위 가중치가 아니다. 따라서 위 두 요약을 retrieval
  candidate/persona_background에 반영하는 현재 구현(`EncounterGate`,
  `_recent_planning_relevant_memories`)이 논문 스펙을 충족한다. 아래 수치 모델은
  논문 공식을 사칭하지 않는 Agent Crossing 제품 확장이며 정성 retrieval을 대체하거나
  계획·행동 프롬프트에 feedback하지 않는다.
- 정보 확산 측정 지표: seed fact 인지 agent 비율 (미구현, §5-A)

### 8.1 방향성 관계 상태 (Agent Crossing extension, relationship-v1)

- 관계는 game session 안에서 `(subject_agent_id, target_agent_id)` 방향별로 독립한다.
  자기 관계는 금지한다. persona에 명시 baseline이 있으면 그 값을 사용하고 미지정
  방향쌍은 중립값으로 생성한다. 자연어 persona를 런타임에서 숫자로 추측하지 않는다.
- 축은 `familiarity 0..100`, `trust -100..100`, `affinity -100..100`,
  `tension 0..100`, `romantic_interest 0..100`이다. `affinity`는 친구·이웃·동료로서의
  인간적 호감이고 `romantic_interest`는 연애 관계에 대한 관심이다. 연애 의향 없음은
  0으로 나타내며 불편함·불신은 tension/trust로 표현한다.
- 평범한 대화·도움은 `romantic_interest`를 올리지 않는다. 이 축은
  `ROMANTIC_INTEREST_RECOGNIZED +8`, `ROMANTIC_GESTURE_WELCOMED +8`,
  `ROMANTIC_BOUNDARY_SET -10`처럼 명시적인 애정·경계 event에서만 변한다.
  모든 축은 범위를 clamp하고 state `revision`을 증가시킨다.
- LLM은 delta 숫자를 만들지 않는다. 확정 도메인 이벤트만 고정 NORMAL delta를
  요청하며 동일 `(subject,target,source_event_id,event_type)`은 한 번만 적용한다.

| 이벤트                          |  친숙도 |    신뢰 |    호감 |     긴장 |
| ------------------------------- | ------: | ------: | ------: | -------: |
| `DIALOGUE_COMPLETED`            |      +2 |       0 |      +2 |       -2 |
| `HELP_GIVEN` / `HELP_RECEIVED`  | +2 / +2 | +2 / +6 | +2 / +4 |  -2 / -2 |
| `PERSONAL_DISCLOSURE_RECEIVED`  |      +4 |      +4 |      +2 |        0 |
| `COMPLIMENT_RECEIVED`           |      +2 |      +2 |      +4 |       -2 |
| `PROMISE_MADE` / `PROMISE_KEPT` | +2 / +2 | +2 / +8 | +2 / +4 |   0 / -4 |
| `PROMISE_BROKEN`                |       0 |     -10 |      -4 |       +6 |
| `CONFLICT` / `INSULT_RECEIVED`  |  +2 / 0 | -4 / -6 | -6 / -8 | +8 / +10 |
| `APOLOGY_ACCEPTED`              |      +2 |      +4 |      +4 |       -8 |

- game-day/방향쌍별 gross cap은 친숙도 12, 신뢰 24, 인간적 호감 20, 긴장 24,
  이성적 관심 16이다.
- 공개 상태 라벨은 backend가 다음 우선순위로 결정한다: 긴장≥60 `긴장된 관계`,
  신뢰≤-40 `불신하는 관계`, 인간적 호감≤-40 `거리감 있는 관계`, 친숙도<15
  `아직 낯선 사이`, 신뢰≥50이면서 인간적 호감≥50 `가깝고 신뢰하는 관계`,
  인간적 호감≥40 `인간적으로 호감 있는 관계`, 신뢰≥40 `신뢰하는 관계`, 나머지
  `알아가는 관계`. 프런트엔드는 별도 임계값을 만들지 않는다.
- v1 자동 연결은 실제 발화가 있는 대화가 끝날 때 양방향
  `DIALOGUE_COMPLETED`를 1회 기록하는 것까지다. 도움·약속·갈등 규칙은 향후
  canonical committed action signal만 호출한다. plan/current_action 문자열은 쓰지 않는다.
- `WorldRuntime.relationships`가 상태와 event ledger를 소유한다. `RuntimeSaveState`
  schema v4 snapshot이 복원 SSOT이고 DB 관계 테이블은 재생성 가능한 projection이다.

### 8.2 MBTI·연애 선호와 사회적 경계 (Agent Crossing extension)

- MBTI는 캐릭터 저작을 위한 축약 메타데이터다. 각 persona의 `traits`에 유형을
  기록하되, `identity_stable_set`에서 에너지 회복·정보 해석·판단·계획 방식의
  관찰 가능한 행동으로 풀어 쓴다. 유형 문자는 행동을 결정하거나 궁합을 계산하는
  공식이 아니다.
- 연애 선호는 성별을 전제하지 않는 자연어 identity anchor로 표현하며, 끌리는
  행동·마음이 멀어지는 행동·관계 속도·경계를 포함한다. 선호는 가능성이지 특정
  상대 배정이나 관계 의무가 아니다.
- 조우/반응 판단은 MBTI 일치, 평범한 친절, 한 번의 즐거운 대화만으로 연애 감정을
  추론하지 않는다. 실제 관찰 행동과 retrieved memory가 선호에 부합할 때만 정성적
  호감 가능성을 고려하며, 거절과 경계를 우선한다.
- 내향성 자체나 한 번 말을 건 행위는 호감 하락 근거가 아니다. 친밀도가 낮은데도
  원치 않는 접근을 반복하거나, 조용히 있고 싶다는 신호를 무시하거나, 거절 뒤에도
  압박한 기억은 내부 호감 저하·거리 두기·대화 거절의 근거가 될 수 있다.
- 위 정성 판단은 §8.1 수치 상태를 임의로 변경하지 않는다. `romantic_interest`는
  명시적 연애 event에서만 변하며 LLM은 숫자 delta를 출력하지 않는다.

관계 형성 지표:

- 네트워크 밀도 `eta = 2|E| / (|V|(|V|-1))`

---

## 9. API / 이벤트 계약

`WS /ws/world`는 개별 이벤트가 아니라 최신 상태 전체를 보내는 snapshot
스트림이다. 느린 클라이언트에는 오래된 frame을 버리고 가장 최신 frame만
유지한다.

snapshot 필드:

- `revision`
- `map_id`
- `agents[]`

agent 필드:

- `agent_id`
- `name`
- `tile_position`
- `position`
- `destination`
- `current_action`
- `plan`
- `route_remaining`
- `bubble_kind`: `speech | thought | action`
- `bubble_text`: 괄호를 포함하지 않은 사용자 관찰용 한 문장

프런트엔드는 수신 JSON을 shared contract에 맞게 runtime validation한 뒤
Zustand에 저장한다. Phaser는 `tile_position`을 Grid Engine에 전달하며
충돌/경로를 재계산하지 않는다. `bubble_kind=speech`는 실제 확정 발화를 괄호
없이 표시하고, `thought|action`은 프런트엔드가 정확히 한 겹의 괄호로 감싼다.
`model_thought`, self critique, decision trace 같은 내부 진단은 snapshot에 싣지
않는다.

### 9.1 운영 관측 대시보드 계약

- `/dashboard`는 게임 렌더러와 분리된 React 관측 화면이며 Phaser runtime을 부팅하지 않는다.
- `GET /dashboard/state`는 실제 runtime의 현재 상태, 계층 계획, memory와
  reflection 원문, reflection 임계치 진행률을 반환한다. 응답에는
  `snapshot_generated_at`, bounded event buffer의 `oldest_sequence`와
  `latest_sequence`를 포함해 freshness와 cursor gap을 판정할 수 있게 한다.
- `/dashboard`에는 로그인이나 접근 제한을 두지 않는다. memory, reflection,
  방향성 관계 summary/evidence 원문은 공개 화면에서 그대로 제공한다.
- 공개 diagnostics event는 sequence/turn/time/agent/reply/silent/parse-failure/
  decision-reason/action-summary allowlist만 직렬화한다. `thought`,
  `model_thought`, `self_critique`, `decision_process`, governance trace와 provider
  원문은 runtime buffer나 저장 형식에 존재하더라도 공개 응답으로 전달하지 않는다.
- `GET /dashboard/events?after=<sequence>`는 공개 event cursor polling에 사용한다.
  `GET /dashboard/agents/{agent_id}/memories`는 `before_id`, `limit`, `node_type`,
  `min_importance`를 받는 안정적인 역순 cursor와 원문을 제공한다.
- frontend polling은 이전 요청 완료 후 다음 요청을 예약한다. state summary는
  visible 3초/hidden 15초를 기본으로 하며 실패 시 backoff하고 마지막 정상 상태를
  보존한다. event cursor는 visible 1초/hidden 15초로 독립 갱신한다.
- cognitive diagnostics event는 자동 scheduler와 수동 step 경로 모두에서 생성하고
  단조 증가 `sequence`와 world `turn`을 함께 보존한다.
- diagnostics event는 별도 bounded buffer가 소유하며 Brain의 `ActionLoopResult`에
  대시보드 전용 필드를 추가하지 않는다.
- `current_location_path`는 destination이 아니라 authoritative physical pixel을
  기준으로 계산한다. 문 출입 완료처럼 authored door가 location bounds 밖에 있는
  경우에만 도착 상태를 별도 source로 표시하며 이동 중 destination으로 대체하지 않는다.
- 공개 응답에서는 embedding, provider `raw_response`, prompt, API key와 내부
  diagnostics trace를 제외한다. 이 제한은 memory/reflection 원문 공개 여부와
  별개다.
- `/ws/world`는 계속 사용자 관찰용 최신 spatial snapshot만 전달하며 내부 판단
  trace를 포함하지 않는다.
- 관계 수치와 event는 subject 기준의 비대칭 상태를 유지한다. subject의 persona와
  memory에서 파생한 정성 요약·evidence도 공개하되 역방향 agent의 기억을 섞거나
  대칭 복사하지 않는다.
- 관계 API는 `measurement=modeled_v1`, 다섯 축, revision, 최근 event와 적용 delta를
  반환한다. 정성 evidence도 함께 제공하되 memory importance/retrieval score를
  관계 점수로 변환하지 않는다.

God mode 입력:

- 자연어 이벤트 입력 -> perception event로 변환 -> 해당 agent loop에 주입
- `POST /world/god-mode/perception`이 `agent_id` + `content`를 받아
  `MemoryManager.create_observation_from_text`로 observation memory를 즉시 저장하고,
  구성된 경우 §4.3.1 판정기(`PlanDisruptionGate`)를 실행해 react 여부를 결정한다.
- 이 입력은 환경 상태 변경이며, 아직 구현되지 않은 "inner voice"/directive 입력(§3.1.2)과
  별도 경로로 유지한다.

한국어 출력 정책:

- 제품 runtime의 언어는 `ko`로 고정하며 영어 모드를 노출하지 않는다.
- dialogue뿐 아니라 `thought`, `reason`, `critique`, plan action, reflection,
  salient question, insight, summary의 모든 자연어 값은 한국어로 생성한다.
- JSON key, enum, canonical agent/location 이름은 계약과 맵 매칭을 위해 유지할 수
  있지만 사람이 읽는 문장은 한국어를 포함해야 한다.
- 중국어/일본어 문자가 섞이거나 한글이 전혀 없는 최종 발화는 저장 또는 다른
  agent에게 전파하기 전에 `language_policy_violation`으로 차단한다.
- 영어로 생성된 생각/이유/비평은 UI와 로그에 노출하지 않고 한국어 진단 문구로
  대체한다.

---

## 10. 검증 기준 (Definition of Done)

### Memory/Retrieval

- retrieval 수식/상수/정규화 테스트 통과
- 동일 query에서 top-k 일관성 테스트 통과
- 중요 이벤트 우선 노출 테스트 통과

### Reflection

- `>=150` 트리거 테스트 통과
- 질문 3개/insight 5개/ citations 보존 검증 통과

### Planning

- day/hour/minute 계층 생성 테스트 통과
- react 시 현재 시점 이후 계획만 변경됨을 검증

### 프로젝트 레벨

- backend: `pnpm test:backend` 또는 `uv run pytest`
- build: `pnpm -r build`

---

## 11. MVP (v0.1)

- 서로 다른 페르소나 2명
- 메모리 저장 + retrieval + reflection + replan 최소 루프 동작
- 마을 광장 맵에서 자율 이동/대화
- 사용자 관찰/개입(god mode) 가능
