import json

import pytest

from run_town_scenario import main


def test_all_rule_mind_run_prints_report(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--scenario", "valentine"])
    report = json.loads(capsys.readouterr().out)
    assert report["event"] == "밸런타인데이 파티"
    assert report["agent_ids"] == [] and set(report["mind_calls"]) == {"schedule"}
    assert 0.0 <= report["diffusion_rate"] <= 1.0
