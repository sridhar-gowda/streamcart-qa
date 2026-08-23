"""Which screen is showing — the platform-agnostic answer to "where am I?"."""

from __future__ import annotations

from enum import Enum

from streamcart.screenplay.actor import Actor, Question
from streamcart.ui.base import Page
from streamcart.ui.pages import (
    CartPage,
    CheckoutCompletePage,
    CheckoutInformationPage,
    CheckoutOverviewPage,
    InventoryPage,
    LoginPage,
)


class Screen(str, Enum):
    LOGIN = "login"
    INVENTORY = "inventory"
    CART = "cart"
    CHECKOUT_INFORMATION = "checkout information"
    CHECKOUT_OVERVIEW = "checkout overview"
    CHECKOUT_COMPLETE = "checkout complete"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


# Most specific first: every checkout step also shows a header, so markers must be unique per screen.
_SCREENS: tuple[tuple[Screen, type[Page]], ...] = (
    (Screen.CHECKOUT_COMPLETE, CheckoutCompletePage),
    (Screen.CHECKOUT_OVERVIEW, CheckoutOverviewPage),
    (Screen.CHECKOUT_INFORMATION, CheckoutInformationPage),
    (Screen.CART, CartPage),
    (Screen.INVENTORY, InventoryPage),
    (Screen.LOGIN, LoginPage),
)


class TheCurrentScreen(Question[Screen]):
    def answered_by(self, actor: Actor) -> Screen:
        for screen, page in _SCREENS:
            if page(actor.driver).is_displayed():
                return screen
        return Screen.UNKNOWN
