"""Typed errors raised at the framework boundary.

Adapters translate library exceptions (``NoSuchElementException``,
``WebDriverException``, ``URLError`` …) into these types, so nothing above the
adapter layer ever sees a Selenium or Appium exception.

The hierarchy is also the input to failure *classification* in the execution
platform: ``ElementNotFoundError`` becomes a *ui-contract* failure,
``DriverSessionError`` an *environment* failure, and a plain ``AssertionError``
raised by a test step a *product* failure. Keep that mapping in mind when
adding a new error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streamcart.core.capabilities import Capability
    from streamcart.core.locators import Locator, Selector
    from streamcart.core.platform import Platform


class FrameworkError(Exception):
    """Base class for every error raised by the framework itself."""


class ConfigurationError(FrameworkError):
    """The run cannot start: missing layer file, unknown key, absent secret."""


class UnknownPlatformError(ConfigurationError):
    """No driver adapter has registered the requested platform."""


class LocatorNotDefinedError(FrameworkError):
    """A locator has no selector for the platform the run is executing on."""

    def __init__(self, locator: Locator, platform: Platform) -> None:
        self.locator = locator
        self.platform = platform
        defined = ", ".join(locator.keys) or "none"
        super().__init__(
            f"Locator '{locator.name}' has no selector for platform '{platform}' "
            f"(family '{platform.family}'). Defined for: {defined}."
        )


class UnsupportedSelectorError(FrameworkError):
    """The adapter cannot use this selector strategy (e.g. ``ACCESSIBILITY_ID`` on web)."""

    def __init__(self, selector: Selector, platform: Platform) -> None:
        self.selector = selector
        self.platform = platform
        super().__init__(f"Selector strategy '{selector.by}' is not supported on platform '{platform}'.")


class CapabilityNotSupportedError(FrameworkError):
    """A Task or test needs an interaction the current platform cannot perform."""

    def __init__(self, capability: Capability, platform: Platform) -> None:
        self.capability = capability
        self.platform = platform
        super().__init__(f"Platform '{platform}' does not support capability '{capability}'.")


class ConditionTimeoutError(FrameworkError):
    """A condition-based wait expired.

    Raised by ``streamcart.core.waits.wait_until``; ``last_error`` carries the
    most recent exception swallowed while polling, if any.
    """

    def __init__(self, message: str, *, timeout: float, last_error: BaseException | None = None) -> None:
        self.timeout = timeout
        self.last_error = last_error
        suffix = f" (last error: {last_error!r})" if last_error else ""
        super().__init__(f"{message}: timed out after {timeout:.1f}s{suffix}")


class ElementNotFoundError(FrameworkError):
    """The locator matched nothing within the timeout.

    Ambiguous by nature — the UI changed or the locator rotted — which is why
    the platform reports it as *ui-contract* (needs triage) rather than guessing.
    """

    def __init__(self, locator: Locator, platform: Platform, timeout: float) -> None:
        self.locator = locator
        self.platform = platform
        self.timeout = timeout
        try:
            selector = str(locator.for_platform(platform))
        except FrameworkError:
            selector = "<undefined>"
        super().__init__(f"Element '{locator.name}' not found on {platform} within {timeout:.1f}s using {selector}.")


class ElementNotInteractableError(FrameworkError):
    """The element exists but cannot be acted on (hidden, disabled, focus unreachable)."""


class DriverSessionError(FrameworkError):
    """The automation session is broken: browser crashed, Appium died, ECP unreachable.

    Classified as an *environment* failure and therefore eligible for retry.
    """


class AppUnreachableError(FrameworkError):
    """The application itself could not be reached (DNS, 5xx, channel not installed)."""
