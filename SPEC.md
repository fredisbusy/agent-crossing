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
- 메모리 조회 기본 정렬: score 내림차순, 동점 시 최신 생성 우선

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

1. Day plan: 하루 거시 일정(5~8 broad strokes)
2. Hourly plan: **현재 시점이 속한 day plan 항목**을 시간 단위로 세분화한 근미래 계획
3. Minute plan: **현재 시점이 속한 hourly plan 항목**을 5~15분 단위로 세분화한 실행 액션

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
- minute plan은 `end_time - start_time`이 5~15분 범위를 만족해야 함
- day plan만 하루 전체를 미리 생성하고, hourly/minute plan은 near future만 just-in-time으로 재귀 분해한다
- hourly plan은 현재 시점의 active day-plan item(필요 시 다음 전이 1개 포함) 범위를 벗어나지 않는다
- minute plan은 현재 시점의 active hourly-plan item(필요 시 다음 전이 1개 포함) 범위를 벗어나지 않는다

라이브 하루 실행 규칙:

- 시뮬레이션은 매 tick마다 5분씩 진행하며, 서비스 시작 시 당일 06:00에서 시작한다.
- 평상시에는 real 1초당 game 5분을 진행하되, dialogue session 또는 cognitive task가 활성화되면 tick당 game 30초로 감속한다.
- cognitive 구간에는 참여 agent의 현재 공간 계획과 목적지를 유지하고, 대화 완료 또는 실패 후 최신 game clock에 맞춰 계획 실행을 재개한다.
- 즉시 실행 가능한 persona 기반 fallback hierarchy로 하루를 시작하고, qwen이 만든 day broad strokes는 별도 background task에서 생성한 뒤 두 agent 계획을 함께 교체한다.
- 로컬 27B 모델이 대화와 경쟁하지 않도록 live runtime의 hourly/minute 실행 구간은 active day item을 결정론적으로 재귀 분해한다. 독립 planner API의 LLM hourly/minute 생성 기능은 연구·평가용으로 유지한다.
- day plan은 날짜가 바뀔 때 한 번 선택하고, hourly/minute plan은 active parent가 바뀔 때만 JIT 선택한다. LLM 지연은 world clock을 멈추지 않고 cognitive time scale로 감속한다.
- 생성 실패 또는 parent 범위를 벗어난 결과는 같은 장소와 행동을 유지하는 결정론적 하위 계획으로 대체한다.
- active minute plan의 canonical `location`과 `action_content`가 공간 runtime의 목적지와 현재 행동에 직접 반영된다.
- 두 agent가 같은 canonical 목적지에서 인접했을 때만 대화 세션을 열고, 종료 뒤 30분 동안 재조우 대화를 억제한다.
- Jiho의 Sujin에 대한 호감은 Jiho만 가진 private seed memory다. Sujin은 이를 선험적으로 알지 못하며 독립된 일정, 판단, 경계를 유지한다.

react 정책:

- 매 tick마다 “현재 계획 유지 vs 반응” 판정
- 반응 필요 시, 하루 전체를 재생성하지 않고 **현재 시점 이후 계획만** 재수립

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
- agent는 backend 상태가 해당 home에 도착한 경우 outdoor avatar 대신 dollhouse
  안에 표시한다. `current_action`과 `plan`의 행동 키워드는 관찰용 실내 방 위치와
  말풍선에만 사용하며 canonical tile/navigation 상태를 변경하지 않는다.
- interactable은 `location_path`와 쉼표로 구분된 `affordances`를 가져야 한다.
- React HUD와 Phaser scene은 Zustand의 `world/interior` scene context를 공유하고,
  주민 선택 요청은 어느 scene에서도 outdoor follow camera로 연결한다.
- `오늘의 메인이벤트`는 선택 주민의 authoritative active minute와 게임 시각으로
  계산하며, 구현되지 않은 정보 확산률을 임의 수치로 표시하지 않는다.
- 사용자에게 노출하는 interactable 안내는 Tiled의 agent affordance를 설명할 뿐,
  canonical world mutation이나 God mode 입력으로 취급하지 않는다.
- touch 환경은 한 손가락 pan과 두 손가락 pinch zoom을 제공한다.

월드 API:

- `GET /world/map`: 장소, 충돌, 상호작용 물체, 스폰의 canonical snapshot
- `POST /world/observe`: 좌표와 반경을 입력받아 현재 위치와 주변 affordance 반환
- `POST /world/path`: tile 좌표 입력을 받아 충돌을 우회하는 4방향 A\* 경로 반환
- `GET /world/spatial/state`: 현재 공간 revision, 게임 시각, scheduler 상태, 좌표, 목적지, 활성 계층 계획과 하루 계획을 반환
- `POST /world/spatial/step`: 결정론적 공간 tick을 한 번 진행
- `WS /ws/world`: 최신 공간 snapshot을 약 650ms 간격으로 전달
- 목적지가 막혔거나 도달 불가능하면 `reachable=false`, `path=[]`를 반환

공간 실행 규칙:

- live planning이 있으면 active minute plan의 canonical location을 우선하고, 초기 상태에서는 persona의 `current_plan_context`에서 canonical location 또는 alias를 찾는다.
- 목적지 bounds에서 현재 위치와 가장 가까운 walkable tile을 선택한다.
- backend가 계산한 4방향 A\* route를 한 tick에 한 tile씩 소비한다.
- 프런트엔드 tile motion은 `grid-engine@2.48.2`에 위임하고 전역/character
  방향 수를 모두 `NumberOfDirections.FOUR`로 고정한다.
- 연속 snapshot은 Manhattan distance 1인 경우에만 한 tile 이동으로
  애니메이션한다. 누락 frame으로 두 tile 이상 차이가 나면 backend 좌표로
  즉시 재동기화하며 client-side 우회 경로를 만들지 않는다.
- plan이 바뀌면 기존 route를 폐기하고 현재 tile에서 다시 탐색한다.
- 공간 runtime/stream은 DB/LLM 인지 runtime의 실패와 독립적으로 부팅한다.

대화/정보 확산:

- 조우 시 pass-by vs converse 결정
- 대화 중 핵심 정보를 상대 메모리에 주입 가능
- 정보 확산 측정 지표: seed fact 인지 agent 비율

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
- `GET /dashboard/state`는 실제 runtime의 현재 상태, 계층 계획, memory stream,
  reflection 임계치 진행률, 최근 cognitive diagnostics event를 반환한다.
- cognitive diagnostics event는 자동 scheduler와 수동 step 경로 모두에서 생성하고
  단조 증가 `sequence`와 world `turn`을 함께 보존한다.
- diagnostics event는 별도 bounded buffer가 소유하며 Brain의 `ActionLoopResult`에
  대시보드 전용 필드를 추가하지 않는다.
- 공개 응답에서는 embedding, provider `raw_response`, prompt, API key를 제외한다.
- `/ws/world`는 계속 사용자 관찰용 최신 spatial snapshot만 전달하며 내부 판단
  trace를 포함하지 않는다.

God mode 입력:

- 자연어 이벤트 입력 -> perception event로 변환 -> 해당 agent loop에 주입

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
