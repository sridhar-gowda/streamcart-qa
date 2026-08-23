"""Abilities — the platform seam of the Screenplay layer.

A Task says *what* (``ProceedToCheckout``); the actor's ability says *how it
is physically done*: with a pointer and keyboard, with touch, or with a remote
control. Each interaction ability is bound to one ``PlatformFamily`` and
carries the driver for it, so a Task written once runs on every platform of
every family, and a family-specific Task can ask ``actor.has_ability(OperateTheRemote)``.
"""

from __future__ import annotations

from typing import ClassVar

from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.errors import ConfigurationError
from streamcart.core.platform import PlatformFamily


class Ability:
    """Something an actor can do. Marker base; interaction abilities add a driver."""

    def __str__(self) -> str:
        return type(self).__name__


class InteractionAbility(Ability):
    """An ability that drives the product through a ``PlatformDriver`` of one family."""

    family: ClassVar[PlatformFamily]

    def __init__(self, driver: PlatformDriver) -> None:
        if driver.platform.family is not self.family:
            raise ConfigurationError(
                f"{type(self).__name__} needs a {self.family} driver, "
                f"but {driver.platform} is a {driver.platform.family} platform"
            )
        self.driver = driver

    @staticmethod
    def for_driver(driver: PlatformDriver) -> InteractionAbility:
        """The right ability for whatever platform the driver is: the actor never has to know."""
        by_family: dict[PlatformFamily, type[InteractionAbility]] = {
            PlatformFamily.WEB: BrowseTheWeb,
            PlatformFamily.MOBILE: UseTheMobileApp,
            PlatformFamily.TV: OperateTheRemote,
        }
        return by_family[driver.platform.family](driver)

    def __str__(self) -> str:
        return f"{type(self).__name__} on {self.driver.platform}"


class BrowseTheWeb(InteractionAbility):
    """Pointer + keyboard in a browser; navigation by URL."""

    family = PlatformFamily.WEB


class UseTheMobileApp(InteractionAbility):
    """Touch, gestures and the on-screen keyboard in the native app."""

    family = PlatformFamily.MOBILE


class OperateTheRemote(InteractionAbility):
    """A remote control: focus moves with the d-pad, OK selects, there is no pointer."""

    family = PlatformFamily.TV
