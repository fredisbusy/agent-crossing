# Persona diversity design

## Research synthesis

### Generative Agents paper

Park et al. describe an initial identity paragraph as a set of seed memories
covering occupation and relationships, not occupation alone (§3.1). Agent
summary descriptions combine identity, personality, motivational drivers,
occupation, and self-assessment (Appendix A). Plans then combine that summary
with recent experience (§4.3). The design implication is that diverse behavior
must begin with multiple durable motivational axes and relationship-specific
facts before memory and reflection can amplify them.

Source: `Generative Agents - Interactive Simulacra of Human Behavior.pdf`,
§3.1, §4.3, Appendix A.

### Animal Crossing

Animal Crossing separates broad personality from hobby. Hobbies alter visible
activities, conversations, home contents, and carried tools; New Horizons uses
education, fashion, fitness, music, nature, and play as distinct action axes.
Personality subtypes and friendship level add less-common dialogue on top of a
shared personality. The useful pattern is a layered identity:

1. broad temperament,
2. individual hobby and taste,
3. recognizable speech habit,
4. relationship-dependent disclosure.

Sources:

- https://nookipedia.com/wiki/Hobby
- https://nookipedia.com/wiki/Subtype

### Stardew Valley

Stardew Valley residents have schedules that vary by day, weather, season, and
relationship state. Their personalities are expressed through private hobbies,
friends, dislikes, conflicts, and personal arcs: Abigail alternates family
obligations with flute, games, friends, and adventure; Leah's art practice is
paired with independence, an unresolved past relationship, and a concrete
public goal. Friendship progression changes dialogue and unlocks events rather
than merely increasing generic friendliness.

Sources:

- https://stardewvalleywiki.com/Abigail
- https://stardewvalleywiki.com/Leah
- https://stardewvalleywiki.com/Friendship

## Project design rule

Each resident now has six behavioral anchors encoded through the existing JSON
fields:

1. occupation or social role,
2. non-work hobby,
3. communication signature,
4. preference or boundary,
5. personal goal,
6. unresolved tension or relationship-specific stance.

No schema field is added because the current prompts already consume
`identity_stable_set`, `lifestyle_and_routine`, `current_plan_context`, and
`seed_memories`. The most behaviorally important anchors are placed early in
each list because some prompt builders intentionally include only the first two
or three entries.

## Roster differentiation

| Resident | Hobby/action axis | Communication signature | Goal and tension |
| --- | --- | --- | --- |
| 하은 | 야구, 캐치볼, 맥주, 매달 새 취미 체험 | 먼저 말을 걸고 남자에게 적극적으로 플러팅하며 술자리에서 속마음을 더 솔직히 말함 | 주민 야구 모임을 만들고 싶지만 반응이 미지근하면 쉽게 삐짐 |
| 지호 | 헌책 수선, 새벽 새소리 기록 | 말을 고르고 책에 빗대며 캐묻지 않음 | 작은 독서 모임을 열고 싶지만 먼저 초대하기 어려움 |
| 수진 | 계절 음료 실험, 십자말풀이 | 구체적으로 제안하고 분명히 거절 | 주 1회 저녁 휴식을 지키려 하지만 책임감 때문에 미룸 |
| 민지 | 즉석사진, 개인 에세이 | 말이 빠르고 화제를 튕기며 선을 넘으면 사과 | 소식이 아닌 자기 글을 쓰고 싶지만 침묵을 불편해함 |
| 정우 | 나무 조각, 제철 수프 | 짧은 문장과 채소·날씨 비유, 말보다 행동 | 공원 벤치를 고치고 싶지만 도움받는 것을 어색해함 |
| 태오 | 손북, 즉흥 놀이 | 과장과 장난스러운 도전, 모르면 인정 | 마을 피크닉을 열고 싶지만 상대 신호를 자주 놓침 |

## Expected effect

- Day plans can select work, solitary leisure, errands, social play, creative
  work, or deliberate rest instead of treating every encounter as occupation.
- Dialogue has resident-specific pacing and disagreement styles.
- Reflections receive multiple durable topics, reducing the chance that one
  job-related insight becomes the sole recursive identity attractor.
- Relationship differences remain directional: kindness does not imply romance,
  and familiarity does not remove personal boundaries.

## MBTI and romantic-preference extension

MBTI is used only as compact character-authoring metadata. Each label is paired
with a Korean behavioral description in the prompt-visible first identity
statement; the four letters do not determine compatibility, attraction, or a
fixed action. This preserves variation within a type and avoids turning the
roster into a type-matching table.

| Resident | MBTI cue | Romantic preference and pace |
| --- | --- | --- |
| 하은 | ESTP: active social energy, immediate experimentation | confident men who join baseball or new activities; quick attraction and quick sulking |
| 지호 | INFJ: private meaning-making, deliberate preparation | reliable boundaries, quiet humor, gentle initiative; slow |
| 수진 | ESTJ: active coordination, concrete structure | independence, direct communication, mutual respect for work and rest; slow |
| 민지 | ENFP: social possibility-seeking, emotional spontaneity | an engaged listener with an independent passion and gentle grounding; quick spark, earned trust |
| 정우 | ISTP: solitary hands-on problem solving, adaptability | reliable practical care and comfortable silence; very slow |
| 태오 | ESFP: present-focused social play, responsive improvisation | playful participation with clear yes/no feedback; quick spark, slow commitment |

Romantic preference is stored as a durable natural-language identity anchor
with three parts: attractive behavior, behavior that creates distance, and
relationship pace. It does not assign a predetermined partner and is
gender-neutral by default; Haeun's explicit attraction to men is a deliberate
character-specific exception. Existing directional baselines such as Jiho's
private affection for Sujin remain separate facts.

Encounter and reaction prompts apply the following boundary rule:

- Introversion alone never lowers affinity and one ordinary approach is not a
  violation.
- At low familiarity, repeated unwanted approaches, ignored requests for quiet,
  or pressure after refusal are evidence for a colder reaction or pass-by.
- A resident's qualitative internal affinity may change through memories and
  reflections before any public relationship label changes.
- Numeric `romantic_interest` still changes only through the explicit romantic
  events defined in `SPEC.md` §8.1. MBTI and stated preferences never produce a
  numeric delta by themselves.
