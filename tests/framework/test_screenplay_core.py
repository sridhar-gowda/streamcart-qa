"""Actor / Ability / persona mechanics — no browser involved."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from streamcart.core.capabilities import Capability
from streamcart.core.config import Settings
from streamcart.core.errors import CapabilityNotSupportedError, ConfigurationError
from streamcart.screenplay import (
    Actor,
    BrowseTheWeb,
    InteractionAbility,
    MissingAbilityError,
    OperateTheRemote,
    Question,
    Task,
)
from streamcart.testdata import PersonaCatalogue, ProductCatalogue

from .fakes import FAKE_TV, FAKE_WEB, FakeDriver, FakeWebDriver

REPO_DATA = Path(__file__).resolve().parents[2] / "data"


class Record(Task):
    def __init__(self, log: list[str], label: str) -> None:
        self.log, self.label = log, label

    def perform_as(self, actor: Actor) -> None:
        self.log.append(f"{actor.name}:{self.label}")


class NeedsHover(Task):
    requires = (Capability.HOVER,)

    def perform_as(self, actor: Actor) -> None:
        raise AssertionError("must not run on a platform without HOVER")


class TheLog(Question[list[str]]):
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def answered_by(self, actor: Actor) -> list[str]:
        return list(self.log)


def test_ability_is_chosen_by_platform_family() -> None:
    assert isinstance(InteractionAbility.for_driver(FakeDriver(Settings(platform=FAKE_TV))), OperateTheRemote)
    assert isinstance(InteractionAbility.for_driver(FakeWebDriver(Settings(platform=FAKE_WEB))), BrowseTheWeb)
    with pytest.raises(ConfigurationError, match="BrowseTheWeb needs a web driver, but faketv is a tv platform"):
        BrowseTheWeb(FakeDriver(Settings(platform=FAKE_TV)))


def test_actor_performs_tasks_in_order_and_answers_questions() -> None:
    log: list[str] = []
    actor = Actor.named("Ada").who_can(InteractionAbility.for_driver(FakeWebDriver(Settings(platform=FAKE_WEB))))
    actor.attempts_to(Record(log, "first"), Record(log, "second"))
    assert actor.asks(TheLog(log)) == ["Ada:first", "Ada:second"]
    assert actor.driver.platform is FAKE_WEB


def test_capability_requirements_are_checked_before_performing() -> None:
    tv_actor = Actor("Roku viewer").who_can(OperateTheRemote(FakeDriver(Settings(platform=FAKE_TV))))
    with pytest.raises(CapabilityNotSupportedError, match="'faketv' does not support capability 'hover'"):
        tv_actor.attempts_to(NeedsHover())
    web_actor = Actor("Web shopper").who_can(BrowseTheWeb(FakeWebDriver(Settings(platform=FAKE_WEB))))
    with pytest.raises(AssertionError, match="must not run"):  # capability present -> the task itself ran
        web_actor.attempts_to(NeedsHover())


def test_missing_ability_is_a_clear_authoring_error() -> None:
    with pytest.raises(MissingAbilityError, match="Nobody cannot InteractionAbility: abilities are none"):
        _ = Actor("Nobody").driver


def test_personas_load_from_reference_data_and_fail_fast_without_a_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMCART_USERS__DEFAULT__PASSWORD", raising=False)
    monkeypatch.chdir(REPO_DATA.parent / "tests")  # away from any local .env
    catalogue = PersonaCatalogue.from_file(REPO_DATA / "users.yaml", settings=Settings(platform=FAKE_WEB))
    assert {"standard", "locked_out", "problem", "performance_glitch", "error", "visual"} <= set(catalogue.keys())
    assert catalogue.get("locked_out").username == "locked_out_user"
    assert not catalogue.get("standard").has_password
    with pytest.raises(
        ConfigurationError, match=r"Copy \.env\.example to \.env and set STREAMCART_USERS__DEFAULT__PASSWORD"
    ):
        catalogue.resolve("standard")
    with pytest.raises(ConfigurationError, match=r"Unknown persona 'ghost'\. Known personas: standard"):
        catalogue.get("ghost")


def test_personas_resolve_passwords_from_settings() -> None:
    settings = Settings(platform=FAKE_WEB, users={"default": {"password": "shared"}, "error": {"password": "own"}})
    catalogue = PersonaCatalogue.from_file(REPO_DATA / "users.yaml", settings=settings)
    standard = catalogue.resolve("standard")
    assert standard.credentials() == ("standard_user", "shared")
    assert catalogue.resolve("error").credentials() == ("error_user", "own")
    assert "shared" not in repr(standard)
    assert standard.with_password(SecretStr("x")).credentials()[1] == "x"


def test_product_catalogue_is_the_oracle_for_the_inventory() -> None:
    catalogue = ProductCatalogue.from_file(REPO_DATA / "products.yaml")
    assert len(catalogue) == 6
    assert catalogue.by_name("Sauce Labs Backpack").price == Decimal("29.99")
    assert catalogue.expected_tax(Decimal("29.99")) == Decimal("2.40")
    assert catalogue.expected_tax(Decimal("39.98")) == Decimal("3.20")
    with pytest.raises(ConfigurationError, match="Unknown product 'Sauce Labs Hoverboard'"):
        catalogue.by_name("Sauce Labs Hoverboard")
