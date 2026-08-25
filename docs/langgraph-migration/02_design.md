# LangGraph 마이그레이션 스파이크

> **상태 (2026-08-25): 완료로 대체됨 — 이 스파이크가 제안한 마이그레이션은 끝났다.**
> reaction, reflection, planning(day/hourly/minute), 그리고 최상위 brain 루프
> 모두 LangGraph `StateGraph` 러너로 구현되었다: `agents/reaction/graph.py`,
> `agents/reflection/graph.py`, `agents/planning/graph.py`,
> `agents/brain/graph.py`(`AgentBrainGraphRunner`). 아래에 나오는 파일 경로와
> 모듈명은 마이그레이션 이전 코드베이스 기준이라 더 이상 존재하지 않는다 —
> 현재 지침이 아니라 원래 계획의 기록으로만 남겨둔다. 현재 아키텍처는
> `docs/architecture-analysis/02_design.md` §1을 참고할 것.

## 목표

- 기존 백엔드 개념 중 어떤 것을 LangGraph의 state, node, edge, subgraph로
  재구성할 수 있는지 확인한다.
- world/runtime의 권위와 커스텀 메모리 스코어링은 현재 백엔드에 그대로 둔다.
- 첫 마이그레이션 단계는 작고, 되돌릴 수 있고, 동작을 그대로 보존하도록 만든다.

## 브랜치

- `spike/langgraph-feasibility`

## 레포 특화 LangGraph 후보 (원안 — 경로는 현재 stale함)

| 원래 모듈 (마이그레이션 이전) | 제안된 LangGraph 구성 | 우선순위 | 결과 |
| --- | --- | --- | --- |
| `packages/backend/src/llm/governance/pipeline.py` | reaction subgraph | P0 | 완료 — `agents/reaction/graph.py`가 됨. |
| `packages/backend/src/llm/governance/contracts.py` | graph state payloads | P0 | 완료 — `agents/reaction/contracts.py`(`ReactionDecisionTrace` 등)가 됨. |
| `packages/backend/src/llm/guardrails/similarity.py` | conditional edges | P0 | 완료 — semantic/overlap 재시도 라우팅이 `agents/reaction/graph.py`의 조건부 엣지로 구현됨. |
| `packages/backend/src/agents/reflection_workflow.py` | reflection subgraph | P1 | 완료 — `agents/reflection/graph.py`(`ReflectionGraphRunner`)가 됨. |
| `packages/backend/src/agents/agent_brain.py` | top-level agent graph | P2 | 완료 — `agent_brain.py`는 이제 `agents/brain/graph.py`의 `AgentBrainGraphRunner`를 감싸는 얇은 facade. |
| `packages/backend/src/agents/planning/planner.py` | planning subgraph entrypoint | P2 | 완료 — `Planner`가 `agents/planning/graph.py`의 `PlanningGraphRunner`(day/hourly/minute, 각각 parse-retry subgraph 보유)를 감쌈. |
| `packages/backend/src/world/runtime.py` | 커스텀 유지 | Keep | 계획대로 여전히 커스텀 — 런타임 상태의 권위자 역할 유지. |
| `packages/backend/src/world/engine.py` | 커스텀 유지 | Keep | 계획대로 여전히 커스텀. |
| `packages/backend/src/world/session.py` | 커스텀 유지 | Keep | 계획대로 여전히 커스텀. |
| `packages/backend/src/agents/memory/memory_manager.py` | 1단계에서는 커스텀 유지 | Keep | 여전히 커스텀 — 메모리 스코어링(`memory_stream.py`)은 그래프가 아닌 순수 Python으로 남아 있음. |

## 제안된 마이그레이션 순서 (실제 진행됨)

1. **Reaction 파이프라인 접합부** — 완료(`agents/reaction/graph.py`).
2. **Reaction 노드 분리**(intent / utterance / semantic guard / overlap guard /
   finalize) — 완료, `agents/reaction/graph.py`에 명시적 노드로 나타남.
3. **Reflection subgraph** — 완료(`agents/reflection/graph.py`); retrieval,
   저장, citation 검증, importance 카운터 리셋은 계획대로 백엔드 코드에 남음.
4. **최상위 brain 구성** — 완료(`agents/brain/graph.py`의
   `AgentBrainGraphRunner`), 이 스파이크가 애초에 "선택적"이라고 범위를 잡았던
   것보다 더 나아간 결과.

## 후속 조치

마이그레이션은 기술적으로 성공했지만, 이 스파이크가 예상하지 못했던 경계
위반을 하나 드러냈다: `AgentBrainGraphRunner`의 출력 타입(`ActionLoopResult`)이
이제 reaction 그래프의 trace/diagnostics 객체를 그대로 갖고 있다(자세한 내용은
`docs/architecture-analysis/02_design.md` §1.3과 `TODO.md` §2-D 참고). 이 정리 작업은
여기가 아니라 `TODO.md`에서 추적한다.
