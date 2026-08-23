"""Managing the cart."""

from __future__ import annotations

from streamcart.screenplay.actor import Actor, Task
from streamcart.ui.pages import CartPage, CheckoutInformationPage, InventoryPage


class RemoveFromCart(Task):
    """Take a product out of the cart — from the cart screen or straight from the catalogue."""

    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def item(cls, name: str) -> RemoveFromCart:
        return cls(name)

    def perform_as(self, actor: Actor) -> None:
        cart = CartPage(actor.driver)
        if cart.is_displayed():
            cart.item(self.name).remove()
            actor.driver.wait.until(lambda: self.name not in cart.item_names(), message=f"'{self.name}' left the cart")
            return
        card = InventoryPage(actor.driver).product(self.name)
        if card.is_in_cart():
            card.press_cart_button()
            actor.driver.wait.until(lambda: not card.is_in_cart(), message=f"'{self.name}' no longer in the cart")

    def __str__(self) -> str:
        return f"remove '{self.name}' from the cart"


class OpenCart(Task):
    """Go to the cart from the header."""

    def perform_as(self, actor: Actor) -> None:
        InventoryPage(actor.driver).header.open_cart()
        CartPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "open the cart"


class ContinueShopping(Task):
    def perform_as(self, actor: Actor) -> None:
        CartPage(actor.driver).continue_shopping.press()
        InventoryPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "continue shopping"


class ProceedToCheckout(Task):
    def perform_as(self, actor: Actor) -> None:
        CartPage(actor.driver).checkout.press()
        CheckoutInformationPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "proceed to checkout"
