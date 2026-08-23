"""Checking out."""

from __future__ import annotations

from decimal import Decimal

from pytest_bdd import parsers, then, when

from streamcart.screenplay import Actor
from streamcart.screenplay.questions import (
    TheCheckoutError,
    TheConfirmationHeading,
    TheOrderTotals,
    TheOverviewItemNames,
)
from streamcart.screenplay.tasks import CancelCheckout, EnterShippingInformation, FinishOrder, ReturnToProducts
from streamcart.testdata import ProductCatalogue

from .common_steps import quoted_names


@when(
    parsers.re(
        r'the customer enters shipping information with first name "(?P<first_name>[^"]*)", '
        r'last name "(?P<last_name>[^"]*)" and postal code "(?P<postal_code>[^"]*)"'
    )
)
def enters_shipping_information(customer: Actor, first_name: str, last_name: str, postal_code: str) -> None:
    customer.attempts_to(EnterShippingInformation(first_name, last_name, postal_code))


@when("the customer finishes the order")
def finishes_order(customer: Actor) -> None:
    customer.attempts_to(FinishOrder())


@when("the customer cancels the checkout")
def cancels_checkout(customer: Actor) -> None:
    customer.attempts_to(CancelCheckout())


@when("the customer returns to the products")
def returns_to_products(customer: Actor) -> None:
    customer.attempts_to(ReturnToProducts())


@then(parsers.parse('the checkout error says "{message}"'))
def checkout_error_says(customer: Actor, message: str) -> None:
    error = customer.asks(TheCheckoutError())
    assert error is not None, "expected a checkout error, but none is shown"
    assert message in error


@then(parsers.re(r"the overview lists (?P<products>.+)"), converters={"products": quoted_names})
def overview_lists(customer: Actor, products: list[str]) -> None:
    assert customer.asks(TheOverviewItemNames()) == products


@then("the item total is the sum of the listed prices")
def item_total_is_sum(customer: Actor, products: ProductCatalogue) -> None:
    listed = customer.asks(TheOverviewItemNames())
    expected = sum((products.by_name(name).price for name in listed), Decimal("0"))
    assert customer.asks(TheOrderTotals()).item_total == expected


@then(parsers.parse("the tax is {percent:d}% of the item total"))
def tax_is_percent(customer: Actor, products: ProductCatalogue, percent: int) -> None:
    assert Decimal(percent) / 100 == products.tax_rate, "the feature's tax rate disagrees with data/products.yaml"
    totals = customer.asks(TheOrderTotals())
    assert totals.tax == products.expected_tax(totals.item_total)


@then("the total is the item total plus tax")
def total_reconciles(customer: Actor) -> None:
    totals = customer.asks(TheOrderTotals())
    assert totals.total == totals.item_total + totals.tax


@then(parsers.parse('the confirmation says "{message}"'))
def confirmation_says(customer: Actor, message: str) -> None:
    assert customer.asks(TheConfirmationHeading()) == message
