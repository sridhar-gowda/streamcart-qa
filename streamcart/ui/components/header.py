"""The header shown on every signed-in screen: cart link with badge, and the app menu."""

from __future__ import annotations

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import By, Locator
from streamcart.ui.base import Component
from streamcart.ui.components.controls import Button, Link


class CartBadge(Component):
    """The item counter on the cart icon. Absent when the cart is empty."""

    ROOT = Locator.test_id("cart badge", "shopping-cart-badge")

    @property
    def count(self) -> int:
        if not self.is_displayed():
            return 0
        return int(self.root.text.strip() or 0)


class Menu(Component):
    """The slide-out app menu (burger on web; the equivalent drawer on mobile/TV)."""

    OPEN = Locator.define("open menu", web=By.ID("react-burger-menu-btn"), any=By.TEST_ID("open-menu"))
    CLOSE = Locator.define("close menu", web=By.ID("react-burger-cross-btn"), any=By.TEST_ID("close-menu"))
    ALL_ITEMS = Locator.test_id("all items", "inventory-sidebar-link")
    ABOUT = Locator.test_id("about", "about-sidebar-link")
    LOGOUT = Locator.test_id("logout", "logout-sidebar-link")
    RESET_APP_STATE = Locator.test_id("reset app state", "reset-sidebar-link")

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.open_button = Button(driver, self.OPEN)
        self.close_button = Button(driver, self.CLOSE)
        self.all_items = Link(driver, self.ALL_ITEMS)
        self.about = Link(driver, self.ABOUT)
        self.logout = Link(driver, self.LOGOUT)
        self.reset_app_state = Link(driver, self.RESET_APP_STATE)

    def is_open(self) -> bool:
        return self.is_present(self.LOGOUT) and self.element(self.LOGOUT).is_displayed()

    def open(self) -> None:
        self.open_button.press()
        self.wait.until(self.is_open, message="menu open")

    def close(self) -> None:
        self.close_button.press()
        self.wait.until(lambda: not self.is_open(), message="menu closed")


class Header(Component):
    ROOT = Locator.test_id("header", "primary-header")
    CART_LINK = Locator.test_id("cart link", "shopping-cart-link")

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.cart_link = Link(driver, self.CART_LINK)
        self.cart_badge = CartBadge(driver)
        self.menu = Menu(driver)

    def open_cart(self) -> None:
        self.cart_link.goto()
