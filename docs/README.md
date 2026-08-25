# 문서 작업 하네스

`docs/` 하위 문서는 **주제(topic)별 폴더 + 번호 접두 파일** 구조를 따른다.
전역 NestJS 워크플로우의 `00_input → 08_review` 관례를 이 프로젝트(FastAPI +
생성형 에이전트 시뮬레이션, 다중 주제가 병렬로 진행되는 구조)에 맞게 축소한 것이다.

## 왜 주제별 폴더인가

이 프로젝트는 API 서버 하나를 순서대로 만드는 파이프라인이 아니라, "아키텍처
분석", "LangGraph 마이그레이션", "Smallville 인테리어"처럼 독립적인 조사/설계
작업이 동시에 여러 개 진행된다. 루트나 `docs/` 바로 아래 흩어진 개별 파일은
어떤 게 최신인지, 무슨 흐름으로 만들어졌는지 추적하기 어렵다.

## 구조

```
docs/<topic-slug>/
├── 00_input.md         (필수) 요청/트리거 원문과 배경, 관련 TODO.md·SPEC.md 항목
├── 01_requirements.md  (선택) 이 작업 범위의 요구사항 체크리스트 (FR/NFR + 상태)
├── 02_design.md        (필수) 설계/분석 본문 — 결정, 근거(file:line), 트레이드오프
├── 03_changelog.md     (선택) 변경 이력 — 날짜, 커밋, 요약
├── 04_verification.md  (선택) 실제 코드 변경이 있었다면 AGENTS.md §6 검증 실행 로그
└── 05_review.md        (선택) 회고/리뷰 보고서
```

- `<topic-slug>`는 kebab-case (예: `architecture-analysis`, `langgraph-migration`,
  `smallville-interiors`).
- 01/03/04/05는 작업 성격에 따라 생략 가능하다. 순수 분석/조사 문서는 00 + 02만으로 충분하다.
- 상수·공식·계약이 바뀌면 `SPEC.md`, 진행 상태가 바뀌면 `TODO.md`를 같은 작업에서
  함께 갱신한다 (AGENTS.md §5, §8).
- 완료·폐기된 문서는 삭제하지 않고 `00_input.md`(또는 본문 상단)에 상태 배너를
  남긴다. 예: `docs/langgraph-migration/02_design.md` 상단의 "완료로 대체됨" 배너.
- 다른 주제 문서를 참조할 때는 새 경로(`docs/<topic-slug>/0N_*.md`)를 쓴다. 옛
  루트/평면 경로(`docs/ARCHITECTURE_ANALYSIS.md` 등)는 더 이상 유효하지 않다.

## 새 주제 시작할 때

1. `docs/<topic-slug>/00_input.md`에 요청 원문·배경·관련 TODO/SPEC 항목을 기록한다.
2. 구현 전 요구사항이 있으면 `01_requirements.md`에 체크리스트로 정리한다.
3. 설계/분석이 끝나면 `02_design.md`에 근거(file:line 포함)와 함께 기록한다.
4. 코드 변경이 있었다면 `04_verification.md`에 AGENTS.md §6 검증 실행 결과를 남긴다.

## 기존 주제 폴더

| 폴더 | 내용 |
| --- | --- |
| `architecture-analysis/` | `.claude/` 하네스 도메인 분할 기준 코드베이스 검증 분석 |
| `langgraph-migration/` | LangGraph 마이그레이션 스파이크 (완료, 기록용) |
| `smallville-interiors/` | Smallville 논문 Figure 2 기준 실내 렌더링 참조 |
