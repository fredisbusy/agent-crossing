# Agent Crossing

**Generative Agents (Park et al., 2023)** 논문에서 영감을 받은 자율 소셜 시뮬레이션입니다.
**React 19 + Phaser 3**(프론트엔드), **FastAPI**(백엔드)로 구축했습니다.

## 상태

> 개발 진행 중. 핵심 아키텍처는 확정되었고, 인지 루프를 한창 구현하고 있습니다.

## 이 프로젝트의 목표

- NPC가 하루 일정을 계획하고, 경험을 기억하며, 예기치 않은 사건에 반응합니다.
- 에이전트의 사고, 계획, 회고, 기억, 대화는 모두 한국어로 생성·표시됩니다.
  영어만으로 이루어진 발화는 브로드캐스트 전에 거부됩니다.
- 기억은 recency/importance/relevance 점수로 조회됩니다.
- Reflection은 최근 경험으로부터 더 높은 수준의 통찰을 생성합니다.
- 여러 에이전트가 상호작용하고, 정보를 교환하며, 사회적 관계를 형성합니다.

## 기술 스택

- 프론트엔드: React 19, Phaser 3, Zustand, Vite
- 그리드 이동: Grid Engine 2.48.2(Phaser 3 호환, Apache-2.0)
- 백엔드: FastAPI, Pydantic, uvicorn, uv
- AI/메모리: 로컬 LLM(Apple Silicon의 MLX), PostgreSQL + pgvector, sentence-transformers
- 모노레포: pnpm workspace

## 프로젝트 구조

```text
packages/
  shared/      # 공유 타입/상수
  frontend/    # React + Phaser 클라이언트
  backend/     # FastAPI + 에이전트 브레인
```

## 시작하기

### 사전 준비물

- Node.js 20+
- pnpm 9+
- Python 3.11+
- uv

### 설치

```bash
pnpm install
uv sync --project packages/backend
```

### 실행 (개발 모드)

```bash
# 터미널 1
pnpm dev:backend

# 터미널 2
pnpm dev:frontend
```

### LLM 프로바이더 전환

백엔드 런타임은 LiteLLM을 프로바이더 어댑터로 사용합니다. `LLM_BACKEND`로 모델
백엔드를 전환할 수 있으며, 각 백엔드는 `settings.py`에 정의된 프로젝트 승인 모델
이름에 매핑됩니다.

```bash
# Fredly Ollama 게이트웨이
export LLM_BACKEND=ollama

# Google AI Studio
export LLM_BACKEND=google_ai_studio
export GOOGLE_AI_STUDIO_API_KEY=your_api_key
```

### PostgreSQL + pgvector (Docker)

```bash
docker compose up -d
pnpm db:migrate
```

빠른 확인:

