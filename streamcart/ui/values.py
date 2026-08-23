"""Typed reads: turning on-screen text into values the rest of the framework can reason about."""

from __future__ import annotations

import re
from decimal import Decimal

_MONEY = re.compile(r"\$\s*(\d[\d,]*\.\d{2})")


def parse_money(text: str) -> Decimal:
    """``"Item total: $29.99"`` → ``Decimal("29.99")``."""
    match = _MONEY.search(text)
    if match is None:
        raise ValueError(f"No monetary amount in {text!r}")
    return Decimal(match.group(1).replace(",", ""))


def slug(name: str) -> str:
    """The product's identifier in element ids: ``"Sauce Labs Backpack"`` → ``"sauce-labs-backpack"``."""
    return name.strip().lower().replace(" ", "-")
