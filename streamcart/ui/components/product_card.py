"""One product in the catalogue grid."""

from __future__ import annotations

from decimal import Decimal

from streamcart.core.driver.protocol import Element, PlatformDriver
from streamcart.core.locators import By, Locator, xpath_string
from streamcart.ui.base import Component
from streamcart.ui.components.controls import Button
from streamcart.ui.values import parse_money, slug

ADD_LABEL = "Add to cart"
REMOVE_LABEL = "Remove"


class ProductCard(Component):
    ROOT = Locator.test_id("product card", "inventory-item")
    NAME = Locator.test_id("product name", "inventory-item-name")
    DESCRIPTION = Locator.test_id("product description", "inventory-item-desc")
    PRICE = Locator.test_id("product price", "inventory-item-price")
    IMAGE = Locator.define(
        "product image", web=By.CSS("img.inventory_item_img"), any=By.TEST_ID("inventory-item-image")
    )
    CART_BUTTON = Locator.define("cart button", web=By.CSS("button"), any=By.TEST_ID("cart-action"))

    def __init__(self, driver: PlatformDriver, *, root: Element | None = None, locator: Locator | None = None) -> None:
        super().__init__(driver, root=root, locator=locator)

    @classmethod
    def named(cls, driver: PlatformDriver, name: str) -> ProductCard:
        """The card for one product, located by its name — stable across re-renders."""
        web = By.XPATH(
            f"//*[@data-test='inventory-item'][.//*[@data-test='inventory-item-name']"
            f"[normalize-space()={xpath_string(name)}]]"
        )
        return cls(
            driver,
            locator=Locator.define(f"product card '{name}'", web=web, any=By.TEST_ID(f"inventory-item-{slug(name)}")),
        )

    # ------------------------------------------------------------------ reads
    @property
    def name(self) -> str:
        return self.element(self.NAME).text

    @property
    def description(self) -> str:
        return self.element(self.DESCRIPTION).text

    @property
    def price(self) -> Decimal:
        return parse_money(self.element(self.PRICE).text)

    @property
    def image_source(self) -> str:
        return self.element(self.IMAGE).attribute("src") or ""

    @property
    def cart_button(self) -> Button:
        return Button(self.driver, self.CART_BUTTON, within=self.root)

    @property
    def cart_button_label(self) -> str:
        return self.cart_button.label

    def is_in_cart(self) -> bool:
        return self.cart_button_label == REMOVE_LABEL

    # ---------------------------------------------------------------- actions
    def press_cart_button(self) -> None:
        """Press whichever of *Add to cart* / *Remove* the card currently shows."""
        self.cart_button.press()

    def open_details(self) -> None:
        self.element(self.NAME).select()

    def __repr__(self) -> str:
        return f"<ProductCard {self._root_locator or self._root_element}>"
