# LangGraph Migration Spike

> 상태(2026-10-23): 이 문서의 1순위 대상이던 reaction 파이프라인과 `agent_brain`은 옛 2인 대화 스택과 함께 삭제했다(마을 `LLMMind`로 대체). 계획(`agents/planning/graph.py`)도 LangGraph 상태 그래프 세 벌을 재시도 헬퍼 하나로 바꿨다. 지금 LangGraph를 쓰는 곳은 성찰(`agents/reflection/graph.py`)뿐이다. 아래는 당시 스파이크 기록이다.

## Goal

- Check which existing backend concepts can be reconstituted as LangGraph state, nodes, edges, or subgraphs.
- Keep world/runtime authority and custom memory scoring in the current backend.
- Make the first migration step small, reversible, and behavior-preserving.

## Branch

- `spike/langgraph-feasibility`

## Repo-specific LangGraph candidates

| Current module                                         | Proposed LangGraph construct | Priority | Notes                                                                                                                        |
| ------------------------------------------------------ | ---------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `packages/backend/src/llm/governance/pipeline.py`      | reaction subgraph            | P0       | Best first target. Already an explicit multi-step decision loop with retry branches.                                         |
| `packages/backend/src/llm/governance/contracts.py`     | graph state payloads         | P0       | Existing dataclasses already define stable reaction input/output boundaries.                                                 |
| `packages/backend/src/llm/guardrails/similarity.py`    | conditional edges            | P0       | Semantic retry and overlap retry map directly to graph routing.                                                              |
| `packages/backend/src/agents/reflection_workflow.py`   | reflection subgraph          | P1       | Good fit after the reaction spike; still needs backend-owned persistence and citation validation.                            |
| `packages/backend/src/agents/agent_brain.py`           | top-level agent graph        | P2       | Possible later, but too wide for a first migration step because it mixes memory writes, reflection, and action side effects. |
| `packages/backend/src/agents/planning/planner.py`      | planning subgraph entrypoint | P2       | Good future fit once planning is more complete and world-wired.                                                              |
| `packages/backend/src/world/runtime.py`                | keep custom                  | Keep     | Must remain authoritative runtime state.                                                                                     |
| `packages/backend/src/world/engine.py`                 | keep custom                  | Keep     | Owns turn stepping, final reply commit, and policy trace integration.                                                        |
| `packages/backend/src/world/session.py`                | keep custom                  | Keep     | Owns speaker rotation, queues, and dialogue history authority.                                                               |
| `packages/backend/src/agents/memory/memory_manager.py` | keep custom in phase 1       | Keep     | Domain memory scoring and persistence rules should not move in the first LangGraph step.                                     |

## Proposed migration order

1. **Reaction pipeline seam**
   - Introduce a LangGraph wrapper around the current reaction pipeline.
   - Preserve current output behavior.
   - Keep the existing `LlmGateway.decide_reaction()` interface unchanged.
2. **Reaction node split**
   - Break the legacy reaction callable into explicit LangGraph nodes: intent, utterance, semantic guard, overlap guard, finalize.
3. **Reflection subgraph**
   - Move question generation and insight generation orchestration into LangGraph.
   - Keep retrieval, persistence, citation validation, and importance counter reset in backend code.
4. **Optional AgentBrain composition**
   - Evaluate whether `AgentBrain.action_loop()` should become a higher-level graph after the inner subgraphs are proven.

## First implementation step

### Scope

- Add LangGraph as a backend dependency.
- Add a `reaction_graph` module that compiles a tiny `StateGraph` around the current reaction decision call.
- Route `ReactionPipeline.decide_reaction()` through that graph while preserving behavior.

### Why this first

- Smallest blast radius.
- Existing tests already cover reaction behavior.
- Gives concrete evidence that LangGraph can sit at a stable adapter seam before we split the logic into smaller nodes.

## Validation checklist

- Existing reaction unit tests still pass.
- New graph wrapper unit test passes.
- No changes to world/runtime/session behavior.
- No changes to memory scoring or persistence contracts.
