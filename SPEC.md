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

대화/정보 확산:

- 조우 시 pass-by vs converse 결정
- 대화 중 핵심 정보를 상대 메모리에 주입 가능
- 정보 확산 측정 지표: seed fact 인지 agent 비율

관계 형성 지표:

- 네트워크 밀도 `eta = 2|E| / (|V|(|V|-1))`

---

## 9. API / 이벤트 계약 (초안)

WebSocket 이벤트 최소 단위:

- `agent_id`
- `position`
- `current_action`
- `current_plan_item`
- `dialogue`
- `emoji`
- `timestamp`

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
- 마을 광장 맵에서 자율 이동/대화 (하이브리드: 에이전트 N명 + 규칙 NPC, §12)
- 사용자 관찰/개입(god mode) 가능

---

## 12. 하이브리드 마을: 주민 = 몸 + 마음

마을의 모든 등장인물은 **주민(Resident)** 이다. 주민은 공유 구현인 **몸(Body)** 과 교체 가능한 **마음(Mind)** 으로 이루어진다.

- 몸: 위치(타일 좌표 + 위치 경로), 이동(경로 탐색), 행동 실행·지속, 사물 사용, 관찰 수집, 말풍선·이모지. LLM을 부르지 않는다.
- 마음: 무엇을 할지 정한다. 두 구현이 같은 `Mind` 프로토콜을 따른다.
  - `LLMMind`: §3~§7의 논문 인지 루프(기억 스트림·검색·성찰·하루 계획·반응). 대화는 문장과 화행을 한 번의 구조화 출력으로 낸다.
  - `ScheduleMind`: 스타듀밸리·동물의 숲식 규칙 NPC(일정표·조건 분기·대사 템플릿). LLM 호출 0.
- **사회 상태는 하나만 구현한다** (`minds/social`). 두 마음이 같은 `SocialState`를 가진다.
  - 할 일 목록(`Agenda`) = 평소 일과(`Routine`) + 행사 약속(주최·손님). 일과의 출처만 다르다(규칙 마음은 일정표, LLM 마음은 하루 계획). 약속 구간이 일과를 덮어쓰고, 손님은 30분 전, 주최자는 60분 전에 가서 준비한다.
  - 우호도(대화 +2, 초대 수락 +1, 선물 +5, 3시간 대화 쿨다운, 3일 넘게 못 보면 "오랜만"), 사실 저장소(행사 소문 포함).
  - 화행 효과(§13)와 대화 멈춤 조건, 꺼낼 이야깃거리(초대 → 선물 → 소문)는 `SocialState`가 같은 규칙으로 정한다. 마음은 무엇을 말할지만 따로 고른다(규칙 마음은 확률·조건, LLM 마음은 프롬프트에 이야깃거리를 싣고 모델이 고른다).
  - 시작 상태(여는 행사 `hosting`, 아는 사실 `seed_facts`, 시작 우호도 `friendships`)는 주민 설정에 있고, 마음 종류와 무관하게 팩토리가 똑같이 심는다. LLM 마음은 시작 기억과 여는 행사·아는 사실을 기억 스트림에도 넣고, 우호도는 대화 프롬프트에 싣는다.
- 주민 설정(`residents/*.json`)은 페르소나(`persona/` 형식) + `mind: "llm" | "schedule"` + 일정 원형을 가진다. `mind` 값만 바꿔 어떤 주민이든 에이전트로 올리거나 NPC로 내린다. 실행 시 `--agents Isabella,Klaus` 또는 `--agent-count N`으로 지정한다.
- **불가지 원칙**: 어떤 마음도 다른 주민의 마음 종류를 알 수 없다. 관찰·대화 문장 형식은 마음 종류와 무관하게 같고, LLM 프롬프트에 `NPC`·`agent`·`rule` 같은 단어를 넣지 않는다. 마음 종류는 디버그 인스펙터에만 노출한다.
- 분 단위 실행(걷기·사물 사용)은 에이전트도 몸이 처리한다. LLMMind는 분 단위 계획 항목(§7)까지만 정하고 몸이 실행한다.

