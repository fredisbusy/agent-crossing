# residents/pose

행동 문구·이모지 → 행동 종류(아이콘 이름) → 주민 포즈. Phaser를 모르는 순수 함수만 둔다.

- 진입점: `index.ts` (`classifyAction`, `choosePose`, `SpotMap`)
- `spots.ts`: 맵 가구·장식 객체(`game/map/objects`의 `MapSprite`)에서 의자·소파·벤치·침대 칸을 찾는다.
- 의존: `game/map/objects`(타입만), `town-layout`. 위 층(`resident-view`)이 이 폴더를 쓴다.
