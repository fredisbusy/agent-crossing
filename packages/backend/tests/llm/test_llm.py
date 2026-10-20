"""
LLM 추론 속도 및 한국어 품질 테스트
Day 1-2: Qwen 2.5-3B 검증

Run with: uv run pytest tests/test_llm.py -v -s
"""

import time

import pytest
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
TARGET_LATENCY_SECONDS = 3.0


@pytest.fixture(scope="module")
def model_and_tokenizer():
    """모델과 토크나이저를 로드하는 fixture (모듈 단위 캐싱)"""
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME).to("mps")
    return model, tokenizer


@pytest.mark.skip(reason="외부 모델 필요 - 수동 실행: uv run pytest tests/test_llm.py -v -s")
class TestQwenInference:
    """Qwen 2.5-3B 모델 추론 테스트"""

    test_prompts = [
        ("마을 주민 (날씨)", "당신은 친절한 마을 주민입니다. 오늘 날씨에 대해 이야기해주세요."),
        ("카페 주인 (대화)", "당신은 작은 마을 카페의 주인입니다. 손님에게 오늘의 추천 메뉴를 소개해주세요."),
        ("도서관 사서 (기억)", "당신은 마을 도서관의 사서입니다. 어제 만난 사람에 대해 기억을 떠올려보세요."),
    ]

    @pytest.mark.parametrize("name,prompt", test_prompts)
    def test_inference_latency(self, model_and_tokenizer: tuple, name: str, prompt: str):
        """각 프롬프트에 대한 추론 시간이 목표 이하인지 확인"""
        model, tokenizer = model_and_tokenizer

        start = time.time()
        inputs = tokenizer(prompt, return_tensors="pt").to("mps")
        outputs = model.generate(
            **inputs, max_new_tokens=100, do_sample=True, temperature=0.7, top_p=0.9
        )
        elapsed = time.time() - start

        assert elapsed < TARGET_LATENCY_SECONDS, f"{name}: {elapsed:.2f}s >= {TARGET_LATENCY_SECONDS}s"

    @pytest.mark.parametrize("name,prompt", test_prompts)
    def test_korean_response_quality(self, model_and_tokenizer: tuple, name: str, prompt: str):
        """한국어 응답이 생성되는지 확인"""
        model, tokenizer = model_and_tokenizer

        inputs = tokenizer(prompt, return_tensors="pt").to("mps")
        outputs = model.generate(
            **inputs, max_new_tokens=100, do_sample=True, temperature=0.7, top_p=0.9
        )
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        response_text = response[len(prompt):].strip()

        assert len(response_text) > 0, f"{name}: 응답이 비어있음"
