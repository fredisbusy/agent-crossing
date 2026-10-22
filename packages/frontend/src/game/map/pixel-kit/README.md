# map/pixel-kit (시험)

stardewrogue 픽셀 에셋 팩을 마을 바닥에 얹어 보는 시험 기능. `?art=pixel-kit`일 때만 켜진다.

- 책임: Tiled `ground` 레이어 8종(풀·길·마루·벽·물·가구·문·나무)을 팩 프레임으로 바꿔 그린다. 벽·물·길은 이웃 마스크 자동타일, 가구는 2칸씩 묶는다.
- 주민 스프라이트는 `game/residents/villager-figure.ts`가 같은 아틀라스로 그린다.
- 진입점: `index.ts` (`planPixelKit` 순수 계획, `preloadPixelKit`·`drawPixelKit` Phaser 그리기).
- 에셋: `src/assets/pixel-kit/atlas.png`·`atlas.tp.json` (stardewrogue `public/assets`, 커밋 c48b303 복사본. 그림 목록은 stardewrogue `docs/03_town_assets.md`). 출처는 `src/assets/LICENSES.md`.
- 의존 방향: `map → pixel-kit`. 이 폴더는 `map`의 `TILE` 상수만 읽는다.
