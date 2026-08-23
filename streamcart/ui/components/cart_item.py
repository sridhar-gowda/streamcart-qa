"""One line of the cart (also used on the checkout overview)."""

from __future__ import annotations

from decimal import Decimal

from streamcart.core.driver.protocol import Element, PlatformDriver
from streamcart.core.locators import By, Locator, xpath_string
from streamcart.ui.base import Component
from streamcart.ui.components.controls import Button
from streamcart.ui.values import parse_money, slug


class CartItem(Component):
    ROOT = Locator.test_id("cart item", "inventory-item")
    QUANTITY = Locator.test_id("item quantity", "item-quantity")
    NAME = Locator.test_id("item name", "inventory-item-name")
    PRICE = Locator.test_id("item price", "inventory-item-price")
    REMOVE = Locator.define("remove from cart", web=By.CSS("button"), any=By.TEST_ID("remove"))

    def __init__(self, driver: PlatformDriver, *, root: Element | None = None, locator: Locator | None = None) -> None:
        super().__init__(driver, root=root, locator=locator)

    @classmethod
    def named(cls, driver: PlatformDriver, name: str) -> CartItem:
        web = By.XPATH(
            f"//*[@data-test='inventory-item'][.//*[@data-test='inventory-item-name']"
            f"[normalize-space()={xpath_string(name)}]]"
        )
        return cls(
            driver, locator=Locator.define(f"cart item '{name}'", web=web, any=By.TEST_ID(f"cart-item-{slug(name)}"))
        )

    @property
    def name(self) -> str:
        return self.element(self.NAME).text

    @property
    def price(self) -> Decimal:
        return parse_money(self.element(self.PRICE).text)

    @property
    def quantity(self) -> int:
        return int(self.element(self.QUANTITY).text.strip())

    @property
    def remove_button(self) -> Button:
        return Button(self.driver, self.REMOVE, within=self.root)

    def remove(self) -> None:
        self.remove_button.press()
