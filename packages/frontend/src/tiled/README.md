# tiled

Tiled(town.json) 읽기의 단일 창구와 지도 상수.

- 책임: 지도 상수(`TILE_SIZE`, `TILE` gid, 레이어·속성 이름), Tiled JSON 타입, `location_path` 사각형 파싱, 사각형 포함·가장 작은 영역 조회.
- 진입점: `index.ts`. 다른 기능은 이 진입점만 import한다.
- 의존 방향: 다른 기능을 import하지 않는다(맨 아래 층). `town-layout`, `game/map`이 이 폴더를 쓴다.
- 내장 대체 마을의 기하는 여기가 아니라 `town-layout`에 있다.
