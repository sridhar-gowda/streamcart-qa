from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from streamcart.screenplay.actor import Actor, Question
from streamcart.ui.pages import CheckoutCompletePage, CheckoutInformationPage, CheckoutOverviewPage


@dataclass(frozen=True)
class OrderTotals:
    item_total: Decimal
    tax: Decimal
    total: Decimal
    payment_information: str
    shipping_information: str


class TheOrderTotals(Question[OrderTotals]):
    def answered_by(self, actor: Actor) -> OrderTotals:
        summary = CheckoutOverviewPage(actor.driver).summary
        return OrderTotals(
            summary.item_total, summary.tax, summary.total, summary.payment_information, summary.shipping_information
        )


class TheOverviewItemNames(Question[list[str]]):
    def answered_by(self, actor: Actor) -> list[str]:
        return [item.name for item in CheckoutOverviewPage(actor.driver).items()]


class TheCheckoutError(Question["str | None"]):
    """The validation message on the information step, or None when there is none."""

    def answered_by(self, actor: Actor) -> str | None:
        error = CheckoutInformationPage(actor.driver).error
        return error.message if error.is_displayed() else None


class TheConfirmationHeading(Question[str]):
    def answered_by(self, actor: Actor) -> str:
        return CheckoutCompletePage(actor.driver).heading.text


class TheConfirmationMessage(Question[str]):
    def answered_by(self, actor: Actor) -> str:
        return CheckoutCompletePage(actor.driver).message.text
