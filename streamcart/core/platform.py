"""Platform identities.

A *platform* is a product target (the web app, Roku, Fire TV). An *adapter* is
an automation technology (Selenium, Appium, Roku's ECP). They are not
one-to-one: one Appium adapter serves both iOS and Android.

Platforms are therefore **declared by the adapter that drives them** and
registered through ``core.driver.registry``; this module only defines what a
platform *is*. The core never holds a list of platforms — that is what makes
"adding a platform changes no existing file" literally true, and
``tests/framework/test_architecture.py`` proves it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PlatformFamily(str, Enum):
    """How a user physically interacts with the product.

    Deliberately a closed set: a family is an *interaction model*, and a new
    one means new Screenplay Abilities and locator conventions, not merely a
    new adapter. Every platform belongs to exactly one family.
    """

    WEB = "web"  # pointer + keyboard, URL navigation
    MOBILE = "mobile"  # touch, gestures, on-screen keyboard
    TV = "tv"  # remote control, focus-based navigation, no pointer

    def __str__(self) -> str:
        return self.value


_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*$")


def normalise(value: str) -> str:
    """``"Fire TV"`` → ``"firetv"``: what users type becomes what adapters declare."""
    return re.sub(r"[\s_\-]+", "", value.strip().lower())


@dataclass(frozen=True)
class Platform:
    """One product target.

    ``name`` is the canonical id used on the command line (``--platform roku``),
    in config folder names (``config/platform/roku.yaml``), in Gherkin tags
    (``@roku``) and as a locator key (``roku=By.ID(...)``).
    """

    name: str
    family: PlatformFamily
    default_target: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _NAME_PATTERN.match(self.name):
            raise ValueError(f"Platform name {self.name!r} must be lowercase letters/digits (e.g. 'firetv')")

    @property
    def is_web(self) -> bool:
        return self.family is PlatformFamily.WEB

    @property
    def is_mobile(self) -> bool:
        return self.family is PlatformFamily.MOBILE

    @property
    def is_tv(self) -> bool:
        return self.family is PlatformFamily.TV

    def matches(self, value: str) -> bool:
        """True for the canonical name or any alias, ignoring case and separators."""
        wanted = normalise(value)
        return wanted == self.name or any(normalise(alias) == wanted for alias in self.aliases)

    def __str__(self) -> str:
        return self.name
