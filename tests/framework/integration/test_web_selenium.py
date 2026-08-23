"""The Selenium adapter against the real SauceDemo site.

These are framework integration tests (does the adapter honour the protocol
in a real browser?), not product tests — those are Gherkin features.
"""

from __future__ import annotations

import pytest

from streamcart.core.config import Settings
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.errors import AppUnreachableError, ElementNotFoundError
from streamcart.core.locators import By, Locator

pytestmark = [pytest.mark.suite("integration"), pytest.mark.platform("web")]

LOGIN_BUTTON = Locator.test_id("login button", "login-button")
USERNAME = Locator.test_id("username field", "username")
LOGIN_FORM = Locator.define("login form", web=By.CSS("form"))
MISSING = Locator.define("missing", web=By.CSS("#does-not-exist"))
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def _web_only(settings: Settings) -> None:
    if settings.platform.name != "web":
        pytest.skip("Selenium adapter integration test runs on the web platform only")


def test_starts_navigates_and_finds_by_test_id(driver: PlatformDriver) -> None:
    driver.open("/")
    button = driver.find(LOGIN_BUTTON)
    assert button.is_displayed()
    assert button.is_enabled()
    assert button.attribute("value") == "Login"
    assert "saucedemo.com" in driver.current_location()
    assert driver.screenshot().startswith(PNG_SIGNATURE)
    assert "login" in driver.page_source().lower()


def test_elements_compose_and_accept_text(driver: PlatformDriver) -> None:
    driver.open("/")
    form = driver.find(LOGIN_FORM)
    username = form.find(USERNAME)  # scoped lookup — what makes Components composable
    username.enter_text("standard_user")
    assert username.attribute("value") == "standard_user"
    username.enter_text("locked_out_user")  # clear=True by default
    assert username.attribute("value") == "locked_out_user"
    assert len(form.find_all(Locator.define("inputs", web=By.CSS("input")))) == 3


def test_missing_elements_are_typed_errors(driver: PlatformDriver) -> None:
    driver.open("/")
    with pytest.raises(ElementNotFoundError, match=r"Element 'missing' not found on web within 0\.5s"):
        driver.find(MISSING, timeout=0.5)
    assert driver.is_present(MISSING) is False
    assert driver.is_present(LOGIN_BUTTON) is True
    assert driver.find_all(MISSING, timeout=0) == []


@pytest.mark.parametrize(
    "url",
    ["http://localhost:1/", "http://nonexistent.invalid/"],  # connection refused / DNS failure (RFC 2606 TLD)
    ids=["refused", "dns"],
)
def test_unreachable_application_is_a_typed_error(driver: PlatformDriver, url: str) -> None:
    with pytest.raises(AppUnreachableError, match=r"could not reach|ERR_NAME_NOT_RESOLVED"):
        driver.open(url)
