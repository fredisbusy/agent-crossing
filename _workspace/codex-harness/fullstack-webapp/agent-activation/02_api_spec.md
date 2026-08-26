# API 명세

`PATCH /agents/{agent_id}/activation`, 요청 `{ "enabled": boolean }`, 응답
`{ "agent_id": string, "name": string, "enabled": boolean }`.

- 404: persona roster에 없는 주민
- 409: 활성 주민이 2명 미만이 되는 요청
- `GET /dashboard/state`는 전체 `agent_activations`와 활성 runtime `agents`를 분리한다.
