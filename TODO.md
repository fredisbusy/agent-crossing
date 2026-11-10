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
- [x] 로컬 LLM + 벡터 DB PoC 통과 (MLX/Vector DB)
- [x] `P0` 메모리 영속 스토어 전환 확정 (PostgreSQL + pgvector)

## 1) Memory Stream & Retrieval (논문 핵심 1)

- [x] `P0` MemoryObject 스키마를 코드와 1:1로 맞춘다
  - Depends on: 없음
  - DoD:
    - [x] 기본 메모리 객체/스트림을 구현한다 (`packages/backend/src/memory/memory_object.py`, `packages/backend/src/memory/memory_stream.py`)
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

- [x] `P1` 임베딩 호출·relevance 계산을 최적화한다 (SPEC §5 공식은 그대로)
  - DoD:
    - [x] 같은 텍스트는 LRU 캐시로 재임베딩하지 않는다 (`EMBEDDING_CACHE_SIZE`, 주민 간 공유)
    - [x] 여러 문장은 `embed_many` 한 번의 요청으로 묶는다
    - [x] relevance를 기억마다 반복하지 않고 행렬 연산 한 번으로 계산한다
    - [x] 캐시·배치·LRU 축출 단위 테스트를 추가한다

- [x] `P1` 논문 루프 의미를 유지하며 틱 처리 속도를 올린다 (SPEC §4·§5 공식·임계값은 그대로)
  - DoD:
    - [x] 관찰 N개를 임베딩 1회·중요도 LLM 1회 배치로 저장한다 (깨진 배치는 건별 재채점, 추론 모델은 출력 상한에 여유)
    - [x] 마을 틱에서 주민별 관찰·행동 호출과 겹치지 않는 조우 쌍을 동시에 처리한다 (같은 시드 같은 결과)
    - [x] 2인 경로 관찰 기억을 메타데이터 없는 자연어 문장(ko/en)으로 저장한다
    - [x] reaction 첫 시도를 의도+발화 결합 1회 호출로 받고, 실패·빈 발화면 2단계로 폴백한다
    - [x] retrieve 점수를 증분 임베딩 행렬과 numpy 벡터 연산으로 계산한다 (참조 구현과 순서까지 동등)
    - [x] LLM·임베딩 동시 요청 상한 `LLM_MAX_CONCURRENCY`를 둔다
    - [x] 실제 모델로 배치 중요도 형식 준수를 확인한다 (결합 reaction은 옛 2인 스택과 함께 삭제) — 2026-11-09 실측: 배치 44회·단건 30회 모두 형식 준수(실패 0), 중앙값 4.4초

- [x] `P1` LLM 직렬 대기를 줄인다 (2026-10-23, SPEC §3·§6·§14)
  - DoD:
    - [x] 성찰: 질문 3개 검색(top_k 30)을 먼저 끝내고 질문별 통찰을 동시에 만들고, 통찰 저장을 임베딩·중요도 배치 1회로 한다
    - [x] 내가 한 말은 다음 기억 쓰기에 합쳐 배치 저장하고, 시작 기억도 배치 1회로 저장한다
    - [x] LLM 응답 기록·재생 캐시(`LLM_RESPONSE_CACHE`), 재시도 `LLM_NUM_RETRIES`(기본 1), litellm 지연 import
    - [x] 가짜 LLM(고정 지연) 밸런타인 36.5시간·LLM 주민 3명: 전체 대기 851 → 473 호출분, 성찰 1회 26.7 → 4.5, 대화 한 마디 응답 2.9 → 1.45
    - [x] 같은 측정에 계층 계획 분해(시간 40·분 80회)·반응 판정(61회)·요약(6회)을 더한 최종 main: 전체 대기 884 호출분(생성 호출 661회), 처음 851과 비슷한 비용으로 논문 기능을 채움
    - [x] 실제 모델로 지연과 동시 통찰 호출(스레드 안전)을 다시 잰다
      - 2026-11-09 실측 조건: 생성 `gpt-6-luna`(byfred), 임베딩 로컬 bge-m3(Gemini 크레딧 소진으로 대체), 밸런타인 첫 24시간, LLM 주민 2명(Isabella·Klaus)과 규칙 주민 6명
      - 결과: 실제 22분, 생성 202회(합계 1389초), 임베딩 124회·229문장, 오류 0, 동시 진행 최대 3
      - 성찰 2회: 질문 1회 뒤 통찰 3개를 서로 다른 스레드에서 동시에 만들었고(통찰 5.5~9.2초) 오류 없음
      - 호출 지연 중앙값: 반응 판정 5.0초, 발화·조우 4.2초, 시간 분해 4.9초, 분 분해 13.8초, 하루 계획·재계획 13.9초(최대 84.8초)
      - 하루 계획 JSON 형식 실패 2/12(뒤에 `</final` 같은 꼬리가 붙음), 재시도로 복구

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

