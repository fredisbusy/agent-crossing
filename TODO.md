# Agent Crossing Project TODO

논문(Generative Agents, 2023) 스펙을 위에서 아래로 읽으면서,
기능을 작은 단위로 하나씩 구현하기 위한 실행 보드.

## 사용 규칙

- 우선순위: `P0`(핵심), `P1`(핵심 확장), `P2`(검증/고도화)
- 순서 원칙: 같은 섹션에서는 위에서 아래 순서로만 진행
- 체크 기준: 항목 아래 `DoD`를 모두 만족하면 `[x]`
- 의존성: `Depends on`이 완료되기 전에는 시작하지 않음
- 기준 문서: 알고리즘/상수/계약은 `SPEC.md` + `AGENTS.md`와 동기화

---

## 0) Foundation

- [x] 프로젝트 기본 골격 확정 (`packages/shared`, `packages/frontend`, `packages/backend`)
- [x] Frontend 런타임 부팅 (React 19 + Phaser 3 + Zustand)
- [x] Backend 런타임 부팅 (FastAPI + uv)
- [x] LLM provider 클라이언트 경로를 정리하고 호환 import를 유지한다 (`packages/backend/src/llm/clients`)
- [x] Qwen 생성 호출의 추론 강도를 `low`로 고정한다
- [x] `P0` 모든 LLM JSON 출력을 schema-constrained generation으로 안정화한다
  - DoD:
    - [x] Pydantic 응답 모델에서 JSON Schema를 생성해 provider 호출과 사후 검증에 재사용한다
    - [x] 계획/반성/중요도/반응 JSON에 필수 필드, 추가 필드 금지, 배열 개수, 텍스트 길이 제한을 적용한다
    - [x] token-limit 종료를 parse failure와 구분하고 출력 예산을 한 번 증액해 재시도한다
    - [x] 출력 토큰 상한 대신 prompt/schema 필드 제한으로 응답 길이를 제어한다
- [x] 로컬 LLM + 벡터 DB PoC 통과 (MLX/Vector DB)
- [x] `P0` 메모리 영속 스토어 전환 확정 (PostgreSQL + pgvector)

## 1) Memory Stream & Retrieval (논문 핵심 1)

- [x] `P0` MemoryObject 스키마를 코드와 1:1로 맞춘다
  - Depends on: 없음
  - DoD:
    - [x] 기본 메모리 객체/스트림을 구현한다 (`packages/backend/src/agents/memory/memory_object.py`, `packages/backend/src/agents/memory/memory_stream.py`)
    - [x] 필수 필드(`id`, `content`, `created_at`, `last_accessed`, `importance`, `node_type`)를 저장/조회 경로에 반영한다
    - [x] 확장 필드(`citations`, `embedding`)를 지원한다
    - [x] 필드 이름 충돌(`content/creation_timestamp` vs `content/created_at`)을 하나로 정리한다

- [x] `P0` Importance scoring을 안정적으로 계산한다
  - Depends on: MemoryObject 스키마 동기화
  - DoD:
    - [x] 기억 생성 시 LLM 출력으로 중요도를 `1~10` 정수로 산정한다
    - [x] 파싱 실패 시 fallback 규칙(기본값 3)을 적용한다
    - [x] 단위 테스트로 점수 범위/실패 경로를 검증한다

- [x] `P0` Retrieval score(가중합)를 공식대로 계산한다
  - Depends on: MemoryObject 스키마 동기화
  - DoD:
    - [x] Recency decay를 `0.995 ** hours_since_last_access`로 계산한다
    - [x] Relevance를 query embedding vs memory embedding cosine similarity로 계산한다
    - [x] 최종 점수를 `score = (alpha * recency) + (beta * importance) + (gamma * relevance)`로 계산한다
    - [x] 기본 가중치 `alpha = beta = gamma = 1.0`을 적용한다
    - [x] 각 항목을 Min-Max로 `[0,1]` 정규화한다
    - [x] 단위 테스트로 계산식/정규화 edge case를 검증한다

