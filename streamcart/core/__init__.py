"""Core contracts: everything above this package depends on these and nothing else.

Nothing in ``streamcart.core`` — except ``core.driver.adapters`` — may import an
automation library. That boundary is enforced by ruff's banned-api rules and by
``tests/framework/test_architecture.py``.
"""

from streamcart.core.capabilities import Capability
from streamcart.core.errors import FrameworkError
from streamcart.core.locators import By, Locator, Selector
from streamcart.core.platform import Platform, PlatformFamily

__all__ = ["By", "Capability", "FrameworkError", "Locator", "Platform", "PlatformFamily", "Selector"]
