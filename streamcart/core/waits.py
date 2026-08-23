"""Condition-based waiting — the framework's only wait strategy.

Every wait in the framework is "poll a condition until it is truthy or a
deadline passes". Adapters use it for element presence and readiness, Tasks
use it for state transitions (``wait_until(lambda: cart.badge_count() == 3)``),
and the execution platform uses it for session health checks.

This module contains the one sanctioned ``time.sleep`` in the codebase — the
interval between polls. ruff bans ``time.sleep`` everywhere else
(``pyproject.toml`` → ``banned-api``), which is what makes the assignment's
"no fixed sleeps" rule a build guarantee rather than a code-review hope.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from streamcart.core.errors import ConditionTimeoutError

T = TypeVar("T")

DEFAULT_TIMEOUT = 10.0
DEFAULT_INTERVAL = 0.25


def wait_until(
    condition: Callable[[], T],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = DEFAULT_INTERVAL,
    message: str = "condition not met",
    ignored: tuple[type[BaseException], ...] = (),
) -> T:
    """Poll ``condition`` until it returns a truthy value and return that value.

    ``ignored`` exceptions raised by the condition are swallowed and retried
    (an adapter passes its library's "not found" exception here); any other
    exception propagates immediately. On expiry raises ``ConditionTimeoutError``
    carrying ``message`` and the last swallowed error.
    """
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while True:
        try:
            value = condition()
            if value:
                return value
        except ignored as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            raise ConditionTimeoutError(message, timeout=timeout, last_error=last_error)
        time.sleep(interval)  # the sanctioned sleep — see module docstring


@dataclass(frozen=True)
class Waiter:
    """A ``wait_until`` pre-bound to a configuration's timeouts.

    Drivers hold one so that Pages and Tasks never hard-code seconds:
    ``driver.wait.until(lambda: ..., message="cart badge updated")``.
    """

    timeout: float = DEFAULT_TIMEOUT
    interval: float = DEFAULT_INTERVAL

    def until(
        self,
        condition: Callable[[], T],
        *,
        message: str = "condition not met",
        timeout: float | None = None,
        ignored: tuple[type[BaseException], ...] = (),
    ) -> T:
        return wait_until(
            condition,
            timeout=self.timeout if timeout is None else timeout,
            interval=self.interval,
            message=message,
            ignored=ignored,
        )
