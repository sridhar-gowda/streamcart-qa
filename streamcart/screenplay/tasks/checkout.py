"""The three checkout steps, and the whole purchase as one Task."""

from __future__ import annotations

from streamcart.screenplay.actor import Actor, Task
from streamcart.screenplay.tasks.cart import OpenCart, ProceedToCheckout
from streamcart.screenplay.tasks.inventory import AddToCart
from streamcart.ui.pages import (
    CartPage,
    CheckoutCompletePage,
    CheckoutInformationPage,
    CheckoutOverviewPage,
    InventoryPage,
)


class EnterShippingInformation(Task):
    """Fill the shipping form (blank values are left blank) and continue; settle on the overview or an error."""

    def __init__(self, first_name: str = "", last_name: str = "", postal_code: str = "") -> None:
        self.first_name = first_name
        self.last_name = last_name
        self.postal_code = postal_code

    @classmethod
    def with_(cls, *, first_name: str = "", last_name: str = "", postal_code: str = "") -> EnterShippingInformation:
        return cls(first_name, last_name, postal_code)

    def perform_as(self, actor: Actor) -> None:
        page = CheckoutInformationPage(actor.driver)
        for field, value in (
            (page.first_name, self.first_name),
            (page.last_name, self.last_name),
            (page.postal_code, self.postal_code),
        ):
            if value:
                field.type(value)
        page.continue_button.press()
        overview = CheckoutOverviewPage(actor.driver)
        actor.driver.wait.until(
            lambda: overview.is_displayed() or page.error.is_displayed(),
            message="checkout information outcome (overview or an error message)",
        )

    def __str__(self) -> str:
        return f"enter shipping information ({self.first_name!r}, {self.last_name!r}, {self.postal_code!r})"


class FinishOrder(Task):
    def perform_as(self, actor: Actor) -> None:
        CheckoutOverviewPage(actor.driver).finish.press()
        CheckoutCompletePage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "finish the order"


class CancelCheckout(Task):
    """Cancel from whichever checkout step is showing and wait to leave it."""

    def perform_as(self, actor: Actor) -> None:
        information = CheckoutInformationPage(actor.driver)
        overview = CheckoutOverviewPage(actor.driver)
        if information.is_displayed():
            information.cancel.press()
            CartPage(actor.driver).wait_until_displayed()
        else:
            overview.cancel.press()
            InventoryPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "cancel the checkout"


class ReturnToProducts(Task):
    def perform_as(self, actor: Actor) -> None:
        CheckoutCompletePage(actor.driver).back_home.press()
        InventoryPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "return to the products"


class CompletePurchase(Task):
    """The whole journey after login, composed from the smaller Tasks."""

    def __init__(self, *names: str) -> None:
        self.names = names
        self.shipping = EnterShippingInformation()

    @classmethod
    def of(cls, *names: str) -> CompletePurchase:
        return cls(*names)

    def shipping_to(self, first_name: str, last_name: str, postal_code: str) -> CompletePurchase:
        self.shipping = EnterShippingInformation(first_name, last_name, postal_code)
        return self

    def perform_as(self, actor: Actor) -> None:
        actor.attempts_to(AddToCart.items(*self.names), OpenCart(), ProceedToCheckout(), self.shipping, FinishOrder())

    def __str__(self) -> str:
        return "complete a purchase of " + ", ".join(f"'{n}'" for n in self.names)
