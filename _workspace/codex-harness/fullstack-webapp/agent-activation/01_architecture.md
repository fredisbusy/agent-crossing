# 아키텍처

- PostgreSQL 전역 `agent_roster`가 활성 상태의 SSOT다.
- 세션은 전체 주민 상태를 보존하고 `enabled_agent_ids`만 실행 집합으로 사용한다.
- 활성 주민만 계획, 이동, 조우, 자동 인지, spatial snapshot에 참여한다.
- 토글은 기존 `session_lock`과 scheduler safe pause를 재사용한다.
- 현재 대화 runtime 제약에 맞춰 최소 2명을 활성 상태로 유지한다.
