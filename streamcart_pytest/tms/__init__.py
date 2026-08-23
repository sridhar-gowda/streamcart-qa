"""Test-management integration behind one small protocol.

Two directions:

- **selection**: ``--tms-plan KEY`` asks the adapter which test cases a plan
  contains and runs exactly those (matched on ``@TC-…`` / ``@XRAY-…`` tags);
- **publication**: at session end the run results becomes one *test
  execution* in the TMS with one result per linked test case.

The *n-executions* model: a test case is executed many times — per platform,
target, environment, build and retry. Each run publishes **one execution
keyed by (team, platform, target, env, run id)** with environment labels, so
a Chrome result never overwrites a Firefox result and reruns within a run are
*attempts* of one result, not separate results. Shards of one run are merged
into one run_results before publishing (``streamcart merge-results``).

Adapters: ``xray`` (Jira), ``codebeamer``, ``memory`` (tests/demos), ``none``.
A TMS being down never fails a build: the channel logs and moves on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from streamcart.core.errors import ConfigurationError
from streamcart_pytest.results import RunResults

if TYPE_CHECKING:
    from streamcart.core.config import Settings


@dataclass(frozen=True)
class TmsResult:
    test_key: str
    status: str  # passed | failed | skipped | flaky | known-issue
    comment: str = ""
    duration: float = 0.0
    attempts: int = 1
    category: str | None = None
    evidence: tuple[str, ...] = ()


class TmsAdapter(Protocol):
    name: str

    def resolve_plan(self, plan_key: str) -> list[str]:
        """Test case keys in a plan / test set, in the TMS's order."""
        ...

    def publish(self, run_results: RunResults, results: Sequence[TmsResult]) -> str:
        """Create the execution for this run and report every result; return the execution key."""
        ...


def results_from(run_results: RunResults) -> list[TmsResult]:
    """One ``TmsResult`` per linked test case; a scenario linked to two cases reports to both."""
    out: list[TmsResult] = []
    for record in run_results.results:
        if not record.tms_ids:
            continue
        if record.outcome == "passed":
            status = "flaky" if record.attempts > 1 else "passed"
        elif record.outcome in ("failed", "error"):
            status = "known-issue" if record.known_issue else "failed"
        elif record.outcome == "xfailed":
            status = "known-issue" if record.known_issue else "skipped"
        else:
            status = "skipped"
        comment = _comment(record, run_results)
        for key in record.tms_ids:
            out.append(
                TmsResult(
                    test_key=key,
                    status=status,
                    comment=comment,
                    duration=record.duration,
                    attempts=record.attempts,
                    category=record.category,
                    evidence=tuple(record.artifacts.values()),
                )
            )
    return out


def _comment(record: Any, run_results: RunResults) -> str:
    parts = [
        f"{record.nodeid} on {run_results.platform}/{run_results.target} ({run_results.env}), run {run_results.run_id}"
    ]
    if record.attempts > 1:
        parts.append(
            f"passed on attempt {record.attempts}" if record.outcome == "passed" else f"{record.attempts} attempts"
        )
    if record.category:
        parts.append(f"category: {record.category}")
    if record.known_issue:
        parts.append(f"known issue: {record.known_issue}")
    if record.message:
        parts.append(record.message.splitlines()[0][:300])
    return " | ".join(parts)


class NullTms:
    """No TMS configured: selection by plan is impossible, publication is a no-op."""

    name = "none"

    def resolve_plan(self, plan_key: str) -> list[str]:
        raise ConfigurationError(
            f"Cannot resolve test plan '{plan_key}': no test-management system is configured "
            "(set tms.provider to xray or codebeamer, and tms.token in the environment)."
        )

    def publish(self, run_results: RunResults, results: Sequence[TmsResult]) -> str:
        return ""


@dataclass
class InMemoryTms:
    """A fake TMS for framework tests and demos: plans are a dict, executions accumulate in memory."""

    name: str = "memory"
    plans: dict[str, list[str]] = field(default_factory=dict)
    executions: list[dict[str, Any]] = field(default_factory=list)

    def resolve_plan(self, plan_key: str) -> list[str]:
        try:
            return list(self.plans[plan_key])
        except KeyError:
            raise ConfigurationError(
                f"Unknown test plan '{plan_key}'. Known: {', '.join(self.plans) or 'none'}"
            ) from None

    def publish(self, run_results: RunResults, results: Sequence[TmsResult]) -> str:
        key = f"MEM-{len(self.executions) + 1}"
        self.executions.append({"key": key, "label": run_results.execution_label, "results": list(results)})
        return key


def adapter_for(settings: Settings) -> TmsAdapter:
    provider = settings.tms.provider
    if provider == "none":
        return NullTms()
    if provider == "memory":
        return InMemoryTms()
    if provider == "xray":
        from streamcart_pytest.tms.xray import XrayAdapter

        return XrayAdapter.from_settings(settings)
    if provider == "codebeamer":
        from streamcart_pytest.tms.codebeamer import CodebeamerAdapter

        return CodebeamerAdapter.from_settings(settings)
    raise ConfigurationError(f"Unknown tms.provider '{provider}'")
