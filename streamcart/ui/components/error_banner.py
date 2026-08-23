"""The inline error shown by forms (login, checkout information)."""

from __future__ import annotations

from streamcart.core.locators import Locator
from streamcart.ui.base import Component


class ErrorBanner(Component):
    ROOT = Locator.test_id("error message", "error")
    DISMISS = Locator.test_id("dismiss error", "error-button")

    @property
    def message(self) -> str:
        return self.root.text

    def dismiss(self) -> None:
        self.element(self.DISMISS).select()
