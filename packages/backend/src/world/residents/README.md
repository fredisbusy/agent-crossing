# world/residents

주민 = 설정 + 몸 + 마음 + 대기 관찰 큐 (SPEC §12).

- 책임: 주민 설정 로드·마음 승격 규칙(`config.py`), 경로 이동·행동 만료(`body.py`), 주민 조립(`resident.py`).
- 진입점: `ResidentConfig`, `load_resident_configs`, `apply_mind_selection`, `Body`, `Resident`, `MindFactory`.
- 데이터: `packages/backend/residents/*.json` (원형은 `residents/archetypes/`, 로더가 제외).
- 의존: `world.contracts`의 `Space`·`Mind`만 쓴다. 마음·공간 구현은 import하지 않는다.
- 마음 종류는 `ResidentConfig.mind`에만 있고 `ResidentPublicView`에는 담기지 않는다.
- 이동 불가 시 제자리 idle로 바꾸고 관찰 "…로 갈 수 없었다"를 남긴다.
