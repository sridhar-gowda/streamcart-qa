"""Fixtures for framework self-tests.

These tests exercise the framework's own contracts (locators, registry,
configuration, plugin) — they never touch SauceDemo. Product behaviour lives
in ``features/`` as Gherkin.
"""

from __future__ import annotations

import os
from importlib.metadata import entry_points
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Everything under tests/framework is the framework's own suite — never product regression."""
    for item in items:
        if HERE in Path(str(item.path)).resolve().parents:
            item.add_marker(pytest.mark.suite("framework"))


@pytest.fixture(autouse=True)
def _no_allure_html_in_inner_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inner (pytester) product runs would each start the Allure CLI's JVM; one dedicated test covers it."""
    monkeypatch.setenv("STREAMCART_REPORT__ALLURE_HTML", "false")


def write_config_tree(root: Path, files: dict[str, str]) -> Path:
    """Create a throwaway ``config/`` tree: ``{"base.yaml": "...", "target/x.yaml": "..."}``."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


MINIMAL_TREE = {
    "base.yaml": "timeouts:\n  default: 10\nweb:\n  headless: true\n",
    "platform/web.yaml": "web:\n  browser: chrome\n",
    "platform/roku.yaml": "tv:\n  ecp_port: 8060\n",
    "target/chrome.yaml": "web:\n  headless: true\n",
    "target/chrome-headed.yaml": "web:\n  headless: false\n",
    "target/roku-lab.yaml": "tv:\n  ecp_host: 10.0.0.5\n",
    "env/dev.yaml": "app:\n  base_url: https://dev.example\n",
}


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    return write_config_tree(tmp_path / "config", MINIMAL_TREE)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No ambient STREAMCART_* variables and no ``.env`` from the developer's checkout."""
    for name in list(os.environ):
        if name.startswith("STREAMCART_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def plugin_args() -> list[str]:
    """``-p`` argument for pytester runs when the plugin is not installed as an entry point."""
    installed = any(ep.value.startswith("streamcart_pytest.plugin") for ep in entry_points(group="pytest11"))
    return [] if installed else ["-p", "streamcart_pytest.plugin"]
