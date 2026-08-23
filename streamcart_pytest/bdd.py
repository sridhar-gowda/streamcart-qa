"""Gherkin tags → pytest markers.

One tag vocabulary drives selection, skipping and reporting:

    @web @ios @android @firetv @roku @appletv   platform(...)   — runs only on those platforms
    @smoke @regression @e2e                     suite(...)      — which runs include it
    @critical                                   critical        — failures page rather than notify
    @quarantine                                 quarantine      — runs, never fails the build
    @requires:swipe,dpad                        requires(...)   — skipped where the platform lacks it
    @known_issue:SC-123                         known_issue(...) — expected, tracked failure
    @TC-LOGIN-001 @XRAY-1042 @CB-55             tms(...)        — test-management link
    anything else                               feature(...)    — functional area

Scenarios without a platform tag run everywhere; scenarios without a suite tag
belong to the regression suite.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

from streamcart.core.driver.registry import registered_platforms

SUITES = frozenset({"smoke", "regression", "e2e", "integration"})
TMS_TAG = re.compile(r"^[A-Z][A-Z0-9]*-[A-Z0-9-]*\d$")


def marker_for_tag(tag: str) -> pytest.MarkDecorator:
    """The marker a Gherkin tag becomes."""
    name, _, argument = tag.partition(":")
    if name == "requires":
        return pytest.mark.requires(*[c.strip() for c in argument.split(",") if c.strip()])
    if name in ("known_issue", "known-issue"):
        return pytest.mark.known_issue(argument)
    if tag in SUITES:
        return pytest.mark.suite(tag)
    if tag == "critical":
        return pytest.mark.critical
    if tag == "quarantine":
        return pytest.mark.quarantine
    if tag in registered_platforms():
        return pytest.mark.platform(tag)
    if TMS_TAG.match(tag):
        return pytest.mark.tms(tag)
    return pytest.mark.feature(tag)


@pytest.hookimpl(optionalhook=True, tryfirst=True)  # firstresult hook: run before pytest-bdd's default
def pytest_bdd_apply_tag(tag: str, function: Callable[..., Any]) -> bool:
    marker_for_tag(tag)(function)
    return True  # handled — pytest-bdd must not also apply a raw marker named after the tag