- [x] `P0` Retriever 품질을 테스트로 고정한다
  - Depends on: Retrieval scoring 구현
  - DoD:
    - [x] `add_memory` 단위 테스트를 작성한다 (`packages/backend/tests/test_memory_stream.py`)
    - [x] 동일 query 재호출 시 top-k 결과가 일관적인지 확인한다
    - [x] 중요 이벤트(high importance)가 retrieval 상위에 노출되는지 확인한다
    - [x] `pnpm test:backend` 또는 `uv run pytest`가 통과한다

## 2) Reflection Loop (논문 핵심 2)

### 2-A. Trigger와 누적값 관리

- [x] `P1` Reflection trigger를 임계치 기반으로 동작시킨다
  - Depends on: Retrieval scoring 구현
  - DoD:
    - [x] 최근 이벤트 누적 중요도 `>= 150`에서 reflection을 실행한다
    - [x] reflection 실행 후 누적값 리셋 정책을 적용한다
  - [x] 임계치 테스트를 추가한다

### 2-B. Reflection 생성 파이프라인 세분화

- [x] `P1` reflection 입력 메모리 윈도우를 고정한다
  - Depends on: Reflection trigger 구현
  - DoD:
    - [x] 최근 기억 100개를 시간 역순으로 수집한다
    - [x] 기억 부족 시 가능한 개수만 사용하고 실패 없이 진행한다

- [x] `P1` salient question 3개를 생성한다
  - Depends on: reflection 입력 메모리 윈도우 고정
  - DoD:
    - [x] LLM 출력에서 질문 3개를 안정적으로 파싱한다
    - [x] 파싱 실패 시 fallback 질문 생성 규칙을 적용한다

- [x] `P1` 질문별 관련 기억 retrieval을 수행한다
  - Depends on: salient question 3개 생성
  - DoD:
    - [x] 질문마다 관련 기억 top-k를 조회한다
    - [x] 질문별 retrieval 결과를 구분된 구조로 유지한다

- [x] `P1` high-level insight 5개를 생성한다
  - Depends on: 질문별 관련 기억 retrieval 수행
  - DoD:
    - [x] insight 5개를 생성하고 빈 항목 없이 저장한다
    - [ ] insight마다 source question을 연결한다

- [x] `P1` insight citations를 memory id로 연결한다
  - Depends on: high-level insight 5개 생성
  - DoD:
    - [x] insight별 근거 memory id 목록을 `citations`에 저장한다
    - [x] 존재하지 않는 memory id가 citations에 들어가지 않도록 검증한다

### 2-C. Reflection 재귀 활용

- [x] `P1` reflection memory를 retrieval 후보에 포함한다
  - Depends on: insight citations 연결
  - DoD:
    - [x] node_type=REFLECTION 메모리가 retrieval 후보군에 포함된다
    - [x] observation/reflection 혼합 시 점수 계산이 깨지지 않는다

- [x] `P1` reflection-on-reflection 회귀 테스트를 추가한다
  - Depends on: reflection memory retrieval 후보 포함
  - DoD:
    - [x] reflection이 다음 reflection 생성에 사용되는 시나리오 테스트를 추가한다
    - [x] 기존 retrieval 테스트가 회귀 없이 통과한다

### 2-D. Reaction 생성 파이프라인 안정화

- [x] `P1` reaction 생성을 2-call(판단/문장생성)로 분리한다
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [x] 1차 호출에서 `should_react` 판단과 근거 필드를 JSON으로 파싱한다
    - [x] 2차 호출에서 `utterance`를 생성하고 semantic/overlap guard를 적용한다
    - [x] 단위 테스트로 retry/parse-fallback 경로를 검증한다

