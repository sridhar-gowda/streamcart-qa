from __future__ import annotations

from itertools import count

import pytest

from streamcart.core.errors import ConditionTimeoutError
from streamcart.core.waits import Waiter, wait_until


def test_returns_the_first_truthy_value() -> None:
    ticks = count()
    assert wait_until(lambda: next(ticks) >= 3 and "ready", timeout=2, interval=0.01) == "ready"


def test_times_out_with_message_and_last_error() -> None:
    class NotYetError(Exception):
        pass

    def flaky() -> bool:
        raise NotYetError("still loading")

    with pytest.raises(ConditionTimeoutError, match=r"cart badge: timed out after 0\.1s") as info:
        wait_until(flaky, timeout=0.1, interval=0.01, message="cart badge", ignored=(NotYetError,))
    assert isinstance(info.value.last_error, NotYetError)


def test_unexpected_exceptions_propagate_immediately() -> None:
    def broken() -> bool:
        raise KeyError("boom")

    with pytest.raises(KeyError):
        wait_until(broken, timeout=1, interval=0.01)


def test_waiter_binds_configured_timeouts() -> None:
    waiter = Waiter(timeout=0.2, interval=0.01)
    with pytest.raises(ConditionTimeoutError, match=r"after 0\.2s"):
        waiter.until(lambda: False)
    with pytest.raises(ConditionTimeoutError, match=r"after 0\.4s"):  # an explicit timeout beats the bound one
        waiter.until(lambda: False, timeout=0.4)
