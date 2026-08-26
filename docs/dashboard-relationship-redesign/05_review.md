# 기획 리뷰

## 계약 적합성

- **실제 runtime 사용**: 관계 근거는 기존 persona와 memory, 상대 상태는 spatial
  snapshot을 사용한다. mock metric을 제안하지 않았다.
- **비대칭 관점 유지**: 선택 주체의 private evidence만 사용하고 역방향 기억을
  합치지 않는다(`SPEC.md:412-414`).
- **관계 모델 승인 반영**: `measurement=modeled_v1`의 다섯 축과 최근 event delta를
  표시하되 memory importance를 점수로 바꾸지 않는다.
- **진단 경계 유지**: prompt, raw response, 내부 필터 원문을 공개 관계 payload에
  추가하지 않는다(`SPEC.md:407-411`).
- **소유 계층 유지**: 수치 state는 WorldRuntime 관계 서비스, 정성 근거는 dashboard
  read-model이 소유하며 Brain 결과와 `/ws/world` 계약을 확장하지 않는다.
- **기존 아키텍처 유지**: React/Vite/FastAPI 경계 안에서만 변경하도록 기획했다.

## 현재 구현과의 차이

| 영역        | 현재                                    | 기획안                                |
| ----------- | --------------------------------------- | ------------------------------------- |
| 요약 후보   | 이름이 포함된 첫 persona 또는 memory    | 관계·상호작용 의미를 통과한 근거      |
| 근거 수     | 반환 배열 길이, 최대 5                  | 전체 수와 잘림 여부 구분              |
| 위치        | destination을 현재 위치로 표시          | authoritative 현재 위치와 목적지 분리 |
| 레이아웃    | 2열 반복 카드와 인라인 details          | 대상 목록 + 선택 관계 상세            |
| 호감도 표시 | `호감도 · 정성 상태`                    | `정성 관계 기록`                      |
| 내부 용어   | TO/PERSONA/MEMORY/action code 노출 가능 | 한국어 presentation과 안전한 빈 상태  |
| 조회 범위   | 일반 기억 `memory_limit`에 종속         | 관계 전용 조회 범위와 정렬 정책       |
| 탭 역할     | 개요와 관계 탭에 전체 패널 중복         | 개요는 축약, 관계 탭은 전체 탐색      |

## 위험과 완화

- **과도한 필터로 실제 관계 기억이 사라질 수 있음**: persona, 대화, 도움, 갈등,
  약속 fixture를 양성 사례로 함께 고정한다.
- **현재 위치 계산이 프런트엔드에 중복될 수 있음**: backend world map을 단일
  기준으로 사용하고 프런트엔드는 경로를 재해석하지 않는다.
- **근거 중요도가 호감도로 오해될 수 있음**: 기본 관계 UI에서 숨기고 진단용일
  때만 `기억 중요도`로 명시한다.
- **관점 전환이 단순 대상 선택처럼 보일 수 있음**: 제목과 URL 상태를 함께 바꿔
  주체 변경을 명확히 한다.

## 리뷰 결론

기획안은 현재 SPEC/TODO의 방향성·비대칭성·진단 경계를 유지하면서, 화면에서
확인된 의미 오염과 정보 구조 문제를 해결할 수 있다. 구현에 들어갈 때는
`summary_status`, 근거 전체 수, `current_location_path`를 실제 계약 변경으로 확정한 뒤
`SPEC.md`와 `TODO.md`를 같은 변경에서 갱신해야 한다.

## 구현 검증 결과

- 관계·저장·API 타깃 테스트: 48 passed, 1 skipped
- 프런트 테스트: 20 passed, 빌드 통과
- Alembic: `0005 (head)`, autogenerate drift 없음
- 라이브 브라우저: 대상 5명, 지표 5개, 관점 전환 정상, 390px 가로 넘침 및 콘솔 오류 없음
- 전체 백엔드: 222 passed, 11 skipped, 관계 범위 밖의 기존 planning/settings 실패 5건
