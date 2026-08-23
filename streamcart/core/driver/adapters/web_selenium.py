"""Web platform: Selenium 4 WebDriver.

The only place the web stack touches Selenium. Everything that crosses the
boundary is translated:

    Selenium                                      →  framework
    ------------------------------------------------------------------
    NoSuchElementException (after waiting)        →  ElementNotFoundError
    ElementNotInteractable / ClickIntercepted     →  ElementNotInteractableError
    StaleElementReferenceException                →  re-resolve once, then as above
    SessionNotCreated / InvalidSessionId /
      NoSuchWindow / lost connection              →  DriverSessionError
    navigation lands on a browser error page      →  AppUnreachableError
    any other WebDriverException                  →  FrameworkError

Browsers are started through Selenium Manager (bundled with Selenium ≥ 4.6), so
no driver binaries are installed by hand; ``web.remote_url`` switches the same
code to a Grid or a cloud provider.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    InvalidSessionIdException,
    NoSuchElementException,
    NoSuchWindowException,
    SessionNotCreatedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By as SeleniumBy
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
from selenium.webdriver.remote.webelement import WebElement

from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.protocol import Element, Key
from streamcart.core.driver.registry import register_platform
from streamcart.core.errors import (
    AppUnreachableError,
    CapabilityNotSupportedError,
    ConditionTimeoutError,
    DriverSessionError,
    ElementNotFoundError,
    ElementNotInteractableError,
    FrameworkError,
    UnsupportedSelectorError,
)
from streamcart.core.locators import By, Locator, Selector, xpath_string
from streamcart.core.platform import Platform, PlatformFamily

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings

T = TypeVar("T")

WEB = Platform("web", PlatformFamily.WEB, default_target="chrome", aliases=("browser",))

_ERROR_PAGES = ("chrome-error://", "edge-error://", "about:neterror")
_KEYS: dict[Key, str] = {
    Key.ENTER: Keys.ENTER,
    Key.SELECT: Keys.ENTER,
    Key.ESCAPE: Keys.ESCAPE,
    Key.TAB: Keys.TAB,
    Key.BACKSPACE: Keys.BACKSPACE,
    Key.UP: Keys.ARROW_UP,
    Key.DOWN: Keys.ARROW_DOWN,
    Key.LEFT: Keys.ARROW_LEFT,
    Key.RIGHT: Keys.ARROW_RIGHT,
}


@register_platform(WEB)
class SeleniumWebDriver(BaseDriver):
    """Drives the StreamCart web app (SauceDemo in this assessment) in a browser."""

    capabilities = FAMILY_BASELINE[PlatformFamily.WEB]

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._driver: RemoteWebDriver | None = None
        self.input_anomalies = 0  # pointer clicks the browser dropped; surfaced in reports as an environment signal

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        web = self.settings.web
        options = self._build_options()
        try:
            if web.remote_url:
                self._driver = webdriver.Remote(command_executor=web.remote_url, options=options)
            else:
                factory: Callable[..., RemoteWebDriver] = {
                    "chrome": webdriver.Chrome,
                    "firefox": webdriver.Firefox,
                    "edge": webdriver.Edge,
                    "safari": webdriver.Safari,
                }[web.browser]
                self._driver = factory(options=options)
            self._driver.set_page_load_timeout(self.settings.timeouts.page_load)
            self._driver.set_script_timeout(self.settings.timeouts.script)
            self._driver.implicitly_wait(0)  # all waiting is explicit and condition-based
            if not web.headless:
                self._driver.set_window_size(*web.window_size)
        except (SessionNotCreatedException, WebDriverException) as exc:
            self._driver = None
            raise DriverSessionError(f"Could not start {web.browser}: {exc.msg}") from exc
        self.log.info("Started %s (%s) headless=%s", web.browser, web.remote_url or "local", web.headless)

    def stop(self) -> None:
        if self._driver is None:
            return
        try:
            self._driver.quit()
        except WebDriverException as exc:  # the session may already be gone; that is fine on shutdown
            self.log.debug("quit() raised %s", exc.__class__.__name__)
        finally:
            self._driver = None

    def _build_options(self) -> ArgOptions:
        web = self.settings.web
        width, height = web.window_size
        options: ArgOptions
        if web.browser in ("chrome", "edge"):
            options = webdriver.ChromeOptions() if web.browser == "chrome" else webdriver.EdgeOptions()
            if web.headless:
                options.add_argument("--headless=new")
            for arg in (
                f"--window-size={width},{height}",
                "--disable-gpu",
                "--no-sandbox",  # required inside containers
                "--disable-dev-shm-usage",  # avoids /dev/shm exhaustion in Docker
                "--disable-extensions",
                "--lang=en-US",
            ):
                options.add_argument(arg)
            options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        elif web.browser == "firefox":
            options = webdriver.FirefoxOptions()
            if web.headless:
                options.add_argument("-headless")
            options.add_argument(f"--width={width}")
            options.add_argument(f"--height={height}")
        else:
            options = webdriver.SafariOptions()  # Safari has no headless mode
        options.page_load_strategy = web.page_load_strategy
        for arg in web.extra_args:
            options.add_argument(arg)
        for name, value in web.capabilities.items():
            options.set_capability(name, value)
        return options

    @property
    def _raw(self) -> RemoteWebDriver:
        if self._driver is None:
            raise DriverSessionError("Browser session is not started (call start())")
        return self._driver

    @contextmanager
    def _translating(self, action: str) -> Iterator[None]:
        """Translate Selenium session/transport failures into framework errors."""
        try:
            yield
        except (InvalidSessionIdException, NoSuchWindowException) as exc:
            raise DriverSessionError(f"{action}: browser session lost ({exc.msg})") from exc
        except ElementClickInterceptedException as exc:
            raise ElementNotInteractableError(f"{action}: another element intercepts the click ({exc.msg})") from exc
        except ElementNotInteractableException as exc:
            raise ElementNotInteractableError(f"{action}: element not interactable ({exc.msg})") from exc
        except WebDriverException as exc:
            message = str(exc.msg or "")
            if "not connected" in message or "connection refused" in message.lower():
                raise DriverSessionError(f"{action}: lost connection to the browser ({message})") from exc
            raise FrameworkError(f"{action}: {type(exc).__name__}: {message}") from exc

    # ----------------------------------------------------------- navigation
    def open(self, destination: str) -> None:
        url = destination if urlparse(destination).scheme else urljoin(self.settings.app.base_url + "/", destination)
        try:
            self._raw.get(url)
        except TimeoutException as exc:
            raise AppUnreachableError(f"{url} did not load within {self.settings.timeouts.page_load:.0f}s") from exc
        except WebDriverException as exc:
            message = str(exc.msg or "")
            # Firefox: "Reached error page"; Chromium DNS failures: "net::ERR_NAME_NOT_RESOLVED"
            if "Reached error page" in message or "net::ERR_" in message:
                raise AppUnreachableError(f"{url}: {message.splitlines()[0]}") from exc
            raise DriverSessionError(f"open({url}): {message}") from exc
        if self._landed_on_error_page():  # Chromium renders connection failures as a page, no exception
            raise AppUnreachableError(f"{url}: browser could not reach the application")

    _ERROR_PAGE_PROBE = """
        if (document.body && /\\bneterror\\b/.test(document.body.className)) return 'chrome:neterror';
        if (document.getElementById('main-frame-error')) return 'chromium:main-frame-error';
        const nav = performance.getEntriesByType('navigation')[0];
        if (nav && nav.responseStatus === 0 && nav.transferSize === 0 && location.protocol.startsWith('http')) {
            return 'navigation:no-response';
        }
        return null;
    """

    def _landed_on_error_page(self) -> bool:
        """Chromium browsers keep the requested URL and render an error page instead of raising."""
        if self._raw.current_url.startswith(_ERROR_PAGES):
            return True
        try:
            signal = self._raw.execute_script(self._ERROR_PAGE_PROBE)
        except WebDriverException:
            return False
        if signal:
            self.log.debug("error page detected via %s", signal)
        return bool(signal)

    def current_location(self) -> str:
        with self._translating("current_location"):
            return self._raw.current_url

    # ------------------------------------------------------------- elements
    def _resolve(self, selector: Selector) -> tuple[str, str]:
        by, value = selector.by, selector.value
        if by is By.TEST_ID:
            return SeleniumBy.CSS_SELECTOR, f'[{self.settings.web.test_id_attribute}="{value}"]'
        if by is By.TEXT:
            return SeleniumBy.XPATH, f"//*[normalize-space(.)={xpath_string(value)}]"
        mapping = {
            By.CSS: SeleniumBy.CSS_SELECTOR,
            By.XPATH: SeleniumBy.XPATH,
            By.ID: SeleniumBy.ID,
            By.NAME: SeleniumBy.NAME,
            By.LINK_TEXT: SeleniumBy.LINK_TEXT,
        }
        try:
            return mapping[by], value
        except KeyError:
            raise UnsupportedSelectorError(selector, self.platform) from None

    def _locate(self, locator: Locator, *, timeout: float | None, within: WebElement | None = None) -> WebElement:
        by, value = self._resolve(locator.for_platform(self.platform))
        scope = within if within is not None else self._raw
        effective = self.wait.timeout if timeout is None else timeout
        try:
            with self._translating(f"find {locator}"):
                return self.wait.until(
                    lambda: scope.find_element(by, value),
                    timeout=effective,
                    message=f"find {locator}",
                    ignored=(NoSuchElementException, StaleElementReferenceException),
                )
        except ConditionTimeoutError:
            raise ElementNotFoundError(locator, self.platform, effective) from None

    def _locate_all(
        self, locator: Locator, *, timeout: float | None, within: WebElement | None = None
    ) -> list[WebElement]:
        by, value = self._resolve(locator.for_platform(self.platform))
        scope = within if within is not None else self._raw
        effective = self.wait.timeout if timeout is None else timeout
        with self._translating(f"find_all {locator}"):
            if effective <= 0:
                return scope.find_elements(by, value)
            try:
                return self.wait.until(
                    lambda: scope.find_elements(by, value),
                    timeout=effective,
                    message=f"find_all {locator}",
                    ignored=(StaleElementReferenceException,),
                )
            except ConditionTimeoutError:
                return []

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        return WebElementHandle(self, self._locate(locator, timeout=timeout), locator)

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        return [WebElementHandle(self, el, locator) for el in self._locate_all(locator, timeout=timeout)]

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        try:
            self._locate(locator, timeout=timeout)
        except ElementNotFoundError:
            return False
        return True

    # ---------------------------------------------------------------- input
    _ARM_CLICK_PROBE = """
        const el = arguments[0], token = arguments[1];
        window.__sc_page = window.__sc_page || Math.random().toString(36).slice(2);
        window.__sc_clicks = window.__sc_clicks || {};
        el.addEventListener('click', () => { window.__sc_clicks[token] = true; }, {once: true, capture: true});
        return window.__sc_page;
    """
    _READ_CLICK_PROBE = """
        const token = arguments[0];
        const hit = !!(window.__sc_clicks && window.__sc_clicks[token]);
        if (window.__sc_clicks) { delete window.__sc_clicks[token]; }
        return [hit, window.__sc_page || null];
    """
    _SYNTHETIC_CLICK = """
        const el = arguments[0];
        if (el.tagName === 'OPTION') {
            el.selected = true;
            const select = el.closest('select');
            if (select) {
                select.dispatchEvent(new Event('input', {bubbles: true}));
                select.dispatchEvent(new Event('change', {bubbles: true}));
            }
            return;
        }
        el.click();
    """

    def click(self, element: WebElement, locator: Locator) -> None:
        """A WebDriver click whose delivery is verified, with a DOM-dispatched fallback.

        The enterprise-managed Chrome 151 on the development machine silently dropped
        synthetic pointer input after short idle periods (no ``pointerdown`` ever reached
        the page) while Edge did not. A one-shot listener tells us whether the click
        event actually fired; if it did not — and the page did not navigate — the
        element is clicked from the DOM instead. Every fallback is logged and counted in
        ``input_anomalies`` so reports show it as an *environment* signal, not silence.
        """
        if element.tag_name == "option":  # chromedriver selects options without pointer events
            element.click()
            try:
                selected = element.is_selected()
            except StaleElementReferenceException:
                return  # the page re-rendered in response to the selection: it took effect
            if not selected:
                self._synthetic_click(element, locator)
            return
        token = uuid4().hex
        page_before = self._raw.execute_script(self._ARM_CLICK_PROBE, element, token)
        element.click()
        delivered, page_after = self._raw.execute_script(self._READ_CLICK_PROBE, token)
        if delivered or page_after != page_before:  # a navigation means the click certainly landed
            return
        self._synthetic_click(element, locator)

    _SYNTHETIC_TYPE = """
        const el = arguments[0], text = arguments[1], clear = arguments[2];
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;  // bypass React's value tracker
        el.focus();
        setter.call(el, clear ? text : el.value + text);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    """

    def type_text(self, element: WebElement, text: str, *, clear: bool, locator: Locator) -> None:
        """Keyboard input whose arrival is verified, with a DOM fallback (same rationale as ``click``)."""
        if clear:
            element.clear()
        before = "" if clear else (element.get_attribute("value") or "")
        element.send_keys(text)
        if (element.get_attribute("value") or "") == before + text:
            return
        self.input_anomalies += 1
        self.log.warning(
            "Browser dropped keyboard input on %s; set the value from the DOM instead (anomaly #%d)",
            locator,
            self.input_anomalies,
        )
        self._raw.execute_script(self._SYNTHETIC_TYPE, element, text, clear)

    def _synthetic_click(self, element: WebElement, locator: Locator) -> None:
        self.input_anomalies += 1
        self.log.warning(
            "Browser dropped the pointer click on %s; dispatched a DOM click instead (anomaly #%d)",
            locator,
            self.input_anomalies,
        )
        self._raw.execute_script(self._SYNTHETIC_CLICK, element)

    def press(self, key: Key) -> None:
        with self._translating(f"press {key}"):
            if key is Key.BACK:
                self._raw.back()
                return
            if key not in _KEYS:  # HOME / MENU / PLAY_PAUSE are remote-control buttons
                raise CapabilityNotSupportedError(Capability.DPAD, self.platform)
            ActionChains(self._raw).send_keys(_KEYS[key]).perform()

    def hover(self, locator: Locator) -> None:
        self.require(Capability.HOVER)
        element = self._locate(locator, timeout=None)
        with self._translating(f"hover {locator}"):
            ActionChains(self._raw).move_to_element(element).perform()

    # ----------------------------------------------------------- diagnostics
    def screenshot(self) -> bytes:
        with self._translating("screenshot"):
            return self._raw.get_screenshot_as_png()

    def page_source(self) -> str:
        with self._translating("page_source"):
            return self._raw.page_source

    def console_logs(self) -> list[str]:
        get_log = getattr(self._driver, "get_log", None)  # Chromium drivers only
        if get_log is None:
            return []
        try:
            entries = get_log("browser")
        except WebDriverException:  # the session may not expose the browser log
            return []
        return [f"{entry.get('level', '')} {entry.get('message', '')}".strip() for entry in entries]


class WebElementHandle:
    """``Element`` over a Selenium ``WebElement``.

    Re-resolves itself once through its locator if the DOM re-rendered
    underneath it, so React list updates never surface as stale references.
    """

    def __init__(
        self, driver: SeleniumWebDriver, element: WebElement, locator: Locator, parent: WebElementHandle | None = None
    ):
        self._driver = driver
        self._element = element
        self._locator = locator
        self._parent = parent

    @property
    def locator(self) -> Locator:
        return self._locator

    def _current(self) -> WebElement:
        """The underlying element, re-resolved (recursively through parents) if stale."""
        try:
            self._element.is_enabled()
        except StaleElementReferenceException:
            return self._relocate()
        return self._element

    def _relocate(self) -> WebElement:
        scope = self._parent._current() if self._parent is not None else None
        self._element = self._driver._locate(self._locator, timeout=None, within=scope)
        return self._element

    def _call(self, action: str, fn: Callable[[WebElement], T]) -> T:
        with self._driver._translating(f"{action} {self._locator}"):
            try:
                return fn(self._element)
            except StaleElementReferenceException:
                return fn(self._relocate())

    @property
    def text(self) -> str:
        return self._call("text", lambda el: el.text)

    def is_displayed(self) -> bool:
        return self._call("is_displayed", lambda el: el.is_displayed())

    def is_enabled(self) -> bool:
        return self._call("is_enabled", lambda el: el.is_enabled())

    def attribute(self, name: str) -> str | None:
        return self._call(f"attribute {name}", lambda el: el.get_attribute(name))

    def select(self) -> None:
        """Click once the element is visible, enabled and not covered — retrying within the wait budget."""

        def attempt(el: WebElement) -> bool:
            if not (el.is_displayed() and el.is_enabled()):
                return False
            try:
                self._driver.click(el, self._locator)
            except (ElementClickInterceptedException, ElementNotInteractableException):
                return False  # overlay / animation still in the way; poll again
            return True

        try:
            self._driver.wait.until(lambda: self._call("select", attempt), message=f"{self._locator} clickable")
        except ConditionTimeoutError as exc:
            raise ElementNotInteractableError(f"{self._locator} never became clickable: {exc}") from exc

    def enter_text(self, text: str, *, clear: bool = True) -> None:
        self._call("enter_text", lambda el: self._driver.type_text(el, text, clear=clear, locator=self._locator))

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        child = self._driver._locate(locator, timeout=timeout, within=self._current())
        return WebElementHandle(self._driver, child, locator, parent=self)

    def find_all(self, locator: Locator) -> list[Element]:
        children = self._driver._locate_all(locator, timeout=0, within=self._current())
        return [WebElementHandle(self._driver, el, locator, parent=self) for el in children]

    def __repr__(self) -> str:
        return f"<WebElement {self._locator}>"
