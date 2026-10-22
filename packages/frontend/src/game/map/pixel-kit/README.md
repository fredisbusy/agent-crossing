# map/pixel-kit

stardewrogue 픽셀 에셋 팩으로 마을을 그리는 기본 화풍. 아틀라스를 못 읽었을 때만(`hasPixelKit`이 거짓) 코드로 그린 타일(`tileset-art.ts`)과 원형 주민이 대체 화면이 된다.

- 책임: Tiled `ground` 레이어 8종(풀·길·마루·벽·물·가구·문·나무)을 팩 프레임으로 바꿔 그린다. 벽·물·길은 이웃 마스크 자동타일, 가구는 2칸씩 묶는다.
- 주민 스프라이트는 `game/residents/villager-figure.ts`가 같은 아틀라스로 그린다.
- 진입점: `index.ts` (`planPixelKit` 순수 계획, `preloadPixelKit`·`drawPixelKit`·`hasPixelKit` Phaser 그리기).
- 에셋: `src/assets/pixel-kit/atlas.png`·`atlas.tp.json` (stardewrogue `public/assets`, 커밋 42efc43 복사본. 그림 목록은 stardewrogue `docs/03_town_assets.md`). 출처는 `src/assets/LICENSES.md`.
- 의존 방향: `map → pixel-kit`. 이 폴더는 `map`의 `TILE` 상수만 읽는다.
- 장소별 스타일(place-style.ts, 계약 E절 표), 가구·장식 배치(object-plan.ts: 깔개·꽃·연꽃은 바닥에 굽고 나머지는 y-정렬), 간판(signs.ts·object-layer.ts, 건물 정면에 걸고 정면 밖으로 나가지 않게 맞춘다), 새·나비(critters.ts, 장면 시간 기반 결정론)가 같은 진입점으로 buildTownMap 안에서 그려진다.
