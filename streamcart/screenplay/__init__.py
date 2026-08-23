"""Screenplay: business intent, expressed by actors.

    actor.attempts_to(Login.as_(standard), AddToCart.item("Sauce Labs Backpack"))
    assert actor.asks(TheCartBadgeCount()) == 1

- An **Actor** is who the scenario is about (a persona) and what they can do.
- An **Ability** is how they interact: ``BrowseTheWeb``, ``UseTheMobileApp``,
  ``OperateTheRemote`` — one per interaction family; it carries the platform driver.
- A **Task** is something they do, described in product language. Tasks compose
  Pages and Components; they never contain locators or assertions.
- A **Question** is something they can find out, returned as a typed value.

This is the only layer test code talks to. A step definition is one call to
``attempts_to`` or one ``asks`` followed by an assertion — nothing else.
"""

from streamcart.screenplay.ability import Ability, BrowseTheWeb, InteractionAbility, OperateTheRemote, UseTheMobileApp
from streamcart.screenplay.actor import Actor, MissingAbilityError, Question, Task

__all__ = [
    "Ability",
    "Actor",
    "BrowseTheWeb",
    "InteractionAbility",
    "MissingAbilityError",
    "OperateTheRemote",
    "Question",
    "Task",
    "UseTheMobileApp",
]
