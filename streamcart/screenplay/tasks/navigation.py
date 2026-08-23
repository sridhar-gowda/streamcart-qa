from __future__ import annotations

from streamcart.screenplay.actor import Actor, Task
from streamcart.ui.base import Page


class Open(Task):
    """Go straight to a screen: a URL on web, a deep link or screen id elsewhere."""

    def __init__(self, page: type[Page]) -> None:
        self.page = page

    @classmethod
    def the(cls, page: type[Page]) -> Open:
        return cls(page)

    def perform_as(self, actor: Actor) -> None:
        page = self.page(actor.driver)
        page.open()
        page.wait_until_displayed()

    def __str__(self) -> str:
        return f"open the {self.page.__name__}"
