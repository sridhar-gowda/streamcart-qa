"""The three checkout screens: information, overview, confirmation."""

from __future__ import annotations

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import Locator
from streamcart.ui.base import Page
from streamcart.ui.components.cart_item import CartItem
from streamcart.ui.components.controls import Button, Text, TextField
from streamcart.ui.components.error_banner import ErrorBanner
from streamcart.ui.components.header import Header
from streamcart.ui.components.order_summary import OrderSummary


class CheckoutInformationPage(Page):
    PATH = "/checkout-step-one.html"
    TITLE = Locator.test_id("page title", "title")
    FIRST_NAME = Locator.test_id("first name", "firstName")
    LAST_NAME = Locator.test_id("last name", "lastName")
    POSTAL_CODE = Locator.test_id("postal code", "postalCode")
    CANCEL = Locator.test_id("cancel", "cancel")
    CONTINUE = Locator.test_id("continue", "continue")
    MARKER = POSTAL_CODE

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.title = Text(driver, self.TITLE)
        self.header = Header(driver)
        self.first_name = TextField(driver, self.FIRST_NAME)
        self.last_name = TextField(driver, self.LAST_NAME)
        self.postal_code = TextField(driver, self.POSTAL_CODE)
        self.cancel = Button(driver, self.CANCEL)
        self.continue_button = Button(driver, self.CONTINUE)
        self.error = ErrorBanner(driver)


class CheckoutOverviewPage(Page):
    PATH = "/checkout-step-two.html"
    TITLE = Locator.test_id("page title", "title")
    CANCEL = Locator.test_id("cancel", "cancel")
    FINISH = Locator.test_id("finish", "finish")
    MARKER = FINISH

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.title = Text(driver, self.TITLE)
        self.header = Header(driver)
        self.summary = OrderSummary(driver)
        self.cancel = Button(driver, self.CANCEL)
        self.finish = Button(driver, self.FINISH)

    def items(self) -> list[CartItem]:
        return [CartItem(self.driver, root=element) for element in self.elements(CartItem.ROOT)]


class CheckoutCompletePage(Page):
    PATH = "/checkout-complete.html"
    TITLE = Locator.test_id("page title", "title")
    HEADING = Locator.test_id("confirmation heading", "complete-header")
    MESSAGE = Locator.test_id("confirmation message", "complete-text")
    BACK_HOME = Locator.test_id("back to products", "back-to-products")
    MARKER = HEADING

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.title = Text(driver, self.TITLE)
        self.header = Header(driver)
        self.heading = Text(driver, self.HEADING)
        self.message = Text(driver, self.MESSAGE)
        self.back_home = Button(driver, self.BACK_HOME)
