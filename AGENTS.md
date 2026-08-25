# Agent Crossing Development Guide (for AI Agents) 🤖

이 문서는 **Sisyphus** 및 모든 하위 에이전트가 이 레포에서 작업할 때 따를 수 있는 운영 지침입니다.

## 0. 권한과 적용 범위

- 이 문서는 `/Users/yoon.homme/Projects/agent-crossing` 전체에 적용되는 우선 지침입니다.
- 다른 문서와 충돌할 경우 **SPEC.md**와 **TODO.md**가 우선입니다.
- `AGENTS.md`는 유지보수형 지침으로, 팀원/에이전트간 일관된 판단을 보장하기 위해 의사결정 기준을 명시합니다.

## 1. 핵심 원칙 (Core Principles)

1. **Brain-First**: UI/연출보다 생성형 에이전트의 인지 루프 정확도를 우선합니다.
2. **Strict Typing**: TypeScript와 Python type hint를 엄격히 적용해 런타임 불안정성을 줄입니다.
3. **No Slop**: 최소 수정 원칙, 의미적 일관성, 명확한 근거(문서/코드) 유지.
4. **Single Source of Truth**: 시스템 동작의 기준은 `SPEC.md`와 `TODO.md`의 정의를 따릅니다.

## 2. 모듈 경계 (Module Boundaries)

```
packages/
├── shared/              # 공통 타입, 상수, DTO, 메시지 스키마
├── frontend/            # React 19 + Phaser 3
│   ├── src/game/        # Phaser scene, 엔티티, 렌더링 로직
│   ├── src/components/  # React UI 컴포넌트 (DOM 조작 금지)
│   └── src/stores/      # Zustand 상태 저장소 (UI-게임 브릿지)
└── backend/             # FastAPI
    ├── src/api/         # HTTP/WebSocket 엔드포인트
    ├── src/agents/      # 에이전트 뇌, decision pipeline
    └── src/memory/      # Retrieval Scorer, memory stream, pgvector 인터페이스
```

- **금지**: Phaser에서 DOM 직접 접근(`document.querySelector` 등).
- 상태 공유 규칙: 게임 상태 변경은 가능하면 `frontend/src/stores/`를 통해 UI와 동기화합니다.

## 3. 실행 전 확인 (Mandatory Readiness Checks)

- 작업 시작 전 `TODO.md`의 해당 항목과 상태를 확인한다.
- 설계 변경이 클수록 `SPEC.md`의 대응 절을 선행 검토한다.
- 기존 의존성/설정의 영향 범위를 확인한다. (`package.json`, `pyproject.toml`, `pnpm-workspace.yaml`).

## 4. 코딩 규칙 (Coding Standards)

### TypeScript (frontend/shared)

- JSX는 `react-jsx` 사용(`import React` 불필요).
- `any`, `as any`, `@ts-ignore`는 금지.
- 함수 기반 컴포넌트는 `function` 문을 우선 사용.
- 공유 타입이 필요하면 `packages/shared`에서 먼저 정의 후 임포트.

### Python (backend)

- 의존성/스크립트는 `uv` 기반(`uv sync`, `uv run ...`).
- API 경계, DTO, 도메인 모델에 타입 힌트와 Pydantic validation 사용을 일관되게 유지.
- 내부 구현 전용이 아닌 클래스(예: API request/response schema, 공유 DTO)는 선언 파일에서 분리해 별도 모듈(예: `api/schemas.py`)로 관리한다.
- 비동기 처리(`async/await`)를 우선 적용하고, 차단형 I/O를 동기 루틴으로 남기지 않는다.
- 변경 시 가능하면 기존 함수 시그니처를 지키고, 예측 가능한 예외 경로를 명시한다.
- 클래스/필드 설명이 필요할 때는 `#` 주석 대신 `"""..."""` 형태를 사용하고, 기본적으로 **필드 선언 바로 위**에 배치한다.

## 5. Generative Agent Spec 준수 규칙

LLM 호출/행동 설계 시 프롬프트 컨텍스트는 다음을 모두 포함한다.

