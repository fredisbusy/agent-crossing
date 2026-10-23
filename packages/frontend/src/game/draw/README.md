# draw

코드로 그리는 그림이 함께 쓰는 작은 도구.

- 책임: 캔버스 2D 일부 타입 `Painter`와 사각형 채우기 `rect`, 문자열 해시 `stringHash`, 글꼴 `LABEL_FONT`.
- 진입점: `index.ts`.
- 의존 방향: 아무것도 import하지 않는다. `map`(tileset-art, facade, pixel-kit의 object-layer)과 `residents`가 쓴다.
