"""Architecture tests — the rubric's structural claims, executed.

1. Automation libraries are contained in ``core/driver/adapters``.
2. The framework core names no platform: adding one cannot require a core edit.
3. Adding a platform really does take new files only — proven by adding one here.
4. Every registered platform ships its configuration layers.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

import streamcart
from streamcart.core.capabilities import FAMILY_BASELINE, Capability
from streamcart.core.config import load_settings
from streamcart.core.driver import registry
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.protocol import Element, Key
from streamcart.core.driver.registry import create_driver, register_platform, registered_platforms
from streamcart.core.locators import By, Locator
from streamcart.core.platform import Platform, PlatformFamily

from .conftest import MINIMAL_TREE, write_config_tree

PACKAGE_ROOT = Path(streamcart.__file__).parent
REPO_ROOT = PACKAGE_ROOT.parent
ADAPTERS = PACKAGE_ROOT / "core" / "driver" / "adapters"
CONTAINED_LIBRARIES = ("selenium", "appium")


def _modules(root: Path, *, exclude: Path | None = None) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        if exclude is not None and exclude in path.parents:
            continue
        yield path


def _imports(tree: ast.AST) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def _code_strings(tree: ast.Module) -> Iterator[str]:
    """String constants that are not docstrings."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.value


def test_automation_libraries_are_only_imported_by_adapters() -> None:
    offenders = []
    for path in list(_modules(PACKAGE_ROOT, exclude=ADAPTERS)) + list(_modules(REPO_ROOT / "streamcart_pytest")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        leaked = [name for name in _imports(tree) if name.split(".")[0] in CONTAINED_LIBRARIES]
        if leaked:
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(leaked)}")
    assert not offenders, "automation libraries leaked out of the adapter layer:\n" + "\n".join(offenders)


def test_framework_core_names_no_platform() -> None:
    families = {family.value for family in PlatformFamily}
    platform_names = set(registered_platforms()) - families  # 'web' is both a family and a platform
    offenders = []
    for path in _modules(PACKAGE_ROOT / "core", exclude=ADAPTERS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        named = sorted({s for s in _code_strings(tree) if s.lower() in platform_names})
        if named:
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {named}")
    assert not offenders, "the core must not special-case platforms:\n" + "\n".join(offenders)


class PlayStationDriver(BaseDriver):
    """A brand-new platform, written without touching a single existing file."""

    capabilities = FAMILY_BASELINE[PlatformFamily.TV]

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def open(self, destination: str) -> None: ...

    def current_location(self) -> str:
        return "store"

    def find(self, locator: Locator, *, timeout: float | None = None) -> Element:
        raise NotImplementedError

    def find_all(self, locator: Locator, *, timeout: float | None = None) -> list[Element]:
        return []

    def is_present(self, locator: Locator, *, timeout: float = 0.0) -> bool:
        return False

    def press(self, key: Key) -> None: ...

    def screenshot(self) -> bytes:
        return b""

    def page_source(self) -> str:
        return ""


@pytest.mark.usefixtures("clean_env")  # the developer's .env must not leak into a framework proof
def test_adding_a_platform_requires_new_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry.discover_adapters()
    monkeypatch.setattr(registry, "_PLATFORMS", dict(registry._PLATFORMS))
    monkeypatch.setattr(registry, "_DRIVERS", dict(registry._DRIVERS))

    # New file 1: the adapter module declares its platform and registers its driver.
    playstation = Platform("playstation", PlatformFamily.TV, default_target="ps5-lab")
    register_platform(playstation)(PlayStationDriver)

    # New files 2 and 3: a platform layer and a target layer.
    tree = dict(MINIMAL_TREE)
    tree["platform/playstation.yaml"] = "tv:\n  keypress_delay: 0.2\n"
    tree["target/ps5-lab.yaml"] = "tv:\n  ecp_host: 10.0.0.9\n"
    config_dir = write_config_tree(tmp_path / "config", tree)

    # Existing code resolves, configures and drives it.
    settings = load_settings({"platform": "playstation"}, config_dir=config_dir)
    assert settings.platform is playstation
    assert settings.target == "ps5-lab"
    assert "platform/playstation.yaml" in settings.loaded_files
    assert settings.tv.keypress_delay == 0.2

    driver = create_driver(settings)
    assert isinstance(driver, PlayStationDriver)
    assert driver.supports(Capability.DPAD)

    # Existing locators already cover it through their family key.
    checkout = Locator.define("checkout", web=By.CSS("[data-test=checkout]"), tv=By.TEXT("Checkout"))
    assert checkout.for_platform(settings.platform) == By.TEXT("Checkout")
    assert Locator.test_id("login", "login-button").for_platform(settings.platform) == By.TEST_ID("login-button")


def test_every_registered_platform_ships_its_config_layers() -> None:
    config = REPO_ROOT / "config"
    for name, platform in registered_platforms().items():
        assert (config / "platform" / f"{name}.yaml").is_file(), f"missing config/platform/{name}.yaml"
        assert (config / "target" / f"{platform.default_target}.yaml").is_file(), (
            f"missing config/target/{platform.default_target}.yaml for {name}"
        )


def _ui_locators() -> Iterator[tuple[str, Locator]]:
    """Every ``Locator`` declared on a class in ``streamcart.ui`` (pages and components)."""
    import importlib
    import inspect
    import pkgutil

    import streamcart.ui as ui

    for module_info in pkgutil.walk_packages(ui.__path__, prefix="streamcart.ui."):
        module = importlib.import_module(module_info.name)
        for class_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            for attr, value in vars(cls).items():
                if isinstance(value, Locator):
                    yield f"{class_name}.{attr}", value


def test_ui_locators_use_known_keys_and_cover_the_implemented_platform() -> None:
    web = registered_platforms()["web"]
    known = set(registered_platforms()) | {family.value for family in PlatformFamily} | {"any"}
    locators = list(_ui_locators())
    assert len(locators) > 20, "expected the UI model to declare its locators as class attributes"
    for owner, locator in locators:
        unknown = set(locator.keys) - known
        assert not unknown, f"{owner} uses unknown locator keys {sorted(unknown)}"
        assert locator.supports(web), f"{owner} has no selector for the implemented platform (web)"
