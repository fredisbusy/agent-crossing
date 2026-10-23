# llm

LLM 호출의 범용 기반. 에이전트·마음·월드를 import하지 않는다(AGENTS.md §10-2, `tests/policy/test_layering.py`).

- 진입점: `__init__.py` (`LiteLlmClient`, `build_provider_client`, 임베딩 인코더, 중요도 채점기)
- `clients/`: provider 클라이언트와 응답 캐시
- `importance_prompts.py`: 중요도 채점 프롬프트(문자열만 받는다)
- `templates/`, `template_loader.py`: 프롬프트 템플릿(범용, agents·minds가 아래로 import)
- 계획·성찰 프롬프트와 파싱, `LlmGateway`는 `agents/`가 소유한다.
