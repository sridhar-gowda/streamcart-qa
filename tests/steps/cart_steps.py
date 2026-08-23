"""Reviewing the cart."""

from __future__ import annotations

from decimal import Decimal

from pytest_bdd import given, parsers, then, when

from streamcart.screenplay import Actor
from streamcart.screenplay.questions import CartLine, TheCartItemNames, TheCartItems
from streamcart.screenplay.tasks import ContinueShopping, OpenCart, ProceedToCheckout


@given("the customer has opened the cart")
@when("the customer opens the cart")
def opens_cart(customer: Actor) -> None:
    customer.attempts_to(OpenCart())


@when("the customer continues shopping")
def continues_shopping(customer: Actor) -> None:
    customer.attempts_to(ContinueShopping())


@given("the customer has proceeded to checkout")
def has_proceeded_to_checkout(customer: Actor) -> None:
    customer.attempts_to(OpenCart(), ProceedToCheckout())


@when("the customer proceeds to checkout")
def proceeds_to_checkout(customer: Actor) -> None:
    customer.attempts_to(ProceedToCheckout())


@then("the cart contains:")
def cart_contains(customer: Actor, datatable: list[list[str]]) -> None:
    header, *rows = datatable
    expected = [
        CartLine(name=row["product"], price=Decimal(row["price"]), quantity=int(row["quantity"]))
        for row in (dict(zip(header, values, strict=True)) for values in rows)
    ]
    assert customer.asks(TheCartItems()) == expected


@then(parsers.parse('the cart contains only "{product}"'))
def cart_contains_only(customer: Actor, product: str) -> None:
    assert customer.asks(TheCartItemNames()) == [product]
