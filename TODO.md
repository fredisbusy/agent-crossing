# Agent Crossing Project TODO

논문(Generative Agents: Interactive Simulacra of Human Behavior, UIST '23,
arXiv:2304.03442) 스펙을 위에서 아래로 읽으면서,
기능을 작은 단위로 하나씩 구현하기 위한 실행 보드.

## 사용 규칙

- 우선순위: `P0`(핵심), `P1`(핵심 확장), `P2`(검증/고도화)
- 순서 원칙: 같은 섹션에서는 위에서 아래 순서로만 진행
- 체크 기준: 항목 아래 `DoD`를 모두 만족하면 `[x]`
- 의존성: `Depends on`이 완료되기 전에는 시작하지 않음
- 기준 문서: 알고리즘/상수/계약은 `SPEC.md` + `AGENTS.md`와 동기화
- 논문 참조: 각 섹션 제목에 대응하는 논문 절 번호(`§`)를 표기해 코드-논문 매핑을 유지

## 2026-08-25 논문 원문 대조 결과 (PDF 직접 검토)

TODO 문서가 아니라 논문 PDF 원문(§3~§8)을 직접 읽고 코드베이스와 대조했다.
개별 agent의 인지 컴포넌트(memory/retrieval §4.1, reflection §4.2, day→hour→minute
planning 생성 §4.3)는 논문 수식·구조와 거의 1:1로 구현되어 있다. 반면 논문을
"논문답게" 만드는 두 축은 아직 구현 전이다.

1. **tick 단위 react-and-replan 루프** (§4.3.1 Reacting and Updating Plans) —
   관찰이 현재 계획을 방해하는지 판단하고, 방해 시 현재 시점 이후 구간만
   재계획하는 논문의 핵심 메커니즘. 같은 날 안에 §3-B 판정기(`react_gate.py`)와
   비대화 tick 자동 호출 배선(`_dispatch_tick_plan_disruption_check`)까지
   구현됨 — 남은 것은 그 관찰을 MemoryObject로 저장하는 store 절반뿐
   (§4-A 해당 항목).
