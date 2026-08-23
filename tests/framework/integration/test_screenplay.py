"""Tasks and Questions against the real SauceDemo — the layer the Gherkin steps will call."""

from __future__ import annotations

from decimal import Decimal

import pytest

from streamcart.core.config import Settings
from streamcart.core.errors import ConfigurationError
from streamcart.screenplay import Actor
from streamcart.screenplay.questions import (
    Screen,
    TheActiveSortOrder,
    TheCartBadgeCount,
    TheCartItems,
    TheCheckoutError,
    TheConfirmationHeading,
    TheCurrentScreen,
    TheLoginError,
    TheOrderTotals,
    TheProduct,
    TheProductNames,
    TheProductPrices,
)
from streamcart.screenplay.tasks import (
    AddToCart,
    CompletePurchase,
    EnterShippingInformation,
    Login,
    Logout,
    OpenCart,
    ProceedToCheckout,
    RemoveFromCart,
    SortInventory,
)
from streamcart.testdata import PersonaCatalogue, ProductCatalogue
from streamcart.ui.components import SortOrder

pytestmark = [pytest.mark.suite("integration"), pytest.mark.platform("web")]

BACKPACK = "Sauce Labs Backpack"
BIKE_LIGHT = "Sauce Labs Bike Light"


@pytest.fixture(autouse=True)
def _web_only(settings: Settings) -> None:
    if settings.platform.name != "web":
        pytest.skip("Screenplay integration tests run on the web platform only")


@pytest.fixture(autouse=True)
def _needs_password(personas: PersonaCatalogue) -> None:
    try:
        personas.resolve("standard")
    except ConfigurationError as exc:
        pytest.skip(str(exc))


def test_login_lands_on_the_products(actor: Actor, personas: PersonaCatalogue, products: ProductCatalogue) -> None:
    actor.attempts_to(Login.as_(personas.resolve("standard")))
    assert actor.asks(TheCurrentScreen()) is Screen.INVENTORY
    assert actor.asks(TheLoginError()) is None
    assert actor.asks(TheProductNames()) == sorted(products.names())
    assert actor.asks(TheActiveSortOrder()) is SortOrder.NAME_A_TO_Z


def test_locked_out_persona_is_refused(actor: Actor, personas: PersonaCatalogue) -> None:
    actor.attempts_to(Login.as_(personas.resolve("locked_out")))
    assert actor.asks(TheCurrentScreen()) is Screen.LOGIN
    error = actor.asks(TheLoginError())
    assert error is not None
    assert "locked out" in error


def test_keyboard_submission_is_capability_gated(actor: Actor, personas: PersonaCatalogue) -> None:
    actor.attempts_to(Login.as_(personas.resolve("standard")).submitting_with_the_keyboard())
    assert actor.asks(TheCurrentScreen()) is Screen.INVENTORY


def test_cart_and_sorting_tasks(actor: Actor, personas: PersonaCatalogue) -> None:
    actor.attempts_to(Login.as_(personas.resolve("standard")), AddToCart.items(BACKPACK, BIKE_LIGHT))
    assert actor.asks(TheCartBadgeCount()) == 2
    assert actor.asks(TheProduct.named(BACKPACK)).in_cart is True
    actor.attempts_to(RemoveFromCart.item(BIKE_LIGHT))
    assert actor.asks(TheCartBadgeCount()) == 1
    actor.attempts_to(SortInventory.by(SortOrder.PRICE_HIGH_TO_LOW))
    prices = actor.asks(TheProductPrices())
    assert prices == sorted(prices, reverse=True)
    actor.attempts_to(OpenCart())
    assert actor.asks(TheCartItems())[0].name == BACKPACK
    actor.attempts_to(RemoveFromCart.item(BACKPACK))
    assert actor.asks(TheCartItems()) == []


def test_checkout_validation_and_totals(actor: Actor, personas: PersonaCatalogue, products: ProductCatalogue) -> None:
    actor.attempts_to(
        Login.as_(personas.resolve("standard")),
        AddToCart.items(BACKPACK, BIKE_LIGHT),
        OpenCart(),
        ProceedToCheckout(),
        EnterShippingInformation.with_(first_name="Ada"),
    )
    assert actor.asks(TheCheckoutError()) == "Error: Last Name is required"
    actor.attempts_to(EnterShippingInformation.with_(first_name="Ada", last_name="Lovelace", postal_code="SW1A 1AA"))
    assert actor.asks(TheCurrentScreen()) is Screen.CHECKOUT_OVERVIEW
    totals = actor.asks(TheOrderTotals())
    expected_items = products.by_name(BACKPACK).price + products.by_name(BIKE_LIGHT).price
    assert totals.item_total == expected_items == Decimal("39.98")
    assert totals.tax == products.expected_tax(expected_items)
    assert totals.total == totals.item_total + totals.tax


def test_complete_purchase_is_one_composed_task(actor: Actor, personas: PersonaCatalogue) -> None:
    actor.attempts_to(
        Login.as_(personas.resolve("standard")),
        CompletePurchase.of(BACKPACK).shipping_to("Ada", "Lovelace", "SW1A 1AA"),
    )
    assert actor.asks(TheCurrentScreen()) is Screen.CHECKOUT_COMPLETE
    assert actor.asks(TheConfirmationHeading()) == "Thank you for your order!"
    actor.attempts_to(Logout())
    assert actor.asks(TheCurrentScreen()) is Screen.LOGIN
