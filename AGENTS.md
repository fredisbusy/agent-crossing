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
├── frontend/            # React 19 + Phaser 4
│   ├── src/game/        # Phaser scene, 엔티티, 렌더링 로직
│   ├── src/components/  # React UI 컴포넌트 (DOM 조작 금지)
│   ├── src/net/         # WebSocket 수신·틱 간격 추정 (DOM 접근은 여기까지)
│   ├── src/tiled/       # Tiled 맵 파싱·지도 상수
│   └── src/stores/      # Zustand 상태 저장소 (UI-게임 브릿지)
└── backend/             # FastAPI
    ├── src/api/         # HTTP/WebSocket 엔드포인트 (TownRuntime 서비스)
    ├── src/world/       # 마을 틱 루프·런타임, 공간, 주민(몸), 시나리오 조립, 공유 계약
    ├── src/minds/       # 마음: LLMMind(논문 인지 루프), ScheduleMind(규칙), 공유 사회 상태
    ├── src/agents/      # 인지 부품: memory stream·Retrieval Scorer, reflection, planning, LlmGateway
    └── src/llm/         # LLM 클라이언트(응답 캐시), 임베딩, 중요도 채점, 템플릿 로더
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
  - 구조 정책: `pnpm check:structure` (§10)
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

- 각 작업은 작은 단위로 분해하고, 변경 범위를 명시한 후 진행한다.
- 의미 변경이 있으면 `SPEC.md`, `TODO.md`의 항목 번호를 언급한다.
- 커밋 메시지는 `<type>(<scope>): <subject>` 형식 유지.
- 작업 완료 시마다 관련 변경만 선별해 Conventional Commit 형식으로 커밋한다.
- 회귀를 줄이기 위해 파일 범위를 좁은 변경으로 반복 적용하고, 불필요한 리팩터링을 피한다.

## 9. Mind / Governance / Diagnostics 경계 규칙

논문 핵심 루프(Perceive/Retrieve/Reflect/Plan/React)와 운영 디버깅 정보를 섞지 않기 위해 아래 규칙을 따른다.

- 마음이 몸·마을에 넘기는 결과(`ActionIntent`, `Utterance`, `EncounterChoice`, `world/contracts.py`)에는 행동에 필요한 필드만 둔다.
- LLM 응답 파싱·재시도·fallback 같은 처리와 그 추적 정보는 그 호출을 소유한 모듈이 가진다: 계획은 `agents/planning`(재시도 헬퍼·파싱), 성찰은 `agents/reflection`, 중요도는 `llm/importance_scorer`, 반응 판정은 `minds/llm/planning/reaction`.
- `raw_response`, `parse_error`, retry count, threshold, fallback reason 같은 필드는 도메인 상태가 아닌 **governance trace**로 취급한다.
- 판정 근거처럼 관측성 중심의 정보는 결과 객체에 싣지 말고 마음의 진단 버퍼(예: `LLMMind.reaction_log`)나 별도 diagnostics에 둔다.
- API·로그 출력 형식은 api/diagnostics 쪽이 정하고, 마음은 그 형식에 의존하지 않는다.
- 새 필드를 추가할 때는 먼저 분류한다: (1) 행동 결정에 필수인 도메인 필드인지, (2) 운영/디버깅 필드인지. (2)는 마음의 결과 객체에 직접 추가하지 않는다.

## 10. 코드 구조 정책 (Code Structure Policy)

목표: 사람과 에이전트가 파일 하나만 읽고도 맥락을 잡고, 병렬 작업이 서로 충돌하지 않는 코드베이스를 유지한다.

### 10-1. 크기 상한 (`pnpm check:structure`, `pnpm test:backend`가 강제)

| 대상 | 권장 | 상한 |
|---|---|---|
| 소스 파일(`.py`, `.ts`, `.tsx`) | 300줄 | 400줄 |
| 테스트 파일 | 300줄 | 500줄 |
| 한 폴더의 코드 파일 수(`__init__.py` 제외) | 7개 | 10개 |
| 함수·메서드 | 40줄 | 80줄(리뷰에서 확인) |

- 상한에 닿으면 기능을 더 넣기 전에 먼저 나눈다. 같은 커밋에서 "나누기"와 "기능 추가"를 섞지 않는다(나누는 커밋을 먼저).
- 기존 위반은 `scripts/structure_baseline.json`에 기록돼 있고, **지금보다 커지면 실패한다(래칫)**. 위반을 줄였으면 `python3 scripts/check_structure.py --update-baseline`으로 기준선을 줄인다. 기준선에 새 항목을 손으로 추가하지 않는다.

### 10-2. 폴더는 기능(도메인) 단위로

- 기술 계층(`utils/`, `helpers/`, `models/`)으로 모으지 않고 기능으로 묶는다. 예: `world/space/`, `world/residents/`, `minds/schedule/`.
- 폴더마다 공개 진입점을 둔다(Python `__init__.py`의 `__all__`, TS `index.ts`). 다른 기능은 진입점만 import하고 내부 파일을 직접 import하지 않는다.
- 기능 폴더 안 기본 배치: `contracts.py`(Protocol·DTO·스키마) → 구현 파일들 → `README.md`(10줄 안팎: 책임, 진입점, 의존 방향). 새 기능 폴더를 만들면 README도 같이 만든다.
- 의존 방향은 한쪽으로만: `api → world → minds/agents → memory·llm`. 아래 층이 위 층을 import하지 않는다. 순환이 필요해 보이면 `contracts`로 인터페이스를 내린다. `tests/policy/test_layering.py`가 AST로 강제한다(`llm`→`agents`·`minds`·`world`·`api`, `agents`→`minds`·`world`·`api`, `minds`·`world`→`api` 금지, 문자열 동적 import 포함).

### 10-3. 테스트 배치

- 테스트는 소스 구조를 그대로 따른다: `src/world/space/pathfinding.py` → `tests/world/space/test_pathfinding.py`.
- `tests/` 최상위에는 새 파일을 추가하지 않는다(기준선 위반 폴더).
- 테스트는 LLM·네트워크 없이 돈다. LLM이 필요한 경로는 가짜 클라이언트 또는 응답 캐시로 대체하고, 실제 호출 테스트는 마커(`live_*`)로 분리한다.

### 10-4. 에이전트가 작업하기 좋은 코드

- 계약 먼저: 여러 작업이 만나는 경계(몸·마음, 화행, 월드 상태 DTO)는 구현 전에 `contracts`/`packages/shared`에 타입을 확정하고, 병렬 작업은 그 계약만 보고 진행한다.
- 이름은 검색되게: 같은 개념에 같은 단어를 쓴다(주민 `resident`, 마음 `mind`, 몸 `body`, 화행 `speech_act`). 약어·동의어를 섞지 않는다.
- 전역 상태·싱글톤을 만들지 않는다. 시계·난수·LLM 클라이언트는 주입한다(재현 가능한 시뮬레이션의 전제).
- 시뮬레이션 로직은 결정론적으로: 같은 시드 + 같은 LLM 응답 캐시 → 같은 결과.
- 매직 넘버는 이름 붙은 상수나 설정으로 두고, SPEC에 있는 값이면 SPEC 절 번호를 주석으로 단다.
