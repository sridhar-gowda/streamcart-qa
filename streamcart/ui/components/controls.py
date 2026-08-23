"""Atomic controls: the vocabulary every page is written in.

Each control is rooted by the locator passed to it and exposes the one or two
primitives that kind of element has. Verbs are platform-neutral: a ``Button``
is *pressed* — a click on web, a tap on mobile, focus-then-OK on TV.
"""

from __future__ import annotations

from streamcart.core.driver.protocol import Element, PlatformDriver
from streamcart.core.locators import Locator
from streamcart.ui.base import Component


class Control(Component):
    def __init__(self, driver: PlatformDriver, locator: Locator, *, within: Element | None = None) -> None:
        super().__init__(driver, locator=locator, within=within)

    @property
    def locator(self) -> Locator:
        assert self._root_locator is not None
        return self._root_locator

    def is_enabled(self) -> bool:
        return self.root.is_enabled()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.locator}>"


class Button(Control):
    def press(self) -> None:
        self.root.select()

    @property
    def label(self) -> str:
        return self.root.text or (self.root.attribute("value") or "")


class Link(Control):
    def goto(self) -> None:
        self.root.select()

    @property
    def label(self) -> str:
        return self.root.text


class TextField(Control):
    def type(self, text: str, *, clear: bool = True) -> None:
        self.root.enter_text(text, clear=clear)

    def clear(self) -> None:
        self.root.enter_text("", clear=True)

    @property
    def value(self) -> str:
        return self.root.attribute("value") or ""

    @property
    def placeholder(self) -> str:
        return self.root.attribute("placeholder") or ""


class Text(Control):
    @property
    def text(self) -> str:
        return self.root.text


class Image(Control):
    @property
    def source(self) -> str:
        return self.root.attribute("src") or ""

    @property
    def alt(self) -> str:
        return self.root.attribute("alt") or ""
