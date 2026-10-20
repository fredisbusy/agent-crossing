# map/pixel-kit (시험)

stardewrogue 픽셀 에셋 팩을 마을 바닥에 얹어 보는 시험 기능. `?art=pixel-kit`일 때만 켜진다.

- 책임: Tiled `ground` 레이어의 풀·길·나무 칸을 팩 프레임으로 바꿔 그린다. 건물·물은 팩에 그림이 없어 기존 타일을 둔다.
- 진입점: `index.ts` (`planPixelKit` 순수 계획, `preloadPixelKit`·`drawPixelKit` Phaser 그리기).
- 에셋: `src/assets/pixel-kit/atlas.png`·`atlas.tp.json` (stardewrogue `public/assets`, 커밋 40f3c1e 복사본). 출처는 `src/assets/LICENSES.md`.
- 의존 방향: `map → pixel-kit`. 이 폴더는 `map`의 `TILE` 상수만 읽는다.
