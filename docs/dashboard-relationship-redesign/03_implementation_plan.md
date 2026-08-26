# 관계 수치 모델 구현 계획

## 결정

- 관계는 game session에 귀속되는 방향성 상태다. `하은 → 지호`와 `지호 → 하은`은
  서로 다른 상태와 revision을 가진다.
- `WorldRuntime.relationships`가 live owner이며 Brain 결과에는 점수나 분류 trace를
  추가하지 않는다.
- `RuntimeSaveState` schema v4 snapshot이 복원 기준이다. SQLAlchemy 관계 상태·event
  테이블은 조회 projection이며 save 때 snapshot에서 재생성한다.
- 실제 발화가 있는 대화 종료는 양쪽에 `DIALOGUE_COMPLETED`를 정확히 한 번 적용한다.
- 도움·약속·갈등 규칙은 준비하되 `current_action`/plan 문자열로 호출하지 않는다.
- `affinity`는 인간적 호감, `romantic_interest`는 이성적 관심으로 분리한다. 일반
  대화는 후자를 바꾸지 않고 persona baseline 또는 명시적 애정·경계 event만 바꾼다.

## 데이터 흐름

```mermaid
flowchart LR
  A[확정 대화 종료] --> B[RelationshipService]
  C[향후 committed action] --> B
  B --> D[방향성 state]
  B --> E[event ledger]
  D --> F[RuntimeSaveState v4]
  E --> F
  F --> G[SQLAlchemy projection]
  D --> H[/dashboard/state]
  E --> H
  I[persona + private memory filter] --> H
  H --> J[대상 목록 + 관계 상세 UI]
```

## 호환과 운영

- v3 snapshot은 새 필드 기본값으로 로드하고 다음 저장부터 v4로 기록한다.
- shared type, Pydantic DTO, frontend parser는 `modeled_v1`로 동시에 전환한다.
- event ledger는 세션당 10,000건 계약으로 두며 임의 trim하지 않는다. 장기 세션의
  checkpoint/compaction은 후속 과제다.
