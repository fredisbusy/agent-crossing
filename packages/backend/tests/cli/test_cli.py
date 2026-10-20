"""
AgentBrain CLI 통합 테스트

Run with: uv run pytest tests/test_cli.py -v -s
"""

import pytest


@pytest.mark.skip(reason="AgentBrain 미구현 - 구현 후 활성화")
class TestAgentBrain:
    """AgentBrain 기본 동작 테스트"""

    def test_perceive(self, agents):
        jiho, _ = agents
        jiho.perceive("오늘 아침 도서관 창밖으로 수진이 카페 문을 여는 것을 보았다.")

    def test_converse(self, agents):
        _, sujin = agents
        msg = "안녕하세요 수진님! 오늘도 일찍 시작하시네요."
        response = sujin.converse("지호", msg)
        assert isinstance(response, str)
        assert len(response) > 0

    def test_conversation_exchange(self, agents):
        jiho, sujin = agents
        msg1 = "안녕하세요 수진님! 오늘도 일찍 시작하시네요."
        resp1 = sujin.converse("지호", msg1)

        msg2 = "네, 도서관도 곧 열 시간이네요. 오늘 그 책 다 읽으셨어요?"
        resp2 = jiho.converse("수진", msg2)

        assert isinstance(resp1, str)
        assert isinstance(resp2, str)
