"""Roku: the External Control Protocol (ECP) over plain HTTP.

Roku is the platform that proves the driver protocol is not WebDriver-shaped:
there is no Selenium, no Appium, no session object — just HTTP calls to port
8060 on the device and an XML view of the SceneGraph. Yet it satisfies the
same ``PlatformDriver`` protocol as Chrome does.

    protocol method     ECP request
    ------------------------------------------------------------------
    open(destination)   POST /launch/<channel>?contentId=<destination>
    page_source()       GET  /query/app-ui            (SceneGraph XML)
    find()              parse app-ui XML; match id / text / tag / xpath
    press(key)          POST /keypress/<Up|Down|Select|Back|Home|...>
    enter_text()        POST /keypress/Lit_<char> per character
    select()            FocusNavigator (focused="true" attribute + bounds) then Select
    current_location()  GET  /query/active-app + top scene name
    screenshot()        developer web server (digest auth, ``tv.dev_password``)

Only the standard library is used. **Status: stub** — real device behaviour is
untested here; the XML parsing is exercised by unit tests on captured samples.
"""

from __future__ import annotations

import base64
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import suppress
from typing import TYPE_CHECKING

from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.focus import FocusNavigator, Rect
from streamcart.core.driver.protocol import Direction, Element, Key
from streamcart.core.driver.registry import register_platform
from streamcart.core.errors import (
    AppUnreachableError,
    ConditionTimeoutError,
    DriverSessionError,
    ElementNotFoundError,
    UnsupportedSelectorError,
)
from streamcart.core.locators import By, Locator, Selector
from streamcart.core.platform import Platform, PlatformFamily

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

ROKU = Platform("roku", PlatformFamily.TV, default_target="roku-lab")

_ECP_KEYS: dict[Key, str] = {
    Key.UP: "Up",
    Key.DOWN: "Down",
    Key.LEFT: "Left",
    Key.RIGHT: "Right",
    Key.SELECT: "Select",
    Key.ENTER: "Enter",
    Key.BACK: "Back",
    Key.HOME: "Home",
    Key.MENU: "Info",
    Key.PLAY_PAUSE: "Play",
    Key.BACKSPACE: "Backspace",
}
_DIRECTION_KEYS: dict[Direction, Key] = {
    Direction.UP: Key.UP,
    Direction.DOWN: Key.DOWN,
    Direction.LEFT: Key.LEFT,
    Direction.RIGHT: Key.RIGHT,
}


