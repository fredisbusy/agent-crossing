import pytest

from llm.clients import CallRecord, RecordingProviderClient


class _Inner:
    def generate(self, *, prompt: str, **_: object) -> str:
        if prompt == "boom":
            raise ValueError("no")
        return f"re:{prompt}"

    def embed_many(self, *, inputs: list[str], **_: object) -> list[list[float]]:
        return [[1.0] for _ in inputs]


def test_records_generate_and_embed_without_changing_results() -> None:
    records: list[CallRecord] = []
    client = RecordingProviderClient(_Inner(), records.append)
    client.label = "07:00"

    assert client.generate(prompt="hi", format_json=True) == "re:hi"
    assert client.embed_many(inputs=["a", "b"]) == [[1.0], [1.0]]
    assert client.embed(input="a") == [1.0]

    generate, embed, single = records
    assert (generate.op, generate.prompt, generate.response) == ("generate", "hi", "re:hi")
    assert generate.label == "07:00" and generate.format_json and generate.error is None
    assert (embed.op, embed.input_count, single.input_count) == ("embed", 2, 1)
    assert all(record.concurrent == 1 and record.seconds >= 0 for record in records)


def test_records_error_and_reraises() -> None:
    records: list[CallRecord] = []
    client = RecordingProviderClient(_Inner(), records.append)

    with pytest.raises(ValueError):
        client.generate(prompt="boom")

    assert records[0].error == "ValueError: no" and records[0].response == ""