> 2026-10-23: 아래 2-D와 4)의 옛 2인 대화 스택(AgentBrain·reaction graph·guardrails·engine/session/runtime·persona)은 마을 LLMMind로 대체되어 삭제했다. 기록으로만 남긴다.

- [x] `P1` reaction 생성을 2-call(판단/문장생성)로 분리한다
  - Depends on: Reflection Loop 핵심 완료
  - DoD:
    - [x] 1차 호출에서 `should_react` 판단과 근거 필드를 JSON으로 파싱한다
    - [x] 2차 호출에서 `utterance`를 생성하고 semantic/overlap guard를 적용한다
    - [x] 단위 테스트로 retry/parse-fallback 경로를 검증한다

- [x] `P1` Brain/Governance/Diagnostics 경계를 분리한다
  - Depends on: reaction 2-call 파이프라인 분리
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

- [x] `P1` 에이전트 요약 설명(논문 부록 A)을 하루 1회 만들어 계획·조우·대화 프롬프트에 싣는다 (SPEC §7)
  - DoD:
    - [x] 검색 3번 + LLM 1회, 그날 캐시, 실패 시 정체성 문장으로 대체
    - [x] 프롬프트에 NPC·agent·rule 단어를 넣지 않는다

- [x] `P1` hourly plan 생성기를 구현한다
  - Depends on: day plan 생성기 구현
  - DoD:
    - [x] active day plan 항목 입력을 기준으로 near-future hourly plan을 생성한다
    - [x] 현재 시점 기준 active day plan 항목을 선택한다
    - [x] hourly plan이 시간 순서로 정렬된다
    - [x] 마을 LLMMind가 하루 계획 항목당 1회 just-in-time으로 만들어 쓴다 (2026-10-23, SPEC §12)

- [x] `P1` minute plan(5~15분 단위) 생성기를 구현한다
  - Depends on: hourly plan 생성기 구현
  - DoD:
    - [x] minute plan 단위가 5~15분 범위를 만족한다
    - [x] active hourly plan 항목 입력을 기준으로 near-future minute plan을 생성한다
    - [x] 현재 시점 기준 active hourly plan 항목을 선택한다
    - [x] 현재 시점 기준 다음 실행 항목을 즉시 찾을 수 있다
    - [x] 마을 LLMMind가 지금의 분 단위 행동을 몸에 넘기고, 실패하면 시간 항목 끝까지 하루 구간으로 대체한다 (SPEC §12)
    - [x] 실제 모델로 하루당 분해 호출 수(추정 20~35회)와 행동 서술 품질을 잰다 — 2026-11-09: 시간 분해 18회·분 분해 24회로 주민당 평균 21회(재계획이 많은 Isabella 28, Klaus 14). 서술은 장소·행동이 구체적이고 자연스러움(예: "공통점과 차이점을 주제별 비교표로 정리하고 출처를 확인한다")

### 3-B. Tick react 판정과 부분 재계획

- [x] `P1` tick마다 이벤트-계획 충돌 판정기를 구현한다 (2026-10-23, SPEC §7)
  - Depends on: minute plan 생성기 구현
  - DoD:
    - [x] 관찰 이벤트가 현재 계획을 방해/우선하는지 판정한다(깨움마다 새 시야·사건 관찰이 있으면 LLM 1회, 잠·약속 중 생략)
    - [x] 판정 결과(reason/code)를 로그 가능 형태로 남긴다(`LLMMind.reaction_log`, 최근 20개)
    - [x] 실제 모델로 하루당 판정·반응 횟수와 반응 내용 품질을 잰다 — 2026-11-09: 판정 32회(Isabella 14, Klaus 18) 중 반응 7회(전부 Isabella의 손님 맞이·파티 안내). 거절 이유도 타당했지만 Isabella가 13~14시에 재계획을 6번 몰아서 함(아래 6-B 후속)

