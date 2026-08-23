"""The product catalogue — the oracle for what the inventory should show."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from streamcart.core.errors import ConfigurationError
from streamcart.testdata.loader import data_file, read_mapping

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Product:
    name: str
    price: Decimal


class ProductCatalogue:
    FILE_NAME = "products.yaml"

    def __init__(self, products: Sequence[Product], *, tax_rate: Decimal) -> None:
        self._products = list(products)
        self.tax_rate = tax_rate

    @classmethod
    def from_file(cls, path: Path) -> ProductCatalogue:
        raw = read_mapping(path)
        try:
            products = [Product(name=str(p["name"]), price=Decimal(str(p["price"]))) for p in raw.get("products", [])]
            tax_rate = Decimal(str(raw.get("tax_rate", "0")))
        except (KeyError, TypeError, ArithmeticError) as exc:
            raise ConfigurationError(f"{path}: each product needs a name and a decimal price ({exc})") from exc
        return cls(products, tax_rate=tax_rate)

    @classmethod
    def from_settings(cls, settings: Settings) -> ProductCatalogue:
        return cls.from_file(data_file(settings.data_dir, cls.FILE_NAME))

    def __iter__(self) -> Iterator[Product]:
        return iter(self._products)

    def __len__(self) -> int:
        return len(self._products)

    def names(self) -> list[str]:
        return [p.name for p in self._products]

    def prices(self) -> list[Decimal]:
        return [p.price for p in self._products]

    def by_name(self, name: str) -> Product:
        for product in self._products:
            if product.name == name:
                return product
        raise ConfigurationError(f"Unknown product '{name}'. Known: {', '.join(self.names())} (data/{self.FILE_NAME}).")

    def expected_tax(self, item_total: Decimal) -> Decimal:
        """Tax as the product computes it: rate applied to the item total, rounded to the cent."""
        return (item_total * self.tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)
