# agents

논문 인지 루프의 계획·기억·성찰 (SPEC §3~§7). `llm` 아래층만 import하고 `minds`·`world`·`api`는 import하지 않는다.

- `llm_gateway.py`: `LlmGateway`(성찰 질문·통찰, 계획 completion 어댑터), `InsightWithCitation`
- `planning/`: 하루·시간·분 계획 프롬프트, 파싱, 재시도 그래프, 선택
- `memory/`: 기억 객체·스트림·관리자, 성찰 프롬프트(`reflection_prompts.py`)
- `reflection/`: 성찰 그래프
- `graph_support.py`: LangGraph 공용 헬퍼