## 13. 화행(Speech Act) 계약

대화 발화는 자연어 문장 + 구조화된 화행 목록을 함께 가진다. NPC는 화행만 읽고 규칙으로 반응하며, 에이전트는 문장을 관찰로 받는다.

- 화행 종류: `greet`, `smalltalk`, `share_fact`, `ask`, `invite`, `accept`, `decline`, `farewell`.
- 화행 종류에 `gift`(`item` 필수)를 더한다. 행사를 싣는 화행은 `event`, `start_time`, `end_time`(없으면 60분), `location_path`, `host_id`를 가진다. 주최자 정보는 전해 듣는 동안 유지된다.
- `invite`: `event`, `start_time`, `location_path` 필수. 받은 주민은 행사를 사실로 배운다. 아는 행사(약속·소문)에 남을 부르면 동행 초대이고, 처음 꺼내는 행사를 초대한 주민만 그 행사의 주최자가 된다.
- 대화 멈춤(공통): 내가 작별했거나 방금 내가 말했으면 말하지 않는다. 내 차례 상한에 닿았거나 상대가 작별했으면 이번 말로 작별한다. 단, 작별과 함께 온 초대에는 먼저 답한다.
- 행사 소문 문장("내일 오후 5시부터 …")은 말하는 시점 기준으로 다시 쓰고, 같은 상대에게는 주제당 한 번만 전한다. 주최자에게는 전하지 않는다.
- `accept`: 행사에 가겠다는 말. 초대에 대한 답이든 소문을 듣고 한 말이든, 다른 약속과 겹치지 않으면 말한 주민의 할 일 목록에 손님 약속이 생긴다. 약속은 이 화행으로만 생긴다(주최 제외).
- `share_fact`: `topic`, `fact` 필수. 행사 필드가 붙으면 행사 소문이다. 사실 저장소에 `(topic, fact, source_resident_id, learned_at, event)`로 넣고, 이후 만나는 주민에게 전한다(§8 정보 확산). 곁에서 엿들은 소문도 배운다.
- 엿들은 `invite`·`gift`는 자기 것이 아니므로 반영하지 않는다. 같은 발화를 여러 경로(대화 기록·관찰)로 받아도 한 번만 반영한다.
- 규칙 마음: 초대는 우호도가 원형 기준 이상이고 시간이 겹치지 않으면 수락한다. 소문 행사는 한 번만 고민해 `event_interest`(주최자와 우호도 10 이상이면 +0.3) 확률로 간다. 손님은 우호도 20 이상인 주민을 같이 가자고 초대한다. 기념일 선물 풍습이 있으면 우호도 10 이상인 주민에게 하루 한 번 선물한다.
- LLMMind는 발화 생성 호출의 구조화 출력으로 화행을 함께 낸다(추가 호출 없음). 행사 화행의 시각·장소는 모델 출력이 아니라 아는 행사에서 채운다. 모르는 행사의 `accept`나 필수 필드가 빠진 화행은 버리고, 남는 화행이 없으면 `smalltalk` 하나로 대체한다. 문장 자체가 없으면 대화를 끝낸다.

## 14. 시뮬레이션 시간 모드