class EcpClient:
    """Minimal ECP transport. Separate from the driver so it can be faked in tests."""

    def __init__(self, host: str, port: int = 8060, timeout: float = 5.0) -> None:
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def get(self, path: str) -> bytes:
        return self._request("GET", path)

    def post(self, path: str) -> bytes:
        return self._request("POST", path)

    def _request(self, method: str, path: str) -> bytes:
        request = urllib.request.Request(self.base + path, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            raise AppUnreachableError(f"ECP {method} {path} -> HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise DriverSessionError(f"Roku at {self.base} unreachable: {exc.reason}") from exc


def parse_bounds(value: str | None) -> Rect | None:
    """SceneGraph ``bounds="{x, y, w, h}"`` → Rect."""
    if not value:
        return None
    numbers = [float(part) for part in value.strip("{} ").replace(",", " ").split()]
    if len(numbers) != 4:
        return None
    return Rect(*numbers)


@register_platform(ROKU)
class RokuEcpDriver(BaseDriver):
    """Drives the StreamCart Roku channel through ECP."""

    # ECP has no console-log API (the BrightScript debug console is a telnet session on port 8085).
    capabilities = FAMILY_BASELINE[PlatformFamily.TV] | {Capability.HARDWARE_BACK}

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._ecp: EcpClient | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        """Verify the device answers ECP and the channel is installed."""
        tv = self.settings.tv
        if not tv.ecp_host:
            raise DriverSessionError("tv.ecp_host is not configured for this target")
        self._ecp = EcpClient(tv.ecp_host, tv.ecp_port, timeout=self.settings.timeouts.default)
        apps = ET.fromstring(self._ecp.get("/query/apps"))
        if not any(app.get("id") == tv.channel_id for app in apps.iter("app")):
            raise AppUnreachableError(f"Channel '{tv.channel_id}' is not installed on Roku {tv.ecp_host}")
        self.log.info("Roku %s answered ECP; channel %s present", tv.ecp_host, tv.channel_id)

    def stop(self) -> None:
        """Return to the Roku home screen so the next session starts clean."""
        if self._ecp is not None:
            with suppress(DriverSessionError, AppUnreachableError):
                self._ecp.post("/keypress/Home")
        self._ecp = None

    @property
    def _client(self) -> EcpClient:
        if self._ecp is None:
            raise DriverSessionError("Roku session is not started (call start())")
        return self._ecp

    # ----------------------------------------------------------- navigation
    def open(self, destination: str) -> None:
        """Launch the channel; a non-empty destination becomes the deep-link ``contentId``."""
        path = f"/launch/{self.settings.tv.channel_id}"
        if destination and destination != "/":
            path += "?" + urllib.parse.urlencode({"contentId": destination.lstrip("/"), "mediaType": "screen"})
        self._client.post(path)
        self.wait.until(self._channel_is_active, timeout=self.settings.timeouts.page_load, message="channel launch")

    def _channel_is_active(self) -> bool:
        active = ET.fromstring(self._client.get("/query/active-app"))
        app = active.find("app")
        return app is not None and app.get("id") == self.settings.tv.channel_id

    def current_location(self) -> str:
        """``<channel>/<top scene node id>`` — the closest thing a SceneGraph app has to a URL."""
        root = self._ui()
        scene = root.find(".//*[@name]")
        return f"{self.settings.tv.channel_id}/{scene.get('name') if scene is not None else ''}"

    # ------------------------------------------------------------- elements
    def _ui(self) -> ET.Element:
        return ET.fromstring(self._client.get("/query/app-ui"))

    def _matches(self, selector: Selector) -> Iterator[ET.Element]:
        root = self._ui()
        by, value = selector.by, selector.value
        if by in (By.TEST_ID, By.ID):
            yield from (n for n in root.iter() if n.get("id") == value or n.get("name") == value)
        elif by is By.TEXT:
            yield from (n for n in root.iter() if n.get("text") == value)
        elif by is By.ROKU_TAG:
            yield from root.iter(value)
        elif by is By.XPATH:
            yield from root.iterfind(value)  # ElementTree's XPath subset
        else:
            raise UnsupportedSelectorError(selector, self.platform)

    def _locate(self, locator: Locator, *, timeout: float | None) -> ET.Element:
        selector = locator.for_platform(self.platform)
        effective = self.wait.timeout if timeout is None else timeout

        def first_match() -> tuple[ET.Element] | None:
            # Wrapped in a tuple: an ElementTree node without children is *falsy*, which would
            # make the condition-based wait treat a found leaf node as "not there yet".
            node = next(self._matches(selector), None)
            return None if node is None else (node,)

        try:
            found = self.wait.until(first_match, timeout=effective, message=f"find {locator}")
        except ConditionTimeoutError:
            raise ElementNotFoundError(locator, self.platform, effective) from None
        if found is None:  # unreachable: wait.until only returns truthy values
            raise ElementNotFoundError(locator, self.platform, effective)
        return found[0]

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return RokuNodeHandle(self, self._locate(locator, timeout=timeout), locator)

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        selector = locator.for_platform(self.platform)
        return [RokuNodeHandle(self, node, locator) for node in self._matches(selector)]

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        try:
            self._locate(locator, timeout=timeout)
        except ElementNotFoundError:
            return False
        return True

    # ---------------------------------------------------------------- input
    def press(self, key: Key) -> None:
        self._client.post(f"/keypress/{_ECP_KEYS[key]}")

    def type_text(self, text: str) -> None:
        """ECP literal keypresses — the Roku way to type without the on-screen keyboard."""
        for char in text:
            self._client.post(f"/keypress/Lit_{urllib.parse.quote(char, safe='')}")

    # --------------------------------------------------------------- focus
    def _focused_rect(self) -> Rect | None:
        focused = next((n for n in self._ui().iter() if n.get("focused") == "true"), None)
        return parse_bounds(focused.get("bounds")) if focused is not None else None

    def _settle(self) -> None:
        """Wait for the focus move to render — a condition wait, not a sleep; no move is also an answer."""
        before = self._focused_rect()
        with suppress(ConditionTimeoutError):
            self.wait.until(
                lambda: self._focused_rect() != before,
                timeout=self.settings.timeouts.focus_settle,
                message="focus move",
            )

    def navigator(self) -> FocusNavigator:
        return FocusNavigator(
            focused=self._focused_rect,
            press=lambda direction: self.press(_DIRECTION_KEYS[direction]),
            settle=self._settle,
            max_moves=self.settings.tv.max_focus_moves,
        )

    # ----------------------------------------------------------- diagnostics
    def screenshot(self) -> bytes:
        """Via the developer web server (port 80, digest auth) — needs ``tv.dev_password``."""
        tv = self.settings.tv
        if tv.dev_password is None:
            raise DriverSessionError("Roku screenshots need tv.dev_password (STREAMCART_TV__DEV_PASSWORD)")
        credentials = base64.b64encode(f"rokudev:{tv.dev_password.get_secret_value()}".encode()).decode()
        request = urllib.request.Request(
            f"http://{tv.ecp_host}/pkgs/dev.jpg", headers={"Authorization": f"Basic {credentials}"}
        )
        with urllib.request.urlopen(request, timeout=self.settings.timeouts.default) as response:
            return bytes(response.read())

    def page_source(self) -> str:
        return self._client.get("/query/app-ui").decode("utf-8", errors="replace")


class RokuNodeHandle:
    """``Element`` over a SceneGraph node snapshot from ``/query/app-ui``."""

    def __init__(self, driver: RokuEcpDriver, node: ET.Element, locator: Locator) -> None:
        self._driver = driver
        self._node = node
        self._locator = locator

    @property
    def locator(self) -> Locator:
        return self._locator

    def _fresh(self) -> ET.Element:
        self._node = self._driver._locate(self._locator, timeout=None)
        return self._node

    @property
    def text(self) -> str:
        return self._fresh().get("text", "")

    def is_displayed(self) -> bool:
        return self._fresh().get("visible", "true") != "false"

    def is_enabled(self) -> bool:
        return self._fresh().get("focusable", "true") != "false"

    def attribute(self, name: str) -> str | None:
        return self._fresh().get(name)

    def _rect(self) -> Rect:
        bounds = parse_bounds(self._fresh().get("bounds"))
        if bounds is None:
            raise ElementNotFoundError(self._locator, self._driver.platform, 0.0)
        return bounds

    def select(self) -> None:
        """d-pad the focus onto this node, then press Select."""
        self._driver.navigator().move_to(self._rect)
        self._driver.press(Key.SELECT)

    def enter_text(self, text: str, *, clear: bool = True) -> None:
        """Focus the field, then type with literal keypresses."""
        self.select()
        if clear:
            for _ in self._fresh().get("text", ""):
                self._driver.press(Key.BACKSPACE)
        self._driver.type_text(text)
        self._driver.press(Key.BACK)  # leave the keyboard

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        selector = locator.for_platform(self._driver.platform)
        for node in self._fresh().iter():
            if selector.by in (By.TEST_ID, By.ID) and node.get("id") == selector.value:
                return RokuNodeHandle(self._driver, node, locator)
            if selector.by is By.TEXT and node.get("text") == selector.value:
                return RokuNodeHandle(self._driver, node, locator)
        raise ElementNotFoundError(locator, self._driver.platform, timeout or 0.0)

    def find_all(self, locator: Locator) -> list[Element]:
        selector = locator.for_platform(self._driver.platform)
        nodes = self._fresh().iter(selector.value) if selector.by is By.ROKU_TAG else self._fresh().iter()
        wanted = selector.value
        return [
            RokuNodeHandle(self._driver, node, locator)
            for node in nodes
            if selector.by is By.ROKU_TAG or node.get("id") == wanted or node.get("text") == wanted
        ]
