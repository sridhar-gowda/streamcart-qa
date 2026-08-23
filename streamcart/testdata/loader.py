from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from streamcart.core.errors import ConfigurationError


def read_mapping(path: Path) -> dict[str, Any]:
    """Load one YAML reference-data file, insisting on a top-level mapping."""
    if not path.is_file():
        raise ConfigurationError(f"Reference data file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ConfigurationError(f"{path} must contain a mapping at the top level")
    return dict(data)


def data_file(data_dir: Path | None, file_name: str) -> Path:
    if data_dir is None:
        raise ConfigurationError(
            f"No reference data directory configured (looked for data/{file_name}). "
            "Run from the repository root or set STREAMCART_DATA_DIR."
        )
    return data_dir / file_name
