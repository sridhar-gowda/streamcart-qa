"""Capabilities: the explicit mechanism for platform-specific behaviour.

A driver *declares* what it can do; Tasks and tests *ask* before relying on
it. This replaces ``if platform == "roku"`` branches with a negotiable
contract: a scenario tagged ``@requires:hover`` is skipped on TV with a
reason, and a Task can choose an alternative path when a capability is absent.

Capabilities are deliberately coarse. They describe interaction models, not
individual keywords.
"""

from __future__ import annotations

from enum import Enum

from streamcart.core.platform import PlatformFamily


class Capability(str, Enum):
    """Interaction capabilities a platform driver may provide."""

    # Navigation
    OPEN_URL = "open_url"  # navigate to an arbitrary URL (web)
    DEEP_LINK = "deep_link"  # open an app screen via deep link / ECP launch
    HARDWARE_BACK = "hardware_back"  # device back button (Android, Fire TV, Roku)
    # Pointer family
    HOVER = "hover"
    RIGHT_CLICK = "right_click"
    DRAG_AND_DROP = "drag_and_drop"
    KEYBOARD = "keyboard"  # physical keyboard text entry
    MULTI_WINDOW = "multi_window"
    ALERTS = "alerts"  # native browser dialogs
    # Touch family
    TAP = "tap"
    SWIPE = "swipe"
    PINCH = "pinch"
    LONG_PRESS = "long_press"
    ROTATE = "rotate"
    ON_SCREEN_KEYBOARD = "on_screen_keyboard"
    # Remote family
    DPAD = "dpad"  # directional focus movement
    FOCUS_NAVIGATION = "focus_navigation"  # "select" means move-focus-then-OK
    VOICE = "voice"
    # Diagnostics
    SCREENSHOT = "screenshot"
    PAGE_SOURCE = "page_source"  # DOM / view hierarchy / SceneGraph XML
    CONSOLE_LOGS = "console_logs"

    def __str__(self) -> str:
        return self.value


# What each interaction family is expected to support. Adapters start from their
# family baseline and add or remove (a Roku box, for instance, has no console log
# API, so the Roku adapter removes CONSOLE_LOGS).
FAMILY_BASELINE: dict[PlatformFamily, frozenset[Capability]] = {
    PlatformFamily.WEB: frozenset(
        {
            Capability.OPEN_URL,
            Capability.HOVER,
            Capability.RIGHT_CLICK,
            Capability.DRAG_AND_DROP,
            Capability.KEYBOARD,
            Capability.MULTI_WINDOW,
            Capability.ALERTS,
            Capability.SCREENSHOT,
            Capability.PAGE_SOURCE,
            Capability.CONSOLE_LOGS,
        }
    ),
    PlatformFamily.MOBILE: frozenset(
        {
            Capability.DEEP_LINK,
            Capability.TAP,
            Capability.SWIPE,
            Capability.PINCH,
            Capability.LONG_PRESS,
            Capability.ROTATE,
            Capability.ON_SCREEN_KEYBOARD,
            Capability.SCREENSHOT,
            Capability.PAGE_SOURCE,
        }
    ),
    PlatformFamily.TV: frozenset(
        {
            Capability.DEEP_LINK,
            Capability.DPAD,
            Capability.FOCUS_NAVIGATION,
            Capability.ON_SCREEN_KEYBOARD,
            Capability.SCREENSHOT,
            Capability.PAGE_SOURCE,
        }
    ),
}
