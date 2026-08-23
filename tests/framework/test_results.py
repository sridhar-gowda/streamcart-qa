"""The run results: the output contract every report and channel is derived from."""

from __future__ import annotations

from pathlib import Path

import pytest

from streamcart_pytest.results import ResultRecord, RunResults, merge_files, safe_name


def _run_results(run_id: str, **records: str) -> RunResults:
    run_results = RunResults(run_id=run_id, team="streamcart-qa", platform="web", target="chrome", env="dev")
    run_results.results = [
        ResultRecord(nodeid=n, outcome=o, attempts=2 if o == "flaky" else 1) for n, o in records.items()
    ]
    for r in run_results.results:
        if r.outcome == "flaky":
            r.outcome, r.category = "passed", "flaky"
    return run_results


def test_run_results_round_trip_through_json(tmp_path: Path) -> None:
    run_results = _run_results("r1", a="passed", b="failed")
    run_results.results[1].category = "product"
    run_results.results[1].artifacts = {"screenshot": "b/screenshot.png"}
    path = run_results.write(tmp_path / "run-results.json")
    loaded = RunResults.read(path)
    assert loaded.run_id == "r1"
    assert loaded.execution_label == "streamcart-qa/web/chrome/dev/r1"
    assert loaded.counts()["failed"] == 1
    assert loaded.by_category() == {"product": [loaded.results[1]]}
    assert loaded.results[1].artifacts == {"screenshot": "b/screenshot.png"}


def test_shard_results_merge_into_one_run(tmp_path: Path) -> None:
    first = _run_results("r1", a="passed", b="flaky")
    first.input_anomalies = 2
    second = _run_results("r1", c="failed")
    second.input_anomalies = 1
    paths = [first.write(tmp_path / "s1.json"), second.write(tmp_path / "s2.json")]
    merged = merge_files(paths)
    assert sorted(r.nodeid for r in merged.results) == ["a", "b", "c"]
    assert merged.input_anomalies == 3
    assert [r.nodeid for r in merged.flaky()] == ["b"]
    with pytest.raises(ValueError, match="different runs"):
        RunResults.merge([first, _run_results("r2", d="passed")])


def test_safe_name_is_filesystem_friendly_and_unique() -> None:
    assert safe_name("tests/steps/test_login.py::test_x[a-b]") == "tests_steps_test_login.py_test_x_a-b"
    long = safe_name("x" * 300)
    assert len(long) <= 100
    assert long != safe_name("x" * 301)
