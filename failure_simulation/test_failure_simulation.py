"""Binds failure_outcomes.feature (a report walkthrough, not a product feature) and adds its one special step."""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import scenarios, when

from streamcart.core.errors import DriverSessionError

HERE = Path(__file__).resolve().parent
MARKER = HERE / ".session-dropped-once"

scenarios(str(HERE / "failure_outcomes.feature"))


@when("the browser session drops once")
def session_drops_once() -> None:
    """Simulate an environment failure on the first attempt only: the retry then passes."""
    if not MARKER.exists():
        MARKER.write_text("dropped", encoding="utf-8")
        raise DriverSessionError("browser session lost (simulated once for the report example)")
