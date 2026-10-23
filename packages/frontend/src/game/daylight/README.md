# game/daylight

- 책임: `WorldSnapshot.sim_time`으로 낮·저녁·밤 표현(맵 MULTIPLY 틴트, 가로등 빛, 실내 불빛, 건물 정면 창불)을 결정한다. 장면 시간과 무관하게 결정론적이다.
- 진입점: `index.ts`(Phaser 없음: `daylightForSimTime`, `simHourOf`, `isNightHour`), `layer.ts`(Phaser: `DaylightLayer`).
- 구간: 새벽 5-7시 분홍, 낮 7-17시 효과 없음, 저녁 17-19시 노을, 밤 19-5시 남색. 상수는 `daylight-phase.ts`.
- 가로등 빛(`light_pool`, `lamp_post_lit`)은 픽셀 팩 아틀라스가 있을 때만 그린다(없으면 틴트·실내 불빛만).
- 정면 창불은 `map/facade`의 `facadeGlassRects`(창·문 유리 자리)에 ADD 사각형을 얹는다.
- 의존: `game/map`(`objects`, `pixel-kit`, `facade`, 장소 타입)만 import한다.