- **Persona**: 에이전트 이름, 성격, 핵심 가치.
- **Current Plan**: 현재 Minute Plan / short-term plan.
- **Retrieved Memories**: Retrieval Scorer로 선별된 관련 기억 목록.
- **Spatial Context**: 위치 트리(`Town > Building > Room`) 기반 레이블.

기본 로직 제약

- 단순 벡터 유사도 검색으로만 retrieval을 종료하지 않는다.
- retrieval/reflect/plan의 수식, 상수, 임계값, 계획 계층은 `SPEC.md`를 단일 기준으로 따른다.
- 위 상수/공식이 바뀌면 `SPEC.md`와 `TODO.md`를 같은 변경에서 함께 업데이트한다.

## 6. 검증 규칙 (Verification Rules)

- 작업 완료 후 다음을 최소 1회 실행한다.
  - Backend 변경: `pnpm test:backend` 또는 `uv run pytest`
  - 공유/Frontend/Backend 빌드: `pnpm -r build`
  - 특정 패키지 빌드:
    - `pnpm --filter @agent-crossing/shared build`
    - `pnpm --filter @agent-crossing/frontend build`
  - Python 단일 파일 실행/테스트 수정 시 `uv run pytest <path>`로 범위를 좁혀 검증.
- 포맷/정적 검사 실패 시 즉시 수정하고 재실행한다.
- 경량 변경이라도 `TODO.md`에서 항목 상태를 갱신한다.

## 7. 실수 방지 목록 (Anti-Patterns)

- TODO가 완료되었는데 체크를 하지 않거나 반대로 체크만 하고 구현 미완료.
- `Spec`과 다른 점수 공식/임계값 사용(예: recency만 쓰는 retrieval).
- `shared` 타입을 직접 중복 정의하거나 프런트/백엔드에서 서로 다른 이름의 DTO 사용.
- `TODO.md`/`SPEC.md`의 과업 흐름을 무시하고 즉시 구현.
- 빠른 임시 해결을 위해 `@ts-ignore`, 강한 타입 단절, 무차별 전역 상태 변경.

## 8. 작업 흐름 및 PR 규칙

- 조사/설계 문서가 필요한 작업(아키텍처 분석, 마이그레이션 스파이크, 논문 대비
  설계 검토 등)은 `docs/README.md`의 주제별 폴더 하네스(`docs/<topic-slug>/00_input.md` ~)를
  따른다.
- 각 작업은 작은 단위로 분해하고, 변경 범위를 명시한 후 진행한다.
- 의미 변경이 있으면 `SPEC.md`, `TODO.md`의 항목 번호를 언급한다.
- 커밋 메시지는 `<type>(<scope>): <subject>` 형식 유지.
- 작업 완료 시마다 관련 변경만 선별해 Conventional Commit 형식으로 커밋한다.
- 회귀를 줄이기 위해 파일 범위를 좁은 변경으로 반복 적용하고, 불필요한 리팩터링을 피한다.

## 9. Brain / Governance / Diagnostics 경계 규칙

논문 핵심 루프(Perceive/Retrieve/Reflect/Plan/React)와 운영 디버깅 정보를 섞지 않기 위해 아래 규칙을 따른다.

- `agents/agent_brain.py`의 `ActionLoopResult`에는 런타임 행동에 필요한 최소 필드만 유지한다. (예: `talk`, `utterance`, `speak_decision`, `action_intent`, `silent_reason`)
- LLM 반응 파싱/재시도/억제/fallback/threshold 관련 추적 정보는 `llm/governance` 또는 `llm/guardrails`가 소유한다.
- `raw_response`, `parse_error`, retry count, threshold, suppress/fallback reason 같은 필드는 도메인 상태가 아닌 **governance trace**로 취급한다.
- `model_thought`, `self_critique`, `decision_process`, `action_summary`처럼 관측성 중심의 표현/포맷팅은 Brain 내부에서 조립하지 말고 별도 diagnostics 모듈에서 생성한다.
- API/시뮬레이터 로그 출력 형식은 diagnostics 계층에서 결정하고, Brain은 해당 형식에 의존하지 않는다.
- 새 필드를 추가할 때는 먼저 분류한다: (1) 행동 결정에 필수인 도메인 필드인지, (2) 운영/디버깅 필드인지. (2)는 Brain 결과 객체에 직접 추가하지 않는다.
