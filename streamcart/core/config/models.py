"""Typed configuration models.

Every knob the framework reads is declared here with a default and a
description, so ``config/*.yaml`` files can be validated (unknown keys are an
error — a typo never silently falls back to a default) and the settings object
is fully typed in every layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from streamcart.core.platform import Platform


def _coerce_platform(value: Any) -> Any:
    """``"roku"`` → the registered ``Platform`` (adapters are discovered on demand)."""
    if isinstance(value, str):
        from streamcart.core.driver.registry import platform_named

        return platform_named(value)
    return value


def _default_platform() -> Platform:
    return _coerce_platform("web")  # type: ignore[no-any-return]


# NoDecode: pydantic-settings would otherwise JSON-decode the env value "roku" because the
# field type is a dataclass; we want the raw name handed to the validator instead.
PlatformField = Annotated[Platform, NoDecode, BeforeValidator(_coerce_platform)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AppSettings(_Strict):
    name: str = "StreamCart"
    base_url: str = Field(default="", description="Web entry point; mobile/TV ignore it unless deep-linking")
    deep_link_scheme: str = Field(default="streamcart://", description="Used by mobile/TV ``open()``")


class TimeoutSettings(_Strict):
    default: float = Field(default=10.0, description="Element and condition waits")
    page_load: float = Field(default=30.0, description="Navigation / screen transition")
    script: float = 30.0
    poll_interval: float = Field(default=0.25, description="Polling interval for condition-based waits")
    focus_settle: float = Field(default=0.3, description="TV: time for a focus move to render before the next key")


class WebSettings(_Strict):
    browser: Literal["chrome", "firefox", "edge", "safari"] = "chrome"
    headless: bool = True
    window_size: tuple[int, int] = (1440, 900)
    remote_url: str | None = Field(default=None, description="Selenium Grid / cloud provider endpoint; None = local")
    page_load_strategy: Literal["normal", "eager", "none"] = "normal"
    test_id_attribute: str = Field(default="data-test", description="DOM attribute behind ``By.TEST_ID``")
    extra_args: list[str] = Field(default_factory=list, description="Extra browser CLI arguments")
    capabilities: dict[str, object] = Field(default_factory=dict, description="Merged into the session capabilities")


class MobileSettings(_Strict):
    appium_url: str | None = None
    automation_name: Literal["UiAutomator2", "XCUITest"] | None = None
    device_name: str | None = None
    platform_version: str | None = None
    udid: str | None = None
    app: str | None = Field(default=None, description="Path or URL of the .apk/.ipa under test")
    app_package: str | None = None
    app_activity: str | None = None
    bundle_id: str | None = None
    new_command_timeout: int = 120
    capabilities: dict[str, object] = Field(default_factory=dict)


class TvSettings(_Strict):
    ecp_host: str | None = Field(default=None, description="Roku: device IP for the External Control Protocol")
    ecp_port: int = 8060
    channel_id: str = Field(default="dev", description="Roku: sideloaded channel is always 'dev'")
    dev_password: SecretStr | None = Field(default=None, description="Roku developer web server (screenshots)")
    keypress_delay: float = Field(default=0.1, description="Delay between remote key presses")
    max_focus_moves: int = Field(default=40, description="d-pad presses allowed to reach one element")


class UserCredential(_Strict):
    """Only ever populated from the environment — see ``.env.example``."""

    password: SecretStr


class ReportSettings(_Strict):
    root: Path = Field(
        default=Path("reports"), description="Product runs: <root>/runs/<id>/; framework runs: <root>/framework/<id>/"
    )
    kind: Literal["auto", "product", "framework"] = Field(
        default="auto", description="auto = framework when only tests/framework is collected, else product"
    )
    html: bool = Field(default=True, description="Write report.html (pytest-html, self-contained)")
    junit: bool = Field(default=True, description="Write junit.xml")
    summary: bool = Field(default=True, description="Write summary.md")
    cucumber_json: bool = Field(default=True, description="Product runs: write cucumber.json (BDD tooling, TMS import)")
    allure: bool = Field(default=True, description="Write allure-results/ when allure-pytest-bdd is installed")
    allure_html: bool = Field(
        default=True, description="Generate allure-report/index.html from the results when the Allure CLI is on PATH"
    )


class ArtifactSettings(_Strict):
    on_failure: bool = True
    always: bool = False
    screenshot: bool = True
    page_source: bool = True
    console_logs: bool = True
    store: Literal["local", "s3", "azure"] = "local"
    s3_bucket: str | None = None
    s3_prefix: str = ""
    azure_container: str | None = None
    retention_days: int = 30


class RetrySettings(_Strict):
    max_attempts: int = Field(default=2, ge=1, description="1 = never retry")
    only_categories: list[str] = Field(
        default_factory=lambda: ["environment"],
        description="Failure categories eligible for retry. Product defects are never retried.",
    )


class TmsSettings(_Strict):
    provider: Literal["none", "xray", "codebeamer", "memory"] = Field(
        default="none", description="'memory' is an in-process fake for tests and demos"
    )
    base_url: str | None = None
    project_key: str | None = None
    token: SecretStr | None = None
    plan: str | None = Field(default=None, description="Default test plan / test set")
    upload: bool = Field(default=False, description="Publish results at session end")


class Settings(BaseSettings):
    """The resolved configuration for one pytest session."""

    model_config = SettingsConfigDict(
        env_prefix="STREAMCART_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # CI passes "" for unset inputs; that must mean "not set", not "empty value"
        extra="forbid",
        case_sensitive=False,
    )

    # --- selectors: decide which layer files load; never set inside YAML ---
    platform: PlatformField = Field(default_factory=_default_platform)
    env: str = "dev"
    target: str = Field(default="", description="Execution target; empty = the platform's default")

    # --- identity ---
    team: str = Field(default="streamcart-qa", description="Prefix for artifact keys and TMS labels")
    run_id: str | None = Field(default=None, description="Set by the plugin; shared across xdist workers")
    build: str | None = Field(default=None, description="Product build / commit under test, for the TMS record")

    # --- sections ---
    app: AppSettings = Field(default_factory=AppSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    mobile: MobileSettings = Field(default_factory=MobileSettings)
    tv: TvSettings = Field(default_factory=TvSettings)
    users: dict[str, UserCredential] = Field(default_factory=dict)
    report: ReportSettings = Field(default_factory=ReportSettings)
    artifacts: ArtifactSettings = Field(default_factory=ArtifactSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    tms: TmsSettings = Field(default_factory=TmsSettings)

    # --- provenance (filled by the loader) ---
    config_dir: Path | None = None
    data_dir: Path | None = Field(default=None, description="Reference data: data/users.yaml, data/products.yaml")
    loaded_files: list[str] = Field(default_factory=list)

    def password_for(self, persona: str) -> SecretStr | None:
        """Per-persona secret, falling back to ``users.default``."""
        credential = self.users.get(persona) or self.users.get("default")
        return credential.password if credential else None

    def describe(self) -> str:
        # ASCII only: this line is printed by pytest's terminal writer on every console.
        return (
            f"platform={self.platform.name} ({self.platform.family}) | env={self.env} | "
            f"target={self.target or self.platform.default_target} | base_url={self.app.base_url or '-'} | "
            f"run_id={self.run_id or '-'}"
        )
