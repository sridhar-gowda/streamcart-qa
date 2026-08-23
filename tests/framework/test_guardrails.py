"""The disqualifier controls, exercised: the bans and contracts must actually bite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(sys.executable).parent


def _ruff(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--config", str(REPO_ROOT / "pyproject.toml"), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_time_sleep_is_a_lint_error_in_page_and_test_code(tmp_path: Path) -> None:
    victim = tmp_path / "sleepy_page.py"
    victim.write_text("import time\n\n\ndef wait_for_badge():\n    time.sleep(2)\n", encoding="utf-8")
    result = _ruff("--select", "TID251", str(victim))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout
    assert "Fixed sleeps are banned" in result.stdout


def test_selenium_imports_are_a_lint_error_outside_adapters(tmp_path: Path) -> None:
    victim = tmp_path / "leaky_task.py"
    victim.write_text("from selenium.webdriver.common.by import By\n", encoding="utf-8")
    result = _ruff("--select", "TID251", str(victim))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Selenium may only be imported inside streamcart/core/driver/adapters/" in result.stdout


def test_the_real_adapter_layer_is_allowed_to_import_selenium() -> None:
    result = _ruff("--select", "TID251", "streamcart/core/driver/adapters/web_selenium.py")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(
    not (SCRIPTS / "lint-imports").exists() and not (SCRIPTS / "lint-imports.exe").exists(),
    reason="import-linter not installed",
)
def test_layer_contracts_hold() -> None:
    executable = SCRIPTS / ("lint-imports.exe" if sys.platform == "win32" else "lint-imports")
    result = subprocess.run([str(executable)], capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Contracts: 3 kept, 0 broken" in result.stdout


def _settings_has_path(path: list[str]) -> bool:
    """``["tms", "upload"]`` → does ``Settings.tms.upload`` exist? (dict fields accept any key)."""
    from pydantic import BaseModel

    from streamcart.core.config import Settings

    model: type[BaseModel] = Settings
    for index, part in enumerate(path):
        field = model.model_fields.get(part)
        if field is None:
            return False
        annotation = field.annotation
        origin = getattr(annotation, "__origin__", None)
        if origin is dict:
            return index <= len(path) - 2  # dict[str, Model]: one key level, then the value model's fields
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            model = annotation
        elif index != len(path) - 1:
            return False
    return True


def test_every_environment_variable_in_ci_and_compose_maps_to_a_setting() -> None:
    """Configuration drift guard: a STREAMCART_* name in a workflow, compose file or .env.example
    must correspond to a Settings field, so nothing the pipeline sets can be silently ignored."""
    import re

    sources = [*(REPO_ROOT / ".github").rglob("*.yml"), REPO_ROOT / "compose.yaml", REPO_ROOT / ".env.example"]
    names = {
        name for source in sources for name in re.findall(r"STREAMCART_[A-Z0-9_]+", source.read_text(encoding="utf-8"))
    }
    assert names, "expected STREAMCART_* variables in the pipeline definitions"
    read_directly = {"STREAMCART_RUN_ID", "STREAMCART_CONFIG_DIR", "STREAMCART_DATA_DIR"}
    unknown = []
    for name in sorted(names - read_directly):
        path = [part.lower() for part in name.removeprefix("STREAMCART_").split("__")]
        if path == ["users", "default", "password"] or path == ["users", "standard", "password"]:
            path = ["users", "default", "password"]
        if not _settings_has_path(path):
            unknown.append(name)
    assert not unknown, f"environment variables with no Settings field: {unknown}"


def test_no_credentials_are_committed() -> None:
    """The SauceDemo password is public, but nothing we wrote may contain it — only the assignment brief does."""
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.split()
    assert ".env" not in tracked
    needle = "secret_" + "sauce"  # assembled so this file does not trip its own scan
    for path in tracked:
        if path.startswith("docs/assignment/"):  # the brief we were given, verbatim
            continue
        if path.endswith((".py", ".yaml", ".yml", ".feature", ".toml", ".md", ".txt", ".example", ".cfg", ".ini")):
            text = (REPO_ROOT / path).read_text(encoding="utf-8", errors="ignore")
            assert needle not in text, f"{path} contains a credential"
