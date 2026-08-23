"""Browsing the catalogue."""

from __future__ import annotations

from streamcart.core.capabilities import Capability
from streamcart.core.driver.protocol import Direction
from streamcart.screenplay.actor import Actor, Task
from streamcart.ui.components import SortOrder
from streamcart.ui.pages import InventoryPage


class AddToCart(Task):
    """Put one or more products in the cart from the catalogue."""

    def __init__(self, *names: str) -> None:
        self.names = names

    @classmethod
    def item(cls, name: str) -> AddToCart:
        return cls(name)

    @classmethod
    def items(cls, *names: str) -> AddToCart:
        return cls(*names)

    def perform_as(self, actor: Actor) -> None:
        inventory = InventoryPage(actor.driver)
        for name in self.names:
            card = inventory.product(name)
            if not card.is_in_cart():
                card.press_cart_button()
                actor.driver.wait.until(card.is_in_cart, message=f"'{name}' shows as in the cart")

    def __str__(self) -> str:
        return "add to the cart: " + ", ".join(f"'{n}'" for n in self.names)


class SortInventory(Task):
    """Change the catalogue order and wait for the control to reflect it."""

    def __init__(self, order: SortOrder) -> None:
        self.order = order

    @classmethod
    def by(cls, order: SortOrder) -> SortInventory:
        return cls(order)

    def perform_as(self, actor: Actor) -> None:
        inventory = InventoryPage(actor.driver)
        inventory.sort.choose(self.order)
        actor.driver.wait.until(lambda: inventory.sort.active is self.order, message=f"sort order '{self.order.label}'")

    def __str__(self) -> str:
        return f"sort the products by '{self.order.label}'"


class SwipeThroughProducts(Task):
    """Scroll the catalogue with a swipe — a touch interaction, so only mobile platforms can do it."""

    requires = (Capability.SWIPE,)

    def __init__(self, direction: Direction = Direction.UP) -> None:
        self.direction = direction

    def perform_as(self, actor: Actor) -> None:
        actor.driver.swipe(self.direction, within=InventoryPage.PRODUCT_LIST)

    def __str__(self) -> str:
        return f"swipe {self.direction.value} through the products"
