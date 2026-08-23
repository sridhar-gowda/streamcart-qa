from __future__ import annotations

from streamcart.screenplay.actor import Actor, Question
from streamcart.ui.pages import LoginPage


class TheLoginError(Question["str | None"]):
    """The login error banner's message, or None when login did not fail."""

    def answered_by(self, actor: Actor) -> str | None:
        error = LoginPage(actor.driver).error
        return error.message if error.is_displayed() else None
