"""pytest entry point for the StreamCart execution platform.

Wiring only — each concern lives in its own module:

    selection      --platform / --suite / --tms-ids / --tms-plan, capability skips
    bdd            Gherkin tags → markers
    classification failure categories; retry by category (environment by default)
    runtime        per-test classification + evidence on the worker; records on the controller
    results        the run results (reports/runs/<run-id>/run-results.json)
    stores         artifact stores (local, S3, Azure)
    tms            Xray / codeBeamer / in-memory adapters
    channels       where the run results are published at session end
    reporting      terminal summary, summary.md, pytest-html column, junit properties
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from streamcart.core.config import Settings, load_settings
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.driver.registry import create_driver
from streamcart.core.errors import ConfigurationError
from streamcart.core.logs import configure_logging
from streamcart.screenplay import Actor, InteractionAbility
from streamcart.testdata import PersonaCatalogue, ProductCatalogue
from streamcart_pytest import bdd, hookspecs, reporting, runtime, selection
from streamcart_pytest.channels import ChannelReceipt, LocalResultsChannel, ResultChannel, TmsChannel, publish_all
from streamcart_pytest.classification import exceptions_for
from streamcart_pytest.results import RunResults, now_iso
from streamcart_pytest.stores import ArtifactStore, artifact_store_for
from streamcart_pytest.tms import adapter_for

SETTINGS_KEY = pytest.StashKey[Settings]()
SELECTION_KEY = pytest.StashKey[selection.SelectionSummary]()
RUN_DIR_KEY = pytest.StashKey[Path]()
REPORT_KIND_KEY = pytest.StashKey[str]()
STORE_KEY = pytest.StashKey[ArtifactStore]()
COLLECTOR_KEY = pytest.StashKey[runtime.Collector]()
RUN_RESULTS_KEY = pytest.StashKey[RunResults]()
RECEIPTS_KEY = pytest.StashKey[list[ChannelReceipt]]()
ANOMALIES_KEY = pytest.StashKey[int]()
STARTED_AT_KEY = pytest.StashKey[str]()
PASSED_ON_RETRY_KEY = pytest.StashKey[bool]()
RUN_ID_ENV = "STREAMCART_RUN_ID"
WORKER_RUN_ID_KEY = "streamcart_run_id"
WORKER_ANOMALIES_KEY = "streamcart_input_anomalies"

MARKERS = {
    "platform(*names)": "Scenario applies only to the named platforms (see --platform).",
    "suite(name)": "Execution suite: smoke, regression, e2e, integration.",
    "tms(id)": "Link to a test-management test case, e.g. tms('XRAY-1042').",
    "requires(*capabilities)": "Capabilities the scenario needs; auto-skipped on platforms lacking them.",
    "feature(name)": "Functional area tag from the feature file.",
    "quarantine": "Known-flaky: runs but never fails the build.",
    "known_issue(ticket)": "Expected failure tracked in a ticket; reported as known-issue, not as a defect.",
    "critical": "Business-critical path; failures page rather than notify.",
    "slow": "Deliberately slow scenario (e.g. a throttled persona); excluded from the PR gate.",
}

pytest_bdd_apply_tag = bdd.pytest_bdd_apply_tag
pytest_html_results_table_header = pytest.hookimpl(optionalhook=True)(reporting.html_header_cells)
pytest_html_results_table_row = pytest.hookimpl(optionalhook=True)(reporting.html_row_cells)


def new_run_id() -> str:
    """``20260822_143021_f47ac10b`` — sortable timestamp plus short uuid."""
    return f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def _is_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


# ------------------------------------------------------------------ options
def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    pluginmanager.add_hookspecs(hookspecs)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("streamcart", "StreamCart execution platform")
    group.addoption("--platform", dest="sc_platform", metavar="NAME", help="Target platform (default: web)")
    group.addoption("--env", dest="sc_env", metavar="NAME", help="Environment layer: dev, staging, prod")
    group.addoption("--target", dest="sc_target", metavar="NAME", help="Execution target, e.g. chrome, chrome-grid")
    group.addoption("--base-url", dest="sc_base_url", metavar="URL", help="Override app.base_url")
    group.addoption("--headed", dest="sc_headed", action="store_true", default=False, help="Show the browser")
    group.addoption("--run-id", dest="sc_run_id", metavar="ID", help="Correlation id (default: generated)")
    group.addoption("--config-dir", dest="sc_config_dir", metavar="DIR", help="Configuration directory")
    group.addoption("--tms-plan", dest="sc_tms_plan", metavar="KEY", help="Run the test cases of this TMS plan / set")
    group.addoption("--no-retry", dest="sc_no_retry", action="store_true", default=False, help="Disable retries")
    group.addoption(
        "--retry-categories",
        dest="sc_retry_categories",
        metavar="LIST",
        help="Failure categories that get one retry, comma-separated (default from settings: environment). "
        "A pass on retry is always reported as flaky.",
    )
    group.addoption(
        "--report-kind",
        dest="sc_report_kind",
        choices=["auto", "product", "framework"],
        default=None,
        help="Where reports go: product runs -> reports/runs, framework self-tests -> reports/framework",
    )
    selection.add_options(group)


def _report_kind(config: pytest.Config, settings: Settings) -> str:
    """Framework self-tests report separately from product runs; 'auto' looks at what was collected."""
    explicit = config.getoption("sc_report_kind") or settings.report.kind
    if explicit != "auto":
        return str(explicit)
    args = [Path(str(a).split("::")[0]) for a in (config.args or []) if not str(a).startswith("-")]
    if args and all("framework" in a.parts for a in args):
        return "framework"
    return "product"


def _overrides_from(config: pytest.Config, run_id: str) -> dict[str, Any]:
    return {
        "platform": config.getoption("sc_platform"),
        "env": config.getoption("sc_env"),
        "target": config.getoption("sc_target"),
        "run_id": run_id,
        "app": {"base_url": config.getoption("sc_base_url")},
        "web": {"headless": False} if config.getoption("sc_headed") else {},
        "retry": _retry_override(config.getoption("sc_retry_categories")),
    }


def _retry_override(value: str | None) -> dict[str, Any]:
    categories = [c.strip() for c in (value or "").split(",") if c.strip()]
    return {"only_categories": categories} if categories else {}


def _resolve_run_id(config: pytest.Config) -> str:
    worker_input: dict[str, Any] = getattr(config, "workerinput", {}) or {}
    return (
        worker_input.get(WORKER_RUN_ID_KEY)
        or config.getoption("sc_run_id")
        or os.environ.get(RUN_ID_ENV)
        or new_run_id()
    )


# ---------------------------------------------------------------- configure
@pytest.hookimpl(tryfirst=True)  # before pytest-html / junitxml read their output paths
def pytest_configure(config: pytest.Config) -> None:
    for marker, description in MARKERS.items():
        config.addinivalue_line("markers", f"{marker}: {description}")

    run_id = _resolve_run_id(config)
    try:
        settings = load_settings(_overrides_from(config, run_id), config_dir=config.getoption("sc_config_dir"))
    except ConfigurationError as exc:
        raise pytest.UsageError(f"streamcart configuration error: {exc}") from exc

    kind = _report_kind(config, settings)
    run_dir = settings.report.root / ("framework" if kind == "framework" else "runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    collector = runtime.Collector()
    config.stash[SETTINGS_KEY] = settings
    config.stash[REPORT_KIND_KEY] = kind
    config.stash[RUN_DIR_KEY] = run_dir
    config.stash[STARTED_AT_KEY] = now_iso()
    config.stash[STORE_KEY] = artifact_store_for(settings, run_dir)
    config.stash[COLLECTOR_KEY] = collector
    config.stash[ANOMALIES_KEY] = 0
    # One observer per session: turns every TestReport (local or from an xdist worker) into a record.
    config.pluginmanager.register(_ReportObserver(collector), name=f"streamcart-observer-{id(config)}")
    configure_logging(run_id)

    report = settings.report
    if not _is_worker(config):
        if report.html and not config.getoption("htmlpath", None):
            config.option.htmlpath = str(run_dir / "report.html")
            config.option.self_contained_html = True
        if report.junit and not config.getoption("xmlpath", None):
            config.option.xmlpath = str(run_dir / "junit.xml")
        if kind == "product" and report.cucumber_json and _unset(config, "cucumber_json_path"):
            config.option.cucumber_json_path = str(run_dir / "cucumber.json")
    # Allure results are written by every process (workers included) into one directory.
    if kind == "product" and report.allure and _unset(config, "allure_report_dir"):
        config.option.allure_report_dir = str(run_dir / "allure-results")


def _unset(config: pytest.Config, option: str) -> bool:
    """True when the option exists (its plugin is installed) and the user did not set it."""
    try:
        return not config.getoption(option)
    except ValueError:
        return False


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node: Any) -> None:
    """xdist (controller side): hand the run id to every worker."""
    node.workerinput[WORKER_RUN_ID_KEY] = node.config.stash[SETTINGS_KEY].run_id


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: Any, error: Any) -> None:
    """xdist (controller side): collect each worker's input-anomaly count."""
    output = getattr(node, "workeroutput", {}) or {}
    node.config.stash[ANOMALIES_KEY] = node.config.stash.get(ANOMALIES_KEY, 0) + int(
        output.get(WORKER_ANOMALIES_KEY, 0)
    )


