## 인물

$persona

## 지금

- 시각: $now
- 장소: $place
- 하던 일: $activity

## 새로 본 것

$observations

## 떠오르는 기억

$memories

## 지시

$name은(는) 이 관찰에 반응해야 하는가? 그렇다면 어떤 반응이 적절한가?
하던 일을 이어 가도 충분하면 반응하지 않는다. 반응한다면 지금부터 할 행동 하나를 정하고, 장소는 아는 장소 이름으로 쓴다.

## 출력

JSON만 출력한다: {"react": <boolean>, "reason": "<짧은 이유>", "reaction": {"description": "<한국어 행동>", "location": "<장소 이름>", "minutes": <정수>}}
반응하지 않으면 reaction은 생략한다.
