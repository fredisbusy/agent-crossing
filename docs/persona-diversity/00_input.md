# Persona diversity input

## Status

Implemented on 2026-08-26.

## User request

> 논문과 이런 비슷한 게임(예를들면 동물의숲, 스타듀밸리) 캐릭터들의
> 페르소나를 찾아보고, 우리 캐릭터들을 좀더 개성있고 다양한 의사소통,
> 행동을 할수 있게 페르소나를 업데이트 해보자

Follow-up request on 2026-08-26:

> MBTI도 있으면 좋을거같지않아? 외향적인지 내향적인지 등등
> 그리고 좋아하는 이상형도 있으면 좋을 것 같아. 그럼 특정 인물에게
> 연애하고싶은 기분이 들수도있잖아

> 누군가가 내향적인 사람한테 안친한데 자꾸 말걸거나 하면 내적 호감이
> 떨어질수도 있겠지

## Background

- The live dashboard showed that Minji's reflections repeatedly collapsed her
  identity into work and interpersonal duties.
- The roster has six persona JSON files under `packages/backend/persona/`.
- Persona changes must remain compatible with the existing `PersonaLoader` and
  the Korean-only cognition policy.
- Actions and routines must use places that can be grounded in Briar Cove's
  existing public map: plaza, cafe, library, market, and park.

## Related project contracts

- `SPEC.md` sections 6-9: reflection, planning, world grounding, Korean output.
- `TODO.md` sections 2, 3, and 4: reflection, planning, and N-agent world loop.
- `AGENTS.md` sections 1, 3, 5, 6, and 8.
