from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from streamcart.screenplay.actor import Actor, Question
from streamcart.ui.components import SortOrder
from streamcart.ui.pages import InventoryPage


@dataclass(frozen=True)
class ProductSummary:
    name: str
    description: str
    price: Decimal
    image_source: str
    in_cart: bool


class TheProductNames(Question[list[str]]):
    """Names in display order."""

    def answered_by(self, actor: Actor) -> list[str]:
        return InventoryPage(actor.driver).product_names()


class TheProductPrices(Question[list[Decimal]]):
    """Prices in display order."""

    def answered_by(self, actor: Actor) -> list[Decimal]:
        return InventoryPage(actor.driver).product_prices()


class TheProducts(Question[list[ProductSummary]]):
    """Everything shown on each card, in display order."""

    def answered_by(self, actor: Actor) -> list[ProductSummary]:
        return [
            ProductSummary(card.name, card.description, card.price, card.image_source, card.is_in_cart())
            for card in InventoryPage(actor.driver).products()
        ]


class TheProduct(Question[ProductSummary]):
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def named(cls, name: str) -> TheProduct:
        return cls(name)

    def answered_by(self, actor: Actor) -> ProductSummary:
        card = InventoryPage(actor.driver).product(self.name)
        return ProductSummary(card.name, card.description, card.price, card.image_source, card.is_in_cart())

    def __str__(self) -> str:
        return f"the product '{self.name}'"


class TheCartBadgeCount(Question[int]):
    def answered_by(self, actor: Actor) -> int:
        return InventoryPage(actor.driver).header.cart_badge.count


class TheActiveSortOrder(Question[SortOrder]):
    def answered_by(self, actor: Actor) -> SortOrder:
        return InventoryPage(actor.driver).sort.active
