from __future__ import annotations

from decimal import Decimal

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import Locator
from streamcart.ui.base import Page
from streamcart.ui.components.controls import Text
from streamcart.ui.components.header import Header
from streamcart.ui.components.product_card import ProductCard
from streamcart.ui.components.sort_select import SortSelect


class InventoryPage(Page):
    PATH = "/inventory.html"
    TITLE = Locator.test_id("page title", "title")
    PRODUCT_LIST = Locator.test_id("product list", "inventory-list")
    MARKER = PRODUCT_LIST

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.title = Text(driver, self.TITLE)
        self.header = Header(driver)
        self.sort = SortSelect(driver)

    def products(self) -> list[ProductCard]:
        """Every card currently in the grid, in display order."""
        return [ProductCard(self.driver, root=element) for element in self.elements(ProductCard.ROOT)]

    def product(self, name: str) -> ProductCard:
        return ProductCard.named(self.driver, name)

    def product_names(self) -> list[str]:
        return [card.name for card in self.products()]

    def product_prices(self) -> list[Decimal]:
        return [card.price for card in self.products()]
