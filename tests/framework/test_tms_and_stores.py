from __future__ import annotations

from pathlib import Path

import pytest

from streamcart.core.config import Settings
from streamcart.core.errors import ConfigurationError
from streamcart_pytest.artifacts import capture_artifacts
from streamcart_pytest.channels import LocalResultsChannel, TmsChannel, publish_all
from streamcart_pytest.results import ResultRecord, RunResults
from streamcart_pytest.stores import LocalArtifactStore, S3ArtifactStore, artifact_store_for
from streamcart_pytest.tms import InMemoryTms, NullTms, adapter_for, results_from
from streamcart_pytest.tms.codebeamer import build_run_payload
from streamcart_pytest.tms.xray import build_import_payload

from .fakes import FAKE_WEB, PNG, FakeWebDriver


def _run_results() -> RunResults:
    run_results = RunResults(run_id="r1", team="streamcart-qa", platform="web", target="chrome", env="staging")
    run_results.results = [
        ResultRecord(nodeid="a", outcome="passed", tms_ids=["TC-1"]),
        ResultRecord(nodeid="b", outcome="passed", attempts=2, category="flaky", tms_ids=["TC-2"]),
        ResultRecord(
            nodeid="c", outcome="failed", category="product", message="badge 2 != 1", tms_ids=["TC-3", "TC-4"]
        ),
        ResultRecord(nodeid="d", outcome="xfailed", known_issue="SC-9", tms_ids=["TC-5"]),
        ResultRecord(nodeid="e", outcome="skipped", tms_ids=["TC-6"]),
        ResultRecord(nodeid="f", outcome="passed"),  # unlinked: never reported
    ]
    return run_results


def test_results_map_to_one_tms_result_per_linked_case() -> None:
    results = results_from(_run_results())
    by_key = {r.test_key: r for r in results}
    assert set(by_key) == {"TC-1", "TC-2", "TC-3", "TC-4", "TC-5", "TC-6"}
    assert by_key["TC-1"].status == "passed"
    assert by_key["TC-2"].status == "flaky"
    assert "passed on attempt 2" in by_key["TC-2"].comment
    assert by_key["TC-3"].status == "failed"
    assert "category: product" in by_key["TC-3"].comment
    assert by_key["TC-5"].status == "known-issue"
    assert by_key["TC-6"].status == "skipped"


def test_in_memory_tms_round_trip_and_plan_resolution() -> None:
    tms = InMemoryTms(plans={"PLAN-1": ["TC-1", "TC-3"]})
    assert tms.resolve_plan("PLAN-1") == ["TC-1", "TC-3"]
    with pytest.raises(ConfigurationError, match="Unknown test plan 'PLAN-9'"):
        tms.resolve_plan("PLAN-9")
    run_results = _run_results()
    settings = Settings(platform=FAKE_WEB, tms={"provider": "memory", "upload": True})
    receipts = publish_all(run_results, [TmsChannel(tms, settings)])
    assert receipts[0].ok
    assert run_results.tms_execution == "MEM-1"
    assert tms.executions[0]["label"] == "streamcart-qa/web/chrome/staging/r1"  # the n-executions key
    assert len(tms.executions[0]["results"]) == 6


def test_null_tms_and_adapter_selection() -> None:
    assert isinstance(adapter_for(Settings(platform=FAKE_WEB)), NullTms)
    assert isinstance(adapter_for(Settings(platform=FAKE_WEB, tms={"provider": "memory"})), InMemoryTms)
    with pytest.raises(ConfigurationError, match="no test-management system is configured"):
        NullTms().resolve_plan("PLAN-1")
    with pytest.raises(ConfigurationError, match=r"tms\.provider=xray needs"):
        adapter_for(Settings(platform=FAKE_WEB, tms={"provider": "xray"}))


def test_xray_and_codebeamer_payloads_carry_the_execution_identity() -> None:
    run_results = _run_results()
    results = results_from(run_results)
    xray = build_import_payload(run_results, results, plan_key="XRAY-PLAN-7")
    assert xray["info"]["testPlanKey"] == "XRAY-PLAN-7"
    assert xray["info"]["testEnvironments"] == ["web", "chrome", "staging"]
    assert {t["testKey"]: t["status"] for t in xray["tests"]}["TC-2"] == "PASSED"
    assert {t["testKey"]: t["status"] for t in xray["tests"]}["TC-5"] == "FAILED"
    cb = build_run_payload(run_results, results, test_set_id="4711")
    assert cb["testSetIds"] == [4711]
    assert cb["name"] == "web-chrome-staging-r1"
    assert {r["testCaseId"]: r["result"] for r in cb["results"]}["TC-6"] == "Not Applicable"


def test_channel_failures_are_reported_not_raised(tmp_path: Path) -> None:
    class Broken:
        name = "broken"

        def publish(self, run_results: RunResults) -> None:
            raise RuntimeError("TMS is down")

    run_results = _run_results()
    receipts = publish_all(run_results, [Broken(), LocalResultsChannel(tmp_path)])  # type: ignore[list-item]
    assert [r.ok for r in receipts] == [False, True]
    assert "RuntimeError: TMS is down" in run_results.receipts["broken"]
    assert (tmp_path / "run-results.json").is_file()


def test_local_store_and_artifact_capture(tmp_path: Path) -> None:
    settings = Settings(platform=FAKE_WEB)
    store = artifact_store_for(settings, tmp_path)
    assert isinstance(store, LocalArtifactStore)
    captured = capture_artifacts(FakeWebDriver(settings), "tests/x.py::test_y[1]", store, settings)
    assert set(captured) == {"screenshot", "page_source", "console_log"}
    assert captured["screenshot"] == "tests_x.py_test_y_1/screenshot.png"
    assert (tmp_path / "artifacts" / captured["screenshot"]).read_bytes() == PNG
    assert (tmp_path / "artifacts" / captured["console_log"]).read_text(encoding="utf-8") == "INFO fake console line"


def test_remote_store_stubs_fail_with_guidance(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match=r"needs artifacts\.s3_bucket"):
        artifact_store_for(Settings(platform=FAKE_WEB, artifacts={"store": "s3"}), tmp_path)
    store = S3ArtifactStore("evidence", prefix="streamcart-qa/staging/web/r1")
    with pytest.raises(ConfigurationError, match="needs boto3"):
        store.put("x/shot.png", b"")
