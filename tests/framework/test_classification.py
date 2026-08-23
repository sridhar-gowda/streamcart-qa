from __future__ import annotations

import pytest

from streamcart.core.errors import (
    AppUnreachableError,
    CapabilityNotSupportedError,
    ConditionTimeoutError,
    ConfigurationError,
    DriverSessionError,
    ElementNotFoundError,
    ElementNotInteractableError,
)
from streamcart.core.locators import By, Locator
from streamcart.screenplay.actor import MissingAbilityError
from streamcart_pytest.classification import FailureCategory, classify, classify_exception, exceptions_for

from .fakes import FAKE_WEB


@pytest.mark.parametrize(
    ("exc", "category"),
    [
        (AssertionError("badge is 2, expected 1"), FailureCategory.PRODUCT),
        (ElementNotFoundError(Locator.define("x", web=By.CSS("#x")), FAKE_WEB, 1.0), FailureCategory.UI_CONTRACT),
        (ElementNotInteractableError("covered"), FailureCategory.UI_CONTRACT),
        (ConditionTimeoutError("overview", timeout=10), FailureCategory.UI_CONTRACT),
        (DriverSessionError("browser gone"), FailureCategory.ENVIRONMENT),
        (AppUnreachableError("502"), FailureCategory.ENVIRONMENT),
        (ConnectionError("refused"), FailureCategory.ENVIRONMENT),
        (ConfigurationError("no password"), FailureCategory.TEST_DEFECT),
        (MissingAbilityError("cannot BrowseTheWeb"), FailureCategory.TEST_DEFECT),
        (KeyError("oops"), FailureCategory.TEST_DEFECT),
        (ZeroDivisionError(), FailureCategory.TEST_DEFECT),
    ],
)
def test_exceptions_map_to_categories(exc: BaseException, category: FailureCategory) -> None:
    assert classify_exception(exc) is category


def test_a_tracked_known_issue_wins_over_the_exception_type() -> None:
    assert classify(AssertionError("x"), known_issue="SC-123") is FailureCategory.KNOWN_ISSUE
    assert classify(AssertionError("x"), known_issue=None) is FailureCategory.PRODUCT


def test_retry_policy_is_derived_from_categories() -> None:
    retryable = exceptions_for(["environment"])
    assert DriverSessionError in retryable
    assert AppUnreachableError in retryable
    assert AssertionError not in retryable
    assert ElementNotFoundError not in retryable
    assert CapabilityNotSupportedError in exceptions_for(["test-defect"])
    with pytest.raises(ValueError, match="not a valid FailureCategory"):
        exceptions_for(["nonsense"])
