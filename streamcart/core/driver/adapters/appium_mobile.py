"""Mobile platforms (iOS, Android): Appium.

One adapter serves both mobile platforms because the Appium Python client is
identical for them; the differences — UiAutomator2 vs XCUITest, hardware back
button, id conventions — are data, not code paths. This is also why a
*platform* and an *adapter* are separate concepts in the framework.

**Status: stub.** The signatures, capability declarations and selector
mappings are real; the bodies are the calls a working implementation makes,
but nothing here has been executed against a device in this assessment
(SCENARIO.md: "You are NOT expected to have working Appium"). Appium is
imported lazily so the framework runs Web tests without it installed.

How the protocol maps onto touch:

    open(destination)   launch the app, or deep-link ``streamcart://<destination>``
    select()            tap
    enter_text()        tap the field, type through the on-screen keyboard
    press(BACK)         Android hardware back; iOS has no equivalent → CapabilityNotSupportedError
    swipe()             W3C pointer action from the centre of ``within`` (or the screen)
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.protocol import Direction, Element, Key
from streamcart.core.driver.registry import register_platform
from streamcart.core.errors import (
    CapabilityNotSupportedError,
    ConditionTimeoutError,
    DriverSessionError,
    ElementNotFoundError,
    UnsupportedSelectorError,
)
from streamcart.core.locators import By, Locator, Selector
from streamcart.core.platform import Platform, PlatformFamily

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

IOS = Platform("ios", PlatformFamily.MOBILE, default_target="iphone-sim", aliases=("iphone",))
ANDROID = Platform("android", PlatformFamily.MOBILE, default_target="pixel7-lab", aliases=("aos",))

# Android key events (https://developer.android.com/reference/android/view/KeyEvent)
_ANDROID_KEYCODES: dict[Key, int] = {
    Key.BACK: 4,
    Key.HOME: 3,
    Key.MENU: 82,
    Key.ENTER: 66,
    Key.TAB: 61,
    Key.BACKSPACE: 67,
    Key.UP: 19,
    Key.DOWN: 20,
    Key.LEFT: 21,
    Key.RIGHT: 22,
    Key.SELECT: 23,
    Key.PLAY_PAUSE: 85,
}


@register_platform(IOS, ANDROID)
class AppiumMobileDriver(BaseDriver):
    """Drives the native StreamCart apps through an Appium server."""

    capabilities = FAMILY_BASELINE[PlatformFamily.MOBILE]

    @classmethod
    def declared_capabilities(cls, platform: Platform) -> frozenset[Capability]:
        if platform.name == "android":
            return cls.capabilities | {Capability.HARDWARE_BACK}
        return cls.capabilities

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._driver: Any = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        """Open an Appium session with capabilities built from ``settings.mobile``."""
        mobile = self.settings.mobile
        if not mobile.appium_url:
            raise DriverSessionError("mobile.appium_url is not configured for this target")
        try:
            from appium import webdriver
            from appium.options.android import UiAutomator2Options
            from appium.options.ios import XCUITestOptions
        except ImportError as exc:  # pragma: no cover - exercised only without the mobile extra
            raise DriverSessionError("Appium client not installed: uv sync --extra mobile") from exc

        options: Any
        if self.platform.name == "android":
            options = UiAutomator2Options()
            options.app_package = mobile.app_package
            options.app_activity = mobile.app_activity
        else:
            options = XCUITestOptions()
            options.bundle_id = mobile.bundle_id
        options.device_name = mobile.device_name
        options.platform_version = mobile.platform_version
        options.udid = mobile.udid
        options.app = mobile.app
        options.new_command_timeout = mobile.new_command_timeout
        for name, value in mobile.capabilities.items():
            options.set_capability(name, value)
        try:
            self._driver = webdriver.Remote(mobile.appium_url, options=options)
        except Exception as exc:  # Appium raises WebDriverException subclasses; all mean "no session"
            raise DriverSessionError(f"Could not create Appium session at {mobile.appium_url}: {exc}") from exc
        self.log.info("Appium session started on %s (%s)", mobile.device_name, self.platform)

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
        """Deep-link into the app (``streamcart://inventory``); an empty destination re-activates it."""
        mobile = self.settings.mobile
        if not destination or destination == "/":
            app_id = mobile.app_package if self.platform.name == "android" else mobile.bundle_id
            self._raw.activate_app(app_id)
            return
        scheme = self.settings.app.deep_link_scheme
        url = destination if "://" in destination else f"{scheme}{destination.lstrip('/')}"
        self._raw.get(url)

    def current_location(self) -> str:
        """Current Android activity or, on iOS, the accessibility id of the root view."""
        if self.platform.name == "android":
            return str(self._raw.current_activity)
        root = self._raw.find_element("class name", "XCUIElementTypeApplication")
        return str(root.get_attribute("name") or "")

    # ------------------------------------------------------------- elements
    def _resolve(self, selector: Selector) -> tuple[str, str]:
        from appium.webdriver.common.appiumby import AppiumBy

        mapping = {
            By.TEST_ID: AppiumBy.ACCESSIBILITY_ID,  # the shared data-test id is the accessibility id
            By.ACCESSIBILITY_ID: AppiumBy.ACCESSIBILITY_ID,
            By.RESOURCE_ID: AppiumBy.ID,
            By.ID: AppiumBy.ID,
            By.XPATH: AppiumBy.XPATH,
            By.NAME: AppiumBy.NAME,
            By.IOS_PREDICATE: AppiumBy.IOS_PREDICATE,
            By.ANDROID_UIAUTOMATOR: AppiumBy.ANDROID_UIAUTOMATOR,
        }
        if selector.by is By.TEXT:
            return AppiumBy.XPATH, f"//*[@text={selector.value!r} or @label={selector.value!r}]"
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
                ignored=(Exception,),  # NoSuchElementException; kept generic to avoid importing selenium here
            )
        except ConditionTimeoutError:
            raise ElementNotFoundError(locator, self.platform, effective) from None

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return MobileElementHandle(self, self._locate(locator, timeout=timeout), locator)

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        by, value = self._resolve(locator.for_platform(self.platform))
        return [MobileElementHandle(self, el, locator) for el in self._raw.find_elements(by, value)]

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        try:
            self._locate(locator, timeout=timeout)
        except ElementNotFoundError:
            return False
        return True

    # ---------------------------------------------------------------- input
    def press(self, key: Key) -> None:
        """Hardware keys on Android; iOS only has HOME (``mobile: pressButton``)."""
        if self.platform.name == "android":
            self._raw.press_keycode(_ANDROID_KEYCODES[key])
            return
        if key is Key.HOME:
            self._raw.execute_script("mobile: pressButton", {"name": "home"})
            return
        raise CapabilityNotSupportedError(Capability.HARDWARE_BACK, self.platform)

    def swipe(self, direction: Direction, *, within: Locator | None = None) -> None:
        """A W3C pointer swipe across 60% of the element (or screen) in ``direction``."""
        self.require(Capability.SWIPE)
        if within is not None:
            rect = self._locate(within, timeout=None).rect
        else:
            size = self._raw.get_window_size()
            rect = {"x": 0, "y": 0, "width": size["width"], "height": size["height"]}
        cx, cy = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
        dx = rect["width"] * 0.3 * {"left": -1, "right": 1}.get(direction.value, 0)
        dy = rect["height"] * 0.3 * {"up": -1, "down": 1}.get(direction.value, 0)
        self._raw.execute_script(
            "mobile: swipeGesture" if self.platform.name == "android" else "mobile: swipe",
            {"left": cx + dx, "top": cy + dy, "width": 1, "height": 1, "direction": direction.value, "percent": 0.6},
        )

    def long_press(self, locator: Locator) -> None:
        self.require(Capability.LONG_PRESS)
        element = self._locate(locator, timeout=None)
        self._raw.execute_script("mobile: longClickGesture", {"elementId": element.id, "duration": 1000})

    # ----------------------------------------------------------- diagnostics
    def screenshot(self) -> bytes:
        return bytes(self._raw.get_screenshot_as_png())

    def page_source(self) -> str:
        """The view hierarchy as XML — what ``By.XPATH`` queries run against."""
        return str(self._raw.page_source)


class MobileElementHandle:
    """``Element`` over an Appium element."""

    def __init__(self, driver: AppiumMobileDriver, element: Any, locator: Locator) -> None:
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

    def select(self) -> None:
        """Tap."""
        self._element.click()

    def enter_text(self, text: str, *, clear: bool = True) -> None:
        """Tap the field then type via the on-screen keyboard; hide it afterwards where possible."""
        if clear:
            self._element.clear()
        self._element.send_keys(text)
        with suppress(Exception):  # not every screen shows a keyboard; hiding is best-effort
            self._driver._raw.hide_keyboard()

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return MobileElementHandle(
            self._driver, self._driver._locate(locator, timeout=timeout, within=self._element), locator
        )

    def find_all(self, locator: Locator) -> list[Element]:
        by, value = self._driver._resolve(locator.for_platform(self._driver.platform))
        return [MobileElementHandle(self._driver, el, locator) for el in self._element.find_elements(by, value)]
