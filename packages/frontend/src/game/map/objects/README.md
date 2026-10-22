# map/objects

맵의 `furniture`·`decor` 객체 레이어(이름 = 아틀라스 프레임, 사각형 = 프레임 크기)를 읽는 계약.

- 진입점: `index.ts` (`extractMapSprites`, `MapSprite`, 레이어 이름 상수)
- 생성: `scripts/maps/generate_town_map.py` → `packages/shared/maps/town.json`
- 의존: 없음. 그리기(`pixel-kit`)·주민(`residents`)·낮밤 장면이 이 계약만 보고 쓴다.
