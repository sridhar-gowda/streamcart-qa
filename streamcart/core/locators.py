"""Multi-platform locators.

A ``Locator`` is a *named* element with one ``Selector`` per platform or
family it exists on. Pages and Components declare locators; adapters resolve
them with ``locator.for_platform(driver.platform)``. Nothing above the adapter
layer ever holds a raw CSS string or an Appium strategy.

Keys are open: any registered platform name (``roku=``), any family name
(``web=``, ``mobile=``, ``tv=``) or ``any=`` as the catch-all. Resolution is
platform → family → any, so a new TV platform is covered by every ``tv=``
selector on day one and can override individual elements with its own key —
without touching this module.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum

from streamcart.core.errors import LocatorNotDefinedError
from streamcart.core.platform import Platform

ANY = "any"
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*$")


def xpath_string(value: str) -> str:
    """Quote ``value`` as an XPath string literal (embedded quotes handled via ``concat``)."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in value.split("'")) + ")"


class By(str, Enum):
    """Selector strategies. Each adapter maps these onto its library's own."""

    TEST_ID = "test_id"  # the shared data-test convention; each adapter maps it natively
    CSS = "css"
    XPATH = "xpath"
    ID = "id"
    NAME = "name"
    LINK_TEXT = "link_text"
    TEXT = "text"  # visible text match — the lingua franca of TV automation
    ACCESSIBILITY_ID = "accessibility_id"  # iOS accessibilityIdentifier / Android contentDescription
    RESOURCE_ID = "resource_id"  # Android resource-id
    IOS_PREDICATE = "ios_predicate"
    ANDROID_UIAUTOMATOR = "android_uiautomator"
    ROKU_TAG = "roku_tag"  # SceneGraph node type, e.g. "Button"

    def __call__(self, value: str) -> Selector:
        """``By.CSS("[data-test=x]")`` reads better than ``Selector(By.CSS, ...)``."""
        return Selector(self, value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Selector:
    """A single strategy/value pair."""

    by: By
    value: str

    def __str__(self) -> str:
        return f"{self.by}={self.value!r}"


@dataclass(frozen=True)
class Locator:
    """A named element with a selector per platform or family.

    Build one with :meth:`define` or, for elements that follow the shared
    ``data-test`` convention on every platform, :meth:`test_id`.
    """

    name: str
    _entries: tuple[tuple[str, Selector], ...] = field(default=(), repr=False, compare=True)

    # ----------------------------------------------------------------- builders
    @classmethod
    def define(cls, name: str, **selectors: Selector) -> Locator:
        """``Locator.define("checkout", web=By.CSS(...), tv=By.TEXT("Checkout"), roku=By.ID("checkoutBtn"))``.

        Keys are platform names, family names or ``any``. A platform key always
        beats its family key, which beats ``any``.
        """
        if not selectors:
            raise ValueError(f"Locator '{name}' must define at least one selector")
        entries: list[tuple[str, Selector]] = []
        for key, selector in selectors.items():
            if not _KEY_PATTERN.match(key):
                raise ValueError(f"Locator '{name}': key {key!r} must be a lowercase platform or family name")
            if not isinstance(selector, Selector):
                raise TypeError(f"Locator '{name}': {key}= must be a Selector, got {type(selector).__name__}")
            entries.append((key, selector))
        return cls(name, tuple(entries))

    @classmethod
    def test_id(cls, name: str, test_id: str) -> Locator:
        """The shared ``data-test`` convention, resolved natively by each adapter.

        Web renders ``data-test="<id>"``; the mobile and TV apps expose the same
        id as the accessibility identifier; Roku's SceneGraph uses the node id.
        The locator carries only the id — *how* it is matched is the adapter's
        business, so one line in a Page covers every platform, including ones
        that do not exist yet.
        """
        return cls.define(name, any=By.TEST_ID(test_id))

    # ---------------------------------------------------------------- queries
    @property
    def selectors(self) -> Mapping[str, Selector]:
        return dict(self._entries)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self._entries)

    def supports(self, platform: Platform) -> bool:
        return any(key in (platform.name, platform.family.value, ANY) for key in self.keys)

    def for_platform(self, platform: Platform) -> Selector:
        """Resolve platform → family → any, or raise ``LocatorNotDefinedError``."""
        table = dict(self._entries)
        for key in (platform.name, platform.family.value, ANY):
            if key in table:
                return table[key]
        raise LocatorNotDefinedError(self, platform)

    def __iter__(self) -> Iterator[tuple[str, Selector]]:
        return iter(self._entries)

    def __str__(self) -> str:
        return self.name
