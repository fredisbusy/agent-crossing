"""주민별 말투: 동물의 숲 성격 유형처럼 말투 유형 + 말버릇 (SPEC §12).

말투 정의(높임 여부·설명)는 두 마음이 함께 쓴다. 규칙 마음은 말투별 대사 템플릿을,
LLM 마음은 같은 설명을 프롬프트에 싣는다.
"""

import random
from dataclasses import dataclass
from typing import Literal

Voice = Literal[
    "warm", "bookish", "calm", "gruff", "bright", "cool", "sporty", "dreamy"
]
Tone = Literal["polite", "casual"]

VOICE_TONE: dict[Voice, Tone] = {
    "warm": "polite",
    "bookish": "polite",
    "calm": "polite",
    "gruff": "casual",
    "bright": "casual",
    "cool": "casual",
    "sporty": "casual",
    "dreamy": "casual",
}

VOICE_DESCRIPTION: dict[Voice, str] = {
    "warm": "다정하고 상냥한 존댓말. 상대를 챙기고 반가움을 숨기지 않는다.",
    "bookish": "차분하고 조리 있는 존댓말. 생각을 정리해 말하고 가끔 아는 것을 덧붙인다.",
    "calm": "점잖고 느긋한 존댓말. 말수가 적고 따뜻하게 맞장구친다.",
    "gruff": "툭툭 던지는 무뚝뚝한 반말. 투덜거리지만 속은 정이 많다.",
    "bright": "밝고 들뜬 반말. 감탄이 많고 말이 빠르다.",
    "cool": "무심하고 짧은 반말. 군더더기 없이 할 말만 한다.",
    "sporty": "힘찬 반말. 몸 움직이는 이야기를 좋아하고 기운을 북돋운다.",
    "dreamy": "느릿하고 몽글한 반말. 풍경과 느낌을 자주 이야기한다.",
}

CATCHPHRASE_PROBABILITY = 0.25
"""대사 끝에 말버릇을 붙일 확률."""


@dataclass(frozen=True)
class SpeechStyle:
    voice: Voice
    catchphrase: str | None = None
    """말끝에 가끔 붙이는 말버릇. 예: "헤헤"."""

    @property
    def tone(self) -> Tone:
        return VOICE_TONE[self.voice]

    def describe(self) -> str:
        """프롬프트용 한 줄 설명."""
        text = f"말투: {VOICE_DESCRIPTION[self.voice]}"
        if self.catchphrase:
            text += f" 말버릇 '{self.catchphrase}'를 가끔 말끝에 붙인다."
        return text

    def decorate(self, text: str, rng: random.Random) -> str:
        """말버릇을 확률로 말끝에 붙인다."""
        if not self.catchphrase or rng.random() >= CATCHPHRASE_PROBABILITY:
            return text
        return f"{text} {self.catchphrase}"
