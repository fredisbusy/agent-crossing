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
- building portal은 semantic `kind`를 interior template(cafe/library/market/home)에
  연결한다. 실내는 독립 scene으로 렌더링하고 출구 portal로 outdoor scene에 복귀한다.
- agent는 backend 상태가 해당 building에 도착한 경우에만 interior에 표시한다.
- interactable은 `location_path`와 쉼표로 구분된 `affordances`를 가져야 한다.

월드 API:

- `GET /world/map`: 장소, 충돌, 상호작용 물체, 스폰의 canonical snapshot
- `POST /world/observe`: 좌표와 반경을 입력받아 현재 위치와 주변 affordance 반환
- `POST /world/path`: tile 좌표 입력을 받아 충돌을 우회하는 4방향 A\* 경로 반환
- `GET /world/spatial/state`: 현재 공간 revision, 좌표, 목적지, 남은 경로 반환
- `POST /world/spatial/step`: 결정론적 공간 tick을 한 번 진행
- `WS /ws/world`: 최신 공간 snapshot을 약 650ms 간격으로 전달
- 목적지가 막혔거나 도달 불가능하면 `reachable=false`, `path=[]`를 반환

공간 실행 규칙:

- persona의 `current_plan_context`에서 canonical location 또는 alias를 찾는다.
- 목적지 bounds에서 현재 위치와 가장 가까운 walkable tile을 선택한다.
- backend가 계산한 4방향 A\* route를 한 tick에 한 tile씩 소비한다.
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

프런트엔드는 수신 JSON을 shared contract에 맞게 runtime validation한 뒤
Zustand에 저장한다. Phaser는 `position`만 렌더링에 사용하며 충돌/경로를
재계산하지 않는다. `dialogue`, `emoji`, cognitive plan item은 후속 social
overlay 이벤트로 확장한다.

God mode 입력:

- 자연어 이벤트 입력 -> perception event로 변환 -> 해당 agent loop에 주입

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
