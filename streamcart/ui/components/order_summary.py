"""The totals block on the checkout overview."""

from __future__ import annotations

from decimal import Decimal

from streamcart.core.locators import By, Locator
from streamcart.ui.base import Component
from streamcart.ui.values import parse_money


class OrderSummary(Component):
    ROOT = Locator.define("order summary", web=By.CSS(".summary_info"), any=By.TEST_ID("summary-info"))
    PAYMENT = Locator.test_id("payment information", "payment-info-value")
    SHIPPING = Locator.test_id("shipping information", "shipping-info-value")
    SUBTOTAL = Locator.test_id("item total", "subtotal-label")
    TAX = Locator.test_id("tax", "tax-label")
    TOTAL = Locator.test_id("total", "total-label")

    @property
    def payment_information(self) -> str:
        return self.element(self.PAYMENT).text

    @property
    def shipping_information(self) -> str:
        return self.element(self.SHIPPING).text

    @property
    def item_total(self) -> Decimal:
        return parse_money(self.element(self.SUBTOTAL).text)

    @property
    def tax(self) -> Decimal:
        return parse_money(self.element(self.TAX).text)

    @property
    def total(self) -> Decimal:
        return parse_money(self.element(self.TOTAL).text)
