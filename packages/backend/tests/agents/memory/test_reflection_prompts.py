import datetime

import numpy as np
from agents.memory.memory_object import MemoryObject, NodeType
from agents.memory.reflection_prompts import build_salient_questions_prompt


def test_salient_prompt_uses_strict_json_contract_line() -> None:
    memory = MemoryObject(
        id=1,
        node_type=NodeType.OBSERVATION,
        citations=None,
        content="Met classmate at the cafe.",
        created_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        last_accessed_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        importance=4,
        embedding=np.asarray([0.1, 0.2], dtype=np.float32),
    )
    prompt = build_salient_questions_prompt(agent_name="Eddy Lin", memories=[memory])

    assert "Return strict JSON only with this exact shape and no extra text:" in prompt
    assert '"questions": [' in prompt
