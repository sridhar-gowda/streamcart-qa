"""Two-phase configuration loading.

Phase 1 — *selectors*: ``platform``, ``env`` and ``target`` are resolved from
CLI > environment > ``.env`` > defaults. They decide **which** layer files load.
The platform name is resolved against the driver registry, so an unknown
platform fails here with the list of registered ones.

Phase 2 — *settings*: the chosen YAML layers are deep-merged (later wins) and
become a pydantic-settings source that sits *below* the environment, so that a
GitHub secret or a local ``.env`` overrides YAML, and a CLI flag overrides both.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from streamcart.core.config.models import Settings
from streamcart.core.driver.registry import platform_named
from streamcart.core.errors import ConfigurationError
from streamcart.core.platform import Platform

CONFIG_DIR_ENV = "STREAMCART_CONFIG_DIR"
DATA_DIR_ENV = "STREAMCART_DATA_DIR"
SELECTOR_KEYS = ("platform", "env", "target")


class Selectors(BaseSettings):
    """Phase 1: which layers to load. Reads CLI (as init kwargs), env and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="STREAMCART_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    platform: str = "web"
    env: str = "dev"
    target: str | None = None

    def resolved_platform(self) -> Platform:
        return platform_named(self.platform)

    def resolved_target(self) -> str:
        return self.target or self.resolved_platform().default_target


# --------------------------------------------------------------------------- files
def find_config_dir(explicit: str | Path | None = None) -> Path:
    """Explicit path > ``$STREAMCART_CONFIG_DIR`` > ``./config`` > repo-relative ``config``."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get(CONFIG_DIR_ENV):
        candidates.append(Path(os.environ[CONFIG_DIR_ENV]))
    candidates.append(Path.cwd() / "config")
    candidates.append(Path(__file__).resolve().parents[3] / "config")
    for candidate in candidates:
        if (candidate / "base.yaml").is_file():
            return candidate.resolve()
    looked = ", ".join(str(c) for c in candidates)
    raise ConfigurationError(f"No configuration directory with a base.yaml found. Looked in: {looked}")


def find_data_dir(config_dir: Path) -> Path | None:
    """``$STREAMCART_DATA_DIR`` > ``<config>/../data`` > ``./data``. Reference data is optional."""
    candidates: list[Path] = []
    if os.environ.get(DATA_DIR_ENV):
        candidates.append(Path(os.environ[DATA_DIR_ENV]))
    candidates += [config_dir.parent / "data", Path.cwd() / "data"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


def config_files(platform: Platform, env: str, target: str, config_dir: Path) -> list[Path]:
    """The ordered layer files for these selectors. Every required layer must exist."""
    layers = [
        ("base", config_dir / "base.yaml"),
        ("platform", config_dir / "platform" / f"{platform.name}.yaml"),
        ("target", config_dir / "target" / f"{target}.yaml"),
        ("env", config_dir / "env" / f"{env}.yaml"),
    ]
    files: list[Path] = []
    for layer, path in layers:
        if not path.is_file():
            available = sorted(p.stem for p in path.parent.glob("*.yaml")) if path.parent.is_dir() else []
            raise ConfigurationError(
                f"No {layer} configuration named '{path.stem}' (expected {path}). "
                f"Available {layer}s: {', '.join(available) or 'none'}."
            )
        files.append(path)
    local = config_dir / "local.yaml"
    if local.is_file():
        files.append(local)
    return files


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursive dict merge; ``override`` wins; lists replace rather than append."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(value, Mapping) and isinstance(current, Mapping):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def read_layers(files: Sequence[Path]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in files:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ConfigurationError(f"{path} must contain a mapping at the top level")
        for key in SELECTOR_KEYS:
            if key in data:
                raise ConfigurationError(
                    f"{path} sets '{key}'. Selectors are chosen on the command line or via "
                    f"STREAMCART_{key.upper()}, never inside a layer file."
                )
        merged = deep_merge(merged, data)
    return merged


# ------------------------------------------------------------------- sources
class LayeredYamlSource(PydanticBaseSettingsSource):
    """A pydantic-settings source backed by the merged layer files."""

    def __init__(self, settings_cls: type[BaseSettings], files: Sequence[Path]) -> None:
        super().__init__(settings_cls)
        self.files = list(files)
        self._data = read_layers(self.files)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return dict(self._data)


def _bind(files: Sequence[Path]) -> type[Settings]:
    """A ``Settings`` subclass whose source chain includes these layer files."""

    class LayeredSettings(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            # Highest priority first.
            return (init_settings, env_settings, dotenv_settings, LayeredYamlSource(settings_cls, files))

    LayeredSettings.__name__ = LayeredSettings.__qualname__ = "Settings"
    return LayeredSettings


# --------------------------------------------------------------------- entry
def _prune(value: Any) -> Any:
    """Drop ``None`` leaves so an unset CLI flag never masks a lower layer."""
    if isinstance(value, Mapping):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    return value


def load_settings(overrides: Mapping[str, Any] | None = None, *, config_dir: str | Path | None = None) -> Settings:
    """Resolve the session configuration.

    ``overrides`` are the highest-priority values (CLI flags), as a nested
    mapping that mirrors ``Settings``: ``{"platform": "roku", "web": {"headless": False}}``.
    Raises ``ConfigurationError`` with an actionable message on any problem.
    """
    init: dict[str, Any] = _prune(dict(overrides or {}))
    selector_kwargs = {key: init[key] for key in SELECTOR_KEYS if key in init}
    if isinstance(selector_kwargs.get("platform"), Platform):
        selector_kwargs["platform"] = selector_kwargs["platform"].name
    selectors = Selectors(**selector_kwargs)
    platform = selectors.resolved_platform()
    target = selectors.resolved_target()
    directory = find_config_dir(config_dir)
    files = config_files(platform, selectors.env, target, directory)

    init["platform"] = platform
    init["env"] = selectors.env
    init["target"] = target
    init["config_dir"] = directory
    init["data_dir"] = find_data_dir(directory)
    init["loaded_files"] = [str(f.relative_to(directory)).replace(os.sep, "/") for f in files]

    try:
        settings = _bind(files)(**init)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigurationError(
            f"Invalid configuration ({problems}). Layers: {' -> '.join(init['loaded_files'])}"
        ) from exc
    _check_browser_matches_target(settings)
    return settings


WEB_BROWSERS = ("chrome", "firefox", "edge", "safari")


def _check_browser_matches_target(settings: Settings) -> None:
    """The browser is part of the target. A target named after a browser (``chrome``, ``chrome-grid``,
    ``firefox``...) runs that browser, so a report for a target always describes that browser.
    Overriding ``web.browser`` underneath such a target is refused instead of silently honoured."""
    if not settings.platform.is_web or not settings.target:
        return
    named = settings.target.split("-", 1)[0]
    if named in WEB_BROWSERS and settings.web.browser != named:
        raise ConfigurationError(
            f"Target '{settings.target}' runs {named}, but web.browser is '{settings.web.browser}' "
            f"(layers: {' -> '.join(settings.loaded_files)}). Choose the matching target instead of "
            f"overriding the browser, e.g. --target {settings.web.browser}."
        )