```bash
docker compose exec postgres psql -U agent -d agent_crossing -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

결과에 `vector`가 포함되어 있으면 pgvector가 활성화된 것입니다.

SQLAlchemy(`packages/backend/src/db/models.py`)와 Alembic
(`packages/backend/alembic/`)이 PostgreSQL 스키마와 마이그레이션을 함께
소유합니다 — 모델이 스키마를 정의하고, Alembic 리비전이 그 변경을 추적합니다.
유용한 명령어:

```bash
pnpm db:status                      # 현재 적용된 리비전 확인
pnpm db:revision "설명"              # 모델 변경을 새 리비전으로 autogenerate
```

### 게임 세이브 슬롯

HUD는 RPG 스타일의 **새 게임**, **지금 저장**, **불러오기** 컨트롤을 제공합니다.
세이브에는 월드 시계, 위치와 경로, 페르소나 상태, 기억, 계획 캐시, 대화 상태,
조우 쿨다운, 공개 인지 로그가 포함됩니다. 동일한 동작을 다음 API로도 수행할 수
있습니다:

- `GET /sessions`
- `POST /sessions`
- `POST /sessions/current/save`
- `POST /sessions/{session_id}/load`

### 테스트

```bash
pnpm test:backend
# 또는
uv run --project packages/backend pytest -c packages/backend/pyproject.toml packages/backend/tests
```

## 로드맵

- 논문 기준 구현 체크리스트는 `TODO.md`를 참고하세요.
- 아키텍처 및 기술 스펙은 `SPEC.md`를 참고하세요.

## Briar Cove 월드 맵

첫 플레이 가능한 월드는 `packages/shared/assets/briar-cove.tmj`에 Tiled 호환
JSON 파일로 저장된 40×28 시맨틱 타운 맵입니다. 이 파일은 다음 항목들의 단일
소스입니다:

- 이름이 있는 위치와 계층형 `location_path` 값
- 백엔드 내비게이션이 사용하는 충돌 경계
- 인터랙션 가능한 오브젝트와 에이전트 어포던스
- 에이전트 스폰 지점과 시각적 경로

FastAPI 월드는 `GET /world/map`, `POST /world/observe`, `POST /world/path`를
통해 관측·내비게이션 판단을 소유합니다. Phaser는 타운을 렌더링하기 위해 같은
맵을 읽을 뿐, 이동 가능 여부를 직접 판단하지 않습니다.

### 실시간 이동 파이프라인

시작 시 백엔드는 각 페르소나의 현재 계획을 이름이 있는 맵 목적지로 변환하고,
충돌을 피하는 4방향 A* 경로를 찾은 뒤, 공간(spatial) 틱마다 에이전트를 한
타일씩 전진시킵니다. `ws://localhost:8001/ws/world`가 최신 권위 스냅샷을
브로드캐스트하면 Zustand가 이를 검증·저장하고, Phaser는 픽셀 에이전트를 해당
좌표로 애니메이션합니다.

Phaser는 타일 이동을 `NumberOfDirections.FOUR` 설정의 Grid Engine에 위임합니다.
일반적인 서버 업데이트는 정확히 한 칸의 수평/수직 이동만 애니메이션합니다.
클라이언트가 프레임을 놓친 뒤 재연결하면, 충돌 지형을 뚫는 로컬 경로를 임의로
만들지 않고 최신 권위 타일로 즉시 스냅합니다. 이후 버전의 Grid Engine은 Phaser 4를
대상으로 하기 때문에 버전은 `2.48.2`로 고정되어 있습니다.

유용한 엔드포인트:

- `GET /world/spatial/state`: 현재 revision, 경로, 위치를 확인
- `POST /world/spatial/step`: 디버깅용으로 결정론적 한 스텝 진행
- `WS /ws/world`: 실시간 공간 스냅샷 스트림 구독

공간 월드는 PostgreSQL/LLM 인지 런타임과 독립적으로 시작됩니다. LLM을 사용할
수 없어도 맵 이동과 WebSocket은 계속 사용할 수 있으며, 인지 관련 엔드포인트만
`503`을 반환합니다.

백엔드는 다른 로컬 서비스와 충돌하지 않도록 루프백 포트 `8001`을 사용합니다.
로컬 HTTP 개발 시 Vite가 자동으로 여기에 연결됩니다:

```bash
uv run --project packages/backend uvicorn api.main:app --app-dir packages/backend/src --port 8001
pnpm dev:frontend
```

HTTPS 배포 시에는 `/ws/world`를 `127.0.0.1:8001`로 프록시하세요. 프론트엔드는
동일한 공개 호스트에 자동으로 `wss://`를 사용합니다.

Briar Cove를 확장하려면 `packages/shared/assets/briar-cove.tmj`에 시맨틱
오브젝트를 추가하거나 옮기세요. 오브젝트 ID를 안정적으로 유지하고
`location_path`를 추가하면, 백엔드와 픽셀 렌더러가 별도의 맵 정의 없이 동일한
레이어를 공유해서 사용합니다.

주택은 실외 맵 위에 지붕 없는 Smallville 스타일 돌하우스 뷰로 표현됩니다.
침실, 주방, 공용 공간, 욕실 가구는 항상 보이며, 집에 도착한 에이전트는 현재
행동에 맞는 방으로 투영되어 읽을 수 있는 계획 말풍선과 함께 표시됩니다. 이
실내 투영은 관측용일 뿐이며, 에이전트의 정식(canonical) 타일과 경로는 여전히
백엔드가 소유합니다.

## 참고 자료

- 논문: [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)

## 라이선스

미정