- [x] `P1` Brain/Governance/Diagnostics 경계를 분리한다
  - Depends on: reaction 2-call 파이프라인 분리
  - Regressed 2026-08-25: `docs/architecture-analysis/02_design.md` §1.3 코드 분석 결과
    `ActionLoopResult`(`agents/brain/types.py:64,66`)가 `reaction_trace`
    (`raw_response`/`parse_error`/retry count 포함)와 `diagnostics`
    (`model_thought`/`self_critique`/`decision_process` 포함) 필드를 그대로
    갖고 있음을 확인. AGENTS.md §9 위반 — 아래 DoD는 실제로 미충족.
  - Resolved 2026-08-25: `ActionLoopResult`(`agents/brain/types.py`)에서
    `reaction_trace`/`diagnostics` 필드를 제거. `AgentBrainGraphRunner.run()`과
    `AgentBrain.action_loop()`이 `(ActionLoopResult, ReactionDecision | None)`
    튜플을 반환하도록 변경해 governance 원천 데이터를 별도 채널로 분리.
    `world/engine.py`가 `llm/governance/trace_payload.py`의
    `merge_policy_trace`/`is_reaction_parse_failure`로 trace를 병합하고,
    `agents/decision_diagnostics.py`의 `build_action_diagnostics`를 직접 호출해
    진단 정보를 조립하도록 이동.
  - DoD:
    - [x] ActionLoopResult에서 디버그/관측성 필드를 분리하고 핵심 행동 필드만 유지한다
    - [x] reaction trace 머지 로직을 governance 계층 유틸로 이동한다
    - [x] diagnostics 포맷팅(`action_summary`, `decision_process` 등)을 별도 모듈로 분리한다

## 3) Planning & Re-planning (논문 핵심 3)

### 3-A. 계층형 계획 생성

- [x] `P1` day plan 생성기(5~8 broad strokes)를 구현한다
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [x] day plan 항목 수가 5~8 범위를 만족한다
    - [x] 각 항목에 `start_time`, `end_time`, `location`, `action_content`가 포함된다

- [x] `P1` hourly plan 생성기를 구현한다
  - Depends on: day plan 생성기 구현
  - DoD:
    - [x] active day plan 항목 입력을 기준으로 near-future hourly plan을 생성한다
    - [x] 현재 시점 기준 active day plan 항목을 선택한다
    - [x] hourly plan이 시간 순서로 정렬된다

- [x] `P1` minute plan(기본 5~15분 단위) 생성기를 구현한다
  - Depends on: hourly plan 생성기 구현
  - DoD:
    - [x] 모델 생성 minute 단위가 5~15분 범위를 만족하고 최종 시간창 보정은 5분 단위를 유지한다
    - [x] active hourly plan 항목 입력을 기준으로 near-future minute plan을 생성한다
    - [x] 현재 시점 기준 active hourly plan 항목을 선택한다
    - [x] 현재 시점 기준 다음 실행 항목을 즉시 찾을 수 있다
    - [x] 논문식 fixed-duration task decomposition으로 minute plan의 시간·장소를 runtime이 조립한다
    - [x] 논문 구현처럼 minute duration 초과분은 끝에서 자르고 부족분은 마지막 항목을 늘려 시간 경계를 맞춘다
    - [x] day/hourly 고정 시간창의 시작·끝·연속성을 semantic retry로 검증한다
    - [x] 8개 초과의 연속 day-plan 초안을 5~8 broad strokes로 병합하고 자정 직전 tail plan을 지원한다
    - [x] hourly/minute 위치를 authoritative parent plan에서 상속한다

### 3-B. Tick react 판정과 부분 재계획

- [ ] `P1` tick마다 이벤트-계획 충돌 판정기를 구현한다
  - Depends on: minute plan 생성기 구현
  - DoD:
    - [ ] 관찰 이벤트가 현재 계획을 방해/우선하는지 판정한다
    - [ ] 판정 결과(reason/code)를 로그 가능 형태로 남긴다

- [ ] `P1` react 발생 시 이후 구간만 재수립한다
  - Depends on: tick 충돌 판정기 구현
  - DoD:
    - [ ] 현재 시점 이전 계획은 보존한다
    - [ ] 현재 시점 이후 계획만 재생성한다

### 3-C. 대화 연계 planning

- [ ] `P2` 조우 시 pass-by vs converse 결정을 구현한다
  - Depends on: react 발생 시 이후 구간만 재수립
  - DoD:
    - [ ] 조우 이벤트 입력으로 행동 선택(pass-by/converse)을 반환한다
    - [ ] 결정 근거(관계/맥락)를 추적 가능하게 남긴다

- [ ] `P2` 대화 결과를 plan 업데이트에 반영한다
  - Depends on: pass-by vs converse 결정 구현
  - DoD:
    - [ ] 대화에서 획득한 새 정보가 memory/plan에 반영된다
    - [ ] 관계 변화가 다음 계획 우선순위에 영향을 준다

