from __future__ import annotations

from decimal import Decimal

import pytest

from streamcart.core.locators import xpath_string
from streamcart.ui.components.sort_select import SortOrder
from streamcart.ui.values import parse_money, slug


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$29.99", Decimal("29.99")),
        ("Item total: $39.98", Decimal("39.98")),
        ("Total: $1,043.19", Decimal("1043.19")),
        ("Tax: $ 2.40", Decimal("2.40")),
    ],
)
def test_parse_money(text: str, expected: Decimal) -> None:
    assert parse_money(text) == expected


def test_parse_money_rejects_text_without_an_amount() -> None:
    with pytest.raises(ValueError, match="No monetary amount"):
        parse_money("Free Pony Express Delivery!")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Sauce Labs Backpack", "sauce-labs-backpack"),
        ("Sauce Labs Bolt T-Shirt", "sauce-labs-bolt-t-shirt"),
        ("Test.allTheThings() T-Shirt (Red)", "test.allthethings()-t-shirt-(red)"),
    ],
)
def test_slug_matches_the_product_ids_the_ui_uses(name: str, expected: str) -> None:
    assert slug(name) == expected


def test_sort_order_round_trips_through_its_label() -> None:
    for order in SortOrder:
        assert SortOrder.from_label(order.label) is order
    assert SortOrder.PRICE_LOW_TO_HIGH.value_key == "lohi"
    with pytest.raises(ValueError, match="Unknown sort order"):
        SortOrder.from_label("Colour")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Backpack", "'Backpack'"),
        ("O'Neil", '"O\'Neil"'),
        ("""say "hi" y'all""", """concat('say "hi" y', "'", 'all')"""),
    ],
)
def test_xpath_string_quotes_safely(value: str, expected: str) -> None:
    assert xpath_string(value) == expected
