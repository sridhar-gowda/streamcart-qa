"""Jira Xray adapter (Xray Cloud REST v2).

**Status: stub.** The payloads and endpoints are the real ones; nothing here has
been exercised against a live Xray instance in this assessment. The payload
builder is pure and unit-tested.

    selection    GraphQL ``getTestPlan(issueId) { tests { results { jira(fields: ["key"]) } } }``
    publication  ``POST /api/v2/import/execution`` — creates one Test Execution carrying every
                 result, with ``info.testEnvironments`` = [platform, target, env] so the same
                 test case keeps a distinct result per environment (the n-executions model)

Status mapping: passed → PASSED · flaky → PASSED (comment records the retry) ·
failed / known-issue → FAILED · skipped → TODO.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from streamcart.core.errors import ConfigurationError
from streamcart_pytest.results import RunResults
from streamcart_pytest.tms import TmsResult

if TYPE_CHECKING:
    from streamcart.core.config import Settings

STATUS = {"passed": "PASSED", "flaky": "PASSED", "failed": "FAILED", "known-issue": "FAILED", "skipped": "TODO"}


def build_import_payload(
    run_results: RunResults, results: Sequence[TmsResult], *, plan_key: str | None
) -> dict[str, Any]:
    """The body of ``POST /api/v2/import/execution`` for this run."""
    info: dict[str, Any] = {
        "summary": (
            f"{run_results.team} | {run_results.platform}/{run_results.target} | "
            f"{run_results.env} | {run_results.run_id}"
        ),
        "description": (
            f"Run {run_results.run_id} on {run_results.host}; build {run_results.build or 'n/a'}; "
            f"{run_results.counts()}; input anomalies: {run_results.input_anomalies}"
        ),
        "testEnvironments": [run_results.platform, run_results.target, run_results.env],
        "startDate": run_results.started_at,
        "finishDate": run_results.finished_at or run_results.started_at,
    }
    if plan_key:
        info["testPlanKey"] = plan_key
    tests = [
        {
            "testKey": r.test_key,
            "status": STATUS.get(r.status, "TODO"),
            "comment": r.comment,
            "evidence": [{"filename": url.rsplit("/", 1)[-1], "data": url} for url in r.evidence],
        }
        for r in results
    ]
    return {"info": info, "tests": tests}


@dataclass
class XrayAdapter:
    name: str
    base_url: str
    project_key: str
    token: str
    plan_key: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> XrayAdapter:
        tms = settings.tms
        base_url, project_key, token = tms.base_url, tms.project_key, tms.token
        if not base_url or not project_key or token is None:
            missing = [n for n, v in (("base_url", base_url), ("project_key", project_key), ("token", token)) if not v]
            raise ConfigurationError(
                f"tms.provider=xray needs {', '.join(missing)} (set STREAMCART_TMS__{missing[0].upper()} ...)"
            )
        return cls("xray", base_url.rstrip("/"), project_key, token.get_secret_value(), tms.plan)

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return dict(json.loads(response.read().decode("utf-8")))

    def resolve_plan(self, plan_key: str) -> list[str]:
        query = {
            "query": (
                "query($key: String!) { getTestPlans(jql: $key, limit: 1) { results { tests(limit: 500) "
                '{ results { jira(fields: ["key"]) } } } } }'
            ),
            "variables": {"key": f"key = {plan_key}"},
        }
        data = self._request("POST", "/api/v2/graphql", query)
        plans = data.get("data", {}).get("getTestPlans", {}).get("results", [])
        if not plans:
            raise ConfigurationError(f"Xray test plan '{plan_key}' not found")
        return [t["jira"]["key"] for t in plans[0]["tests"]["results"]]

    def publish(self, run_results: RunResults, results: Sequence[TmsResult]) -> str:
        payload = build_import_payload(run_results, results, plan_key=self.plan_key)
        response = self._request("POST", "/api/v2/import/execution", payload)
        return str(response.get("key", ""))
