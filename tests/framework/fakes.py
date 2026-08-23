"""Test doubles shared by framework self-tests."""

from __future__ import annotations

from streamcart.core.capabilities import Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.protocol import Element, Key
from streamcart.core.locators import Locator
from streamcart.core.platform import Platform, PlatformFamily

FAKE_TV = Platform("faketv", PlatformFamily.TV, default_target="fake-lab", aliases=("fake-tv",))
OTHER_TV = Platform("othertv", PlatformFamily.TV, default_target="other-lab")
FAKE_WEB = Platform("fakeweb", PlatformFamily.WEB, default_target="fake-browser")
__all__ = ["FAKE_TV", "FAKE_WEB", "OTHER_TV", "PNG", "FakeDriver", "FakeWebDriver"]


class FakeDriver(BaseDriver):
    """A concrete driver that never touches a device; records what was asked of it."""

    capabilities = frozenset({Capability.DPAD, Capability.SCREENSHOT})

    def __init__(self, settings: object) -> None:
        super().__init__(settings)  # type: ignore[arg-type]
        self.opened: list[str] = []
        self.pressed: list[Key] = []

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def open(self, destination: str) -> None:
        self.opened.append(destination)

    def current_location(self) -> str:
        return self.opened[-1] if self.opened else "home"

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        raise NotImplementedError

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        return []

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        return False

    def press(self, key: Key) -> None:
        self.pressed.append(key)

    def screenshot(self) -> bytes:
        return b""

    def page_source(self) -> str:
        return "<scene/>"


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class FakeWebDriver(FakeDriver):
    capabilities = frozenset(
        {Capability.OPEN_URL, Capability.HOVER, Capability.KEYBOARD, Capability.SCREENSHOT, Capability.PAGE_SOURCE}
    )

    def screenshot(self) -> bytes:
        return PNG

    def page_source(self) -> str:
        return "<html><body>fake</body></html>"

    def console_logs(self) -> list[str]:
        return ["INFO fake console line"]
