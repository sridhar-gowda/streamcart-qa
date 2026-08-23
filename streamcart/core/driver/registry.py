"""Driver registry — where platforms come from and how a name becomes a driver.

An adapter declares the platform(s) it drives and registers itself::

    ROKU = Platform("roku", PlatformFamily.TV, default_target="roku-lab")

    @register_platform(ROKU)
    class RokuEcpDriver(BaseDriver): ...

Adapters are discovered automatically from two places:

1. every module in ``streamcart.core.driver.adapters`` (drop a file in, done);
2. the ``streamcart.platforms`` entry-point group, for drivers shipped as
   separate packages.

There is no list of platforms anywhere in the core. That is what makes
"adding a platform requires new files only" provable rather than aspirational —
see ``tests/framework/test_architecture.py``.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, TypeVar

from streamcart.core.errors import ConfigurationError, UnknownPlatformError
from streamcart.core.logs import get_logger
from streamcart.core.platform import Platform, normalise

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings
    from streamcart.core.driver.base import BaseDriver
    from streamcart.core.driver.protocol import PlatformDriver

D = TypeVar("D", bound="type[BaseDriver]")

ADAPTERS_PACKAGE = "streamcart.core.driver.adapters"
ENTRY_POINT_GROUP = "streamcart.platforms"

_PLATFORMS: dict[str, Platform] = {}
_DRIVERS: dict[str, type[BaseDriver]] = {}
_DISCOVERED = False
log = get_logger(__name__)


def register_platform(*platforms: Platform) -> Callable[[D], D]:
    """Class decorator: make ``cls`` the driver for each given platform."""
    if not platforms:
        raise ValueError("register_platform() needs at least one Platform")

    def decorate(cls: D) -> D:
        for platform in platforms:
            existing = _DRIVERS.get(platform.name)
            if existing is not None and existing is not cls:
                raise ConfigurationError(
                    f"Platform '{platform}' already has driver {existing.__qualname__}; "
                    f"refusing to register {cls.__qualname__}"
                )
            _PLATFORMS[platform.name] = platform
            _DRIVERS[platform.name] = cls
        cls.platforms = tuple(platforms)
        return cls

    return decorate


def discover_adapters(*, force: bool = False) -> None:
    """Import every adapter module and entry point so they self-register."""
    global _DISCOVERED
    if _DISCOVERED and not force:
        return
    package = importlib.import_module(ADAPTERS_PACKAGE)
    for module_info in pkgutil.iter_modules(package.__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{ADAPTERS_PACKAGE}.{module_info.name}")
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep.load()
        except Exception as exc:  # a broken third-party driver must not break the run
            log.warning("Could not load platform entry point %s: %s", ep.name, exc)
    _DISCOVERED = True


def registered_platforms() -> dict[str, Platform]:
    """Canonical name → Platform, for everything currently registered."""
    discover_adapters()
    return dict(_PLATFORMS)


def platform_named(value: str | Platform) -> Platform:
    """Resolve ``"roku"``, ``"Fire TV"``, an alias, or a ``Platform`` instance."""
    if isinstance(value, Platform):
        return value
    discover_adapters()
    wanted = normalise(value)
    if wanted in _PLATFORMS:
        return _PLATFORMS[wanted]
    for platform in _PLATFORMS.values():
        if platform.matches(value):
            return platform
    known = ", ".join(sorted(_PLATFORMS)) or "none"
    raise UnknownPlatformError(
        f"Unknown platform '{value}'. Registered: {known}. "
        f"Add {ADAPTERS_PACKAGE.replace('.', '/')}/<name>.py declaring a Platform and a @register_platform driver."
    )


def driver_class(platform: str | Platform) -> type[BaseDriver]:
    return _DRIVERS[platform_named(platform).name]


def create_driver(settings: Settings) -> PlatformDriver:
    """Instantiate (but do not start) the driver for ``settings.platform``."""
    cls = driver_class(settings.platform)
    log.debug("Creating %s for platform %s", cls.__name__, settings.platform)
    return cls(settings)
