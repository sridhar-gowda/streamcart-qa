"""The ``PlatformDriver`` protocol — the contract every platform adapter fulfils.

This is the seam that makes the framework platform-agnostic. Method names
describe *intent*, not mechanism: ``select`` (not click/tap), ``enter_text``
(not send_keys), ``open`` (not get). Each family interprets them:

    ============  ================  =====================  ===========================
    method        Web               Mobile                 TV
    ============  ================  =====================  ===========================
    open          navigate to URL   launch / deep link     launch channel / deep link
    select        click             tap                    move focus to node, press OK
    enter_text    type              tap + on-screen keys   focus field, d-pad keyboard
    press         keyboard key      hardware key           remote button
    ============  ================  =====================  ===========================

Upper layers type-hint against these protocols, never against a concrete
adapter. ``BaseDriver`` (``base.py``) gives implementers the shared behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Protocol, TypeVar, runtime_checkable

from streamcart.core.capabilities import Capability
from streamcart.core.locators import Locator
from streamcart.core.platform import Platform
from streamcart.core.waits import Waiter

T = TypeVar("T")


class Key(str, Enum):
    """Keys a user can press. Adapters map them to keyboard, hardware or remote keys."""

    ENTER = "enter"
    ESCAPE = "escape"
    TAB = "tab"
    BACKSPACE = "backspace"
    BACK = "back"  # Android back / Fire TV back / Roku back / Apple TV menu
    HOME = "home"
    MENU = "menu"
    SELECT = "select"  # remote OK button
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PLAY_PAUSE = "play_pause"


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@runtime_checkable
class Element(Protocol):
    """A handle on one UI element, resolved for the current platform.

    Elements are short-lived: Components resolve them per interaction rather
    than caching, so a re-rendered React list or a rebuilt SceneGraph node
    never yields a stale reference to the layers above.
    """

    @property
    def locator(self) -> Locator: ...

    @property
    def text(self) -> str:
        """Visible text. Empty string when the element has none."""
        ...

    def is_displayed(self) -> bool: ...

    def is_enabled(self) -> bool: ...

    def attribute(self, name: str) -> str | None:
        """A platform attribute: DOM attribute, view property, SceneGraph field."""
        ...

    def select(self) -> None:
        """Activate the element — click, tap, or focus-then-OK."""
        ...

    def enter_text(self, text: str, *, clear: bool = True) -> None: ...

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        """Resolve a descendant. This is what makes Components composable."""
        ...

    def find_all(self, locator: Locator) -> list[Element]: ...


@runtime_checkable
class PlatformDriver(Protocol):
    """What the framework needs from a platform. Implemented once per platform."""

    @property
    def platform(self) -> Platform: ...

    @property
    def capabilities(self) -> frozenset[Capability]: ...

    @property
    def wait(self) -> Waiter:
        """A ``Waiter`` bound to the configured timeouts."""
        ...

    # ----------------------------------------------------------- lifecycle
    def start(self) -> None:
        """Open the session. Raises ``DriverSessionError`` if it cannot."""
        ...

    def stop(self) -> None:
        """Close the session. Must be safe to call twice."""
        ...

    # ---------------------------------------------------------- navigation
    def open(self, destination: str) -> None:
        """Go somewhere: a URL, a deep link, a screen name. Raises ``AppUnreachableError``."""
        ...

    def current_location(self) -> str:
        """Where we are: URL, activity/view-controller name, or SceneGraph scene."""
        ...

    # ------------------------------------------------------------ elements
    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        """Resolve one element, waiting up to ``timeout`` (default: configured).
        Raises ``ElementNotFoundError``."""
        ...

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        """Resolve every match. Waits for at least one unless ``timeout`` is 0."""
        ...

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool: ...

    def wait_until(self, condition: Callable[[], T], *, timeout: float | None = None, message: str = "") -> T: ...

    # ---------------------------------------------------------------- input
    def press(self, key: Key) -> None: ...

    # ---------------------------------------------- platform-specific actions
    def hover(self, locator: Locator) -> None:
        """Requires ``Capability.HOVER``."""
        ...

    def swipe(self, direction: Direction, *, within: Locator | None = None) -> None:
        """Requires ``Capability.SWIPE``."""
        ...

    def long_press(self, locator: Locator) -> None:
        """Requires ``Capability.LONG_PRESS``."""
        ...

    # ---------------------------------------------------------- diagnostics
    def screenshot(self) -> bytes:
        """PNG bytes."""
        ...

    def page_source(self) -> str:
        """DOM, view hierarchy, or SceneGraph XML — whatever the platform has."""
        ...

    def console_logs(self) -> list[str]:
        """Browser console / logcat / debug console lines collected so far."""
        ...

    # ---------------------------------------------------------- capabilities
    def supports(self, capability: Capability) -> bool: ...

    def require(self, capability: Capability) -> None:
        """Raise ``CapabilityNotSupportedError`` unless supported."""
        ...
