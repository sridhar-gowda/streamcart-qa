from __future__ import annotations

import pytest

from streamcart.core.capabilities import Capability
from streamcart.core.config import Settings
from streamcart.core.driver import registry
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.errors import CapabilityNotSupportedError, ConfigurationError, UnknownPlatformError
from streamcart.core.locators import Locator

from .fakes import FAKE_TV, OTHER_TV, FakeDriver


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty registry that does not trigger adapter discovery."""
    monkeypatch.setattr(registry, "_PLATFORMS", {})
    monkeypatch.setattr(registry, "_DRIVERS", {})
    monkeypatch.setattr(registry, "_DISCOVERED", True)
    monkeypatch.setattr(FakeDriver, "platforms", ())


def test_register_and_create(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV)(FakeDriver)
    settings = Settings(platform=FAKE_TV)
    driver = registry.create_driver(settings)
    assert isinstance(driver, FakeDriver)
    assert isinstance(driver, PlatformDriver)  # structural check against the protocol
    assert driver.platform is FAKE_TV
    assert driver.wait.timeout == settings.timeouts.default
    assert FakeDriver.platforms == (FAKE_TV,)


def test_lookup_by_name_and_alias(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV)(FakeDriver)
    assert registry.platform_named("faketv") is FAKE_TV
    assert registry.platform_named("Fake TV") is FAKE_TV
    assert registry.platform_named(FAKE_TV) is FAKE_TV
    assert registry.registered_platforms() == {"faketv": FAKE_TV}


def test_unknown_platform_names_the_fix(isolated_registry: None) -> None:
    with pytest.raises(
        UnknownPlatformError, match=r"Unknown platform 'nope'. Registered: none. Add .*adapters/<name>\.py"
    ):
        registry.platform_named("nope")


def test_one_adapter_can_serve_several_platforms(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV, OTHER_TV)(FakeDriver)
    assert registry.driver_class(FAKE_TV) is FakeDriver
    assert registry.driver_class("othertv") is FakeDriver
    assert registry.create_driver(Settings(platform=OTHER_TV)).platform is OTHER_TV


def test_driver_refuses_a_platform_it_does_not_serve(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV)(FakeDriver)
    with pytest.raises(ConfigurationError, match="FakeDriver drives faketv, not 'othertv'"):
        FakeDriver(Settings(platform=OTHER_TV))


def test_duplicate_registration_is_rejected(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV)(FakeDriver)

    class Another(FakeDriver):
        pass

    with pytest.raises(ConfigurationError, match="already has driver"):
        registry.register_platform(FAKE_TV)(Another)


def test_capability_negotiation(isolated_registry: None) -> None:
    registry.register_platform(FAKE_TV)(FakeDriver)
    driver = registry.create_driver(Settings(platform=FAKE_TV))
    assert driver.supports(Capability.DPAD)
    assert not driver.supports(Capability.HOVER)
    with pytest.raises(CapabilityNotSupportedError, match="'faketv' does not support capability 'hover'"):
        driver.require(Capability.HOVER)
    with pytest.raises(CapabilityNotSupportedError):
        driver.hover(Locator.test_id("x", "x"))
    assert driver.console_logs() == []  # undeclared -> empty, not an error


def test_declared_but_unimplemented_capability_fails_loudly(isolated_registry: None) -> None:
    class Sloppy(FakeDriver):
        capabilities = frozenset({Capability.HOVER})

    registry.register_platform(FAKE_TV)(Sloppy)
    driver = registry.create_driver(Settings(platform=FAKE_TV))
    with pytest.raises(NotImplementedError, match="declares HOVER"):
        driver.hover(Locator.test_id("x", "x"))