# --------------------------------------------------------------- collection
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    settings = config.stash.get(SETTINGS_KEY, None)
    if settings is None:
        return
    plan = config.getoption("sc_tms_plan")
    if plan:
        try:
            ids = adapter_for(settings).resolve_plan(plan)
        except ConfigurationError as exc:
            raise pytest.UsageError(f"--tms-plan {plan}: {exc}") from exc
        config.option.sc_tms_ids = ",".join(ids)
    config.stash[SELECTION_KEY] = selection.apply_selection(config, items, settings)
    _apply_retry_policy(config, items, settings)
    _apply_quarantine(items)


def _apply_retry_policy(config: pytest.Config, items: list[pytest.Item], settings: Settings) -> None:
    """Only the configured failure categories retry — by default just *environment*. A team can opt
    in to retrying product or UI-contract failures; either way a pass on retry is reported as flaky."""
    if config.getoption("sc_no_retry") or settings.retry.max_attempts <= 1:
        return
    retryable = exceptions_for(settings.retry.only_categories)
    for item in items:
        if item.get_closest_marker("flaky") is None:
            item.add_marker(pytest.mark.flaky(reruns=settings.retry.max_attempts - 1, only_rerun=list(retryable)))


def _apply_quarantine(items: list[pytest.Item]) -> None:
    """Quarantined and known-issue tests run but cannot fail the build (non-strict xfail).

    Both are decisions written in the feature file (``@quarantine``, ``@known_issue:SC-42``) and
    reviewed like any other change. Cross-run flakiness belongs to the CI analytics or test
    management system fed by the run resultss — the framework reports it per run, it does not
    keep a private history.
    """
    for item in items:
        known = item.get_closest_marker("known_issue")
        if known is not None:
            ticket = known.args[0] if known.args else "untracked"
            item.add_marker(pytest.mark.xfail(reason=f"known issue {ticket}", strict=False))
        elif item.get_closest_marker("quarantine") is not None:
            item.add_marker(pytest.mark.xfail(reason="quarantined (tagged @quarantine)", strict=False))


