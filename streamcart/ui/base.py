"""``Component`` and ``Page`` — the two building blocks of the UI model.

A Component is a reusable piece of UI with an optional root. It can be

- **screen-level** (no root): ``Header(driver)`` — locators resolve against the whole screen;
- **rooted by locator**: ``ErrorBanner`` with ``ROOT = Locator.test_id(...)``;
- **rooted by element**: ``ProductCard(driver, root=element)`` for one item of a list;
- **scoped**: ``Button(driver, locator, within=card_element)``.

Roots are re-resolved on every access rather than cached, so a React
re-render or a rebuilt SceneGraph never hands a stale handle to a Task.

A Page is a Component that also knows its ``PATH`` (URL, deep link or screen
id) and a ``MARKER`` element that exists only on that page.
"""

from __future__ import annotations

from typing import ClassVar

from streamcart.core.driver.protocol import Element, PlatformDriver
from streamcart.core.errors import ElementNotFoundError, FrameworkError
from streamcart.core.locators import Locator
from streamcart.core.waits import Waiter


class Component:
    ROOT: ClassVar[Locator | None] = None

    def __init__(
        self,
        driver: PlatformDriver,
        *,
        root: Element | None = None,
        locator: Locator | None = None,
        within: Element | None = None,
    ) -> None:
        self.driver = driver
        self._root_element = root
        self._root_locator = locator if locator is not None else self.ROOT
        self._within = within

    # ------------------------------------------------------------------ root
    @property
    def root(self) -> Element:
        """The component's root element, resolved fresh."""
        if self._root_element is not None:
            return self._root_element
        if self._root_locator is None:
            raise FrameworkError(f"{type(self).__name__} is screen-level and has no root element")
        return self._scope_find(self._root_locator, timeout=None)

    def _scope_find(self, locator: Locator, *, timeout: float | None) -> Element:
        if self._within is not None:
            return self._within.find(locator, timeout=timeout)
        return self.driver.find(locator, timeout=timeout)

    def _has_root(self) -> bool:
        return self._root_element is not None or self._root_locator is not None

    # -------------------------------------------------------------- lookups
    def element(self, locator: Locator, *, timeout: float | None = None) -> Element:
        """One element inside this component (or on the screen if it has no root)."""
        if self._has_root():
            return self.root.find(locator, timeout=timeout)
        return self._scope_find(locator, timeout=timeout)

    def elements(self, locator: Locator) -> list[Element]:
        if self._has_root():
            return self.root.find_all(locator)
        if self._within is not None:
            return self._within.find_all(locator)
        return self.driver.find_all(locator, timeout=0)

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        try:
            self.element(locator, timeout=timeout)
        except ElementNotFoundError:
            return False
        return True

    def is_displayed(self, *, timeout: float = 0.0) -> bool:
        """Whether the component's root is on screen right now (or within ``timeout``)."""
        if self._root_element is not None:
            return self._root_element.is_displayed()
        if self._root_locator is None:
            return True
        try:
            return self._scope_find(self._root_locator, timeout=timeout).is_displayed()
        except ElementNotFoundError:
            return False

    # ----------------------------------------------------------------- waits
    @property
    def wait(self) -> Waiter:
        return self.driver.wait

    def wait_until_displayed(self, *, timeout: float | None = None) -> None:
        self.wait.until(self.is_displayed, timeout=timeout, message=f"{type(self).__name__} displayed")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} root={self._root_locator or self._root_element}>"


class Page(Component):
    """A screen of the product: a path to open it and a marker that proves it is showing."""

    PATH: ClassVar[str] = "/"
    MARKER: ClassVar[Locator]

    def open(self) -> None:
        """Navigate straight to this page (URL on web, deep link or screen id elsewhere)."""
        self.driver.open(self.PATH)

    def is_displayed(self, *, timeout: float = 0.0) -> bool:
        return self.driver.is_present(self.MARKER, timeout=timeout)
