"""The run results — the output contract of a session.

One ``ResultRecord`` per test, one ``RunResults`` per run. The run results are what
every result channel consumes (local report, TMS, whatever a team adds) and what the CI
``aggregate`` job merges across shards, so that the TMS receives one execution
per run rather than one per shard. It is a record of what happened, written
once at the end — never a channel that tests write to while running.
"""

from __future__ import annotations

import hashlib
import json
import platform as py_platform
import re
import socket
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUTCOMES = ("passed", "failed", "skipped", "xfailed", "xpassed", "error")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_name(nodeid: str, *, limit: int = 100) -> str:
    """A filesystem-safe, unique-enough name for a node id."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid).strip("_")
    if len(cleaned) <= limit:
        return cleaned
    digest = hashlib.sha1(nodeid.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[: limit - 9]}_{digest}"


@dataclass
class ResultRecord:
    nodeid: str
    name: str = ""
    outcome: str = "passed"
    category: str | None = None
    attempts: int = 1
    duration: float = 0.0
    message: str = ""
    exception_type: str = ""
    tms_ids: list[str] = field(default_factory=list)
    suites: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    feature: str = ""
    known_issue: str = ""
    quarantined: bool = False
    skip_reason: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    worker: str = "main"

    @property
    def flaky(self) -> bool:
        return self.outcome == "passed" and self.attempts > 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResultRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RunResults:
    run_id: str
    team: str = ""
    platform: str = ""
    target: str = ""
    env: str = ""
    base_url: str = ""
    build: str = ""
    browser: str = ""
    config_layers: list[str] = field(default_factory=list)  # which configuration files shaped this run, in order
    started_at: str = field(default_factory=now_iso)
    finished_at: str = ""
    host: str = field(default_factory=socket.gethostname)
    python: str = field(default_factory=py_platform.python_version)
    input_anomalies: int = 0
    tms_execution: str = ""
    receipts: dict[str, str] = field(default_factory=dict)
    results: list[ResultRecord] = field(default_factory=list)

    # ------------------------------------------------------------ derived
    def counts(self) -> dict[str, int]:
        counts = dict.fromkeys(OUTCOMES, 0)
        for record in self.results:
            counts[record.outcome] = counts.get(record.outcome, 0) + 1
        return counts

    def by_category(self) -> dict[str, list[ResultRecord]]:
        grouped: dict[str, list[ResultRecord]] = {}
        for record in self.results:
            if record.outcome in ("failed", "error", "xfailed") and record.category:
                grouped.setdefault(record.category, []).append(record)
        return grouped

    def flaky(self) -> list[ResultRecord]:
        return [r for r in self.results if r.flaky]

    @property
    def execution_label(self) -> str:
        """The n-executions key: the same test case executed per platform/target/env/run stays distinct."""
        return f"{self.team}/{self.platform}/{self.target}/{self.env}/{self.run_id}"

    # ----------------------------------------------------------------- io
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["results"] = [r.to_dict() for r in self.results]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResults:
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "results"}
        run_results = cls(**fields)
        run_results.results = [ResultRecord.from_dict(r) for r in data.get("results", [])]
        return run_results

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: Path) -> RunResults:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def merge(cls, runs: Sequence[RunResults]) -> RunResults:
        """Combine shard runs of one run: results keyed by node id, anomalies summed."""
        if not runs:
            raise ValueError("nothing to merge")
        head = runs[0]
        merged = cls.from_dict({k: v for k, v in head.to_dict().items() if k != "results"})
        merged.results = []
        seen: dict[str, ResultRecord] = {}
        merged.input_anomalies = 0
        for run_results in runs:
            if run_results.run_id != head.run_id:
                raise ValueError(f"cannot merge different runs: {head.run_id} and {run_results.run_id}")
            merged.input_anomalies += run_results.input_anomalies
            merged.finished_at = max(merged.finished_at, run_results.finished_at)
            for record in run_results.results:
                seen[record.nodeid] = record  # a later shard's record for the same test supersedes
        merged.results = list(seen.values())
        return merged


def merge_files(paths: Iterable[Path]) -> RunResults:
    return RunResults.merge([RunResults.read(p) for p in paths])
