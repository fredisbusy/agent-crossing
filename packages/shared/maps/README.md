# maps

마을 맵의 정본. 백엔드(`world/space`)와 프런트(vite `publicDir`)가 같은 `town.json`을 읽는다 (SPEC §15).

- 편집: [Tiled](https://www.mapeditor.org/) 1.10 이상으로 `town.json`을 열어 고치고 JSON으로 저장한다(타일 레이어 인코딩은 CSV).
- `ground`: `town-tiles.png`의 8종만 칠한다 — 1 풀, 2 길, 3 마루, 4 벽, 5 물, 6 가구 밑, 7 문, 8 나무. 그림은 게임이 자동타일로 바꿔 그린다.
- `locations`: 사각형 + 문자열 속성 `location_path`(`Smallville > 건물 > 방`). 방은 건물 사각형 안에 둔다. 주민 데이터가 쓰는 장소 이름은 지우지 않는다.
- `furniture`·`decor`: 객체 이름 = 아틀라스 프레임 이름, 크기는 `scripts/maps/town_furniture.py`의 `FRAME_CELLS`·`town_decor.py`의 `DECOR_FRAMES`. 막는 가구 밑은 ground를 6으로 칠한다.
- `facades`: 건물마다 앞벽(건물 사각형 아래 세 줄) 사각형 하나, 객체 이름 = 건물 이름. 프런트가 이 자리에 3/4 시점 정면을 그린다. 건물을 옮기면 같이 옮긴다(`check:map`이 어긋남을 잡는다).
- `collision`: 손대지 않는다. 저장 후 `python3 scripts/maps/check_town_map.py --fix-collision`.
- 검사: `pnpm check:map`. 통과해야 커밋한다.
- `generate_town_map.py`는 초기 맵 생성기다. 다시 돌리면 손 편집이 사라진다(`--force` 필요).
