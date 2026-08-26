## Task

You are grading one interview answer for believability, as part of a
generative-agent evaluation (§6.1 of "Generative Agents: Interactive
Simulacra of Human Behavior").

Question asked: $question
Answer given: $answer

Score the answer from 1 to 5:
- 5: specific, internally consistent with the statements above, and
  clearly grounded in this agent's own memory or identity.
- 3: plausible and in character, but generic or only loosely grounded.
- 1: incoherent, contradicts the statements above, or is not grounded in
  anything shown.

Give one short sentence of reasoning (at most $reasoning_max_chars
characters).

## Output Contract

Return strict JSON only with this exact shape and no extra text: $json_shape
