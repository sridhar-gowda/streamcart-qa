"""Reporting surfaces: terminal summary, Markdown summary, pytest-html column, junit properties."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from streamcart_pytest.channels import ChannelReceipt
from streamcart_pytest.results import RunResults


def summary_lines(run_results: RunResults, receipts: Sequence[ChannelReceipt], run_dir: Path) -> list[str]:
    counts = run_results.counts()
    browser = (
        f" [{run_results.browser}]" if run_results.browser and run_results.browser not in run_results.target else ""
    )
    lines = [
        f"run {run_results.run_id} | {run_results.platform}/{run_results.target}{browser} | {run_results.env} | "
        + " ".join(f"{k}={v}" for k, v in counts.items() if v),
    ]
    by_category = run_results.by_category()
    if by_category:
        lines.append("failures by category: " + ", ".join(f"{c}={len(r)}" for c, r in by_category.items()))
        for category, records in by_category.items():
            for record in records:
                lines.append(
                    f"  [{category}] {record.nodeid}: {record.message.splitlines()[0][:120] if record.message else ''}"
                )
    flaky = run_results.flaky()
    if flaky:
        lines.append(f"flaky (passed only on retry): {len(flaky)}")
        lines.extend(f"  {r.nodeid} (attempt {r.attempts})" for r in flaky)
    quarantined = [r for r in run_results.results if r.quarantined]
    if quarantined:
        lines.append(f"quarantined (non-blocking): {len(quarantined)}")
    if run_results.input_anomalies:
        lines.append(f"environment: browser dropped {run_results.input_anomalies} input event(s); DOM fallback used")
    for receipt in receipts:
        lines.append(f"{'ok' if receipt.ok else 'FAILED'} {receipt.channel}: {receipt.detail}")
    lines.append(f"reports: {run_dir}")
    return lines


def summary_markdown(run_results: RunResults, receipts: Sequence[ChannelReceipt], run_dir: Path) -> str:
    counts = run_results.counts()
    rows = [
        "# StreamCart run summary",
        "",
        f"- **Run**: `{run_results.run_id}` on `{run_results.host}`",
        f"- **Platform / target / env**: {run_results.platform} / {run_results.target}"
        + (f" ({run_results.browser})" if run_results.browser else "")
        + f" / {run_results.env}",
        f"- **Base URL**: {run_results.base_url}",
        f"- **Configuration**: {' -> '.join(run_results.config_layers) or 'defaults'}",
        f"- **Build**: {run_results.build or 'n/a'}",
        f"- **Started / finished**: {run_results.started_at} → {run_results.finished_at}",
        "",
        "| Outcome | Count |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in counts.items()],
        "",
    ]
    by_category = run_results.by_category()
    if by_category:
        rows += ["## Failures by category", "", "| Category | Test | Message |", "|---|---|---|"]
        for category, records in by_category.items():
            for r in records:
                message = (r.message.splitlines()[0] if r.message else "").replace("|", "\\|")[:160]
                rows.append(f"| {category} | `{r.nodeid}` | {message} |")
        rows.append("")
    if run_results.flaky():
        rows += (
            ["## Flaky (passed only on retry)", ""]
            + [f"- `{r.nodeid}` (attempt {r.attempts})" for r in run_results.flaky()]
            + [""]
        )
    if run_results.input_anomalies:
        rows += [
            f"> Environment: the browser dropped {run_results.input_anomalies} input event(s); "
            "the DOM fallback was used.",
            "",
        ]
    rows += (
        ["## Published to", ""] + [f"- {'✅' if r.ok else '❌'} **{r.channel}**: {r.detail}" for r in receipts] + [""]
    )
    rows += ["## Artifacts", "", f"`{run_dir}`", ""]
    return "\n".join(rows)


# ------------------------------------------------------------------ allure
# Allure groups failures into "categories" by matching the failure message or trace. These mirror
# the platform's own taxonomy, so the stakeholder report and the terminal summary agree.
ALLURE_CATEGORIES: list[dict[str, Any]] = [
    {"name": "Product defect", "matchedStatuses": ["failed"], "traceRegex": r"(?s).*AssertionError.*"},
    {
        "name": "UI contract (locator or UI change — triage)",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": (
            r"(?s).*(ElementNotFoundError|ElementNotInteractableError|ConditionTimeoutError|LocatorNotDefinedError).*"
        ),
    },
    {
        "name": "Environment (session, network, app unavailable)",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": r"(?s).*(DriverSessionError|AppUnreachableError|ConnectionError|URLError).*",
    },
    {
        "name": "Test defect (configuration or framework misuse)",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": r"(?s).*(ConfigurationError|CapabilityNotSupportedError|MissingAbilityError).*",
    },
    {
        "name": "Known issue / quarantined",
        "matchedStatuses": ["skipped"],
        "messageRegex": r"(?s).*(known issue|quarantined).*",
    },
    {"name": "Flaky (passed only on retry)", "matchedStatuses": ["passed"], "flaky": True},
]


def flag_flaky_in_allure(item: pytest.Item) -> None:
    """Set Allure's own *flaky* marker on a scenario that passed only on a retry.

    Every attempt is written as an Allure result with the same history id, so the report keeps
    the failed attempts under "Retries"; the marker makes the final pass filterable as flaky.
    Called from the teardown report, before the Allure listener writes the result.
    """
    try:
        from allure_commons.model2 import StatusDetails
        from allure_pytest_bdd.pytest_bdd_listener import PytestBDDListener
        from allure_pytest_bdd.utils import get_uuid
    except ImportError:  # Allure not installed: nothing to flag
        return
    listener = next((p for p in item.config.pluginmanager.get_plugins() if isinstance(p, PytestBDDListener)), None)
    if listener is None:  # Allure results are not enabled for this session
        return
    with listener.lifecycle.update_test_case(uuid=get_uuid(item.nodeid)) as result:
        if result is not None:
            result.statusDetails = result.statusDetails or StatusDetails()
            result.statusDetails.flaky = True


def generate_allure_report(results_dir: Path, output_dir: Path, *, timeout: float = 180.0) -> ChannelReceipt:
    """Render ``allure-results/`` into a single-file HTML report with the Allure CLI, if installed.

    Allure's model is results (JSON) produced by the test run and a report generated from
    them afterwards — locally by ``allure serve``/``allure generate``, in CI by a step that
    installs the CLI. This does the latter automatically when the CLI is on PATH.
    """
    if not results_dir.is_dir() or not any(results_dir.iterdir()):
        return ChannelReceipt("allure-report", True, "no allure results to render")
    executable = shutil.which("allure")
    if executable is None:
        return ChannelReceipt("allure-report", True, f"Allure CLI not installed; run: allure serve {results_dir}")
    command = [executable, "generate", str(results_dir), "--clean", "--single-file", "-o", str(output_dir)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ChannelReceipt("allure-report", False, f"allure generate failed: {exc}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return ChannelReceipt(
            "allure-report", False, f"allure generate failed: {detail[-1] if detail else completed.returncode}"
        )
    return ChannelReceipt("allure-report", True, str(output_dir / "index.html"))


def write_allure_metadata(allure_dir: Path, run_results: RunResults) -> None:
    """``environment.properties`` (shown on the Allure overview) and ``categories.json``."""
    if not allure_dir.is_dir():
        return
    properties = {
        "run_id": run_results.run_id,
        "platform": run_results.platform,
        "target": run_results.target,
        "browser": run_results.browser,
        "config_layers": " -> ".join(run_results.config_layers),  # explains e.g. target=chrome with browser=edge
        "environment": run_results.env,
        "base_url": run_results.base_url,
        "build": run_results.build,
        "host": run_results.host,
        "input_anomalies": str(run_results.input_anomalies),
    }
    (allure_dir / "environment.properties").write_text(
        "".join(f"{k}={v}\n" for k, v in properties.items() if v), encoding="utf-8"
    )
    (allure_dir / "categories.json").write_text(json.dumps(ALLURE_CATEGORIES, indent=2), encoding="utf-8")


# ------------------------------------------------------------ pytest-html
def html_header_cells(cells: list[Any]) -> None:
    cells.insert(2, "<th>Category</th>")
    cells.insert(3, "<th>Attempts</th>")


def html_row_cells(report: Any, cells: list[Any]) -> None:
    category = getattr(report, "sc_category", "") or ""
    attempts = getattr(report, "sc_attempts", 1)
    cells.insert(2, f"<td>{category}</td>")
    cells.insert(3, f"<td>{attempts}</td>")


def record_junit_properties(item: pytest.Item, category: str | None, attempts: int, artifacts: dict[str, str]) -> None:
    """Upsert ``<property>`` entries on the item: a retry re-stamps category and attempts, while the
    evidence captured by an earlier attempt stays linked."""
    props: list[tuple[str, object]] = [("category", category or ""), ("attempts", str(attempts))]
    props += [(f"artifact:{name}", location) for name, location in artifacts.items()]
    replaced = {name for name, _ in props}
    item.user_properties[:] = [(n, v) for n, v in item.user_properties if n not in replaced] + props
