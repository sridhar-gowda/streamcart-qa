"""Browsing the catalogue."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from streamcart.screenplay import Actor
from streamcart.screenplay.questions import TheProduct, TheProducts
from streamcart.screenplay.tasks import AddToCart, RemoveFromCart, SortInventory, SwipeThroughProducts
from streamcart.testdata import ProductCatalogue
from streamcart.ui.components import SortOrder

from .common_steps import quoted_names


@given(parsers.re(r"the customer has added (?P<products>.+) to the cart"), converters={"products": quoted_names})
@when(parsers.re(r"the customer adds (?P<products>.+) to the cart"), converters={"products": quoted_names})
def adds_to_cart(customer: Actor, products: list[str]) -> None:
    customer.attempts_to(AddToCart.items(*products))


@when(parsers.parse('the customer removes "{product}" from the cart'))
def removes_from_cart(customer: Actor, product: str) -> None:
    customer.attempts_to(RemoveFromCart.item(product))


@when(parsers.parse('the customer sorts the products by "{order}"'))
def sorts_products(customer: Actor, order: str) -> None:
    customer.attempts_to(SortInventory.by(SortOrder.from_label(order)))


@when("the customer swipes up through the products")
def swipes_products(customer: Actor) -> None:
    customer.attempts_to(SwipeThroughProducts())


@then(parsers.parse("the customer sees {count:d} products"))
def sees_products(customer: Actor, count: int) -> None:
    assert len(customer.asks(TheProducts())) == count


@then("every product shows a name, a description, a price and an image")
def products_have_details(customer: Actor) -> None:
    for product in customer.asks(TheProducts()):
        assert product.name, "a product has no name"
        assert product.description, f"'{product.name}' has no description"
        assert product.price > 0, f"'{product.name}' has no price"
        assert product.image_source, f"'{product.name}' has no image"


@then("the products match the catalogue")
def products_match_catalogue(customer: Actor, products: ProductCatalogue) -> None:
    shown = {p.name: p.price for p in customer.asks(TheProducts())}
    assert shown == {p.name: p.price for p in products}


@then(parsers.parse("the products are listed by {attribute} {direction}"))
def products_are_sorted(customer: Actor, attribute: str, direction: str) -> None:
    values = [getattr(p, attribute) for p in customer.asks(TheProducts())]
    assert values == sorted(values, reverse=(direction == "descending"))


@then(parsers.parse('"{product}" is marked as in the cart'))
def product_in_cart(customer: Actor, product: str) -> None:
    assert customer.asks(TheProduct.named(product)).in_cart is True


@then(parsers.parse('"{product}" is no longer marked as in the cart'))
def product_not_in_cart(customer: Actor, product: str) -> None:
    assert customer.asks(TheProduct.named(product)).in_cart is False
