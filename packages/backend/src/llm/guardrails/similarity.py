import re
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from llm.embedding_encoder import BatchEmbeddingEncoder, EmbeddingEncodingContext
from utils.math import cosine_similarity

SEMANTIC_HARD_BLOCK_THRESHOLD = 0.92
SEMANTIC_SOFT_PENALTY_THRESHOLD = 0.82


class EmbeddingEncoder(Protocol):
    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray: ...


def latest_partner_utterance(dialogue_history: list[tuple[str, str]]) -> str:
    for partner_talk, _ in reversed(dialogue_history):
        stripped = partner_talk.strip()
        if stripped and stripped != "none":
            return stripped
    return ""


def recent_dialogue_sentences(
    dialogue_history: list[tuple[str, str]],
    *,
    window: int,
) -> list[str]:
    if window < 1:
        return []

    ordered_sentences: list[str] = []
    for partner_talk, my_talk in dialogue_history:
        if partner_talk and partner_talk.strip() and partner_talk.strip() != "none":
            ordered_sentences.append(partner_talk.strip())
        if my_talk and my_talk.strip() and my_talk.strip() != "none":
            ordered_sentences.append(my_talk.strip())

    return ordered_sentences[-window:]


def recent_self_utterances(
    dialogue_history: list[tuple[str, str]],
    *,
    window: int,
) -> list[str]:
    if window < 1:
        return []

    self_utterances = [
        my_talk.strip()
        for _, my_talk in dialogue_history
        if my_talk and my_talk.strip() and my_talk.strip() != "none"
    ]
    return self_utterances[-window:]


def tokenize_for_ngram(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def sentence_ngrams(sentence: str, n: int) -> set[tuple[str, ...]]:
    tokens = tokenize_for_ngram(sentence)
    if not tokens:
        return set()

    if len(tokens) < n:
        n = 1

    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def overlap_ratio(candidate_sentence: str, reference_sentence: str, *, n: int) -> float:
    candidate_ngrams = sentence_ngrams(candidate_sentence, n)
    if not candidate_ngrams:
        return 0.0

    reference_ngrams = sentence_ngrams(reference_sentence, n)
    if not reference_ngrams:
        return 0.0

    overlap_count = len(candidate_ngrams.intersection(reference_ngrams))
    return overlap_count / len(candidate_ngrams)


def max_ngram_overlap(candidate_sentence: str, recent_sentences: list[str]) -> float:
    if not recent_sentences:
        return 0.0
    return max(
        overlap_ratio(candidate_sentence, recent_sentence, n=2)
        for recent_sentence in recent_sentences
    )


def exceeds_ngram_overlap_threshold(
    *,
    candidate_sentence: str,
    recent_sentences: list[str],
    n: int,
    threshold: float,
) -> bool:
    for recent_sentence in recent_sentences:
        if overlap_ratio(candidate_sentence, recent_sentence, n=n) > threshold:
            return True
    return False


def embed_sentences(
    *,
    sentences: list[str],
    embedding_encoder: EmbeddingEncoder | None,
) -> list[tuple[str, np.ndarray]]:
    if embedding_encoder is None:
        return []

    contexts = [EmbeddingEncodingContext(text=sentence) for sentence in sentences]
    if isinstance(embedding_encoder, BatchEmbeddingEncoder):
        embeddings = embedding_encoder.encode_many(contexts)
    else:
        embeddings = [embedding_encoder.encode(context) for context in contexts]
    return list(zip(sentences, embeddings))


@dataclass(frozen=True)
class SemanticOverlapCheck:
    max_similarity: float
    trigger: str


def semantic_overlap_check(
    *,
    candidate_sentence: str,
    reference_sentences: list[str],
    reference_embeddings: list[tuple[str, np.ndarray]],
    embedding_encoder: EmbeddingEncoder | None,
) -> SemanticOverlapCheck:
    if not candidate_sentence.strip() or not reference_sentences:
        return SemanticOverlapCheck(max_similarity=0.0, trigger="none")

    if embedding_encoder is None or not reference_embeddings:
        overlap = max_ngram_overlap(candidate_sentence, reference_sentences)
        if overlap >= SEMANTIC_HARD_BLOCK_THRESHOLD:
            return SemanticOverlapCheck(max_similarity=overlap, trigger="hard")
        if overlap >= SEMANTIC_SOFT_PENALTY_THRESHOLD:
            return SemanticOverlapCheck(max_similarity=overlap, trigger="soft")
        return SemanticOverlapCheck(max_similarity=overlap, trigger="none")

    candidate_embedding = embedding_encoder.encode(
        EmbeddingEncodingContext(text=candidate_sentence)
    )

    best_similarity = 0.0
    for _, reference_embedding in reference_embeddings:
        similarity = float(cosine_similarity(candidate_embedding, reference_embedding))
        if similarity > best_similarity:
            best_similarity = similarity

    if best_similarity >= SEMANTIC_HARD_BLOCK_THRESHOLD:
        return SemanticOverlapCheck(max_similarity=best_similarity, trigger="hard")
    if best_similarity >= SEMANTIC_SOFT_PENALTY_THRESHOLD:
        return SemanticOverlapCheck(max_similarity=best_similarity, trigger="soft")
    return SemanticOverlapCheck(max_similarity=best_similarity, trigger="none")