- [x] `P1` react 발생 시 이후 구간만 재수립한다
  - Depends on: tick 충돌 판정기 구현
  - DoD:
    - [x] 현재 시점 이전 계획은 보존한다
    - [x] 현재 시점 이후 계획만 재생성한다(반응 구간 + 반응 끝 이후 하루 계획 1회, 실패 시 겹침만 잘라 냄)

### 3-C. 대화 연계 planning

- [x] `P2` 조우 시 pass-by vs converse 결정을 구현한다 (2026-11-10, SPEC §12)
  - Depends on: react 발생 시 이후 구간만 재수립
  - DoD:
    - [x] 조우 이벤트 입력으로 행동 선택(pass-by/converse)을 반환한다(`Mind.on_encounter`: 공통 규칙 `rule_choice` 뒤 규칙 마음은 확률, LLM 마음은 LLM 판정)
    - [x] 결정 근거(관계/맥락)를 추적 가능하게 남긴다(두 마음의 `encounter_log`: 근거 종류·우호도·마지막 대화 시각·이유, 최근 20개)

- [x] `P2` 대화 결과를 plan 업데이트에 반영한다 (2026-11-10, SPEC §7 대화 연계 계획)
  - Depends on: pass-by vs converse 결정 구현
  - DoD:
    - [x] 대화에서 획득한 새 정보가 memory/plan에 반영된다(대화가 끝나면 LLM 1회로 메모는 관찰 기억, 계획 메모는 plan 기억과 24시간 동안의 계획 요청 배경으로)
    - [x] 관계 변화가 다음 계획 우선순위에 영향을 준다(우호도 10 이상인 상대 3명까지 계획 요청에 "가까운 사람"으로 싣는다)
    - [ ] 실제 LLM으로 대화 메모·계획 메모 품질과 다음 날 계획 반영을 확인한다
    - [ ] 마을 틱 수준 테스트: 연달은 대화·상대가 먼저 끝냄·엿들은 발화에서 대화 정리가 한 번씩만 도는지 확인한다(지금은 단위 테스트뿐)

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

- [x] `P1` simulation 대화 모드를 open/arc로 분리하고 plan diagnostics를 노출한다
  - Depends on: 짧은 대화 아크를 session/reaction 경계에 도입한다
  - DoD:
    - [x] `dialogue_mode="arc"`에서 기존 짧은 대화 아크 동작을 유지한다
    - [x] `dialogue_mode="open"`에서 `end_dialogue` 신호가 세션을 조기 종료하지 않는다
    - [x] Jiho/Sujin simulation world context를 Morning Dew Cafe로 고정한다
    - [x] `SimulationStepResult`/observability/API 응답에 plan diagnostics를 추가한다

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

- [x] `P1` WebSocket state broadcast를 구현한다
  - Depends on: world clock + tick scheduler 연동
  - DoD:
    - [x] `position`, `action`, `dialogue`, `emoji`를 브로드캐스트한다(`WS /ws/world`, 2026-10-23, SPEC §9)
    - [x] `current_plan`을 스냅샷에 싣는다(`current_plan_item`, 2026-11-10, SPEC §9)
    - [x] 누락 필드 없이 클라이언트에서 파싱 가능하다(프런트 파서 통과, 브라우저에서 연결 확인)

### 4-B. Frontend 시각화

- [ ] `P2` Tiled map + collision을 연결한다
  - Depends on: WebSocket state broadcast 구현
  - DoD:
    - [ ] 맵 충돌 레이어가 이동을 제한한다
    - [ ] agent 이동이 충돌 규칙을 위반하지 않는다

