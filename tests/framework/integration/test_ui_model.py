"""Pages and Components against the real SauceDemo UI.

Integration tests of the UI model: do the locators resolve, do the typed reads
parse, do the primitives act? Product behaviour itself is specified in Gherkin.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from streamcart.core.config import Settings
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.ui.components import SortOrder
from streamcart.ui.pages import (
    CartPage,
    CheckoutCompletePage,
    CheckoutInformationPage,
    CheckoutOverviewPage,
    InventoryPage,
    LoginPage,
)

pytestmark = [pytest.mark.suite("integration"), pytest.mark.platform("web")]

BACKPACK = "Sauce Labs Backpack"
BIKE_LIGHT = "Sauce Labs Bike Light"


@pytest.fixture(autouse=True)
def _web_only(settings: Settings) -> None:
    if settings.platform.name != "web":
        pytest.skip("UI model integration tests run on the web platform only")


@pytest.fixture
def password(settings: Settings) -> str:
    secret = settings.password_for("standard")
    if secret is None:
        pytest.skip("STREAMCART_USERS__DEFAULT__PASSWORD is not set (copy .env.example to .env)")
    return secret.get_secret_value()


@pytest.fixture
def inventory(driver: PlatformDriver, password: str) -> InventoryPage:
    login = LoginPage(driver)
    login.open()
    login.username.type("standard_user")
    login.password.type(password)
    login.login_button.press()
    page = InventoryPage(driver)
    page.wait_until_displayed()
    return page


def test_login_page_fields_and_error_banner(driver: PlatformDriver) -> None:
    login = LoginPage(driver)
    login.open()
    assert login.is_displayed()
    assert login.username.placeholder == "Username"
    login.username.type("nobody")
    login.password.type("wrong")
    assert login.username.value == "nobody"
    assert not login.error.is_displayed()
    login.login_button.press()
    login.error.wait_until_displayed()
    assert "do not match" in login.error.message
    login.error.dismiss()
    assert not login.error.is_displayed()


def test_product_cards_are_typed_and_composable(inventory: InventoryPage) -> None:
    assert inventory.title.text == "Products"
    cards = inventory.products()
    assert len(cards) == 6
    names = inventory.product_names()
    assert names == sorted(names)  # default order is A→Z
    for card in cards:
        assert card.name
        assert card.description
        assert card.price > Decimal("0")
        assert card.image_source.endswith((".jpg", ".png"))
        assert not card.is_in_cart()
    backpack = inventory.product(BACKPACK)
    assert backpack.name == BACKPACK
    assert backpack.price == Decimal("29.99")


def test_cart_button_toggles_and_badge_counts(inventory: InventoryPage) -> None:
    badge = inventory.header.cart_badge
    assert badge.count == 0
    inventory.product(BACKPACK).press_cart_button()
    assert inventory.product(BACKPACK).is_in_cart()
    assert badge.count == 1
    inventory.product(BIKE_LIGHT).press_cart_button()
    assert badge.count == 2
    inventory.product(BACKPACK).press_cart_button()  # now "Remove"
    assert not inventory.product(BACKPACK).is_in_cart()
    assert badge.count == 1


def test_sort_select_changes_order(inventory: InventoryPage) -> None:
    assert inventory.sort.active is SortOrder.NAME_A_TO_Z
    inventory.sort.choose(SortOrder.PRICE_LOW_TO_HIGH)
    assert inventory.sort.active is SortOrder.PRICE_LOW_TO_HIGH
    prices = inventory.product_prices()
    assert prices == sorted(prices)
    inventory.sort.choose(SortOrder.NAME_Z_TO_A)
    names = inventory.product_names()
    assert names == sorted(names, reverse=True)


def test_menu_opens_and_closes(inventory: InventoryPage) -> None:
    menu = inventory.header.menu
    assert not menu.is_open()
    menu.open()
    assert menu.is_open()
    menu.close()
    assert not menu.is_open()


def test_cart_and_checkout_pages(inventory: InventoryPage) -> None:
    inventory.product(BACKPACK).press_cart_button()
    inventory.header.open_cart()

    cart = CartPage(inventory.driver)
    cart.wait_until_displayed()
    assert cart.title.text == "Your Cart"
    assert cart.item_names() == [BACKPACK]
    item = cart.item(BACKPACK)
    assert item.quantity == 1
    assert item.price == Decimal("29.99")
    cart.checkout.press()

    information = CheckoutInformationPage(inventory.driver)
    information.wait_until_displayed()
    information.continue_button.press()
    information.error.wait_until_displayed()
    assert information.error.message == "Error: First Name is required"
    information.first_name.type("Ada")
    information.last_name.type("Lovelace")
    information.postal_code.type("SW1A 1AA")
    information.continue_button.press()

    overview = CheckoutOverviewPage(inventory.driver)
    overview.wait_until_displayed()
    assert [i.name for i in overview.items()] == [BACKPACK]
    assert overview.summary.item_total == Decimal("29.99")
    assert overview.summary.total == overview.summary.item_total + overview.summary.tax
    assert overview.summary.payment_information
    assert overview.summary.shipping_information
    overview.finish.press()

    complete = CheckoutCompletePage(inventory.driver)
    complete.wait_until_displayed()
    assert complete.heading.text == "Thank you for your order!"
    assert "dispatched" in complete.message.text
    complete.back_home.press()
    assert InventoryPage(inventory.driver).is_displayed(timeout=5)
