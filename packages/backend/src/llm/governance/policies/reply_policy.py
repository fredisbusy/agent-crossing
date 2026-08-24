import re
from dataclasses import dataclass
from typing import Literal

from llm.language_policy import contains_korean_text


_KO_DISALLOWED_SCRIPT_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]")
_META_LEAK_PATTERNS = (
    re.compile(r"生成回答|继续生成|决定生成|一如既往地"),
    re.compile(r"```"),
    re.compile(r"[：:]\s*\{"),
    re.compile(r"return\s+strict\s+json", re.IGNORECASE),
    re.compile(r"output\s*contract", re.IGNORECASE),
)


def fallback_reply(language: Literal["ko", "en"]) -> str:
    if language == "ko":
        return "LLM 응답 오류"
    return "LLM Error"


def normalize_reply_for_repeat_check(reply: str) -> str:
    normalized = " ".join(reply.lower().split())
    return normalized.strip(" .,!?:;\"'`()[]{}")


def is_repetitive_reply(reply: str, recent_replies: list[str]) -> bool:
    if not reply:
        return False

    normalized_reply = normalize_reply_for_repeat_check(reply)
    if not normalized_reply:
        return False

    normalized_recent_replies = {
        normalize_reply_for_repeat_check(recent_reply)
        for recent_reply in recent_replies
        if recent_reply.strip()
    }
    return normalized_reply in normalized_recent_replies


def recent_replies_for_echo_check(
    *,
    session_history: list[tuple[str, str]],
    window: int,
) -> list[str]:
    if window < 1:
        return []
    return [reply for _, reply in session_history[-window:]]


@dataclass(frozen=True)
class ReplyPolicyResult:
    reply: str
    suppress_reason: str
    fallback_reason: str


def _sanitize_reply(
    *,
    raw_reply: str,
    language: Literal["ko", "en"],
) -> tuple[str, str]:
    reply = " ".join(raw_reply.strip().split())
    if not reply:
        return "", ""

    for pattern in _META_LEAK_PATTERNS:
        if pattern.search(reply):
            return "", "invalid_reply_content"

    if language == "ko" and _KO_DISALLOWED_SCRIPT_RE.search(reply):
        return "", "language_policy_violation"
    if language == "ko" and not contains_korean_text(reply):
        return "", "language_policy_violation"

    return reply, ""


def apply_reply_policy(
    *,
    raw_reply: str,
    recent_replies: list[str],
    language: Literal["ko", "en"],
    suppress_repeated_replies: bool,
    fallback_on_empty_reply: bool,
) -> ReplyPolicyResult:
    reply, sanitize_reason = _sanitize_reply(raw_reply=raw_reply, language=language)
    suppress_reason = ""

    if sanitize_reason:
        suppress_reason = sanitize_reason
        reply = ""

    if suppress_repeated_replies and is_repetitive_reply(reply, recent_replies):
        suppress_reason = "repeat_echo_suppressed"
        reply = ""

    fallback_reason = ""
    if not reply and fallback_on_empty_reply:
        fallback_reason = "empty_reply_fallback"
        reply = fallback_reply(language)

    return ReplyPolicyResult(
        reply=reply,
        suppress_reason=suppress_reason,
        fallback_reason=fallback_reason,
    )
