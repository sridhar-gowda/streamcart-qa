"""``BaseDriver`` — the class adapters extend.

The protocol in ``protocol.py`` is what *consumers* see; this is what
*implementers* get: capability negotiation, a configured ``Waiter``, and
guard-railed defaults for the platform-specific actions so an adapter that
declares ``HOVER`` but forgets to implement it fails loudly.

One adapter class may drive several platforms (one Appium adapter for iOS and
Android); the instance knows which one it is from ``settings.platform``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, TypeVar

from streamcart.core.capabilities import Capability
from streamcart.core.driver.protocol import Direction, Element, Key
from streamcart.core.errors import CapabilityNotSupportedError, ConfigurationError
from streamcart.core.locators import Locator
from streamcart.core.logs import get_logger
from streamcart.core.platform import Platform
from streamcart.core.waits import Waiter

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

T = TypeVar("T")


class BaseDriver(ABC):
    """Shared behaviour for every platform adapter.

    ``platforms`` is stamped by ``@register_platform``. ``capabilities`` is a
    class attribute that an adapter may refine per instance (an Android build
    has a hardware back button, an iOS build does not).
    """

    platforms: ClassVar[tuple[Platform, ...]] = ()
    capabilities: frozenset[Capability] = frozenset()

    @classmethod
    def declared_capabilities(cls, platform: Platform) -> frozenset[Capability]:
        """What this adapter can do on ``platform`` — known *without* a session.

        The execution platform uses it at collection time to skip scenarios
        tagged ``@requires:<capability>`` with a reason instead of starting a
        device to find out. Adapters serving several platforms override it.
        """
        return cls.capabilities

    def __init__(self, settings: Settings) -> None:
        platform = settings.platform
        if self.platforms and platform.name not in {p.name for p in self.platforms}:
            served = ", ".join(p.name for p in self.platforms)
            raise ConfigurationError(f"{type(self).__name__} drives {served}, not '{platform}'")
        self.platform: Platform = platform
        self.capabilities = type(self).declared_capabilities(platform)
        self.settings = settings
        self.wait = Waiter(timeout=settings.timeouts.default, interval=settings.timeouts.poll_interval)
        self.log = get_logger(f"driver.{platform.name}")

    # ---------------------------------------------------------- capabilities
    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.supports(capability):
            raise CapabilityNotSupportedError(capability, self.platform)

    # ---------------------------------------------------------------- waits
    def wait_until(self, condition: Callable[[], T], *, timeout: float | None = None, message: str = "") -> T:
        return self.wait.until(condition, timeout=timeout, message=message or "condition not met")

    # --------------------------------------------- platform-specific actions
    # Defaults enforce the declaration/implementation contract: if an adapter
    # declares the capability it MUST override the method.
    def hover(self, locator: Locator) -> None:
        self.require(Capability.HOVER)
        raise NotImplementedError(f"{type(self).__name__} declares HOVER but does not implement hover()")

    def swipe(self, direction: Direction, *, within: Locator | None = None) -> None:
        self.require(Capability.SWIPE)
        raise NotImplementedError(f"{type(self).__name__} declares SWIPE but does not implement swipe()")

    def long_press(self, locator: Locator) -> None:
        self.require(Capability.LONG_PRESS)
        raise NotImplementedError(f"{type(self).__name__} declares LONG_PRESS but does not implement long_press()")

    def console_logs(self) -> list[str]:
        if not self.supports(Capability.CONSOLE_LOGS):
            return []
        raise NotImplementedError(f"{type(self).__name__} declares CONSOLE_LOGS but does not implement console_logs()")

    # ------------------------------------------------------------- abstract
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def open(self, destination: str) -> None: ...

    @abstractmethod
    def current_location(self) -> str: ...

    @abstractmethod
    def find(self, locator: Locator, *, timeout: float | None = None) -> Element: ...

    @abstractmethod
    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]: ...

    @abstractmethod
    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool: ...

    @abstractmethod
    def press(self, key: Key) -> None: ...

    @abstractmethod
    def screenshot(self) -> bytes: ...

    @abstractmethod
    def page_source(self) -> str: ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} platform={self.platform.name}>"
