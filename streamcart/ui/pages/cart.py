from __future__ import annotations

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import Locator
from streamcart.ui.base import Page
from streamcart.ui.components.cart_item import CartItem
from streamcart.ui.components.controls import Button, Text
from streamcart.ui.components.header import Header


class CartPage(Page):
    PATH = "/cart.html"
    TITLE = Locator.test_id("page title", "title")
    CART_LIST = Locator.test_id("cart list", "cart-list")
    CONTINUE_SHOPPING = Locator.test_id("continue shopping", "continue-shopping")
    CHECKOUT = Locator.test_id("checkout", "checkout")
    MARKER = CHECKOUT

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.title = Text(driver, self.TITLE)
        self.header = Header(driver)
        self.continue_shopping = Button(driver, self.CONTINUE_SHOPPING)
        self.checkout = Button(driver, self.CHECKOUT)

    def items(self) -> list[CartItem]:
        return [CartItem(self.driver, root=element) for element in self.elements(CartItem.ROOT)]

    def item(self, name: str) -> CartItem:
        return CartItem.named(self.driver, name)

    def item_names(self) -> list[str]:
        return [item.name for item in self.items()]