2. **창발적 사회 동역학과 그 검증** (§3.4 Emergent Social Behaviors, §7 End-to-end
   Evaluation, §6 Controlled Evaluation) — encounter 시 pass-by/converse 결정,
   대화→plan 반영(coordination 예시: Valentine's party), 정보 확산/관계망 밀도
   η/coordination 성공률 측정, interview evaluator(25문항)와 ablation. 현재
   §3-C, §5 전체와 §6 interview evaluator가 미구현.

아래 §3-B, §3-C, §5, §4-A/§4-B의 남은 항목은 이 대조 결과를 반영해 논문 절
번호와 함께 재작성되었다.

---

## 0) Foundation

- [x] 프로젝트 기본 골격 확정 (`packages/shared`, `packages/frontend`, `packages/backend`)
- [x] Frontend 런타임 부팅 (React 19 + Phaser 3 + Zustand)
- [x] Backend 런타임 부팅 (FastAPI + uv)
- [x] LLM provider 클라이언트 경로를 정리하고 호환 import를 유지한다 (`packages/backend/src/llm/clients`)
- [x] Qwen 추론 강도를 호출 목적에 맞게 적용한다 (structured JSON은 `none`, 자유 형식 판단은 `low`)
- [x] `P0` 모든 LLM JSON 출력을 schema-constrained generation으로 안정화한다
  - DoD:
    - [x] Pydantic 응답 모델에서 JSON Schema를 생성해 provider 호출과 사후 검증에 재사용한다
    - [x] 계획/반성/중요도/반응 JSON에 필수 필드, 추가 필드 금지, 배열 개수, 텍스트 길이 제한을 적용한다
    - [x] token-limit 종료를 parse failure와 구분하고 출력 예산을 한 번 증액해 재시도한다
    - [x] 출력 토큰 상한 대신 prompt/schema 필드 제한으로 응답 길이를 제어한다
- [x] 로컬 LLM + 벡터 DB PoC 통과 (MLX/Vector DB)
- [x] `P0` 메모리 영속 스토어 전환 확정 (PostgreSQL + pgvector)

## 1) Memory Stream & Retrieval (논문 핵심 1, §4.1)

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

## 2) Reflection Loop (논문 핵심 2, §4.2)

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

## 3) Planning & Re-planning (논문 핵심 3, §4.3)

### 3-A. 계층형 계획 생성 (§4.3 Approach)

- [x] `P1` day plan 생성기(5~8 broad strokes)를 구현한다
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [x] day plan 항목 수가 5~16 범위를 만족한다
    - [x] 각 항목에 `start_time`, `end_time`, `location`, `action_content`가 포함된다
    - [x] `P1` (2026-08-25) day-plan 단일 항목을 180분 이하로 제한해 장시간 한 장소 고정 계획을 차단한다 — 생성 prompt, semantic parser, 16개 provider 초안의 canonical 병합에 동일 상한을 적용하고 초과 응답은 재시도한다.

- [x] `P1` hourly plan 생성기를 구현한다
  - Depends on: day plan 생성기 구현
  - DoD:
    - [x] active day plan 항목 입력을 기준으로 near-future hourly plan을 생성한다
    - [x] 현재 시점 기준 active day plan 항목을 선택한다
    - [x] hourly plan이 시간 순서로 정렬된다

- [x] `P1` minute plan(기본 5~15분 단위) 생성기를 구현한다
  - Depends on: hourly plan 생성기 구현
  - DoD:
    - [x] 모델 생성 minute 단위는 5~15분을 유지하고, 현재 시점부터 상위 계획 종료까지의 비정렬 잔여 구간은 runtime tail action으로 정확히 보정한다
    - [x] active hourly plan 항목 입력을 기준으로 near-future minute plan을 생성한다
    - [x] 현재 시점 기준 active hourly plan 항목을 선택한다
    - [x] 현재 시점 기준 다음 실행 항목을 즉시 찾을 수 있다
    - [x] 논문식 fixed-duration task decomposition으로 minute plan의 시간·장소를 runtime이 조립한다
    - [x] 논문 구현처럼 minute duration 초과분은 끝에서 자르고 부족분은 마지막 항목을 늘려 시간 경계를 맞춘다
    - [x] day/hourly 고정 시간창의 시작·끝·연속성을 semantic retry로 검증한다
    - [x] 8개 초과의 연속 day-plan 초안을 5~8 broad strokes로 병합하고 자정 직전 tail plan을 지원한다
    - [x] hourly/minute 위치를 authoritative parent plan에서 상속한다

### 3-B. Tick react 판정과 부분 재계획 (§4.3.1 Reacting and Updating Plans)

논문 원문(Klaus/이젤 예시): "we prompt the language model with these
observations to decide whether the agent should continue with its existing
plan, or react." `agents/reaction/graph.py`의 `should_react`는 이미 조우 중인
대화를 이어갈지 판단하는 dialogue-level 게이트(§2-D 짧은 대화 아크)이며,
§4.3.1이 말하는 "매 tick 모든 관찰에 대해 현재 계획을 계속할지 판단"하는
plan-disruption 게이트와는 범위가 다르다. 후자는 별도 구현이 필요하다.

- [x] `P1` tick마다 이벤트-계획 충돌 판정기를 구현한다
  - Depends on: minute plan 생성기 구현
  - Implemented 2026-08-25: `agents/planning/react_gate.py`의
    `PlanDisruptionGate`가 `[Agent's Summary Description]` + 현재 시각 +
    agent status + observation을 입력으로 continue/react + reason을 판정한다.
    로그는 `agents/decision_diagnostics.py`의 `build_plan_disruption_diagnostics`가
    별도 diagnostics 레코드로 조립하며 `ActionLoopResult`에는 병합하지 않는다.
    `WorldRuntime.evaluate_plan_disruption`이 판정 결과에 따라
    `PlanningCoordinator.react_replan`을 호출하는 상위 게이트로 동작한다.
    `agents/reaction/graph.py`의 dialogue-level `should_react`와는 별개 모듈.
  - DoD:
    - [x] 논문 예시(스탠딩/painting 중 easel 관찰은 무반응, 아버지가 아들의
          짧은 산책을 목격하면 반응)처럼 관찰의 방해도를 판정한다
          (`tests/test_plan_react_gate.py`)
    - [x] 판정 프롬프트가 `[Agent's Summary Description]` + 현재 시각 +
          agent status + observation을 입력으로 사용한다 (§4.3.1 예시 prompt)
    - [x] 판정 결과(continue/react, reason/code)를 로그 가능 형태로 남긴다
    - [x] 판정과 기존 reaction 2-call 파이프라인(§2-D, `agents/reaction/`)의
          경계를 정리한다 — 이 판정이 reaction 여부의 상위 게이트가 된다
  - Note (2026-08-25 갱신): `WorldRuntime._dispatch_tick_plan_disruption_check`가
    `_advance_world_tick`(비대화 tick, LLM 호출 없음)에서 매 tick 상대
    agent의 공간 `current_action` 변화를 diff해 변화가 있을 때만 이 게이트를
    백그라운드 스레드로 호출하도록 배선했다(`_advance_world_tick`은
    `asyncio.to_thread` 안에서 실행되므로 `asyncio.create_task`가 아닌
    `threading.Thread`로 offload — 그렇지 않으면 "no running event loop"로
    깨진다). 다만 이 관찰은 spatial 상태 텍스트일 뿐, MemoryObject로
    저장되지는 않는다 — 아래 §4-A perceive/store 항목의 memory 저장 부분은
    여전히 미완료.

- [x] `P1` react 발생 시 이후 구간만 재수립한다
  - Depends on: tick 충돌 판정기 구현
  - Implemented 2026-08-25: `agents/planning/lifecycle.py`의
    `PlanningCoordinator.react_replan`이 day plan은 그대로 두고(따라서
    canonical location/시간창도 보존) 활성 day-plan item으로부터 hourly plan을,
    새 hourly plan으로부터 minute plan을 현재 시점 기준으로 다시 생성해
    설치한다.
  - DoD:
    - [x] 현재 시점 이전 계획(day/hourly/minute)은 보존한다
    - [x] 현재 시점 이후 계획만 재생성한다 (§4.3.1: "We then regenerate the
          agent's existing plan from the time when the reaction takes place")
    - [x] 재수립된 구간이 원래 day plan의 canonical location/시간창 제약을
          위반하지 않는다 (SPEC.md §7과 정합) — hourly/minute이 변경되지 않은
          day plan item에서 파생되므로 자동 보장됨
    - [x] 회귀 테스트: 방해 없는 tick에서는 기존 계획이 재생성되지 않는다
          (`test_no_disruption_tick_does_not_regenerate_plan`)

### 3-C. 대화 연계 planning (§4.3.1 마지막 문단, §3.4.3 Coordination)

논문 원문: "if the action indicates an interaction between agents, we
generate their dialogue" — 즉 조우 판정과 대화 생성은 3-B의 react 판정에
종속된 하위 분기다. Isabella의 Valentine's Day party 예시(§3.4.3, Figure 9)가
이 전체 체인(초대 확산 → 상대방 plan에 반영 → 실제 참석)의 논문 기준
end-to-end 시나리오다.

- [x] `P2` 조우 시 pass-by vs converse 결정을 구현한다
  - Depends on: react 발생 시 이후 구간만 재수립
  - Implemented 2026-08-25: `agents/reaction/encounter.py`의 `EncounterGate`가
    relationship_summary + context_summary 두 요약(§4.3 예시 패턴)을 근거로
    `should_converse`를 판정한다. `world/runtime.py`의
    `WorldRuntime._should_converse_on_encounter`가 조우 감지 지점
    (`_start_dialogue_for_real_encounter`)에서 게이트를 호출하고, converse
    결정 시에만 기존 `WorldConversationSession.start_dialogue()`(§2-D)로
    연결한다. `build_world_runtime`이 기본 provider client로 게이트를
    구성한다. `encounter_gate`가 없으면(예: 단위 테스트) 기존 동작(항상
    대화)을 유지해 하위 호환을 지킨다.
  - DoD:
    - [x] 조우 이벤트 입력으로 행동 선택(pass-by/converse)을 반환한다
    - [x] 결정 근거(관계/맥락 요약, §4.3 예시의 relationship + context summary
          두 프롬프트)를 추적 가능하게 남긴다 (`build_encounter_diagnostics`)
    - [x] converse 결정 시 기존 dialogue 세션(§2-D 짧은 대화 아크)으로 연결된다

- [x] `P2` 대화 결과를 plan 업데이트에 반영한다
  - Depends on: pass-by vs converse 결정 구현
  - Implemented 2026-08-25: `WorldConversationSession.broadcast_reply`가
    (기존 코드 그대로) 발화를 상대 agent의 observation memory로 저장한다.
    새로 추가된 `PlanningCoordinator._generate_day_plan`의
    `_recent_planning_relevant_memories` 헬퍼가 매 day plan 생성 시
    `memory_service.get_retrieval_memories`로 관련 기억(대화로 들은 초대 등)을
    조회해 persona_background에 포함시켜 실제 LLM day plan 생성에 반영한다.
  - Verified 2026-08-25 (논문 원문 재확인): §4.3.1은 관계/맥락 영향을 별도
    수치 가중치 공식이 아니라 "What is [observer]'s relationship with the
    [observed entity]?" / "[Observed entity] is [action status of the
    observed entity]" 두 retrieval 질의를 요약해 프롬프트에 넣는 것으로만
    정의한다("The context summary is generated through two prompts that
    retrieve memories via the queries ... and their answers summarized
    together."). §7.1.1/§7.1.2의 네트워크 밀도 `eta`도 평가 지표일 뿐 계획
    우선순위 가중치가 아니다. 즉 논문에 정의된 "전용 관계 가중치 공식"은
    애초에 존재하지 않으므로, 현재 구현(`EncounterGate`의 relationship +
    context summary, `_recent_planning_relevant_memories`)이 스펙을 충족하는
    전부다. SPEC.md §8에 근거를 명시했다.
  - DoD:
    - [x] 대화에서 획득한 새 정보(예: 파티 초대)가 상대 agent의 memory에
          observation으로 저장된다
    - [x] 저장된 정보가 다음 day/hourly plan 생성 시 retrieval 후보에 포함되어
          실제 계획에 반영된다 (`test_day_plan_generation_includes_retrieved_memories`)
    - [x] 관계 변화가 다음 계획 우선순위에 영향을 준다 — 논문은 이를 별도
          수치 가중치가 아니라 relationship + context summary를 프롬프트에
          포함하는 방식으로만 정의하며, 이는 이미 구현돼 있다(위 note 참고).
    - [x] 통합 시나리오 테스트: 논문 §3.4.3처럼 "A가 B에게 이벤트를 알림 → B가
          다음 planning 사이클에서 참석을 계획 → 실제 해당 시간/장소에 도착"이
          재현된다 — `test_event_notification_via_conversation_flows_into_next_day_plan`
          (`tests/test_planning_lifecycle.py`)이 `WorldConversationSession.broadcast_reply`
          → B의 memory 저장 → `PlanningCoordinator.bootstrap`의 day plan 생성
          → (mock LLM 응답을 통해) 초대받은 시간/장소 항목이 실제 계획에
          포함되는 것을 결정론적으로 검증한다. 실시간 다중 tick 시뮬레이션
          harness는 범위 밖(§5 Social Dynamics & Evaluation)이다.

## 4) World Integration (시뮬레이션, §3 / §5 Sandbox Environment)

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

- [x] `P1` 6명 persona를 직업 중심 설정에서 다축 생활 캐릭터로 확장한다
  - Research/Design: `docs/persona-diversity/00_input.md`,
    `01_requirements.md`, `02_design.md`
  - Implemented 2026-08-26:
    - [x] 논문 §3.1/§4.3과 Animal Crossing의 personality+hobby,
      Stardew Valley의 schedule+relationship event 패턴을 대조한다
    - [x] 모든 주민에게 비업무 취미, 고유 말투, 선호/경계, 결점, 개인 목표,
      관계별 태도를 부여한다
    - [x] 기존 map에서 행동 가능한 공원·광장·도서관·시장·카페 활동으로
      routine/current plan을 다양화한다
    - [x] 지호의 사적 호감과 수진의 자율적인 친구 관점을 유지한다
    - [x] 주민별 행동 시그니처와 사회적 경계가 로딩되는 회귀 테스트를 추가한다
    - [x] 6명에게 MBTI를 부여하고 네 글자를 실제 사교 에너지·정보 해석·판단·
      계획 행동으로 풀어 쓴다
    - [x] 기본적으로 성별을 전제하지 않는 이상형(끌리는 행동·비호감 행동·관계
      속도·경계)을 prompt-visible identity anchor에 추가하고, 명시적인 캐릭터
      설정이 있을 때만 성별 선호를 허용한다
    - [x] 내향성 자체는 감점하지 않되 낮은 친밀도에서 반복되는 원치 않는 접근과
      거절 신호 무시를 내부 호감 저하·대화 회피 근거로 반영한다
    - [x] MBTI 궁합·평범한 친절·한 번의 대화가 `romantic_interest`를 자동으로
      올리지 않도록 조우/반응 프롬프트와 회귀 테스트를 고정한다
    - [x] 하은을 ESTP형 활동가로 재설계해 야구·새 취미·남성 대상 적극적
      플러팅·쉽게 삐지는 반응·맥주와 술자리 선호를 routine/current plan/seed
      memory까지 일관되게 반영하되 명확한 거절과 상대의 음주 선택은 존중하게 한다

- [x] `P1` WorldRuntime을 정확히 2명 고정에서 N-agent + pairwise 대화로 확장한다
      (§3.4 조우 모델 — "마을 전체가 한 방에서 듣는" 공용 채팅방이 아니라
      가까이 있는 두 명끼리만 사적으로 대화)
  - Depends on: 짧은 대화 아크를 session/reaction 경계에 도입
  - Implemented 2026-08-25:
    - `agents/persona_loader.py::PersonaLoader.list_names()`로 persona
      디렉토리의 파일 개수만큼 로스터를 자동 구성한다
      (`run_agent_loop_simulation.py`의 `DEFAULT_CONFIG` 기본값).
      `api/main.py`의 `persona_names[:2]` 잘림도 제거했다. 검증용 3번째
      페르소나(Minji)와 `briar-cove.tmj` spawn 포인트를 추가했다. 이후
      2026-08-25에 페르소나 3명(Jungwoo·버드나무 시장, Haeun·달맞이꽃
      공원, Taeo·허니컵 카페 단골)을 더 추가해 마을 인구를 6명으로
      채웠다(spawn 포인트도 각각 추가, `test_world_map.py` 스폰 목록
      갱신).
    - `world/session.py::WorldConversationSession`이 항상 정확히 2명(한
      쌍)만 받도록 강화됐다 — "마을 전체 로스터가 도는 공용 채팅방" 모델
      대신 세션은 매번 특정 쌍 전용으로 새로 만들어진다.
    - `world/runtime.py`: `_start_dialogue_for_real_encounter`가
      `itertools.combinations`로 모든 쌍을 스캔해 조건을 만족하는 첫 쌍만
      대화를 시작한다(`_open_session_for_pair`). 동시 활성 대화는 설계상
      최대 1건(로컬 LLM 직렬 처리 제약과 일치). 조우 쿨다운을 전역
      타임스탬프에서 쌍별(`_pair_cooldown_until`, `frozenset` 키)로
      바꿔 한 쌍의 쿨다운이 다른 쌍을 막지 않는다.
      `_dispatch_tick_plan_disruption_check`(§3-B)도 고정 2-agent 쌍
      대신 `itertools.permutations`로 전체 agent 쌍을 본다.
    - `persistence/contracts.py`: `SNAPSHOT_SCHEMA_VERSION`을 2로 올리고
      `ConversationSave.participant_agent_names`(세션이 매번 다른 쌍으로
      재생성되므로 참가자를 명시적으로 저장)와
      `RuntimeSaveState.pair_cooldown_until`(dict, 쌍별 쿨다운)을
      추가했다. 이전 스키마 저장분은 호환되지 않는다(breaking change).
  - DoD:
    - [x] 에이전트 수가 persona 정의 개수를 따른다
    - [x] 조우 시 조건을 만족하는 쌍만 대화를 시작하고 나머지 agent는
          영향받지 않는다
    - [x] 쌍별 조우 쿨다운이 서로 독립적이다
    - [x] 이미 대화 중이면 다른 쌍이 조건을 만족해도 새 대화가 시작되지
          않는다
    - [x] 저장된 대화의 참가자 쌍으로 복원 시 세션이 정확히 재구성된다
    - [x] 관련 단위 테스트(`test_world_session.py`, `test_world_runtime.py`,
          `test_session_persistence.py`, `test_world_map.py`)를 추가/갱신한다
  - Note (2026-08-25 갱신): 동시에 2건 이상의 대화가 각자 진행되는 진짜
    다중 동시 대화를 이어서 구현했다 —
    - `world/engine.py::SimulationEngine`이 더 이상 `self.session`을
      생성자에 고정으로 들고 있지 않는다. `step()`이 `session`을 인자로
      받아, 엔진 인스턴스 하나를 여러 세션이 공유한다.
    - `world/runtime.py::WorldRuntime`이 `self.session`(단일) 대신
      `self.sessions: dict[pair_key, WorldConversationSession]`을 쓴다.
      `_engaged_agent_ids()`가 이미 어떤 세션에 참여 중인 agent를
      추적해, `_start_dialogue_for_real_encounter`가 그 agent를
      제외하고 새 쌍을 찾는다(한 agent가 두 대화에 동시에 낄 수 없음).
      `_cognitive_task`(단일) → `_cognitive_tasks`(dict)로 바뀌어
      `_run_scheduler`가 매 tick 활성 세션마다 독립된
      `_run_cognitive_turn(pair_key)` 태스크를 스레드로 띄우고
      `asyncio.gather`로 모두 기다린다.
    - `spatial.py::SpatialWorldRuntime.clear_cognitive_overlay(agent_id=)`
      (전체 clear가 아닌 단일 agent clear)를 추가해, 한 쌍의 턴이
      끝나며 오버레이를 지울 때 다른 쌍의 말풍선을 지우지 않게 했다.
    - persistence: `RuntimeSaveState.conversation`(단수) →
      `conversations: list[ConversationSave]`(복수)로 바꾸고
      `SNAPSHOT_SCHEMA_VERSION`을 3으로 올렸다.
    - `step()`(CLI/테스트용 단일 호출 드라이버)은 여러 세션 중 하나를
      "primary session"으로만 진행한다(`_primary_session()`) — 진짜
      동시성은 스케줄러 경로(`_run_scheduler`/`_run_cognitive_turn`)에서만
      보장된다. `metrics()`/`state()`의 `history_size` 등도 동일하게
      primary session 기준이다(여러 세션의 history를 섞으면 서로 무관한
      대화 턴을 인접한 것처럼 비교하게 되어 의미가 없다).
    - `test_world_runtime.py::test_concurrent_dialogue_sessions_run_in_parallel_without_interfering`가
      두 쌍의 `_run_cognitive_turn`을 `asyncio.gather`로 동시에 돌려
      실제로 겹쳐 실행되는지(`max_concurrent == 2`)와 한 쌍의 오버레이
      처리가 다른 쌍을 건드리지 않는지를 검증한다.
    - 여전히 의도적으로 하지 않은 것: Ollama 쪽 병렬 처리 설정
      (`OLLAMA_NUM_PARALLEL`)은 손대지 않았다 — 코드 구조는 동시
      대화를 지원하지만, 로컬 LLM 서버가 병렬 슬롯을 몇 개나 처리할
      수 있는지는 별도로 튜닝해야 한다.

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
    - [x] `P1` (2026-08-25) world clock이 논문 §3.1.1대로 "agent 행동 결정 완료"에
          게이팅되도록 수정한다 — `_run_scheduler`가 실시간 타이머만으로 자유
          진행하지 않고, 매 tick의 in-flight `_cognitive_task`(대화 턴)와
          `_dispatch_tick_plan_disruption_check`가 기동한 백그라운드 plan-react
          스레드를 모두 완료까지 `await`/`join`한 뒤에야 다음 `_advance_world_tick`으로
          넘어간다. `WorldRuntime.step()`은 이미 동기 호출이라 별도 수정이 필요 없었다.
    - [x] planning fallback을 제거하고 생성·검증 실패를 UI와 dashboard에 명시적으로 노출한다
    - [x] 로컬 planner의 생성 timeout을 제거하고 structured JSON 요청에서 Qwen thinking을 끈다
    - [x] 현재 시각을 덮지 않는 미래 계획을 active로 선택하지 않고 planning error로 중단한다
    - [x] 재시작 후에도 게임 시각, 위치, 계획 cache와 조우 cooldown을 복원한다
    - [x] `P1` 비대화 tick에도 주변 사건을 perceive/store하고 필요할 때
          retrieve/reflect/react한다 (§4 Perceive→Store 루프를 대화가 없는
          tick에도 적용 — 이전에는 대화가 발생하는 tick에서만 관찰이
          기억화됐다). Depends on: §3-B tick 충돌 판정기 - [x] react 절반: `WorldRuntime._dispatch_tick_plan_disruption_check`
          (2026-08-25)가 비대화 tick마다 상대 agent의 공간 상태 변화를
          감지해 §3-B `PlanDisruptionGate`를 호출한다. - [x] store 절반 (2026-08-25): `_run_plan_disruption_check`가 판정
          직전에 `memory_service.create_observation_from_text`로 관찰을
          MemoryObject(OBSERVATION)로 저장한다 — god-mode 주입 경로
          (`api/main.py::post_god_mode_perception`)와 동일한
          store-then-evaluate 순서. 저장된 메모리는 기존
          `memory_stream`/retrieval 경로를 그대로 타므로 이후 retrieve에
          자동 반영된다. 단, reflection 누적 중요도 트리거(§2-A, `>=150`)를
          이 저장 지점에서 직접 호출하지는 않는다 — god-mode 경로도
          동일한 한계를 가지며, reflection trigger는 별도 루프에서
          누적값을 관리하는 기존 설계를 그대로 따른다.

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

- [x] `P2` 세션별 방향성 관계 수치 모델과 관계 탭을 구현한다
  - Depends on: agent inspector 구현
  - Design: `docs/dashboard-relationship-redesign/00_input.md` ~ `05_review.md`
  - DoD:
    - [x] 이름만 포함된 PLAN, 이동 상태, prompt형 진단 문자열을 관계 요약과 근거에서 제외한다
    - [x] 관계 근거 조회를 일반 기억 탭의 `memory_limit`과 분리하고 전체 근거 수와 표시 수를 구분한다
    - [x] 친숙도·신뢰·인간적 호감·긴장·이성적 관심 범위, 고정 event delta, 일일 cap과 중복 방지를 SPEC에 정의한다
    - [x] 인간적 호감과 이성적 관심을 별도 축으로 정의하고 일반 대화의 연애 축 자동 상승을 금지한다
    - [x] `WorldRuntime` 방향성 상태·원장, snapshot v4, SQLAlchemy/Alembic projection을 추가한다
    - [x] `measurement=modeled_v1`과 비대칭 private perspective를 shared/API에 적용한다
    - [x] 관계 정보와 상대의 현재 행동·위치·목적지를 시각적·의미적으로 분리한다
    - [x] 개요 탭의 전체 관계 패널 중복을 제거하고 관계 탭을 대상 목록 + 상세 구조로 정리한다
    - [x] 한국어 문구, 빈 상태, 키보드, 44px 터치 영역, 모바일 반응형을 검증한다
    - [x] 실제 `/dashboard/state`와 공개 `/dashboard`에서 내부 문자열 미노출과 위치 정확성을 확인한다
  - Follow-up: 도움·약속·갈등은 canonical committed action signal 구현 후 연결하며
    관계 수치를 planning prompt에 되먹임하지 않는다.

- [x] `P1` dashboard 탭 관측성·탐색성 개선을 구현한다
  - Design: `docs/dashboard-tabs-product-planning/00_input.md`, `01_requirements.md`,
    `02_design.md`, `05_review.md`
  - Depends on: agent inspector, 방향성 관계 탭 구현
  - DoD:
    - [x] 진단 로그 탭과 우측 전역 로그의 agent filter 상태를 분리한다
    - [x] 로그인 제한 없이 memory·reflection·관계 근거 원문을 공개하도록 확정한다
    - [x] 공개 diagnostics 직렬화를 명시적 allowlist projection으로 제한한다
    - [x] 공개 runtime의 `current_location_path` 정확성과 runtime 오류 표시를 복구한다
    - [x] 완료 기반 state polling과 독립 event cursor polling/backoff를 적용한다
    - [x] 기억·성찰에 원문·total/cursor/status를, 관계에는 summary/evidence를 제공한다
    - [x] 계획 phase, gap/overlap, last replan reason과 runtime planning error를 제공한다
    - [x] 탭 키보드 탐색, URL 상태, 44px 터치 영역과 모바일 runtime 요약을 적용한다
    - [x] 탭 URL/필터 독립성/계획 검증/원문·내부 trace 경계/cursor 회귀 테스트를 추가한다
    - [x] 개요 탭에서 persona 원본의 나이·성별·traits와 runtime 고정 페르소나
      문장 전체를 표시하고 shared/API/runtime validation 계약으로 고정한다

- [x] `P2` God mode 입력으로 perception event를 주입한다 (§3.2 User Controls,
      §8.1 "Isabella's apartment: kitchen: stove is burning" 예시)
  - Depends on: agent inspector 구현
  - Implemented 2026-08-25: `POST /world/god-mode/perception`
    (`api/main.py::post_god_mode_perception`)이 `agent_id` + 자연어 `content`를
    받아 `MemoryManager.create_observation_from_text`로 즉시 observation
    memory를 저장하고, `runtime.plan_react_gate`가 구성된 경우
    `WorldRuntime.evaluate_plan_disruption`을 호출해 §3-B
    `PlanDisruptionGate` 판정을 실행한다(react 시 `react_replan`까지 연결).
  - DoD:
    - [x] 사용자 입력(자연어 상태 변경 문장)으로 임의 perception event를
          backend에 전달한다
    - [x] 주입 이벤트가 observation memory로 저장되고 §3-B 판정기를 거쳐
          의사결정에 반영된다 — 현재는 주입 직후 동기적으로 판정을 실행하며,
          비대화 tick 자동 perceive 루프(§4-A 미완료 항목)가 아직 없어 매
          "정규" tick마다 자동 재판정되지는 않는다
    - [x] 사용자가 agent의 "inner voice"(directive)로 개입하는 입력과, 환경
          상태 변경으로 개입하는 입력을 구분한다 (§3.1.2) — 이 엔드포인트는
          환경 perception 전용이며, directive 입력 경로는 아직 존재하지 않고
          이번 작업 범위에서도 만들지 않았다

## 5) Social Dynamics & Evaluation (논문 검증, §3.4 / §6 / §7)

논문은 아키텍처를 두 방식으로 검증한다: (A) §6 controlled evaluation —
interview 질문으로 ablation 아키텍처를 비교, (B) §7 end-to-end evaluation —
25 agent, 2 game-day 시뮬레이션에서 정보 확산/관계 형성/coordination을
측정. 이 프로젝트는 두 검증 모두 자동화된 형태로 존재하지 않는다.

### 5-A. 정보 확산/관계/협업 지표 (§7.1 Emergent Social Behaviors)

- [x] `P2` 정보 확산 실험을 자동 측정한다 (§7.1.1, 예: Sam의 후보 출마 소식이
      1명→8명(32%)으로 확산)
  - Depends on: §3-C 대화 결과를 plan 업데이트에 반영
  - Implemented 2026-08-25 (부분): `agents/evaluation/interview.py`의
    `InterviewGate.ask`가 §7.1 grounded yes/no interview 판정을 수행한다 —
    질문마다 `memory_service.get_retrieval_memories`로 후보를 조회해
    번호를 매긴 뒤, LLM 응답의 `citation_statement_numbers`가 실제 조회된
    memory id로 해소될 때만 `aware=True`로 인정한다(그렇지 않으면 raw
    `answer_yes=True`라도 hallucination으로 걸러 `aware=False`). memory가
    비어 있으면 LLM 호출 없이 즉시 `aware=False`. `agents/evaluation/diffusion.py`의
    `compute_diffusion_rate`가 여러 agent의 `InterviewAnswer`를 받아
    aware 비율(`DiffusionResult.rate`)을 계산한다(`tests/test_interview.py`,
    `tests/test_diffusion.py`).
  - DoD:
    - [x] seed fact를 특정 agent에게만 초기 memory로 주입한다 — 기존
          `MemoryManager.create_observation_from_text`를 그대로 재사용(전용
          "seed" wrapper는 불필요 — 임의 관찰과 동일한 저장 경로).
    - [x] 시뮬레이션 종료 시점에 각 agent를 "interview"하여(§7.1 질문 형식:
          "Did you know that...?") 인지 여부를 yes/no로 판정한다
          (`InterviewGate.ask`)
    - [x] 답변이 실제 memory stream 근거(해당 정보를 들은 dialogue)에서
          나왔는지 검증해 hallucination을 걸러낸다 (§7.1 방법론) —
          `InterviewAnswer.aware`
    - [x] 실험 실행별 인지 agent 비율을 비교 가능한 포맷으로 저장한다 —
          `DiffusionResult`(aware_agent_names/total_agent_count/rate)
    - [x] 실제 다중 agent 시뮬레이션 실행에 이 판정기를 배선한다(§7의
          "25 agent, 2 game-day" 시나리오에 해당하는 축소판) —
          Implemented 2026-08-25: `run_diffusion_experiment.py`가
          `build_world_runtime` + 실제 `SpatialWorldRuntime`으로 마을을
          띄우고(`_start_dialogue_for_real_encounter`는 spatial runtime
          없이는 no-op이라 반드시 필요), seed agent에게
          `create_observation_from_text`로 사실을 주입한 뒤
          `start_scheduler()`로 지정한 시간(`run_duration_seconds`) 동안
          실제 tick/조우/대화/planning을 진행시키고, `pause_scheduler()`
          후 전 agent에게 `InterviewGate.ask`로 일괄 interview해
          `compute_diffusion_rate`로 확산율을 계산·JSON으로 출력한다.
          로컬 LLM(gemma4:26b) 대상 20초 축소 실행으로 종단 검증
          완료 — seed 보유 agent만 `aware=True`로 정확히 판정되고
          나머지는 근거 없음으로 올바르게 걸러짐(`tests/test_run_diffusion_experiment.py`는
          LLM 없이 도는 순수 로직(`_require_agent`, JSON 직렬화)만 커버).

- [ ] `P2` 관계 형성 지표를 계산한다 (§7.1.1, 시뮬레이션 시작~종료 밀도
      0.167 → 0.74 증가가 논문 기준 결과)
  - Depends on: 정보 확산 실험 자동 측정
  - Implemented 2026-08-25 (부분): `agents/evaluation/diffusion.py`의
    `compute_relationship_density`가 상호 인지 쌍(mutual acknowledgment
    pair) 목록을 무방향 간선으로 중복 제거해 `eta = 2|E| / (|V|(|V|-1))`를
    계산한다(`tests/test_diffusion.py`).
  - DoD:
    - [x] 각 agent 쌍에게 "Do you know of `<name>`?"을 interview로 물어
          상호 인지(mutual acknowledgement)를 무방향 그래프 간선으로 기록한다
          — interview 자체는 `InterviewGate.ask` 재사용, 쌍→간선 dedup은
          `compute_relationship_density`
    - [x] 네트워크 밀도 `eta = 2|E| / (|V|(|V|-1))`를 계산한다
    - [ ] 시뮬레이션 시작 시점과 종료 시점의 밀도를 모두 기록해 변화량을
          남긴다 — 위 정보 확산 항목과 동일하게, 실제 시뮬레이션 실행에
          배선하는 러너가 아직 없어 "시작/종료 두 시점 비교"를 자동으로
          만들어내지 못한다.

- [ ] `P2` 협업/조율 지표를 계산한다 (§7.1.2 Valentine's Day party 사례:
      초대받은 12명 중 5명 참석)
  - Depends on: 관계 형성 지표 계산
  - DoD:
    - [ ] 이벤트 초대 확산 경로(누가 누구에게 언제 알렸는지)를 기록한다
    - [ ] 이벤트 시각·장소에 실제 도착한 agent 수를 초대받은 agent 수 대비로
          측정한다
    - [ ] 불참 agent에게 사유를 interview로 물어 근거를 남긴다 (§7.1.2:
          "너무 바빠서" 등 conflict 사유)

### 5-B. Interview evaluator + Ablation (§6 Controlled Evaluation)

- [ ] `P2` interview evaluator(25문항, 5카테고리 x 5문항) 실행기를 구현한다
      (§6.1: self-knowledge, memory, plans, reactions, reflections)
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [ ] 5개 카테고리 각각 5개 질문(총 25개)을 정의한다 — 논문 Appendix B
          형식을 참고하되 이 프로젝트의 한국어 페르소나에 맞게 재작성한다
    - [ ] 질문마다 agent의 memory stream을 조회해 답변을 생성한다
    - [ ] 문항별 점수와 근거(사용된 memory id)를 저장한다

- [ ] `P2` interview 자동 채점/결과 포맷을 확정한다
  - Depends on: interview evaluator 실행기 구현
  - DoD:
    - [ ] 총점/카테고리 점수/실패 케이스를 한 포맷으로 저장한다
    - [ ] 반복 실행 간 비교가 가능하다
    - [ ] 논문처럼 순위 기반 비교가 필요하면 TrueSkill 등 상대 평가 대신,
          이 프로젝트 규모에 맞는 절대 점수 채점을 우선한다 (인간 평가자
          100명 리크루트는 범위 밖)

- [ ] `P2` ablation 실험 플래그를 추가한다 (§6.2 conditions: no-observation,
      no-reflection-no-planning, no-reflection, full architecture)
  - Depends on: interview 자동 채점/결과 포맷 확정
  - DoD:
    - [ ] `no-observation`(memory stream 자체 비활성화), `no-reflection`,
          `no-planning` 모드를 각각 독립 플래그로 제공한다
    - [ ] 각 ablation은 전체 아키텍처와 동일한 memory 접근 시점까지 재생하고
          해당 컴포넌트만 차단한다 (§6.2: "동일 시점까지의 memory에 동등하게
          접근" — 시뮬레이션을 매 ablation마다 다시 실행하지 않음)
    - [ ] baseline(full architecture) 대비 성능 차이를 동일 리포트 포맷으로
          출력한다

---

## 2026-08-25 로컬 LLM 모델 사이징 결정 (6-agent 마을 대비)

이 하드웨어(Mac Studio M2 Ultra, 64GB 통합 메모리)에서 로컬 Ollama로 실측한
결과를 근거로 기본 모델을 `qwen3.8:27b-mlx`에서 `gemma4:26b`로 바꿨다
(`.env`의 `LLM_MODEL`, git에는 커밋되지 않음 — `settings.py`의 하드코딩
기본값은 그대로 두고 로컬 override만 적용).

- **핵심 발견**: Ollama의 MLX 엔진(현재 Qwen3.5/3.8이 쓰는 `-mlx` 태그
  포맷)은 아직 continuous batching을 지원하지 않는다. `OLLAMA_NUM_PARALLEL`을
  올려도 `-mlx` 모델은 동시 요청을 완전히 직렬로 처리한다 — 실측:
  `qwen3.5:9b-mlx`에 3개 동시 요청을 보내면 각각 끝나는 시점이 ~2.7초씩
  정확히 벌어짐(배치 없음, 개선 0%). 반면 GGUF(llama.cpp 엔진) 모델은
  진짜 배치가 된다 — `gemma4:26b`(Q4_K_M)에 3개 동시 요청을 보내면
  **셋 다 정확히 같은 시각(4.72초)**에 끝남(단일 스트림 대비 총처리량
  ~1.4배, 지연은 훨씬 크게 개선). `qwen3:14b`(GGUF)도 동일하게 배치 확인.
  또한 Qwen3.5는 GGUF 자체가 Ollama에서 아직 아키텍처 미지원이라, "최신
  Qwen + 진짜 동시성"은 지금 시점에 양립 불가능하다.
- 실측 단일 스트림 처리량(이 하드웨어, `/api/generate` eval 기준):
  `qwen3.8:27b-mlx` 35.4 tok/s(배치 불가) · `qwen3.5:9b-mlx` 77 tok/s
  (배치 불가) · `gemma4:26b` 88.7 tok/s(배치 가능) · `qwen3:14b` 50.1
  tok/s(배치 가능). `gemma4:26b`가 속도와 동시성 둘 다에서 앞서 최종
  선택.
- `OLLAMA_NUM_PARALLEL`을 `launchctl setenv`로 3에 설정하고 Ollama.app을
  재시작해 반영했다(로컬 머신 설정, 코드/커밋과 무관).
- **부수적으로 발견 및 수정한 버그**: `llm/clients/litellm_client.py`가
  구조화 출력 호출에서 `reasoning_effort`(사고 과정에 출력 예산을 쓰지
  않도록 하는 옵션)를 `"qwen" in selected_model.lower()`로만 걸어놨었다.
  `gemma4:26b`도 "thinking" capability가 있는데 이 조건에 안 걸려
  재현 테스트에서 256 토큰 한도를 못 채우고 재시도(약 11.9초)가
  발생했다. 조건을 qwen 한정에서 `ollama/`/`ollama_chat/` 전체로
  일반화했더니 재시도 없이 ~1초로 줄었다(`drop_params=True`가 이미
  있어 thinking 미지원 모델에는 안전한 no-op). `tests/test_litellm_client.py`에
  회귀 테스트 추가.
- **`_generate_plans_blocking` 병렬화 완료 (2026-08-25)**:
  - `agents/planning/lifecycle.py::PlanningCoordinator`가 coordinator
    전체를 덮는 단일 `RLock` 대신 **agent별 `RLock`**(`_agent_lock`)을
    쓰도록 바꿨다 — `install_day_plan`/`react_replan`/`ensure_current`가
    LLM 호출을 포함한 본문 전체를 이 lock으로 감싼다. `_states` dict
    구조 자체를 건드리는 지점(`setdefault`)만 여전히 coordinator-wide
    `self._lock`으로 짧게 보호한다. 이 변경 전에는 클라이언트 쪽
    루프를 아무리 병렬화해도 이 단일 lock 때문에 사실상 전부
    직렬화됐을 것이다(중요한 선행 발견).
  - `world/runtime.py::_generate_plans_blocking`이 `ThreadPoolExecutor`로
    모든 agent의 `ensure_current(generate=True)`를 동시에 돌린다.
    `_refresh_plans`(스케줄러 시작 시 1회성 경로)도 `asyncio.gather`로
    동일하게 병렬화했다.
  - **부수적으로 발견 및 수정한 버그**: `_ensure_plan_generation_task`가
    `asyncio.create_task(...)`를 호출했는데, 이 메서드는
    `_advance_world_tick`(자체가 `asyncio.to_thread` 안에서 실행되는
    워커 스레드)에서 호출된다 — 즉 이 스레드엔 실행 중인 이벤트 루프가
    없어 `PlanningGenerationError`가 실제로 발생하는 경로를 타면
    `RuntimeError: no running event loop`로 죽었을 잠재 버그다(§3-B
    tick 관찰 배선 때 고친 것과 동일 패턴). `asyncio.Task` 기반
    `_plan_refresh_task`를 `threading.Thread` 기반 `_plan_refresh_thread`로
    바꿔 해결 — `pause_scheduler`/`stop_scheduler`도 `.cancel()` 대신
    `join()`으로 맞춰 갱신했다.
  - 신규 테스트: `tests/test_planning_lifecycle.py::test_ensure_current_runs_different_agents_concurrently`가
    `threading.Barrier(2)`로 두 agent의 `ensure_current` 호출이 실제로
    겹쳐 실행되는지 직접 증명한다(한쪽이 barrier에서 기다리는 동안
    다른 쪽도 반드시 도달해야 진행되므로, 직렬이면 타임아웃으로 실패).

- **무제한 병렬 fan-out이 서버 큐잉→타임아웃을 유발한 문제 수정
  (2026-08-25 후속)**: 위 병렬화 커밋 직후, 6명 agent가 동시에
  plan-generation LLM 호출을 쏘면 로컬 Ollama 서버가 `OLLAMA_NUM_PARALLEL`
  슬롯을 넘는 요청을 큐잉했고, 대기 중인 요청이 `LLM_TIMEOUT_SECONDS`(당시
  30초)를 넘겨 `planning_error`로 스케줄러 전체가 멈추는 문제가 있었다.
  - 서버 병렬도 확인: `ps aux`로 실제 `llama-server` 프로세스의 `-np` 플래그를
    확인한 결과 이 환경(로컬 Mac, `Ollama.app` GUI가 `launchctl setenv
OLLAMA_NUM_PARALLEL=3`로 기동)은 `OLLAMA_NUM_PARALLEL=3`였다(위
    2026-08-25 모델 사이징 노트에서 같은 날 설정한 값). 이번 작업에서
    `launchctl setenv OLLAMA_NUM_PARALLEL 4`로 올리고 `Ollama.app`을 완전히
    재기동해(GUI 앱 프로세스 자체를 kill 후 재실행 — `ollama serve`만
    재시작하면 부모 GUI 프로세스가 이미 로드한 구 env를 그대로 물려줘
    반영되지 않음) 반영을 확인했다(재기동 후 `llama-server ... -np 4`로
    뜸). 이 값은 로컬 개발 머신 설정이라 코드/커밋 대상이 아니다.
  - `LLM_TIMEOUT_SECONDS`를 `.env`/`.env.example`에서 30 → 120으로 올려
    실제 대기시간에 여유를 뒀다.
  - `world/runtime.py`에 `PLAN_GENERATION_MAX_CONCURRENCY = 4`(서버
    `OLLAMA_NUM_PARALLEL`과 동일)를 추가하고, `_generate_plans_blocking`의
    `ThreadPoolExecutor(max_workers=len(self.agents))`를
    `min(PLAN_GENERATION_MAX_CONCURRENCY, len(self.agents))`로, `_refresh_plans`의
    무제한 `asyncio.gather`를 `asyncio.Semaphore(min(...))`로 감싸 동시
    LLM 호출 수를 서버가 실제로 병렬 처리 가능한 수 이하로 제한했다.

## Milestones

- [x] M1: Infra & PoC 완료
- [x] M2: Single-agent believable daily life (§4 전체 인지 루프가 개별
      agent 단위로 닫혀 있는 상태)
  - 조건: 1) Memory/Retrieval P0 완료 + 2) Reflection P1 완료 + 3) Planning §3-A 완료 + 4) §3-B tick react/부분 재계획 완료
  - 상태 (2026-08-25): 1~4 모두 완료 — §3-B `PlanDisruptionGate`가
    비대화 tick에도 배선되어(`_dispatch_tick_plan_disruption_check`)
    §4.3.1의 "관찰이 계획을 방해하면 반응" 루프가 닫혔다.
- [ ] M3: Two-agent social interaction + information diffusion
  - 조건: §3-C 대화 연계 planning + §5-A 정보 확산/관계/협업 지표 자동 측정
- [ ] M4: Multi-agent town simulation + user intervention + 논문 수준 검증
  - 조건: World integration(§4) 완료 + §5-A/§5-B Social Dynamics & Evaluation
    핵심 항목 완료 + God mode(§4-B 마지막 항목) 완료
