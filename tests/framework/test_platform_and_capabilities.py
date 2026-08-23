from __future__ import annotations

import pytest

from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.driver.registry import platform_named, registered_platforms
from streamcart.core.errors import UnknownPlatformError
from streamcart.core.platform import Platform, PlatformFamily, normalise


def test_the_six_streamcart_platforms_are_registered_by_their_adapters() -> None:
    platforms = registered_platforms()
    assert {name: p.family for name, p in platforms.items()} == {
        "web": PlatformFamily.WEB,
        "ios": PlatformFamily.MOBILE,
        "android": PlatformFamily.MOBILE,
        "firetv": PlatformFamily.TV,
        "roku": PlatformFamily.TV,
        "appletv": PlatformFamily.TV,
    }


@pytest.mark.parametrize("raw", ["roku", "ROKU", "Fire TV", "fire_tv", "firetv", "apple-tv", "tvOS", "iPhone"])
def test_platform_lookup_is_forgiving_about_spelling_and_aliases(raw: str) -> None:
    assert platform_named(raw).name in {"roku", "firetv", "appletv", "ios"}


def test_unknown_platform_lists_registered_ones() -> None:
    with pytest.raises(UnknownPlatformError, match=r"Unknown platform 'playstation'\. Registered: android, appletv"):
        platform_named("playstation")


def test_platform_names_are_canonical_identifiers() -> None:
    assert normalise("Fire TV") == "firetv"
    with pytest.raises(ValueError, match="lowercase letters/digits"):
        Platform("Fire TV", PlatformFamily.TV, default_target="x")


def test_tv_family_has_no_pointer_or_touch() -> None:
    tv = FAMILY_BASELINE[PlatformFamily.TV]
    assert Capability.DPAD in tv
    assert Capability.FOCUS_NAVIGATION in tv
    assert not tv & {Capability.HOVER, Capability.TAP, Capability.SWIPE, Capability.KEYBOARD}


def test_web_family_can_hover_but_not_swipe() -> None:
    web = FAMILY_BASELINE[PlatformFamily.WEB]
    assert Capability.HOVER in web
    assert Capability.SWIPE not in web
