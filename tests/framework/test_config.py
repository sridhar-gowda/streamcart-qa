from __future__ import annotations

from pathlib import Path

import pytest

from streamcart.core.config import load_settings
from streamcart.core.config.loader import deep_merge
from streamcart.core.driver.registry import registered_platforms
from streamcart.core.errors import ConfigurationError

from .conftest import MINIMAL_TREE, write_config_tree

pytestmark = pytest.mark.usefixtures("clean_env")

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_layers_apply_in_order(config_dir: Path) -> None:
    settings = load_settings(config_dir=config_dir)
    assert settings.platform.name == "web"
    assert settings.env == "dev"
    assert settings.target == "chrome"
    assert settings.loaded_files == ["base.yaml", "platform/web.yaml", "target/chrome.yaml", "env/dev.yaml"]
    assert settings.app.base_url == "https://dev.example"
    assert settings.web.browser == "chrome"  # from the platform layer, untouched by the target layer


def test_target_layer_overrides_base(config_dir: Path) -> None:
    settings = load_settings({"target": "chrome-headed"}, config_dir=config_dir)
    assert settings.web.headless is False
    assert settings.timeouts.default == 10  # sibling keys survive the deep merge


def test_environment_beats_yaml_and_cli_beats_environment(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_WEB__HEADLESS", "true")
    assert load_settings({"target": "chrome-headed"}, config_dir=config_dir).web.headless is True
    cli = load_settings({"target": "chrome-headed", "web": {"headless": False}}, config_dir=config_dir)
    assert cli.web.headless is False


def test_empty_environment_variables_mean_not_set(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CI passes "" for unset workflow inputs; that must not override a layer or break validation."""
    monkeypatch.setenv("STREAMCART_WEB__BROWSER", "")
    monkeypatch.setenv("STREAMCART_TMS__TOKEN", "")
    monkeypatch.setenv("STREAMCART_PLATFORM", "")
    settings = load_settings(config_dir=config_dir)
    assert settings.platform.name == "web"
    assert settings.web.browser == "chrome"
    assert settings.tms.token is None


def test_selectors_come_from_environment_when_not_on_cli(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_PLATFORM", "roku")
    settings = load_settings(config_dir=config_dir)
    assert settings.platform.name == "roku"
    assert settings.target == "roku-lab"  # the platform's default target, declared by its adapter
    assert settings.tv.ecp_host == "10.0.0.5"
    assert "platform/roku.yaml" in settings.loaded_files


def test_secrets_only_from_environment(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_USERS__DEFAULT__PASSWORD", "s3cret")
    monkeypatch.setenv("STREAMCART_USERS__LOCKED_OUT__PASSWORD", "other")
    settings = load_settings(config_dir=config_dir)
    standard = settings.password_for("standard")
    locked_out = settings.password_for("locked_out")
    assert standard is not None
    assert standard.get_secret_value() == "s3cret"  # falls back to `default`
    assert locked_out is not None
    assert locked_out.get_secret_value() == "other"
    assert "s3cret" not in repr(settings)
    assert "s3cret" not in settings.model_dump_json()


def test_missing_target_lists_available(config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match="No target configuration named 'ipad'") as info:
        load_settings({"target": "ipad"}, config_dir=config_dir)
    assert "Available targets: chrome, chrome-headed, roku-lab" in str(info.value)


def test_unknown_platform_fails_in_phase_one(config_dir: Path) -> None:
    with pytest.raises(ConfigurationError, match="Unknown platform 'playstation'"):
        load_settings({"platform": "playstation"}, config_dir=config_dir)


def test_unknown_key_in_yaml_is_rejected(tmp_path: Path) -> None:
    tree = dict(MINIMAL_TREE)
    tree["base.yaml"] = "timeouts:\n  defualt: 10\n"  # typo must not silently fall back to a default
    with pytest.raises(ConfigurationError, match=r"timeouts\.defualt"):
        load_settings(config_dir=write_config_tree(tmp_path / "cfg", tree))


def test_selectors_inside_layer_files_are_rejected(tmp_path: Path) -> None:
    tree = dict(MINIMAL_TREE)
    tree["env/dev.yaml"] = "platform: roku\n"
    with pytest.raises(ConfigurationError, match="Selectors are chosen on the command line"):
        load_settings(config_dir=write_config_tree(tmp_path / "cfg", tree))


@pytest.mark.parametrize("name", sorted(registered_platforms()))
def test_shipped_config_tree_is_valid_for_every_platform(name: str) -> None:
    settings = load_settings({"platform": name}, config_dir=REPO_CONFIG)
    assert settings.platform.name == name
    assert settings.app.base_url.startswith("https://")
    assert f"target/{settings.platform.default_target}.yaml" in settings.loaded_files


def test_deep_merge_replaces_lists_and_merges_dicts() -> None:
    merged = deep_merge({"a": {"x": 1, "y": [1, 2]}, "b": 1}, {"a": {"y": [3], "z": 2}})
    assert merged == {"a": {"x": 1, "y": [3], "z": 2}, "b": 1}


def test_the_browser_is_part_of_the_target(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A target named after a browser runs that browser. Overriding web.browser underneath it is
    refused, so a report for the `chrome` target can never secretly be an Edge report."""
    monkeypatch.setenv("STREAMCART_WEB__BROWSER", "edge")
    with pytest.raises(ConfigurationError, match=r"Target 'chrome' runs chrome.*--target edge"):
        load_settings({"target": "chrome"}, config_dir=config_dir)
    # the command line may still say the matching browser explicitly
    settings = load_settings({"target": "chrome-headed", "web": {"browser": "chrome"}}, config_dir=config_dir)
    assert settings.web.browser == "chrome"