## 4) World Integration (시뮬레이션)

- [x] `P1` simulation harness에서 world 상태/이벤트 로직을 분리한다
  - Depends on: 없음
  - DoD:
    - [x] turn world_context/observed_events 생성 로직을 world 모듈로 이동한다
    - [x] 발화 브로드캐스트와 incoming queue 갱신을 WorldConversationSession 메서드로 캡슐화한다
    - [x] 관련 단위 테스트를 world/session 경계 기준으로 보강한다

- [x] `P1` simulation 실행 코어를 engine/policy/metrics 레이어로 분리한다
  - Depends on: simulation harness에서 world 상태/이벤트 로직 분리
  - DoD:
    - [x] turn 1-step 실행 로직을 `SimulationEngine.step`으로 추출한다
    - [x] 반복 억제/fallback 규칙을 dialogue policy 모듈로 분리한다
    - [x] 품질 지표 계산을 metrics 모듈로 분리하고 harness는 출력만 담당한다
    - [x] engine/policy/metrics 경계 단위 테스트를 추가한다

- [x] `P1` simulation 로그를 운영/디버그 모드로 분리하고 발화 의사결정 과정을 구조화한다
  - Depends on: simulation 실행 코어를 engine/policy/metrics 레이어로 분리
  - DoD:
    - [x] 기본 로그에서 raw_response/상수 필드/빈 필드를 축소한다
    - [x] 세션 시작 시 semantic threshold 등 상수 필드를 1회만 출력한다
    - [x] 발화 결정 과정을 `decision_process`로 구조화해 턴 로그에 출력한다

- [x] `P1` 짧은 대화 아크를 session/reaction 경계에 도입한다
  - Depends on: simulation 로그를 운영/디버그 모드로 분리하고 발화 의사결정 과정을 구조화한다
  - DoD:
    - [x] 대화 세션이 목표 턴 수와 phase(opening/middle/closing)를 계산한다
    - [x] reaction prompt가 goal/remaining turns/wrap-up 지시를 반영한다
    - [x] 관련 단위 테스트로 session 상태와 prompt 반영을 검증한다
    - [x] closing 결정이 `end_dialogue` 구조화 신호를 통해 세션 종료로 연결된다

- [x] `P1` 모든 인지·계획·반성·대화 출력을 한국어로 고정한다
  - Depends on: reaction 생성 파이프라인 안정화
  - DoD:
    - [x] 제품 runtime 언어를 `ko`로 고정한다
    - [x] reaction/planning/reflection LLM 호출에 공통 한국어 system policy를 적용한다
    - [x] 영어-only 최종 발화를 저장/브로드캐스트 전에 차단한다
    - [x] persona 성격/습관/현재 계획/seed memory를 한국어로 제공한다
    - [x] 프런트엔드 계획 fallback과 주민 상태를 한국어로 표시한다

### 4-A. Backend 실시간 파이프라인

- [x] `P1` API runtime에서 world engine step 경로를 재사용한다
  - Depends on: simulation 실행 코어를 engine/policy/metrics 레이어로 분리
  - DoD:
    - [x] app startup에서 world runtime(engine/session)를 초기화한다
    - [x] `/world/state`, `/world/step` 엔드포인트로 코어 step을 호출한다
    - [x] API 단위 테스트로 state/step 응답 계약을 검증한다

