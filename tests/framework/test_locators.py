from __future__ import annotations

import pytest

from streamcart.core.errors import LocatorNotDefinedError
from streamcart.core.locators import By, Locator, Selector
from streamcart.core.platform import Platform, PlatformFamily

# Plain value objects — locators know nothing about the registry.
WEB = Platform("web", PlatformFamily.WEB, default_target="chrome")
IOS = Platform("ios", PlatformFamily.MOBILE, default_target="sim")
ANDROID = Platform("android", PlatformFamily.MOBILE, default_target="lab")
FIRE_TV = Platform("firetv", PlatformFamily.TV, default_target="lab")
ROKU = Platform("roku", PlatformFamily.TV, default_target="lab")


def test_family_keys_expand_and_platform_keys_win() -> None:
    locator = Locator.define(
        "checkout",
        web=By.CSS("[data-test=checkout]"),
        mobile=By.ACCESSIBILITY_ID("checkout"),
        tv=By.TEXT("Checkout"),
        roku=By.ID("checkoutButton"),
    )
    assert locator.for_platform(IOS) == By.ACCESSIBILITY_ID("checkout")
    assert locator.for_platform(ANDROID) == By.ACCESSIBILITY_ID("checkout")
    assert locator.for_platform(FIRE_TV) == By.TEXT("Checkout")
    assert locator.for_platform(ROKU) == By.ID("checkoutButton")  # platform key beats tv=


def test_a_platform_that_does_not_exist_yet_is_covered_by_its_family() -> None:
    playstation = Platform("playstation", PlatformFamily.TV, default_target="ps5-lab")
    locator = Locator.define("checkout", web=By.CSS("#c"), tv=By.TEXT("Checkout"))
    assert locator.supports(playstation)
    assert locator.for_platform(playstation) == By.TEXT("Checkout")


def test_missing_platform_is_a_clear_error() -> None:
    locator = Locator.define("login", web=By.CSS("#login"))
    with pytest.raises(LocatorNotDefinedError, match=r"no selector for platform 'roku' \(family 'tv'\)") as info:
        locator.for_platform(ROKU)
    assert "Defined for: web" in str(info.value)
    assert not locator.supports(ROKU)


def test_test_id_is_a_strategy_that_adapters_resolve_natively() -> None:
    locator = Locator.test_id("login button", "login-button")
    assert locator.keys == ("any",)
    for platform in (WEB, IOS, ANDROID, FIRE_TV, ROKU):
        assert locator.for_platform(platform) == By.TEST_ID("login-button")


def test_any_is_the_fallback_after_platform_and_family() -> None:
    locator = Locator.define("title", any=By.TEST_ID("title"), web=By.CSS("h1"))
    assert locator.for_platform(WEB) == By.CSS("h1")
    assert locator.for_platform(ROKU) == By.TEST_ID("title")


def test_definition_is_validated() -> None:
    with pytest.raises(ValueError, match="at least one selector"):
        Locator.define("empty")
    with pytest.raises(ValueError, match="must be a lowercase platform or family name"):
        Locator.define("bad", **{"Roku": By.ID("x")})
    with pytest.raises(TypeError, match="must be a Selector"):
        Locator.define("bad", web="#x")  # type: ignore[arg-type]


def test_locators_are_value_objects() -> None:
    a = Locator.define("x", web=By.CSS("#x"))
    b = Locator.define("x", web=By.CSS("#x"))
    assert a == b
    assert hash(a) == hash(b)
    assert str(a) == "x"
    assert str(By.CSS("#x")) == "css='#x'"
    assert isinstance(By.XPATH("//a"), Selector)