- 시뮬레이션 시계는 주입한다. 기본 틱 = 게임 시간 1분.
- 마을 달력(`TownCalendar`): 새해(1/1), 밸런타인데이(2/14, 초콜릿), 핼러윈(10/31, 사탕), 크리스마스(12/25, 작은 선물). 날이 바뀌면 모든 주민에게 같은 `event` 관찰("오늘은 밸런타인데이다. …")을 보내고, `MindContext.holidays`로 그날 기념일을 함께 넘긴다.
- `faithful`(기본): 모든 주민의 대기 중인 마음 결정이 끝날 때까지 시계를 멈춘다. 같은 시드 + 같은 LLM 응답 캐시면 같은 결과를 낸다. 평가·재현용.
- `realtime`: 시계는 계속 흐르고, 결정이 늦게 오면 몸은 현재 행동을 이어 간다. 관람용(후순위).
- 행동 진행 중인 주민의 마음은 부르지 않는다. 마음은 다음 경우에만 깨운다.
  1. 행동이 끝났을 때(`until` 도달, `move`는 도착)
  2. 즉시 깨움 사유가 생겼을 때: 대화가 끝남, 이동 실패(같은 목적지 반복 실패는 한 번만)
  3. 조우했을 때(`on_encounter`)와 대화 차례(`respond`)
- 시야 변화와 엿들은 말은 깨움 사유가 아니다. 쌓아 두었다가 다음 깨움 때 함께 전달한다(비용 상한).

## 15. 공간·렌더링 기술

- 맵: Tiled JSON 하나(`packages/shared/maps/town.json`)를 백엔드와 프런트가 함께 읽는다. 타일 레이어 + `collision` 레이어 + 장소 객체 레이어(`location_path` 속성) + `furniture`·`decor` 객체 레이어.
- 맵 정본은 Tiled 에디터로 고친 `town.json`이다. `ground`에는 의미 타일 8종(풀·길·마루·벽·물·가구·문·나무, 편집용 그림 `town-tiles.png`)만 칠하고, 픽셀 화풍은 프런트가 자동타일로 입힌다. `collision`은 손으로 칠하지 않고 ground + 막는 장식에서 계산한다(`check_town_map.py --fix-collision`). 고친 뒤 `pnpm check:map`(장소 트리·주민이 쓰는 장소·길에서의 도달성·객체 이름과 크기·collision 일치)이 통과해야 한다. `generate_town_map.py`는 초기 맵 생성용으로만 남긴다.
- 위치 경로는 §8의 `Town > Building > Room > Object` 트리이며 장소 객체 레이어에서 만든다. 주민마다 아는 장소만 담은 개인 환경 트리를 가진다(논문 4.3).
- 경로 탐색: 충돌 그리드 위 4방향 A*(백엔드). 시뮬레이션 권한은 백엔드 단일이고, 프런트는 WebSocket 스냅샷·변경분을 보간해 그리기만 한다.
- 프런트: Phaser 4 + React 19 + Zustand. 에셋은 코드 생성 → CC0 팩 순(`assets/LICENSES.md` 기록).
- QA 훅: 프런트 `window.render_game_to_text` / `window.advanceTime`, 백엔드 `GET /world/text`(짧은 JSON 상태)·`POST /world/advance`(시뮬레이션 분 단위 진행).

## 16. 하이브리드 평가

- 같은 시나리오(예: 밸런타인 파티 씨앗)를 "전원 LLMMind" 대 "하이브리드"로 돌려 정보 확산률·파티 참석 수·시뮬레이션 하루당 LLM 호출 수·토큰을 비교한다.
- 시나리오 씨앗은 `packages/backend/residents/scenarios/<name>.json`(시작 시각, 길이, 주민별 `hosting`·`seed_facts`·`friendships`·`seed_memories`). 밸런타인 씨앗: 2023-02-13 07:00 시작, 이사벨라가 2/14 17~19시 Hobbs Cafe에서 파티를 연다, 마리아는 클라우스에게 호감(우호도 30).
- 지표(주최자 제외): 행사를 안 주민(`knew_event`), 가기로 한 주민(`committed`), 약속하고 행사 시간에 행사 건물에 온 주민(`attended`), 약속과 무관하게 있었던 주민(`present`), 마음 종류별 호출 수. 실행: `uv run python src/run_town_scenario.py --scenario valentine [--agents id,...]`.
- 식별 지표: 관찰자(LLM 판정자 또는 사람)가 로그만 보고 에이전트를 맞히는 정답률. 낮을수록 NPC 품질이 좋다.
