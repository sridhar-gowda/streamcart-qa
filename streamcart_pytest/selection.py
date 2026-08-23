"""Test selection at collection time.

Platform always applies, then suite, then explicit test-management ids — all
expressed as pytest collection, so ``-k`` and ``-m`` compose with them:

    --platform roku             platform-tagged scenarios for other platforms are *deselected*
    --suite smoke               only scenarios in that suite (untagged ones are 'regression')
    --tms-ids TC-LOGIN-001,...  only scenarios linked to those test cases
    @requires:swipe             *skipped* with a reason where the platform lacks the capability

Deselected vs skipped is deliberate: a Roku-only scenario is not part of a web
run at all, whereas a swipe scenario *is* part of the run — the web platform
just cannot do it, and the report should say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from streamcart.core.capabilities import Capability
from streamcart.core.config import Settings
from streamcart.core.driver.registry import driver_class
from streamcart.core.platform import normalise

DEFAULT_SUITE = "regression"
# Suites that are not part of the product regression: the framework's own tests.
NON_PRODUCT_SUITES = frozenset({"framework", "integration"})


def add_options(group: pytest.OptionGroup) -> None:
    group.addoption("--suite", dest="sc_suites", metavar="NAMES", help="Comma-separated suites: smoke, regression, e2e")
    group.addoption("--tms-ids", dest="sc_tms_ids", metavar="IDS", help="Comma-separated test-management ids to run")


def _csv(value: str | None) -> set[str]:
    return {part.strip() for part in (value or "").split(",") if part.strip()}


@dataclass
class SelectionSummary:
    platform: str
    deselected_platform: int = 0
    deselected_suite: int = 0
    deselected_tms: int = 0
    skipped_capability: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = []
        if self.deselected_platform:
            out.append(f"{self.deselected_platform} scenario(s) deselected: tagged for other platforms")
        if self.deselected_suite:
            out.append(f"{self.deselected_suite} scenario(s) deselected by --suite")
        if self.deselected_tms:
            out.append(f"{self.deselected_tms} scenario(s) deselected by --tms-ids")
        if self.skipped_capability:
            out.append(
                f"{len(self.skipped_capability)} scenario(s) skipped: platform '{self.platform}' lacks a capability"
            )
        return out


def suites_of(item: pytest.Item) -> set[str]:
    """Explicit suite tags; product scenarios are always in the regression suite, framework tests never."""
    explicit = {str(m.args[0]) for m in item.iter_markers("suite") if m.args}
    if explicit & NON_PRODUCT_SUITES:
        return explicit
    return explicit | {DEFAULT_SUITE}


def platforms_of(item: pytest.Item) -> set[str]:
    return {normalise(str(name)) for m in item.iter_markers("platform") for name in m.args}


def tms_ids_of(item: pytest.Item) -> set[str]:
    return {str(i) for m in item.iter_markers("tms") for i in m.args}


def required_capabilities(item: pytest.Item) -> set[Capability]:
    required: set[Capability] = set()
    for marker in item.iter_markers("requires"):
        for raw in marker.args:
            if isinstance(raw, Capability):
                required.add(raw)
                continue
            try:
                required.add(Capability(str(raw).strip().lower()))
            except ValueError:
                known = ", ".join(c.value for c in Capability)
                raise pytest.UsageError(
                    f"{item.nodeid}: unknown capability '{raw}' in @requires. Known: {known}"
                ) from None
    return required


def apply_selection(config: pytest.Config, items: list[pytest.Item], settings: Settings) -> SelectionSummary:
    platform = settings.platform
    declared = driver_class(platform).declared_capabilities(platform)
    wanted_suites = _csv(config.getoption("sc_suites"))
    wanted_ids = _csv(config.getoption("sc_tms_ids"))
    summary = SelectionSummary(platform=platform.name)

    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        platforms = platforms_of(item)
        if platforms and platform.name not in platforms:
            deselected.append(item)
            summary.deselected_platform += 1
            continue
        if wanted_suites and not (wanted_suites & suites_of(item)):
            deselected.append(item)
            summary.deselected_suite += 1
            continue
        if wanted_ids and not (wanted_ids & tms_ids_of(item)):
            deselected.append(item)
            summary.deselected_tms += 1
            continue
        missing = required_capabilities(item) - declared
        if missing:
            names = ", ".join(sorted(c.value for c in missing))
            item.add_marker(pytest.mark.skip(reason=f"platform '{platform}' lacks capability: {names}"))
            summary.skipped_capability.append(item.nodeid)
        kept.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
    return summary
