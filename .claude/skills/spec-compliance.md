---
name: spec-compliance
description: Verify that retrieval/reflect/plan formulas, constants, and thresholds used in code match SPEC.md before merging a change to the cognitive loop.
---

# Spec compliance check

Use when touching `packages/backend/src/agents/{memory,planning,reflection}/`
or any code implementing a scoring formula, threshold, or plan hierarchy.

## Steps

1. Read the relevant section of `SPEC.md` for the formula/constant in question.
2. Grep the implementation for the same constant/weight names.
3. Confirm they match exactly (weights, thresholds, decay rates, top-k values).
4. If retrieval only uses vector similarity with no recency/importance term,
   flag it — AGENTS.md explicitly forbids ending retrieval on similarity alone.
5. If a mismatch or a deliberate change is found, update `SPEC.md` and
   `TODO.md` in the same change (AGENTS.md §5: "위 상수/공식이 바뀌면 SPEC.md와
   TODO.md를 같은 변경에서 함께 업데이트한다").