# ------------------------------------------------------------------ per test
@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[Any]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    settings = item.config.stash.get(SETTINGS_KEY, None)
    store = item.config.stash.get(STORE_KEY, None)
    if settings is not None and store is not None:
        runtime.annotate_report(item, call, report, settings, store)
    if report.when == "call" and report.passed and getattr(item, "execution_count", 1) > 1:
        item.stash[PASSED_ON_RETRY_KEY] = True  # a pass on retry is flaky in every report, Allure included
    elif report.when == "teardown" and item.stash.get(PASSED_ON_RETRY_KEY, False):
        reporting.flag_flaky_in_allure(item)
    return report


class _ReportObserver:
    """Registered per session in ``pytest_configure``; sees reports from every xdist worker on the controller."""

    def __init__(self, collector: runtime.Collector) -> None:
        self.collector = collector

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.collector.observe(report)


# ------------------------------------------------------------- session end
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    settings = config.stash.get(SETTINGS_KEY, None)
    if settings is None:
        return
    if _is_worker(config):
        config.workeroutput[WORKER_ANOMALIES_KEY] = config.stash.get(ANOMALIES_KEY, 0)  # type: ignore[attr-defined]
        return
    run_dir = config.stash[RUN_DIR_KEY]
    run_results = RunResults(
        run_id=settings.run_id or "",
        team=settings.team,
        platform=settings.platform.name,
        target=settings.target,
        env=settings.env,
        base_url=settings.app.base_url,
        build=settings.build or "",
        browser=settings.web.browser if settings.platform.is_web else "",
        config_layers=list(settings.loaded_files),
        started_at=config.stash.get(STARTED_AT_KEY, now_iso()),
        input_anomalies=config.stash.get(ANOMALIES_KEY, 0),
    )
    config.stash[COLLECTOR_KEY].into(run_results)
    run_results.finished_at = now_iso()

    kind = config.stash.get(REPORT_KIND_KEY, "product")
    channels: list[ResultChannel] = [LocalResultsChannel(run_dir)]
    if kind == "product":  # framework self-tests are not product results: they never reach the TMS or team channels
        if settings.tms.provider != "none":
            try:
                channels.append(TmsChannel(adapter_for(settings), settings))
            except ConfigurationError as exc:
                channels.append(_FailedChannel("tms", str(exc)))
        for extra in config.hook.pytest_streamcart_result_channels(settings=settings, run_dir=run_dir):
            channels.extend(extra or [])
    receipts = publish_all(run_results, channels)
    if kind == "product":
        reporting.write_allure_metadata(run_dir / "allure-results", run_results)
        if settings.report.allure and settings.report.allure_html:
            allure = reporting.generate_allure_report(run_dir / "allure-results", run_dir / "allure-report")
            run_results.receipts[allure.channel] = allure.detail
            receipts.append(allure)
    run_results.write(run_dir / "run-results.json")  # final: includes receipts, the TMS key and report locations
    if settings.report.summary:
        (run_dir / "summary.md").write_text(
            reporting.summary_markdown(run_results, receipts, run_dir), encoding="utf-8"
        )
    config.stash[RUN_RESULTS_KEY] = run_results
    config.stash[RECEIPTS_KEY] = receipts


