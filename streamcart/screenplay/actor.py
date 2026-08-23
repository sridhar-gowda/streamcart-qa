"""Actor, Task and Question — the three words every scenario is written in."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from streamcart.core.capabilities import Capability
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.errors import FrameworkError
from streamcart.core.logs import get_logger
from streamcart.screenplay.ability import Ability, InteractionAbility

if TYPE_CHECKING:
    from streamcart.testdata.personas import Persona

T = TypeVar("T")
A = TypeVar("A", bound=Ability)
log = get_logger(__name__)


class MissingAbilityError(FrameworkError):
    """The actor was asked to do something they have no ability for — a test-authoring mistake."""


class Task(ABC):
    """Something an actor does, in product language.

    Subclasses implement ``perform_as`` using Pages and Components only. A Task
    that needs an interaction the platform may lack declares it in ``requires``;
    the actor checks capabilities *before* performing, so an unsupported Task
    fails with ``CapabilityNotSupportedError`` rather than a confusing element error.
    """

    requires: tuple[Capability, ...] = ()

    @abstractmethod
    def perform_as(self, actor: Actor) -> None: ...

    def __str__(self) -> str:
        return type(self).__name__


class Question(ABC, Generic[T]):
    """Something an actor can find out, answered as a typed value."""

    @abstractmethod
    def answered_by(self, actor: Actor) -> T: ...

    def __str__(self) -> str:
        return type(self).__name__


class Actor:
    """Who the scenario is about: a name, optionally a persona, and a set of abilities."""

    def __init__(self, name: str, *, persona: Persona | None = None) -> None:
        self.name = name
        self.persona = persona
        self._abilities: dict[type[Ability], Ability] = {}

    @classmethod
    def named(cls, name: str) -> Actor:
        return cls(name)

    # ------------------------------------------------------------ abilities
    def who_can(self, *abilities: Ability) -> Actor:
        for ability in abilities:
            self._abilities[type(ability)] = ability
        return self

    def has_ability(self, kind: type[Ability]) -> bool:
        return any(isinstance(ability, kind) for ability in self._abilities.values())

    def ability_to(self, kind: type[A]) -> A:
        for ability in self._abilities.values():
            if isinstance(ability, kind):
                return ability
        raise MissingAbilityError(f"{self.name} cannot {kind.__name__}: abilities are {self._describe_abilities()}")

    @property
    def driver(self) -> PlatformDriver:
        """The platform driver behind the actor's interaction ability."""
        return self.ability_to(InteractionAbility).driver

    def _describe_abilities(self) -> str:
        return ", ".join(str(a) for a in self._abilities.values()) or "none"

    # ----------------------------------------------------------- performing
    def attempts_to(self, *tasks: Task) -> Actor:
        for task in tasks:
            for capability in task.requires:
                self.driver.require(capability)
            log.info("%s attempts to %s", self.name, task)
            task.perform_as(self)
        return self

    def asks(self, question: Question[T]) -> T:
        answer = question.answered_by(self)
        log.info("%s asks %s -> %r", self.name, question, answer)
        return answer

    def __repr__(self) -> str:
        return f"<Actor {self.name!r} persona={self.persona} abilities=[{self._describe_abilities()}]>"
