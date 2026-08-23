"""TV platforms driven by Appium: Fire TV (UiAutomator2) and Apple TV (XCUITest).

Both are "Appium devices", but the interaction model is a remote control, not
touch — which is exactly why they get their own adapter rather than a flag on
the mobile one. ``select()`` here means *move focus with the d-pad until the
target has it, then press OK*; the shared algorithm lives in
``core.driver.focus.FocusNavigator``, this adapter only supplies how to read
focus and how to press a key on each device:

    ============  =====================================  ==============================
                  Fire TV                                Apple TV
    ============  =====================================  ==============================
    read focus    ``driver.switch_to.active_element``    element with ``hasFocus == true``
    press key     ``press_keycode`` (Android KeyEvent)   ``mobile: pressButton``
    text entry    ``send_keys`` (ADB injects text)       Siri Remote keyboard via ``send_keys``
    back          KEYCODE_BACK                           MENU button
    ============  =====================================  ==============================

**Status: stub** — see ``appium_mobile.py`` for what that means.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.focus import FocusNavigator, Rect
from streamcart.core.driver.protocol import Direction, Element, Key
from streamcart.core.driver.registry import register_platform
from streamcart.core.errors import (
    ConditionTimeoutError,
    DriverSessionError,
    ElementNotFoundError,
    UnsupportedSelectorError,
)
from streamcart.core.locators import By, Locator, Selector
from streamcart.core.platform import Platform, PlatformFamily

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

FIRE_TV = Platform("firetv", PlatformFamily.TV, default_target="firetv-lab", aliases=("fire-tv", "amazon-firetv"))
APPLE_TV = Platform("appletv", PlatformFamily.TV, default_target="appletv-sim", aliases=("apple-tv", "tvos"))

_FIRETV_KEYCODES: dict[Key, int] = {
    Key.UP: 19,
    Key.DOWN: 20,
    Key.LEFT: 21,
    Key.RIGHT: 22,
    Key.SELECT: 23,
    Key.ENTER: 66,
    Key.BACK: 4,
    Key.HOME: 3,
    Key.MENU: 82,
    Key.PLAY_PAUSE: 85,
    Key.BACKSPACE: 67,
}
_TVOS_BUTTONS: dict[Key, str] = {
    Key.UP: "up",
    Key.DOWN: "down",
    Key.LEFT: "left",
    Key.RIGHT: "right",
    Key.SELECT: "select",
    Key.ENTER: "select",
    Key.BACK: "menu",
    Key.MENU: "menu",
    Key.HOME: "home",
    Key.PLAY_PAUSE: "playpause",
}
_DIRECTION_KEYS: dict[Direction, Key] = {
    Direction.UP: Key.UP,
    Direction.DOWN: Key.DOWN,
    Direction.LEFT: Key.LEFT,
    Direction.RIGHT: Key.RIGHT,
}


@register_platform(FIRE_TV, APPLE_TV)
class AppiumTvDriver(BaseDriver):
    """Drives the Fire TV and Apple TV apps through Appium with remote-control semantics."""

    capabilities = FAMILY_BASELINE[PlatformFamily.TV]

    @classmethod
    def declared_capabilities(cls, platform: Platform) -> frozenset[Capability]:
        if platform.name == "firetv":
            return cls.capabilities | {Capability.HARDWARE_BACK}
        return cls.capabilities

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._driver: Any = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        mobile = self.settings.mobile
        if not mobile.appium_url:
            raise DriverSessionError("mobile.appium_url is not configured for this target")
        try:
            from appium import webdriver
            from appium.options.android import UiAutomator2Options
            from appium.options.ios import XCUITestOptions
        except ImportError as exc:  # pragma: no cover
            raise DriverSessionError("Appium client not installed: uv sync --extra mobile") from exc
        options: Any
        if self.platform.name == "firetv":
            options = UiAutomator2Options()
            options.app_package = mobile.app_package
            options.app_activity = mobile.app_activity
            options.udid = mobile.udid  # Fire TV over network ADB: "<ip>:5555"
        else:
            options = XCUITestOptions()
            options.bundle_id = mobile.bundle_id
            options.platform_name = "tvOS"
        options.device_name = mobile.device_name
        options.platform_version = mobile.platform_version
        options.app = mobile.app
        options.new_command_timeout = mobile.new_command_timeout
        for name, value in mobile.capabilities.items():
            options.set_capability(name, value)
        try:
            self._driver = webdriver.Remote(mobile.appium_url, options=options)
        except Exception as exc:
            raise DriverSessionError(f"Could not create Appium session at {mobile.appium_url}: {exc}") from exc

    def stop(self) -> None:
        if self._driver is None:
            return
        try:
            self._driver.quit()
        finally:
            self._driver = None

    @property
    def _raw(self) -> Any:
        if self._driver is None:
            raise DriverSessionError("Appium session is not started (call start())")
        return self._driver

    # ----------------------------------------------------------- navigation
    def open(self, destination: str) -> None:
        """Launch the app or deep-link (Fire TV: ``am start`` intent; tvOS: URL scheme)."""
        mobile = self.settings.mobile
        if not destination or destination == "/":
            self._raw.activate_app(mobile.app_package if self.platform.name == "firetv" else mobile.bundle_id)
            return
        scheme = self.settings.app.deep_link_scheme
        self._raw.get(destination if "://" in destination else f"{scheme}{destination.lstrip('/')}")

    def current_location(self) -> str:
        if self.platform.name == "firetv":
            return str(self._raw.current_activity)
        root = self._raw.find_element("class name", "XCUIElementTypeApplication")
        return str(root.get_attribute("name") or "")

    # ------------------------------------------------------------- elements
    def _resolve(self, selector: Selector) -> tuple[str, str]:
        from appium.webdriver.common.appiumby import AppiumBy

        if selector.by is By.TEXT:
            return AppiumBy.XPATH, f"//*[@text={selector.value!r} or @label={selector.value!r}]"
        mapping = {
            By.TEST_ID: AppiumBy.ACCESSIBILITY_ID,
            By.ACCESSIBILITY_ID: AppiumBy.ACCESSIBILITY_ID,
            By.RESOURCE_ID: AppiumBy.ID,
            By.ID: AppiumBy.ID,
            By.XPATH: AppiumBy.XPATH,
            By.NAME: AppiumBy.NAME,
            By.IOS_PREDICATE: AppiumBy.IOS_PREDICATE,
            By.ANDROID_UIAUTOMATOR: AppiumBy.ANDROID_UIAUTOMATOR,
        }
        try:
            return mapping[selector.by], selector.value
        except KeyError:
            raise UnsupportedSelectorError(selector, self.platform) from None

    def _locate(self, locator: Locator, *, timeout: float | None, within: Any = None) -> Any:
        by, value = self._resolve(locator.for_platform(self.platform))
        scope = within if within is not None else self._raw
        effective = self.wait.timeout if timeout is None else timeout
        try:
            return self.wait.until(
                lambda: scope.find_element(by, value),
                timeout=effective,
                message=f"find {locator}",
                ignored=(Exception,),
            )
        except ConditionTimeoutError:
            raise ElementNotFoundError(locator, self.platform, effective) from None

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return TvElementHandle(self, self._locate(locator, timeout=timeout), locator)

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        by, value = self._resolve(locator.for_platform(self.platform))
        return [TvElementHandle(self, el, locator) for el in self._raw.find_elements(by, value)]

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        try:
            self._locate(locator, timeout=timeout)
        except ElementNotFoundError:
            return False
        return True

    # ---------------------------------------------------------------- input
    def press(self, key: Key) -> None:
        if self.platform.name == "firetv":
            self._raw.press_keycode(_FIRETV_KEYCODES[key])
        else:
            self._raw.execute_script("mobile: pressButton", {"name": _TVOS_BUTTONS[key]})

    # --------------------------------------------------------------- focus
    def _focused_rect(self) -> Rect | None:
        """Bounds of whatever currently holds focus, or None if nothing does."""
        if self.platform.name == "firetv":
            element = self._raw.switch_to.active_element
            rect = element.rect if element is not None else None
        else:
            focused = self._raw.find_elements("xpath", "//*[@hasFocus='true']")
            rect = focused[0].rect if focused else None
        return Rect(rect["x"], rect["y"], rect["width"], rect["height"]) if rect else None

    def _settle(self) -> None:
        """Let the focus animation finish — a *condition* wait on focus stability, not a sleep."""
        before = self._focused_rect()
        with suppress(ConditionTimeoutError):  # no move within the settle window is also an answer
            self.wait.until(
                lambda: self._focused_rect() != before,
                timeout=self.settings.timeouts.focus_settle,
                message="focus move",
            )  # focus did not move within the settle window; the navigator handles that

    def navigator(self) -> FocusNavigator:
        return FocusNavigator(
            focused=self._focused_rect,
            press=lambda direction: self.press(_DIRECTION_KEYS[direction]),
            settle=self._settle,
            max_moves=self.settings.tv.max_focus_moves,
        )

    # ----------------------------------------------------------- diagnostics
    def screenshot(self) -> bytes:
        return bytes(self._raw.get_screenshot_as_png())

    def page_source(self) -> str:
        return str(self._raw.page_source)


class TvElementHandle:
    """``Element`` over an Appium element with remote-control semantics."""

    def __init__(self, driver: AppiumTvDriver, element: Any, locator: Locator) -> None:
        self._driver = driver
        self._element = element
        self._locator = locator

    @property
    def locator(self) -> Locator:
        return self._locator

    @property
    def text(self) -> str:
        return str(self._element.text or "")

    def is_displayed(self) -> bool:
        return bool(self._element.is_displayed())

    def is_enabled(self) -> bool:
        return bool(self._element.is_enabled())

    def attribute(self, name: str) -> str | None:
        value = self._element.get_attribute(name)
        return None if value is None else str(value)

    def _rect(self) -> Rect:
        rect = self._element.rect
        return Rect(rect["x"], rect["y"], rect["width"], rect["height"])

    def select(self) -> None:
        """Move focus onto this element with the d-pad, then press OK."""
        self._driver.navigator().move_to(self._rect)
        self._driver.press(Key.SELECT)

    def enter_text(self, text: str, *, clear: bool = True) -> None:
        """Focus the field (select), then inject text; the on-screen keyboard is bypassed by Appium."""
        self.select()
        if clear:
            self._element.clear()
        self._element.send_keys(text)
        self._driver.press(Key.BACK)  # dismiss the keyboard

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return TvElementHandle(
            self._driver, self._driver._locate(locator, timeout=timeout, within=self._element), locator
        )

    def find_all(self, locator: Locator) -> list[Element]:
        by, value = self._driver._resolve(locator.for_platform(self._driver.platform))
        return [TvElementHandle(self._driver, el, locator) for el in self._element.find_elements(by, value)]
