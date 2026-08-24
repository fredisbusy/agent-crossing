# Smallville Interior Reference

## Source

- Joon Sung Park et al., *Generative Agents: Interactive Simulacra of Human
  Behavior*, UIST 2023, Figure 2:
  <https://arxiv.org/abs/2304.03442>
- Reference implementation:
  <https://github.com/joonspk-research/generative_agents>

## What the paper shows

Smallville uses an always-visible, roofless dollhouse view instead of hiding
building interiors behind a separate screen. Figure 2 labels a family house
with these semantic areas:

- bathroom
- kitchen
- common room
- bedrooms
- garden

The common room is further grounded in objects such as a bookshelf and table.
The paper states that every primary living space includes a bed, desk, closet,
shelf, bathroom, and kitchen.

This is not only a visual choice. The environment is represented as a
containment tree (`Town > Building > Room > Object`), and an agent's natural
language action is resolved to a leaf object before normal game pathfinding
moves the avatar there.

## Agent Crossing adaptation

Homes on the outdoor map should therefore:

1. render without an opaque roof;
2. expose bedroom, common room, kitchen, and bathroom boundaries at all times;
3. include recognizable bed, desk, shelf, table, kitchen counter, and bathroom
   fixtures;
4. place an agent in the room that best matches its current plan/action;
5. show the current action above the indoor avatar;
6. derive the layout from a reusable home template so new houses do not require
   one-off scene code.

The backend remains authoritative for whether an agent is at a home. The
frontend only projects that state into an indoor observation position; it must
not invent navigation or change the agent's canonical tile.
