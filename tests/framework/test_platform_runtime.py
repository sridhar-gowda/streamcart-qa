"""The execution platform end to end, in pytester sessions: classification, category-gated
retry, quarantine, evidence capture, the run results, and the report files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from .conftest import plugin_args

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(autouse=True)
def _use_repo_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_CONFIG_DIR", str(REPO_CONFIG))
    monkeypatch.delenv("STREAMCART_RUN_ID", raising=False)


def _run_results(pytester: pytest.Pytester, run_id: str) -> dict[str, Any]:
    path = pytester.path / "reports" / "runs" / run_id / "run-results.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_failures_are_classified_and_the_run_results_are_written(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        from streamcart.core.errors import DriverSessionError, ElementNotFoundError, ConfigurationError
        from streamcart.core.locators import By, Locator
        from streamcart.core.driver.registry import platform_named

        @pytest.mark.tms("TC-1")
        def test_product(): assert 1 == 2, "badge mismatch"
        def test_ui_contract():
            raise ElementNotFoundError(Locator.define("x", web=By.CSS("#x")), platform_named("web"), 1.0)
        def test_test_defect(): raise ConfigurationError("no password")
        def test_ok(): pass
        @pytest.mark.known_issue("SC-42")
        def test_known(): assert False
        @pytest.mark.quarantine
        def test_quarantined(): assert False
        """
    )
    result = pytester.runpytest("--run-id", "run-a", "--no-retry", *plugin_args())
    result.assert_outcomes(passed=1, failed=3, xfailed=2)
    # quarantine changes blocking, not the category: the quarantined assertion is still a product failure
    result.stdout.fnmatch_lines(
        ["*streamcart run summary*", "*failures by category: product=2, ui-contract=1, test-defect=1, known-issue=1*"]
    )
    result.stdout.fnmatch_lines(["*quarantined (non-blocking): 1*"])
    run_results = _run_results(pytester, "run-a")
    by_name = {r["name"]: r for r in run_results["results"]}
    assert by_name["test_product"]["category"] == "product"
    assert by_name["test_product"]["tms_ids"] == ["TC-1"]
    assert by_name["test_ui_contract"]["category"] == "ui-contract"
    assert by_name["test_test_defect"]["category"] == "test-defect"
    assert by_name["test_ok"]["outcome"] == "passed"
    assert by_name["test_known"]["outcome"] == "xfailed"
    assert by_name["test_known"]["category"] == "known-issue"
    assert by_name["test_quarantined"]["outcome"] == "xfailed"
    assert by_name["test_quarantined"]["quarantined"] is True
    run_dir = pytester.path / "reports" / "runs" / "run-a"
    assert (run_dir / "report.html").is_file()
    assert (run_dir / "junit.xml").is_file()
    assert (run_dir / "summary.md").is_file()
    junit = (run_dir / "junit.xml").read_text(encoding="utf-8")
    assert 'name="category" value="product"' in junit