- [x] `P1` world clock와 tick scheduler를 붙인다
  - Depends on: Planning & Re-planning 핵심 완료
  - DoD:
    - [x] 단일 기준 시계로 tick이 안정적으로 증가한다
    - [x] tick loop에서 perceive-plan-act 순서가 유지된다
    - [x] 06:00부터 5분 단위로 가속된 하루를 자동 시작한다
    - [x] active minute plan을 canonical 공간 이동과 WebSocket UI에 연결한다
    - [x] 마을 지도와 계획의 canonical 건물 이름을 한국어로 통일한다
    - [x] hourly/minute plan에서 축약된 비-canonical 장소를 거부한다
    - [x] 같은 장소에 실제로 인접한 두 agent만 대화를 시작한다
    - [x] cognitive action 실패를 tick scheduler에서 격리해 world clock과 이동을 계속 진행한다
    - [x] 생성된 day/hourly/minute 계층을 완료 시점의 world clock에 맞춰 설치한다
    - [x] 같은 tick의 다중 agent 계획을 모두 검증한 뒤 schedule과 world clock을 원자적으로 갱신한다
    - [x] local LLM cognitive 구간에는 clock을 감속하고 현재 공간 계획을 유지한다
    - [x] planning fallback을 제거하고 생성·검증 실패를 UI와 dashboard에 명시적으로 노출한다
    - [x] 로컬 planner의 생성 timeout을 제거하고 structured JSON 요청에서 Qwen thinking을 끈다
    - [x] 현재 시각을 덮지 않는 미래 계획을 active로 선택하지 않고 planning error로 중단한다
    - [x] 재시작 후에도 게임 시각, 위치, 계획 cache와 조우 cooldown을 복원한다
    - [ ] 비대화 tick에도 주변 사건을 perceive/store하고 필요할 때 retrieve/reflect/react한다

- [x] `P1` Prisma 기반 RPG 세션 저장/불러오기를 구현한다
  - Depends on: world clock + tick scheduler 연동
  - DoD:
    - [x] Prisma schema와 migration을 세션 DB 구조의 단일 기준으로 사용한다
    - [x] 세션, 캐릭터, 기억/citation, 계층 계획, 대화 상태, 인지 로그를 PostgreSQL에 저장한다
    - [x] 새 세션, 현재 세션 저장, 저장된 세션 목록/불러오기 API를 제공한다
    - [x] HUD에서 현재 슬롯, 새 게임, 저장, 불러오기를 조작할 수 있다
    - [x] 낙관적 save version 충돌과 잘못된 snapshot 복원을 거부한다
    - [x] OrbStack PostgreSQL에서 저장 후 backend 재시작과 세션 복원을 검증한다

- [x] `P1` spatial WebSocket snapshot broadcast를 구현한다
  - Depends on: world clock + tick scheduler 연동
  - DoD:
    - [x] `revision`, `position`, `destination`, `action`, `plan`, `route_remaining`을 브로드캐스트한다
    - [x] 느린 클라이언트에는 stale frame 대신 최신 snapshot을 전달한다
    - [x] shared contract 기반 runtime validation 후 클라이언트에서 파싱한다
    - [x] client disconnect를 능동 수신하고 sender/receiver task와 구독을 함께 정리한다
    - [x] 활성 WebSocket 중 hot reload가 worker 종료를 막지 않는지 회귀 검증한다

- [x] `P1` HTTPS 배포 WebSocket 경로와 로컬 포트를 분리한다
  - Depends on: spatial WebSocket snapshot broadcast 구현
  - DoD:
    - [x] backend는 충돌 없는 loopback `8001` 포트를 사용한다
    - [x] HTTPS frontend는 same-origin `wss://.../ws/world`를 사용한다
    - [x] reverse proxy가 `/ws/world`를 backend로 전달한다

- [x] `P1` cognitive/social WebSocket overlay를 구현한다
  - Depends on: spatial WebSocket snapshot broadcast 구현
  - DoD:
    - [x] 실제 dialogue와 사용자 관찰용 thought/action을 세분화해 전달한다
    - [x] spatial snapshot과 동일 revision/게임 시각으로 전달한다
    - [x] speech는 평문, thought/action은 괄호 한 겹으로 표시한다

### 4-B. Frontend 시각화

- [x] `P2` 논문 데모 형태의 탑다운 픽셀 월드 렌더러를 구현한다
  - Depends on: canonical Tiled semantic map
  - DoD:
    - [x] 32px 타일 단위의 지형/길/광장/물 타일을 렌더링한다
    - [x] 건물, 장식, 상호작용 물체, agent를 pixel-art 규칙으로 표시한다
    - [x] 전체 지도 축소 대신 agent 추적/드래그/줌 카메라를 제공한다
    - [x] 관찰자 패널의 주민 선택을 카메라 추적과 모바일 패널 닫기에 연결한다
    - [x] 관찰자 패널의 대표 사건을 `오늘의 메인이벤트`로 표시한다
    - [x] 메인이벤트를 선택 주민의 실제 minute plan과 게임 시각 진행률로 계산한다
    - [x] idle/blocked/offline/목적지 없음 상태를 거짓 fallback 없이 표시한다
    - [x] 모바일 두 손가락 확대·축소와 장면별 조작 안내를 제공한다
    - [x] 게시판·분수·벤치 선택 시 canonical agent affordance를 안내한다
    - [x] WebSocket spatial snapshot이 agent 이동과 HUD 상태에 반영된다

