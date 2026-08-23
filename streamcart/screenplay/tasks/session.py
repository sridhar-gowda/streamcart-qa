"""Signing in and out."""

from __future__ import annotations

from streamcart.core.capabilities import Capability
from streamcart.core.driver.protocol import Key
from streamcart.screenplay.actor import Actor, Task
from streamcart.testdata.personas import Persona
from streamcart.ui.pages import InventoryPage, LoginPage


class Login(Task):
    """Sign in with a username and password, then wait for the outcome: products or an error."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.submit_with_keyboard = False

    @classmethod
    def as_(cls, persona: Persona) -> Login:
        """``Login.as_(standard)`` — credentials resolved from the persona (fails fast if unset)."""
        username, password = persona.credentials()
        return cls(username, password)

    @classmethod
    def with_credentials(cls, username: str, password: str) -> Login:
        return cls(username, password)

    def submitting_with_the_keyboard(self) -> Login:
        """Submit by pressing Enter instead of the button — needs a physical keyboard."""
        self.submit_with_keyboard = True
        self.requires = (Capability.KEYBOARD,)
        return self

    def perform_as(self, actor: Actor) -> None:
        page = LoginPage(actor.driver)
        if not page.is_displayed():
            page.open()
            page.wait_until_displayed()
        page.username.type(self.username)
        page.password.type(self.password)
        if self.submit_with_keyboard:
            actor.driver.press(Key.ENTER)
        else:
            page.login_button.press()
        inventory = InventoryPage(actor.driver)
        actor.driver.wait.until(
            lambda: inventory.is_displayed() or page.error.is_displayed(),
            message="login outcome (products or an error message)",
        )

    def __str__(self) -> str:
        how = " using the keyboard" if self.submit_with_keyboard else ""
        return f"log in as '{self.username}'{how}"


class Logout(Task):
    """Sign out through the app menu and wait for the login screen."""

    def perform_as(self, actor: Actor) -> None:
        inventory = InventoryPage(actor.driver)
        inventory.header.menu.open()
        inventory.header.menu.logout.goto()
        LoginPage(actor.driver).wait_until_displayed()

    def __str__(self) -> str:
        return "log out"


class ResetAppState(Task):
    """Clear the cart through the app menu (StreamCart's 'Reset App State')."""

    def perform_as(self, actor: Actor) -> None:
        inventory = InventoryPage(actor.driver)
        inventory.header.menu.open()
        inventory.header.menu.reset_app_state.goto()
        inventory.header.menu.close()

    def __str__(self) -> str:
        return "reset the app state"