def test_product_runs_write_the_bdd_report_set(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_REPORT__ALLURE_HTML", "true")  # the one place the CLI is exercised
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest("--run-id", "run-p", "--no-retry", *plugin_args())
    result.assert_outcomes(passed=1)
    run_dir = pytester.path / "reports" / "runs" / "run-p"
    assert {p.name for p in run_dir.iterdir()} >= {
        "report.html",
        "junit.xml",
        "run-results.json",
        "summary.md",
        "cucumber.json",
    }
    allure = run_dir / "allure-results"
    assert (allure / "environment.properties").read_text(encoding="utf-8").startswith("run_id=run-p")
    assert "Product defect" in (allure / "categories.json").read_text(encoding="utf-8")
    result.stdout.fnmatch_lines(["*streamcart: product run -> *run-p*"])
    if shutil.which("allure"):  # the CLI renders results into HTML; without it the summary says how
        assert (run_dir / "allure-report" / "index.html").is_file()
        result.stdout.fnmatch_lines(["*ok allure-report: *index.html*"])
    else:
        result.stdout.fnmatch_lines(["*allure-report: Allure CLI not installed; run: allure serve*"])


def test_framework_runs_report_separately_and_never_touch_product_channels(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STREAMCART_TMS__PROVIDER", "memory")  # a product run would publish here
    monkeypatch.setenv("STREAMCART_TMS__UPLOAD", "true")
    # A directory named like the framework suite (no `tests` package: it would clash with the real one in-process).
    pytester.mkdir("framework")
    (pytester.path / "framework" / "test_tool.py").write_text("def test_tool(): pass\n", encoding="utf-8")
    result = pytester.runpytest("framework", "--run-id", "run-f", "--no-retry", *plugin_args())
    result.assert_outcomes(passed=1)
    run_dir = pytester.path / "reports" / "framework" / "run-f"
    assert (run_dir / "run-results.json").is_file()
    assert not (run_dir / "cucumber.json").exists()
    assert not (run_dir / "allure-results").exists()
    result.stdout.fnmatch_lines(["*streamcart: framework run -> *run-f*"])
    result.stdout.fnmatch_lines(["*ok local: *run-results.json*"])
    result.stdout.no_fnmatch_line("*tms:*")


def test_only_environment_failures_are_retried(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        from pathlib import Path
        from streamcart.core.errors import DriverSessionError

        def attempt(name):
            marker = Path(name)
            first = not marker.exists()
            marker.write_text("x")
            return first

        def test_environment_then_passes():
            if attempt("env.flag"):
                raise DriverSessionError("browser session lost")

        def test_product_is_not_retried():
            if attempt("product.flag"):
                assert False, "a real defect"
        """
    )
    result = pytester.runpytest("--run-id", "run-b", *plugin_args())
    result.assert_outcomes(passed=1, failed=1)
    assert result.parseoutcomes().get("rerun") == 1
    run_results = _run_results(pytester, "run-b")
    by_name = {r["name"]: r for r in run_results["results"]}
    assert by_name["test_environment_then_passes"]["outcome"] == "passed"
    assert by_name["test_environment_then_passes"]["attempts"] == 2
    assert by_name["test_environment_then_passes"]["category"] == "flaky"
    assert by_name["test_product_is_not_retried"]["attempts"] == 1
    result.stdout.fnmatch_lines(["*flaky (passed only on retry): 1*"])


def test_a_pass_on_retry_is_reported_as_flaky_in_every_report(pytester: pytest.Pytester) -> None:
    """The retry may hide an environment failure from the verdict, never from the reports."""
    pytester.makefile(
        ".feature",
        retry="""
        Feature: Session recovery
          Scenario: the session is lost once
            Given the session is established
        """,
    )
    pytester.makepyfile(
        """
        from pathlib import Path
        from pytest_bdd import given, scenarios
        from streamcart.core.errors import DriverSessionError

        scenarios("retry.feature")

        @given("the session is established")
        def _session():
            marker = Path("attempt.flag")
            first = not marker.exists()
            marker.write_text("x")
            if first:
                raise DriverSessionError("browser session lost")
        """
    )
    result = pytester.runpytest("--run-id", "run-r", *plugin_args())
    result.assert_outcomes(passed=1)
    assert result.parseoutcomes().get("rerun") == 1
    record = _run_results(pytester, "run-r")["results"][0]
    assert (record["category"], record["attempts"], record["outcome"]) == ("flaky", 2, "passed")
    run_dir = pytester.path / "reports" / "runs" / "run-r"
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "&lt;td&gt;flaky&lt;/td&gt;" in html  # pytest-html keeps the rows as escaped JSON inside the page
    assert 'name="category" value="flaky"' in (run_dir / "junit.xml").read_text(encoding="utf-8")
    assert "## Flaky (passed only on retry)" in (run_dir / "summary.md").read_text(encoding="utf-8")
    result.stdout.fnmatch_lines(["*flaky (passed only on retry): 1*"])
    allure = [json.loads(p.read_text(encoding="utf-8")) for p in (run_dir / "allure-results").glob("*-result.json")]
    assert len(allure) == 2, "every attempt is an Allure result"
    assert len({r["historyId"] for r in allure}) == 1, "same history id: the report shows the first as a retry"
    final = next(r for r in allure if r["status"] == "passed")
    assert final["statusDetails"]["flaky"] is True


def test_evidence_is_captured_from_the_driver_on_failure(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        from streamcart_pytest.runtime import DRIVER_KEY
        from tests.framework.fakes import FakeWebDriver, FAKE_WEB
        from streamcart.core.config import Settings

        @pytest.fixture
        def fake_driver(request):
            driver = FakeWebDriver(Settings(platform=FAKE_WEB))
            request.node.stash[DRIVER_KEY] = driver
            return driver

        def test_fails_with_evidence(fake_driver):
            assert fake_driver.current_location() == "nowhere"
        """
    )
    pytester.syspathinsert(str(REPO_CONFIG.parent))
    result = pytester.runpytest("--run-id", "run-c", "--no-retry", *plugin_args())
    result.assert_outcomes(failed=1)
    run_results = _run_results(pytester, "run-c")
    record = run_results["results"][0]
    assert record["category"] == "product"
    assert set(record["artifacts"]) == {"screenshot", "page_source", "console_log"}
    run_dir = pytester.path / "reports" / "runs" / "run-c"
    assert (run_dir / "artifacts" / record["artifacts"]["screenshot"]).is_file()
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "data:image/png;base64" in html


def test_teams_can_opt_in_to_retrying_product_failures(pytester: pytest.Pytester) -> None:
    """Retry is a setting, not a rule: --retry-categories widens it; a pass on retry is still flaky."""
    pytester.makepyfile(
        test_opt_in="""
        from pathlib import Path

        def test_assertion_fails_once():
            marker = Path("opt-in.flag")
            first = not marker.exists()
            marker.write_text("x")
            assert not first, "fails on the first attempt only"
        """,
        test_default="""
        from pathlib import Path

        def test_assertion_fails_once():
            marker = Path("default.flag")
            first = not marker.exists()
            marker.write_text("x")
            assert not first, "fails on the first attempt only"
        """,
    )
    widened = pytester.runpytest(
        "test_opt_in.py", "--run-id", "run-w", "--retry-categories", "environment,product", *plugin_args()
    )
    widened.assert_outcomes(passed=1)
    assert widened.parseoutcomes().get("rerun") == 1
    record = _run_results(pytester, "run-w")["results"][0]
    assert (record["category"], record["attempts"]) == ("flaky", 2)

    default = pytester.runpytest("test_default.py", "--run-id", "run-d", *plugin_args())
    default.assert_outcomes(failed=1)  # product failures are not retried unless a team opts in
    assert default.parseoutcomes().get("rerun") is None


def test_teams_add_their_own_result_channels_through_the_hook(pytester: pytest.Pytester) -> None:
    """A conftest implements pytest_streamcart_result_channels; the channel receives the run results."""
    pytester.makeconftest(
        """
        import json

        import pytest

        class TeamDashboard:
            name = "dashboard"
            def __init__(self, run_dir):
                self.run_dir = run_dir
            def publish(self, run_results):
                from streamcart_pytest.channels import ChannelReceipt
                (self.run_dir / "dashboard.json").write_text(json.dumps(run_results.counts()))
                return ChannelReceipt(self.name, True, "pushed to the team dashboard")

        @pytest.hookimpl
        def pytest_streamcart_result_channels(settings, run_dir):
            return [TeamDashboard(run_dir)]
        """
    )
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest("--run-id", "run-h", "--no-retry", *plugin_args())
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*ok dashboard: pushed to the team dashboard*"])
    dashboard = json.loads(
        (pytester.path / "reports" / "runs" / "run-h" / "dashboard.json").read_text(encoding="utf-8")
    )
    assert dashboard["passed"] == 1