- [ ] `P2` 픽셀 아트 팩: stardewrogue 에셋을 마을 기본 화풍으로 쓴다 (아틀라스를 못 읽으면 코드 타일·원형 주민으로 대체)
  - DoD:
    - [x] 풀(가중치 변종)·흙길(자동타일)·나무/덤불을 팩 프레임으로 그린다. 건물·물은 기존 타일
    - [x] 계획에 쓰는 프레임이 모두 아틀라스에 있는지 테스트한다
    - [x] 팩에 없는 그림을 만든다: 물·건물 벽·실내 바닥·문·가구·작은 나무, 주민 5벌(stardewrogue `people`·`town`)
    - [x] 주민을 걷는 방향에 맞춘 서기·걷기 애니로 그린다
    - [x] 기본 화풍으로 켠다(2026-10-22, `?art=pixel-kit` 플래그 제거)
    - [ ] 공용 에셋 저장소로 분리한다(지금은 stardewrogue 아틀라스를 복사해 쓴다)
    - [x] 2차 에셋(2026-10-22): 장소별 바닥·벽·가구 세트·간판, 광장·공원 장식(분수·벤치·가로등·꽃밭·새), 주민 10벌과 앉기·일하기·말하기·자기 포즈, 픽셀 행동 아이콘, 말풍선·이름표 9-slice
    - [x] 맵에 `furniture`·`decor` 객체 레이어를 생성하고 프런트가 장소별 스타일로 그린다
    - [x] 시뮬레이션 시각에 따른 낮·저녁·밤 틴트와 가로등 빛
    - [x] 768px 미만에서 지도 전체 폭과 접이식 주민 시트
    - [ ] 날씨 표현(월드 상태에 날씨가 생기면 아틀라스 `rain`·`snow_fall`을 연결)
    - [x] 마을 배치 A안(2026-10-22): 큰길 + 옆골목 + 아랫골목, 건물별 크기·앞마당·뒷마당(울타리·텃밭·벌통·우편함), 모든 건물 남향
    - [x] 건물 정면(3/4 시점 앞벽 세 줄)을 코드로 그린다: 처마·벽 재질·창 종류·문·가게 차양, 간판은 정면에 건다 (`map/facade/`)
    - [x] 밤에 정면 창에 불을 켠다(낮밤 레이어와 연결)
    - [x] 데스크톱 첫 화면에 마을 전체를 담는다(빈 띠가 20% 이하면 담기 줌, 띠는 어두운 풀밭)

- [x] `P2` 프런트 렌더·번들 성능 (2026-10-23, SPEC §15)
  - DoD:
    - [x] 구운 바닥에 가려진 타일맵 레이어를 만들지 않는다(대체 경로는 유지)
    - [x] 주민 depth·줌 스케일·이름표 배치·행동 분류를 값이 바뀔 때만 다시 계산한다
    - [x] 보간 길이를 스냅샷 도착 간격 EMA로, WebSocket 주소를 설정 가능하게
    - [x] Header·Inspector 구독 범위를 좁힌다
    - [x] Phaser를 동적 import해 첫 화면 진입 청크를 gzip 464KB → 65KB로 줄이고, mock은 `?mock=1`일 때만 받는다

- [ ] `P2` 맵 정본을 Tiled 파일로 바꾸고 에디터로 고칠 수 있게 한다 (SPEC §15)
  - DoD:
    - [x] 편집용 의미 타일 PNG(`packages/shared/maps/town-tiles.png`)와 편집 안내(`maps/README.md`)
    - [x] Tiled에서 실제 그림이 보이게: 의미 타일을 픽셀 그림으로, 가구·장식을 그림 모음 타일셋의 타일 객체로(`export_tileset.py`, `pnpm fix:map`)
    - [x] `pnpm check:map`: 장소 트리·주민이 쓰는 장소·길에서의 도달성·객체 이름과 크기·collision 일치 검사, `--fix-collision`
    - [x] 생성기는 초기 맵 생성용으로 남기고 기존 맵을 `--force` 없이 덮어쓰지 않는다
    - [ ] Tiled에서 마을 배치를 다시 그린다(건물 크기·모양 다양화, 골목·마당)

- [ ] `P2` A\* pathfinding을 적용한다
  - Depends on: Tiled map + collision 연결
  - DoD:
    - [ ] 목표 좌표까지 유효 경로를 계산한다
    - [ ] 경로 불가능 시 fallback 동작을 처리한다

- [ ] `P2` agent inspector(memory/plan/reflection view)를 구현한다
  - Depends on: A\* pathfinding 적용
  - DoD:
    - [ ] 선택한 agent의 memory/plan/reflection을 탭 또는 패널로 조회한다
    - [ ] 최신 tick 데이터와 표시가 동기화된다

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

## 6) Hybrid Town (SPEC §12~§16)

### 6-A. 1차: 계약과 독립 모듈 (병렬)

- [x] `P0` 공유 계약을 확정한다 (`world/contracts.py`, `packages/shared`)
  - DoD:
    - [x] Mind 프로토콜, 화행, 관찰, 행동 의도, 몸 상태, 월드 스냅샷 타입이 정의된다
    - [x] 백엔드 Pydantic 모델과 shared TS 타입 이름이 같다
