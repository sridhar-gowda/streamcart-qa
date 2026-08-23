"""Per-test bookkeeping: classification, artifacts, attempts — and the run results they add up to.

Runs on whichever process executes the test (an xdist worker or the main
process); everything it learns travels to the controller on the ``TestReport``
as plain serialisable attributes (``sc_*``), where ``Collector`` turns reports
into ``ResultRecord``s. That is why the run results is always complete on the
controller with no worker-side files to merge.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from streamcart.core.config import Settings
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.logs import get_logger
from streamcart_pytest.artifacts import capture_artifacts
from streamcart_pytest.classification import FailureCategory, classify
from streamcart_pytest.reporting import record_junit_properties
from streamcart_pytest.results import ResultRecord, RunResults
from streamcart_pytest.selection import platforms_of, suites_of, tms_ids_of
from streamcart_pytest.stores import ArtifactStore

DRIVER_KEY = pytest.StashKey[PlatformDriver]()
log = get_logger(__name__)


def item_metadata(item: pytest.Item) -> dict[str, Any]:
    known = item.get_closest_marker("known_issue")
    feature = item.get_closest_marker("feature")
    return {
        "tms_ids": sorted(tms_ids_of(item)),
        "suites": sorted(suites_of(item)),
        "platforms": sorted(platforms_of(item)),
        "feature": str(feature.args[0]) if feature and feature.args else "",
        "known_issue": str(known.args[0]) if known and known.args else "",
        "quarantined": item.get_closest_marker("quarantine") is not None,
    }


def annotate_report(
    item: pytest.Item, call: pytest.CallInfo[Any], report: pytest.TestReport, settings: Settings, store: ArtifactStore
) -> None:
    """Worker side: classify the failure, capture evidence, stamp the report."""
    meta = item_metadata(item)
    report.sc_meta = meta  # type: ignore[attr-defined]
    attempts = getattr(item, "execution_count", 1) or 1  # pytest-rerunfailures counts the attempts
    report.sc_attempts = attempts  # type: ignore[attr-defined]
    report.sc_category = ""  # type: ignore[attr-defined]
    report.sc_exception = ""  # type: ignore[attr-defined]
    report.sc_artifacts = {}  # type: ignore[attr-defined]

    failed = report.failed or (report.when == "call" and hasattr(report, "wasxfail") and call.excinfo is not None)
    if not failed or call.excinfo is None:
        if report.when == "call" and report.passed and attempts > 1:
            # A pass on retry is flaky in every report — the retry hid a failure, the reports must not.
            report.sc_category = FailureCategory.FLAKY.value  # type: ignore[attr-defined]
            record_junit_properties(item, FailureCategory.FLAKY.value, attempts, {})
        if report.when == "call" and settings.artifacts.always and not report.failed:
            _capture(item, report, settings, store)
        return

    category = classify(call.excinfo.value, known_issue=meta["known_issue"] or None)
    report.sc_category = category.value  # type: ignore[attr-defined]
    report.sc_exception = type(call.excinfo.value).__name__  # type: ignore[attr-defined]
    if settings.artifacts.on_failure:
        _capture(item, report, settings, store)
    record_junit_properties(item, category.value, report.sc_attempts, report.sc_artifacts)


def _capture(item: pytest.Item, report: pytest.TestReport, settings: Settings, store: ArtifactStore) -> None:
    driver = item.stash.get(DRIVER_KEY, None)
    if driver is None:
        return
    artifacts = capture_artifacts(driver, item.nodeid, store, settings)
    report.sc_artifacts = artifacts  # type: ignore[attr-defined]
    _attach_html(report, artifacts, store)


def _attach_html(report: pytest.TestReport, artifacts: dict[str, str], store: ArtifactStore) -> None:
    try:
        from pytest_html import extras
    except ImportError:  # pragma: no cover - pytest-html is a declared dependency
        return
    attachments = list(getattr(report, "extras", []) or [])
    root = getattr(store, "root", None)
    for name, location in artifacts.items():
        if name == "screenshot" and root is not None:
            try:
                data = base64.b64encode((root / location).read_bytes()).decode("ascii")
                attachments.append(extras.png(data, name="screenshot"))
                continue
            except OSError:
                pass
        attachments.append(extras.url(f"artifacts/{location}" if root is not None else location, name=name))
    report.extras = attachments  # type: ignore[attr-defined]


class Collector:
    """Controller side: turns the stream of ``TestReport``s into ``ResultRecord``s."""

    def __init__(self) -> None:
        self.records: dict[str, ResultRecord] = {}

    def observe(self, report: pytest.TestReport) -> None:
        record = self.records.get(report.nodeid)
        if record is None:
            record = ResultRecord(nodeid=report.nodeid, name=report.nodeid.rsplit("::", 1)[-1])
            self.records[report.nodeid] = record
        meta = getattr(report, "sc_meta", None)
        if meta:
            record.tms_ids = meta["tms_ids"]
            record.suites = meta["suites"]
            record.platforms = meta["platforms"]
            record.feature = meta["feature"]
            record.known_issue = meta["known_issue"]
            record.quarantined = meta["quarantined"]
        gateway = getattr(getattr(report, "node", None), "gateway", None)  # set by xdist on the controller
        record.worker = str(getattr(gateway, "id", "main"))
        record.duration += float(getattr(report, "duration", 0.0) or 0.0)

        outcome: str = report.outcome  # pytest-rerunfailures adds "rerun" to pytest's three outcomes
        if outcome == "rerun":
            record.attempts = max(record.attempts, int(getattr(report, "sc_attempts", 1)) + 1)
            return
        if report.when == "setup" and outcome == "skipped":
            record.outcome = "skipped"
            record.skip_reason = _skip_reason(report)
            return
        if outcome == "failed":
            record.outcome = "error" if report.when != "call" else "failed"
            record.attempts = max(record.attempts, int(getattr(report, "sc_attempts", 1)))
            self._take_failure(record, report)
            return
        if report.when != "call":
            return
        if hasattr(report, "wasxfail"):
            record.outcome = "xfailed" if outcome == "skipped" else "xpassed"
            record.attempts = max(record.attempts, int(getattr(report, "sc_attempts", 1)))
            self._take_failure(record, report)
            return
        if outcome == "passed" and record.outcome != "error":
            record.outcome = "passed"
            record.attempts = max(record.attempts, int(getattr(report, "sc_attempts", 1)))
            if record.attempts > 1:
                record.category = FailureCategory.FLAKY.value
            if getattr(report, "sc_artifacts", None):
                record.artifacts = dict(report.sc_artifacts)

    @staticmethod
    def _take_failure(record: ResultRecord, report: pytest.TestReport) -> None:
        record.category = getattr(report, "sc_category", None) or record.category
        record.exception_type = getattr(report, "sc_exception", "") or record.exception_type
        record.artifacts = dict(getattr(report, "sc_artifacts", {}) or {})
        crash = getattr(report.longrepr, "reprcrash", None)
        record.message = getattr(crash, "message", None) or str(report.longrepr or "")[:500]

    def into(self, run_results: RunResults) -> RunResults:
        run_results.results = list(self.records.values())
        return run_results


def _skip_reason(report: pytest.TestReport) -> str:
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    return str(longrepr or "")
