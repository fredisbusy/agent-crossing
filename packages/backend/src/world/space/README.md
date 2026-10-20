# world/space

마을 공간 질의 (SPEC §15). Tiled JSON(`packages/shared/maps/town.json`)을 읽어
`world.contracts.Space`를 구현한다.

- 진입점: `load_town_space()` -> `TownSpace`, `LocationTree.subtree()`(주민 개인 환경 트리)
- 파일: `tiled_loader`(지도 파싱) / `grid`(충돌) / `pathfinding`(4방향 A*) / `location_tree` / `town_space`
- 규칙: 결정론적(동점은 y, x 작은 쪽), 전역 상태 없음
- 의존 방향: `world.contracts`만 import. 맵은 `scripts/maps/generate_town_map.py`로 생성한다.