- [x] `P2` 픽셀 월드와 게임 텍스트의 렌더링 계층을 분리한다
  - [x] 타일·캐릭터는 nearest-neighbor Phaser 캔버스에 유지한다
  - [x] 말풍선·이름표·장소 라벨은 카메라 좌표를 따르는 DOM 오버레이로 렌더링한다
  - [x] 화면 가장자리에서도 텍스트 박스 폭을 유지하고 오버레이 경계에서 자연스럽게 자른다

- [x] `P2` 건물별 pixel interior와 출입 portal을 구현한다
  - Depends on: 탑다운 픽셀 월드 렌더러
  - DoD:
    - [x] cafe/library/market도 지붕 없는 kind별 interior를 메인 맵에 항상 표시한다
    - [x] 건물 문 hover/click으로 확대 interior scene에 진입한다
    - [x] cafe/library/market/home kind별 가구와 바닥 템플릿을 제공한다
    - [x] `ESC`, `E`, 출구 클릭으로 outdoor scene에 복귀한다
    - [x] 확대 interior 주민을 live snapshot으로 갱신하고 선택 시 outdoor follow로 연결한다
    - [x] 새 building object는 kind 기반 interior template을 재사용할 수 있다

- [x] `P2` Smallville형 상시 노출 주택 interior를 구현한다
  - Depends on: 건물별 pixel interior와 출입 portal 구현
  - DoD:
    - [x] home kind는 지붕 없이 침실/주방/공용실/욕실을 메인 맵에 표시한다
    - [x] 침대/책상/책장/테이블/주방/욕실 fixture를 재사용 템플릿으로 렌더링한다
    - [x] 집에 도착한 agent를 행동에 맞는 방에 표시하고 현재 계획을 말풍선으로 보여준다
    - [x] 실내 관찰 위치가 backend canonical tile이나 4방향 route를 변경하지 않는다

- [x] `P2` Tiled map + collision을 연결한다
  - Depends on: WebSocket state broadcast 구현
  - DoD:
    - [x] 맵 충돌 레이어가 backend A\* 이동 후보를 제한한다
    - [x] agent 이동이 backend route만 소비해 충돌 규칙을 위반하지 않는다
    - [x] 건물/물/간판/분수/벤치/나무/가로등을 정적 blocking object로 선언한다

- [x] `P2` A\* pathfinding을 적용한다
  - Depends on: Tiled map + collision 연결
  - DoD:
    - [x] 목표 좌표까지 유효 경로를 계산한다
    - [x] 경로 불가능 시 빈 경로 fallback을 처리한다
    - [x] authored path/광장/공원을 낮은 비용으로 계산해 길을 우선한다

- [x] `P2` 문 출입과 동적 점유 collision을 적용한다
  - Depends on: A\* pathfinding 적용
  - DoD:
    - [x] 건물은 선언된 문 tile을 통해서만 도착할 수 있다
    - [x] agent끼리 같은 tile을 점유하거나 서로 통과하지 않는다
    - [x] 문이 점유되면 문 앞 walkable 대기 tile로 재탐색한다
    - [x] 도착 agent는 외벽이 아니라 건물 내부 activity slot에 표시한다
    - [x] 캐릭터 말풍선과 nameplate의 화면상 겹침을 자동으로 해소한다

