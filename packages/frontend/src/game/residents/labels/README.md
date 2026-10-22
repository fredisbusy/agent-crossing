# residents/labels

주민 머리 위·발밑의 읽는 글자: 이름표(3-patch)와 말풍선(9-slice + 꼬리).

- 진입점: `index.ts` (`NameTag`, `SpeechBubble`)
- 좌표는 화면 px이다. 부모(`resident-view`)가 `scale = 1/카메라 줌`으로 감싸 줌과 상관없이 글자가 10px 이상으로 읽히게 한다.
- `nine-patch.ts`: 아틀라스 조각을 크기별 캔버스 한 장으로 구워 캐시한다(틀 두께 4px 등 규칙은 stardewrogue `ninepatch`).
- 의존: `game/map/pixel-kit`(아틀라스 키). 위 층이 이 폴더를 쓴다.
