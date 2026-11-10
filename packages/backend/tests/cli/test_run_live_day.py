from llm.clients import CallRecord
from run_live_day import call_kind, summarize


def _generate(prompt: str, response: str, *, seconds: float = 1.0) -> CallRecord:
    return CallRecord(
        op="generate",
        label="",
        seconds=seconds,
        thread="t",
        concurrent=1,
        prompt=prompt,
        response=response,
        format_json=True,
    )


def test_call_kind_reads_template_headings_then_response_keys() -> None:
    cases = {
        ("## Task\n\nScore memory importance for", '{"importance":1}'): "importance",
        (
            "## Task\n\nScore the importance of each numbered memory",
            '{"importances":[1]}',
        ): "importance:batch",
        ("## Planning Context\n## Input Active Day Plan Context", "{}"): "plan:hour",
        ("## Planning Context\n## Input Active Hourly Plan Context", "{}"): "plan:minute",
        ("## Persona Context", "{}"): "plan:day",
        ("진술\n## 지시\n상위 수준 통찰 5개를 쓴다", "{}"): "reflect:insight",
        ("진술\n## 지시\n가장 중요한 질문", "{}"): "reflect:question",
        ("## 인물", '{"react": false}'): "react",
        ("## 인물", '{"converse": true}'): "encounter",
        ("## 인물", '{"utterance": "안녕"}'): "speech",
        ("## 인물", '{"summary": "요약"}'): "summary",
        ("## 인물", '{"memo": "메모", "plan_note": ""}'): "talk:notes",
        ("## 인물\n그에게 가장 중요한 것은 가족이다", '{"utterance": "네"}'): "speech",
        ("## 인물", ""): "town:unreadable",
        ("처음 보는 프롬프트", "{}"): "other",
    }
    for (prompt, response), kind in cases.items():
        assert call_kind(_generate(prompt, response)) == kind


def test_summarize_counts_latency_and_format_failures() -> None:
    records = [
        _generate("## Persona Context", '{"items":[]}', seconds=2.0),
        _generate("## Persona Context", '{"items":[]}</final', seconds=4.0),
        CallRecord(op="embed", label="", seconds=0.5, thread="t", concurrent=2, input_count=3),
    ]

    summary = summarize(records)

    assert summary["plan:day"] == {
        "count": 2,
        "median_seconds": 3.0,
        "max_seconds": 4.0,
        "total_seconds": 6.0,
        "bad": 1,
    }
    assert summary["embed"]["count"] == 1 and summary["embed"]["bad"] == 0
