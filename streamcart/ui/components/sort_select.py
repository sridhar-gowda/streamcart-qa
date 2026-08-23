"""The catalogue sort control."""

from __future__ import annotations

from enum import Enum

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.locators import By, Locator
from streamcart.ui.base import Component


class SortOrder(Enum):
    """The four orders StreamCart offers, with the option value and label the UI uses."""

    NAME_A_TO_Z = ("az", "Name (A to Z)")
    NAME_Z_TO_A = ("za", "Name (Z to A)")
    PRICE_LOW_TO_HIGH = ("lohi", "Price (low to high)")
    PRICE_HIGH_TO_LOW = ("hilo", "Price (high to low)")

    @property
    def value_key(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @classmethod
    def from_label(cls, label: str) -> SortOrder:
        for order in cls:
            if order.label.lower() == label.strip().lower():
                return order
        raise ValueError(f"Unknown sort order {label!r}")


class SortSelect(Component):
    ROOT = Locator.test_id("sort select", "product-sort-container")
    ACTIVE_LABEL = Locator.test_id("active sort", "active-option")

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)

    @staticmethod
    def _option(order: SortOrder) -> Locator:
        return Locator.define(
            f"sort option '{order.label}'",
            web=By.CSS(f"option[value='{order.value_key}']"),
            any=By.TEXT(order.label),
        )

    def choose(self, order: SortOrder) -> None:
        """Pick an order: open the control and select the option (a native ``<select>`` on web)."""
        self.root.select()
        self.element(self._option(order)).select()

    @property
    def active(self) -> SortOrder:
        return SortOrder.from_label(self.driver.find(self.ACTIVE_LABEL).text)
