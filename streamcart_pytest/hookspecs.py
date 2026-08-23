"""Extension points for teams building on the execution platform (pluggy hookspecs).

A team that needs its own result destination — a chat notification, an internal
dashboard, a data lake — implements a hook in its ``conftest.py`` (the ``@pytest.hookimpl``
decorator is required: pytest only picks up undecorated functions whose names start with
``pytest_``)::

    @pytest.hookimpl
    def pytest_streamcart_result_channels(settings, run_dir):
        return [TeamsNotifierChannel(settings)]

No framework file changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.hookspec
def pytest_streamcart_result_channels(settings: Any, run_dir: Path) -> list[Any]:
    """Return extra ``ResultChannel`` instances to publish the run results to."""
    raise NotImplementedError
