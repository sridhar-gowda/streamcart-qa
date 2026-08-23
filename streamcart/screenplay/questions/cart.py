from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from streamcart.screenplay.actor import Actor, Question
from streamcart.ui.pages import CartPage


@dataclass(frozen=True)
class CartLine:
    name: str
    price: Decimal
    quantity: int


class TheCartItems(Question[list[CartLine]]):
    def answered_by(self, actor: Actor) -> list[CartLine]:
        return [CartLine(item.name, item.price, item.quantity) for item in CartPage(actor.driver).items()]


class TheCartItemNames(Question[list[str]]):
    def answered_by(self, actor: Actor) -> list[str]:
        return CartPage(actor.driver).item_names()
