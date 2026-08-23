"""Structured logging with run and test correlation.

Every log record carries ``run_id`` and ``test_id`` so that a line in a CI log,
an uploaded artifact and a TMS execution can be joined on the same key. The ids
live in context variables, which makes them correct per xdist worker and per
test without threading arguments through every layer.

The record factory is installed at import time so that pytest's own log
formatter (configured with ``%(run_id)s`` in ``pyproject.toml``) never meets a
record that lacks the fields.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

RUN_ID: ContextVar[str] = ContextVar("streamcart_run_id", default="-")
TEST_ID: ContextVar[str] = ContextVar("streamcart_test_id", default="-")

ROOT_LOGGER_NAME = "streamcart"
_FACTORY_INSTALLED = False


def _install_record_factory() -> None:
    global _FACTORY_INSTALLED
    if _FACTORY_INSTALLED:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.run_id = RUN_ID.get()
        record.test_id = TEST_ID.get()
        return record

    logging.setLogRecordFactory(factory)
    _FACTORY_INSTALLED = True


_install_record_factory()


def configure_logging(run_id: str, level: int = logging.INFO) -> None:
    """Bind the run id and set the framework logger level. Idempotent."""
    RUN_ID.set(run_id)
    logging.getLogger(ROOT_LOGGER_NAME).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a child of the ``streamcart`` logger (``get_logger(__name__)``)."""
    if name == ROOT_LOGGER_NAME or name.startswith(ROOT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


@contextmanager
def bound_test(test_id: str) -> Iterator[None]:
    """Attach ``test_id`` to every record emitted inside the block."""
    token = TEST_ID.set(test_id)
    try:
        yield
    finally:
        TEST_ID.reset(token)
