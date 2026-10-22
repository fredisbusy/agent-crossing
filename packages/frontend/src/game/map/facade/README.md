# map/facade

건물 정면(3/4 시점 앞벽). 위에서 내려다본 단면 지도에 건물마다 다른 처마·벽 재질·창·문을 세워 마을처럼 보이게 한다.

- 책임: 맵 `facades` 객체(건물 이름, 앞벽 두 줄 사각형)를 받아 정면 그림을 코드로 그린다(에셋 팩에 정면 그림이 없다).
- 진입점: `index.ts` (`planFacades` 순수 계획, `paintFacade` 순수 그리기, `drawFacades` Phaser 얹기).
- 건물별 모양은 `facade-style.ts` 표(재질·지붕·덧문·차양). 새 건물은 표에 한 줄 더한다.
- depth는 정면 아래끝이라 길 위 주민은 앞, 건물 안 주민은 뒤에 그려진다. 간판 위치(`signCenterX`)는 `pixel-kit/signs.ts`가 쓴다.
- 의존 방향: `map → facade`, `pixel-kit → facade`. 이 폴더는 `objects`와 `town-layout`만 읽는다.
