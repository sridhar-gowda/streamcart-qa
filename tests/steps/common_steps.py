"""Steps shared by every feature: who the customer is, which screen shows, the cart badge.

The one rule of this layer: a step is a single ``attempts_to`` or a single
``asks`` followed by an assertion. Locators, waits and page objects never
appear here — if a step needs more than one line of logic, that logic belongs
in a Task or a Question.
"""

from __future__ import annotations

import re

import pytest
from pytest_bdd import parsers, then

from streamcart.screenplay import Actor
from streamcart.screenplay.questions import Screen, TheCartBadgeCount, TheCurrentScreen

SCREENS = {
    "sign-in": Screen.LOGIN,
    "products": Screen.INVENTORY,
    "cart": Screen.CART,
    "checkout information": Screen.CHECKOUT_INFORMATION,
    "checkout overview": Screen.CHECKOUT_OVERVIEW,
    "order confirmation": Screen.CHECKOUT_COMPLETE,
}


def quoted_names(text: str) -> list[str]:
    """``'"A" and "B"'`` → ``["A", "B"]`` — how steps list products."""
    return re.findall(r'"([^"]+)"', text)


@pytest.fixture
def customer(actor: Actor) -> Actor:
    """The actor, under the name the feature files use."""
    return actor


@then(parsers.parse("the customer sees the {screen} screen"))
def sees_screen(customer: Actor, screen: str) -> None:
    assert customer.asks(TheCurrentScreen()) is SCREENS[screen]


@then("the customer sees the order confirmation")
def sees_confirmation(customer: Actor) -> None:
    assert customer.asks(TheCurrentScreen()) is Screen.CHECKOUT_COMPLETE


@then("the customer stays on the sign-in screen")
def stays_on_sign_in(customer: Actor) -> None:
    assert customer.asks(TheCurrentScreen()) is Screen.LOGIN


@then(parsers.parse("the cart badge shows {count:d}"))
def cart_badge_shows(customer: Actor, count: int) -> None:
    assert customer.asks(TheCartBadgeCount()) == count
