"""The platform driver boundary.

``protocol``  — what every platform driver looks like to the layers above
``base``      — the abstract class adapters extend (capability checks, waits)
``registry``  — ``@register_platform`` and ``create_driver``; discovers adapters
``adapters``  — the ONLY package allowed to import Selenium / Appium / ECP clients
"""

from streamcart.core.driver.protocol import Direction, Element, Key, PlatformDriver
from streamcart.core.driver.registry import create_driver, register_platform, registered_platforms

__all__ = [
    "Direction",
    "Element",
    "Key",
    "PlatformDriver",
    "create_driver",
    "register_platform",
    "registered_platforms",
]
