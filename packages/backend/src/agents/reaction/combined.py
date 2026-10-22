from llm.clients.types import LlmGenerateOptions
from llm.governance.parsing import parse_reaction_combined, parse_reaction_intent

from .contracts import GenerateClient, ReactionIntent, ReactionUtterance


def generate_intent_step(
    *,
    client: GenerateClient,
    system_prompt: str,
    combined_prompt: str,
    intent_prompt: str,
    options: LlmGenerateOptions,
) -> tuple[ReactionIntent, ReactionUtterance | None, str]:
    """첫 시도: 의도+발화를 한 번에 받는다.

    결합 응답을 파싱하지 못하면 기존 의도 전용 호출로 폴백하고,
    폴백 사유를 세 번째 값(governance trace용)으로 돌려준다.
    """
    response = client.generate(
        prompt=combined_prompt,
        system=system_prompt,
        options=options,
        format_json=True,
    )
    combined = parse_reaction_combined(response)
    if combined.intent.trace.parse_success:
        return combined.intent, combined.utterance, ""

    fallback_response = client.generate(
        prompt=intent_prompt,
        system=system_prompt,
        options=options,
        format_json=True,
    )
    reason = combined.intent.trace.parse_error or "combined_parse_failure"
    return parse_reaction_intent(fallback_response), None, reason
