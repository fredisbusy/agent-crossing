"""LLM 주민의 마음을 만든다: 기억·검색·성찰·계획 부품을 묶어 `LLMMind`로 (SPEC §12)."""

from agents.memory.memory_manager import MemoryManager
from agents.memory.memory_stream import MemoryStream
from agents.planning import Planner
from agents.reflection import Reflection, ReflectionGraphRunner
from llm.clients.provider_factory import ProviderClient
from llm.embedding_encoder import LlmEmbeddingEncoder
from llm.importance_scorer import LlmImportanceScorer
from llm.llm_gateway import LlmGateway
from minds.llm import LLMMind, LlmPersona, ManagedMemory
from world.contracts import LocationPath

from .config import ResidentConfig


def llm_persona(
    config: ResidentConfig, known_places: tuple[LocationPath, ...]
) -> LlmPersona:
    return LlmPersona(
        resident_id=config.resident_id,
        display_name=config.display_name,
        age=config.age,
        identity=tuple(config.description),
        home=config.home_location,
        known_places=known_places,
        seed_memories=tuple(config.seed_memories),
    )


class LLMMindFactory:
    """`ResidentMindFactory(llm_factory=...)`에 넣는다. 시작 상태는 그쪽이 심는다."""

    def __init__(
        self,
        *,
        client: ProviderClient,
        embedding_model: str,
        known_places: tuple[LocationPath, ...],
    ) -> None:
        self._client = client
        self._known_places = known_places
        self._encoder = LlmEmbeddingEncoder(client=client, model=embedding_model)
        """주민끼리 공유해 같은 관찰·대사를 한 번만 임베딩한다."""

    def build(self, config: ResidentConfig) -> LLMMind:
        identity = list(config.description)
        encoder = self._encoder
        manager = MemoryManager(
            memory_stream=MemoryStream(),
            importance_scorer=LlmImportanceScorer(client=self._client),
            embedding_encoder=encoder,
        )
        gateway = LlmGateway(self._client, embedding_encoder=encoder)
        reflection = ReflectionGraphRunner(
            reflection=Reflection(),
            memory_manager=manager,
            llm_gateway=gateway,
            agent_name=config.display_name,
            identity_stable_set=identity,
        )
        return LLMMind(
            persona=llm_persona(config, self._known_places),
            client=self._client,
            planner=Planner(gateway),
            memory=ManagedMemory(
                manager, agent_name=config.display_name, identity=identity
            ),
            reflection=reflection,
        )