class _FailedChannel:
    def __init__(self, name: str, detail: str) -> None:
        self.name = name
        self.detail = detail

    def publish(self, run_results: RunResults) -> ChannelReceipt:
        return ChannelReceipt(self.name, False, self.detail)


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    run_results = config.stash.get(RUN_RESULTS_KEY, None)
    if run_results is None:
        return
    receipts = config.stash.get(RECEIPTS_KEY, [])
    terminalreporter.section("streamcart run summary")
    for line in reporting.summary_lines(run_results, receipts, config.stash[RUN_DIR_KEY]):
        terminalreporter.write_line(line)


# ------------------------------------------------------------------ headers
def pytest_report_header(config: pytest.Config) -> list[str]:
    settings = config.stash.get(SETTINGS_KEY, None)
    if settings is None:
        return []
    return [
        f"streamcart: {settings.describe()}",
        f"streamcart: config {settings.config_dir} :: {' -> '.join(settings.loaded_files)}",
        f"streamcart: {config.stash.get(REPORT_KIND_KEY, 'product')} run -> {config.stash[RUN_DIR_KEY]}",
    ]


def pytest_report_collectionfinish(config: pytest.Config) -> list[str]:
    summary = config.stash.get(SELECTION_KEY, None)
    return [f"streamcart: {line}" for line in summary.lines()] if summary else []


# ----------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Settings:
    """The resolved configuration for this session."""
    return pytestconfig.stash[SETTINGS_KEY]


@pytest.fixture(scope="session")
def run_id(settings: Settings) -> str:
    assert settings.run_id is not None
    return settings.run_id


@pytest.fixture(scope="session")
def run_dir(pytestconfig: pytest.Config) -> Path:
    """Where this run's reports and artifacts are written."""
    return pytestconfig.stash[RUN_DIR_KEY]


@pytest.fixture
def driver(request: pytest.FixtureRequest, settings: Settings) -> Iterator[PlatformDriver]:
    """A started platform driver, one per test.

    A fresh session per test is the isolation guarantee that makes parallel
    execution safe: no cookies, storage or focus state leaks between scenarios,
    on any platform, on any xdist worker. The instance is stashed on the test
    item so failure evidence can be captured from it.
    """
    instance = create_driver(settings)
    instance.start()
    request.node.stash[runtime.DRIVER_KEY] = instance
    try:
        yield instance
    finally:
        anomalies = int(getattr(instance, "input_anomalies", 0) or 0)
        request.config.stash[ANOMALIES_KEY] = request.config.stash.get(ANOMALIES_KEY, 0) + anomalies
        instance.stop()


@pytest.fixture(scope="session")
def personas(settings: Settings) -> PersonaCatalogue:
    """The personas in ``data/users.yaml``; ``personas.resolve("standard")`` adds the password or fails fast."""
    return PersonaCatalogue.from_settings(settings)


@pytest.fixture(scope="session")
def products(settings: Settings) -> ProductCatalogue:
    """The reference catalogue in ``data/products.yaml``."""
    return ProductCatalogue.from_settings(settings)


@pytest.fixture
def actor(driver: PlatformDriver) -> Actor:
    """An actor able to interact with the configured platform — web, mobile or TV alike."""
    return Actor("the customer").who_can(InteractionAbility.for_driver(driver))