- [x] `P2` Phaser Grid Engine 기반 4방향 이동을 적용한다
  - Depends on: A\* pathfinding 적용
  - DoD:
    - [x] Phaser 3.90 호환 `grid-engine@2.48.2`를 고정한다
    - [x] 전역/agent 이동을 `NumberOfDirections.FOUR`로 제한한다
    - [x] 연속 server snapshot은 한 번에 한 cardinal tile만 애니메이션한다
    - [x] 누락 snapshot은 client pathfinding 없이 authoritative tile로 재동기화한다
    - [x] backend 회귀 테스트로 diagonal tile transition이 없음을 검증한다
    - [x] 프런트엔드 presentation/store 회귀 테스트를 `pnpm test`에 연결한다

- [x] `P2` agent inspector(memory/plan/reflection view)를 `/dashboard`로 구현한다
  - Depends on: A\* pathfinding 적용
  - DoD:
    - [x] 선택한 agent의 memory/plan/reflection을 탭 또는 패널로 조회한다
    - [x] 최신 tick 데이터와 표시가 동기화된다
    - [x] 자동 cognitive turn의 thought/action/decision/governance 로그를 별도 diagnostics buffer에 남긴다
    - [x] `/ws/world`에 내부 진단을 섞지 않고 `/dashboard/state` 읽기 전용 API로 제공한다
    - [x] embedding, raw provider response, prompt, API key를 사용자 응답에서 제외한다
    - [x] 선택 agent의 관점에서 다른 agent와의 비대칭 관계 요약과 근거를 표시한다
    - [x] 정식 호감도 모델이 없는 동안 memory importance를 거짓 호감 점수로 변환하지 않는다

- [ ] `P2` God mode 입력으로 perception event를 주입한다
  - Depends on: agent inspector 구현
  - DoD:
    - [ ] 사용자 입력으로 임의 perception event를 backend에 전달한다
    - [ ] 주입 이벤트가 다음 tick 의사결정에 반영된다

## 5) Social Dynamics & Evaluation (논문 검증)

### 5-A. 정보 확산/관계/협업 지표

- [ ] `P2` 정보 확산 실험을 자동 측정한다
  - Depends on: 대화 결과를 plan 업데이트에 반영
  - DoD:
    - [ ] seed fact 주입 후 인지한 agent 비율을 계산한다
    - [ ] 실험 실행별 결과를 비교 가능한 포맷으로 저장한다

- [ ] `P2` 관계 형성 지표를 계산한다
  - Depends on: 정보 확산 실험 자동 측정
  - DoD:
    - [ ] 네트워크 밀도 `eta = 2|E| / (|V|(|V|-1))`를 계산한다
    - [ ] 시간 경과에 따른 밀도 변화를 기록한다

- [ ] `P2` 협업/조율 지표를 계산한다
  - Depends on: 관계 형성 지표 계산
  - DoD:
    - [ ] 이벤트 초대 대비 실제 도착 agent 수를 측정한다
    - [ ] 이벤트별 성공률을 집계한다

### 5-B. Interview evaluator + Ablation

- [ ] `P2` interview evaluator(25문항) 실행기를 구현한다
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [ ] 카테고리(self-knowledge, memory, plans, reactions, reflections)를 모두 평가한다
    - [ ] 문항별 점수와 근거를 저장한다

- [ ] `P2` interview 자동 채점/결과 포맷을 확정한다
  - Depends on: interview evaluator 실행기 구현
  - DoD:
    - [ ] 총점/카테고리 점수/실패 케이스를 한 포맷으로 저장한다
    - [ ] 반복 실행 간 비교가 가능하다

- [ ] `P2` ablation 실험 플래그를 추가한다
  - Depends on: interview 자동 채점/결과 포맷 확정
  - DoD:
    - [ ] `no-observation`, `no-reflection`, `no-planning` 모드를 제공한다
    - [ ] baseline 대비 성능 차이를 동일 리포트 포맷으로 출력한다

---

## Milestones

- [x] M1: Infra & PoC 완료
- [ ] M2: Single-agent believable daily life
  - 조건: 1) Memory/Retrieval P0 완료 + 2) Reflection P1 완료 + 3) Planning P1 완료
- [ ] M3: Two-agent social interaction + information diffusion
  - 조건: 대화 연계 planning + 정보 확산 실험
- [ ] M4: Multi-agent town simulation + user intervention
  - 조건: World integration + Social/Evaluation 핵심 항목 완료
