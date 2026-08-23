"""Failure classification — every failure gets a category, and the category drives policy.

    product       the application behaved wrongly (an assertion in a step failed)   → a defect
    ui-contract   an element was missing / not interactable / never settled         → locator rot or UI change; triage
    environment   the session, the network or the app itself was unavailable        → infrastructure; eligible for retry
    test-defect   the test or the framework was misused (bad config, wrong ability)  → fix the test
    flaky         passed on a retry, or unstable across runs                         → quarantine candidate
    known-issue   expected, tracked failure (``@known_issue:TICKET``)                → non-blocking

Only *environment* failures are retried: retrying a product defect wastes
minutes and hides flakiness data. The mapping is possible because the driver
boundary raises typed errors (``streamcart.core.errors``) instead of leaking
library exceptions.
"""

from __future__ import annotations

import socket
import urllib.error
from collections.abc import Iterable
from enum import Enum

from _pytest.outcomes import Failed

from streamcart.core.errors import (
    AppUnreachableError,
    CapabilityNotSupportedError,
    ConditionTimeoutError,
    ConfigurationError,
    DriverSessionError,
    ElementNotFoundError,
    ElementNotInteractableError,
    LocatorNotDefinedError,
    UnsupportedSelectorError,
)
from streamcart.screenplay.actor import MissingAbilityError


class FailureCategory(str, Enum):
    PRODUCT = "product"
    UI_CONTRACT = "ui-contract"
    ENVIRONMENT = "environment"
    TEST_DEFECT = "test-defect"
    FLAKY = "flaky"
    KNOWN_ISSUE = "known-issue"

    def __str__(self) -> str:
        return self.value


# Ordered: the first category whose exceptions match wins.
CATEGORY_EXCEPTIONS: dict[FailureCategory, tuple[type[BaseException], ...]] = {
    FailureCategory.PRODUCT: (AssertionError, Failed),
    FailureCategory.UI_CONTRACT: (
        ElementNotFoundError,
        ElementNotInteractableError,
        ConditionTimeoutError,
        LocatorNotDefinedError,
        UnsupportedSelectorError,
    ),
    FailureCategory.ENVIRONMENT: (
        DriverSessionError,
        AppUnreachableError,
        ConnectionError,
        TimeoutError,
        socket.timeout,
        urllib.error.URLError,
    ),
    FailureCategory.TEST_DEFECT: (ConfigurationError, CapabilityNotSupportedError, MissingAbilityError),
}


def classify_exception(exc: BaseException) -> FailureCategory:
    for category, types in CATEGORY_EXCEPTIONS.items():
        if isinstance(exc, types):
            return category
    return FailureCategory.TEST_DEFECT


def classify(exc: BaseException, *, known_issue: str | None = None) -> FailureCategory:
    """The category for a failing test: a tracked known issue wins, then the exception type decides."""
    if known_issue:
        return FailureCategory.KNOWN_ISSUE
    return classify_exception(exc)


def exceptions_for(categories: Iterable[str]) -> tuple[type[BaseException], ...]:
    """The exception types behind the given category names — the input to the retry policy."""
    wanted = {FailureCategory(name) for name in categories}
    return tuple(exc for category, types in CATEGORY_EXCEPTIONS.items() if category in wanted for exc in types)