- [x] `P1` 공간: Tiled 맵 로더, 충돌 그리드, A*, 위치 경로 트리를 구현한다 (`world/space/`)
  - DoD:
    - [x] Smallville 구성을 본뜬 코드 생성 맵이 `packages/shared/maps/`에 있다
    - [x] 위치 경로 → 목표 타일 해소, 경로 불가 시 fallback이 테스트된다
- [x] `P1` ScheduleMind: 일정표·조건 분기·우호도·사실 저장소·화행 규칙·대사 템플릿 (`minds/schedule/`)
  - DoD:
    - [x] 초대를 수락하면 일정표에 항목이 생기고 그 시각에 그 장소로 가는 행동을 낸다
    - [x] 들은 사실을 다음 조우에서 확률적으로 전달한다(시드 고정 시 결정론)
- [x] `P1` 주민·몸·시계·마을 틱 루프 (`world/residents/`, `world/town/`)
  - DoD:
    - [x] 주민 설정에서 mind 종류와 에이전트 수를 지정한다
    - [x] 행동 중인 주민의 마음을 부르지 않고, 조우 시 pass-by/converse를 묻는다
    - [x] faithful 모드에서 같은 시드면 같은 결과가 나온다
- [x] `P2` 프런트: Phaser 4 이전, 공유 맵 렌더링, 스냅샷 보간, QA 훅
  - DoD:
    - [x] `window.render_game_to_text` / `window.advanceTime`이 개발 빌드에서 동작한다
- [x] `P2` 구조 정책 기준선 줄이기: `llm/` 큰 파일 분할, `tests/` 소스 구조 미러링
- [x] `P2` 남은 기준선: `agents/planning/graph.py` 분할 (brain·reaction graph·planning state는 옛 스택 삭제로 해소, graph.py는 재시도 헬퍼로 451 → 189줄, 기준선 0건, 2026-10-23)
- [x] `P2` 의존 방향 위반 제거: `llm`이 `agents`를 import하던 계획·성찰 프롬프트·파싱·`LlmGateway`를 agents로 올리고 `tests/policy/test_layering.py`로 고정

### 6-B. 2차: 통합

- [x] `P1` NPC 문체 다양화: 원형 공유 주민의 행동 서술·대사가 같지 않게, 영문 장소명 대신 자연스러운 이름 (SPEC §16 식별 지표)
  - DoD:
    - [x] 주민별 말투 8종·말버릇으로 같은 화행도 주민마다 다른 대사를 낸다 (SPEC §12)
    - [x] 장소를 한국어 이름표로 말하고 관찰·프롬프트도 같은 이름을 쓴다
    - [ ] 행동 서술(일정표 `description`)도 주민별로 다르게 다듬는다
- [x] `P2` 시나리오 씨앗: 주민 설정에 초기 사실(`FactStore`)을 넣어 전원 NPC 마을에서도 확산 시작
  - DoD:
    - [x] 주민 설정·시나리오 JSON의 `hosting`·`seed_facts`·`friendships`가 마음 종류와 무관하게 심어진다 (`world/scenarios/`)
- [x] `P1` 사회 상태 단일화: 약속·우호도·사실·화행 효과를 두 마음이 공유한다 (SPEC §12, `minds/social/`)
  - DoD:
    - [x] 규칙 마음과 LLM 마음이 같은 `SocialState`·`Agenda`를 쓰고, 개념별 별도 구현이 없다
    - [x] 주최자를 LLM 마음으로 바꿔도 같은 시나리오가 같은 규칙으로 돈다(테스트)
- [x] `P1` 밸런타인 부족분: 규칙 마음의 초대·소문 참석·동행 초대, 행사 종료 시각, 주최 준비, 마을 달력·기념일 인사·선물 화행 (SPEC §13, §14)

