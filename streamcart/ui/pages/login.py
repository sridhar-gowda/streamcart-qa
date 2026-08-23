from __future__ import annotations

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import Locator
from streamcart.ui.base import Page
from streamcart.ui.components.controls import Button, TextField
from streamcart.ui.components.error_banner import ErrorBanner


class LoginPage(Page):
    PATH = "/"
    USERNAME = Locator.test_id("username field", "username")
    PASSWORD = Locator.test_id("password field", "password")
    LOGIN_BUTTON = Locator.test_id("login button", "login-button")
    MARKER = LOGIN_BUTTON

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.username = TextField(driver, self.USERNAME)
        self.password = TextField(driver, self.PASSWORD)
        self.login_button = Button(driver, self.LOGIN_BUTTON)
        self.error = ErrorBanner(driver)
