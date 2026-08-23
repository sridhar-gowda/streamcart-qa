"""Result channels — where the results of a finished run are published.

Each channel is isolated: one failing integration never blocks another and never
fails the build — a test result is a fact about the product, not about the
availability of a reporting system. Teams add their own channels through the
``pytest_streamcart_result_channels`` hook.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from streamcart.core.config import Settings
from streamcart.core.logs import get_logger
from streamcart_pytest.results import RunResults
from streamcart_pytest.tms import TmsAdapter, results_from

log = get_logger(__name__)


@dataclass(frozen=True)
class ChannelReceipt:
    channel: str
    ok: bool
    detail: str


class ResultChannel(Protocol):
    name: str

    def publish(self, run_results: RunResults) -> ChannelReceipt: ...


class LocalResultsChannel:
    """``run-results.json`` in the run directory — the file everything else is derived from."""

    name = "local"

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def publish(self, run_results: RunResults) -> ChannelReceipt:
        path = run_results.write(self.run_dir / "run-results.json")
        return ChannelReceipt(self.name, True, str(path))


class TmsChannel:
    name = "tms"

    def __init__(self, adapter: TmsAdapter, settings: Settings) -> None:
        self.adapter = adapter
        self.settings = settings

    def publish(self, run_results: RunResults) -> ChannelReceipt:
        if not self.settings.tms.upload or self.adapter.name == "none":
            return ChannelReceipt(self.name, True, "upload disabled (tms.upload=false or tms.provider=none)")
        results = results_from(run_results)
        if not results:
            return ChannelReceipt(self.name, True, "nothing linked to a test case (@TC-… tags)")
        key = self.adapter.publish(run_results, results)
        run_results.tms_execution = key
        return ChannelReceipt(self.name, True, f"{self.adapter.name} execution {key} ({len(results)} results)")


def publish_all(run_results: RunResults, channels: Sequence[ResultChannel]) -> list[ChannelReceipt]:
    receipts: list[ChannelReceipt] = []
    for channel in channels:
        try:
            receipt = channel.publish(run_results)
        except Exception as exc:  # a channel failure is reported, never raised
            log.warning("Channel %s failed: %s", channel.name, exc)
            receipt = ChannelReceipt(channel.name, False, f"{type(exc).__name__}: {exc}")
        run_results.receipts[receipt.channel] = receipt.detail
        receipts.append(receipt)
    return receipts