- [x] `P1` LLMMind 어댑터(기존 brain을 Mind 프로토콜로 감싸기, 발화 화행 구조화 출력)
  - DoD:
    - [x] 기억 스트림·검색·성찰·하루 계획 부품을 `minds/llm/`에서 `Mind` 프로토콜로 묶는다
    - [x] 가짜 클라이언트로 계획·대화·화행 파싱·약속을 테스트한다(LLM 호출 없음)
    - [x] 실제 LLM으로 마을 하루를 돌려 대화 품질을 확인한다(`live_*`) — 2026-11-09: 조우 판정 8회 중 대화 2회, 발화 22회. 주민 말투("후후")와 화행 구조화(greet·ask·invite)가 지켜지고, 첫날에 7명 모두 파티를 알게 됐고 4명이 참석을 약속함
- [x] `P1` 실제 공간 + 두 마음으로 마을 하루 돌리기(텍스트 로그) — 2026-11-09, 위 실측 조건으로 매시간 `text_state` 로그를 남김
- [x] `P1` 실측(2026-11-09)에서 나온 품질 문제를 고친다
  - DoD:
    - [x] 반응으로 바꾼 계획을 기억할 때 관찰 목록이 문장에 그대로 붙어 깨진다("…를 보고 … 인사한다.하기로 했다") → "<이름>은/는 <본 주민>을/를 보고 이렇게 하기로 했다: <행동>" 한 문장으로 남긴다 (2026-11-10, SPEC §7, `minds/llm/planning/reaction_notes.py`)
    - [x] 짧은 시간 안의 연속 재계획을 줄인다(Isabella 13:04~13:54에 재계획 6회) → 한 주민을 보고 반응하면 게임 시간 60분(`REACTION_COOLDOWN_MINUTES`) 동안 그 주민의 새 관찰은 판정하지 않는다 (2026-11-10, SPEC §7). 실제 LLM 재측정은 아직 하지 않았다
    - [x] 성찰 질문·통찰이 영어로 나온다. 다른 기억처럼 한국어로 맞춘다 → 성찰 프롬프트(머리말·지시·JSON 예시)를 한국어로 바꿨다 (2026-11-10, SPEC §6). 실제 LLM 출력은 아직 확인하지 않았다
    - [x] 이름 뒤 조사가 틀린다("Mei Lin가", "Eddy Lin가") → `josa`가 로마자 이름의 받침을 판정한다(l·m·n·ng, 모음 뒤 b·k·p) (2026-11-10)
    - [x] 이동 서술에 같은 장소가 두 번 나온다("홉스 카페 홀에서 홉스 카페 홀 쪽으로 이동한다") → "홉스 카페 홀 안에서 자리를 옮긴다" (2026-11-10)
    - [x] 규칙 마음이 사실을 전할 때 존댓말 뒤에 평서형 문장이 그대로 붙는다("연구 얘기 들으셨어요? … 조사하고 있다.") → 말투에 맞춰 "…조사하고 있대요." / "…있대."로 바꿔 전한다 (2026-11-10, `minds/schedule/lines.py` `relay`)
- [x] `P1` WebSocket 스냅샷·변경분 브로드캐스트, `/world/text`·`/world/advance`
  - DoD:
    - [x] API가 `TownRuntime`을 서비스한다: `/world/state`·`/world/text`·`/world/advance`·`/world/tick/start|stop`·`WS /ws/world` (2026-10-23, SPEC §9)
    - [x] CLI와 API가 `build_town` 하나로 마을을 조립한다
    - [x] 변경분(delta) 메시지 (2026-11-10, SPEC §9)
    - [ ] 프런트가 delta 하나를 파싱하지 못하면 재연결 전까지 낡은 상태가 남는다. 파싱 실패 시 전체 스냅샷을 다시 받게 한다
- [ ] `P2` 밸런타인 파티 시나리오: 전원 LLM 대 하이브리드 비교 리포트
  - DoD:
    - [x] 시나리오 실행기·지표(확산·약속·참석·마음 호출 수)와 CLI(`run_town_scenario.py`)
    - [x] 전원 규칙 마음 기준선이 결정론적으로 돈다
    - [ ] 실제 LLM으로 전원 LLM 대 하이브리드 비교 리포트를 남긴다

## Milestones

- [x] M1: Infra & PoC 완료
- [ ] M2: Single-agent believable daily life
  - 조건: 1) Memory/Retrieval P0 완료 + 2) Reflection P1 완료 + 3) Planning P1 완료
- [ ] M3: Two-agent social interaction + information diffusion
  - 조건: 대화 연계 planning + 정보 확산 실험
- [ ] M4: Multi-agent town simulation + user intervention
  - 조건: World integration + Social/Evaluation 핵심 항목 완료
