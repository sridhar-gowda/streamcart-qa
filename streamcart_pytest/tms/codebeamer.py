"""codeBeamer adapter (REST API v3).

**Status: stub** — the second adapter exists to prove the ``TmsAdapter``
protocol is not Xray-shaped: codeBeamer models a *Test Set* (selection), a
*Test Run* tracker item (the execution) and per-case *Test Run* children.

    selection    ``GET /api/v3/items/{testSetId}`` → ``testCases[].id`` (the set's ordered references)
    publication  ``POST /api/v3/testruns`` with ``testSetIds`` / ``testCaseIds`` creates the run;
                 ``PUT /api/v3/testruns/{runId}/result`` reports verdicts in bulk

Verdicts: passed/flaky → Passed · failed/known-issue → Failed · skipped → Not Applicable.
Authentication: bearer token (or the technical-user credentials behind it).
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

VERDICT = {
    "passed": "Passed",
    "flaky": "Passed",
    "failed": "Failed",
    "known-issue": "Failed",
    "skipped": "Not Applicable",
}


def build_run_payload(
    run_results: RunResults, results: Sequence[TmsResult], *, test_set_id: str | None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"{run_results.platform}-{run_results.target}-{run_results.env}-{run_results.run_id}",
        "description": (
            f"Run {run_results.run_id}; build {run_results.build or 'n/a'}; anomalies {run_results.input_anomalies}"
        ),
        "testCaseIds": sorted({int(r.test_key.rsplit("-", 1)[-1]) for r in results if r.test_key[-1].isdigit()}),
        "results": [
            {
                "testCaseId": r.test_key,
                "result": VERDICT.get(r.status, "Not Applicable"),
                "conclusion": r.comment,
                "runTime": int(r.duration * 1000),
            }
            for r in results
        ],
    }
    if test_set_id:
        payload["testSetIds"] = [int(test_set_id)]
    return payload


@dataclass
class CodebeamerAdapter:
    name: str
    base_url: str
    token: str
    test_set_id: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> CodebeamerAdapter:
        tms = settings.tms
        if not tms.base_url or not tms.token:
            raise ConfigurationError("tms.provider=codebeamer needs tms.base_url and STREAMCART_TMS__TOKEN")
        return cls("codebeamer", tms.base_url.rstrip("/"), tms.token.get_secret_value(), tms.plan)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=data,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def resolve_plan(self, plan_key: str) -> list[str]:
        item = self._request("GET", f"/api/v3/items/{plan_key}")
        return [f"CB-{ref['id']}" for ref in item.get("testCases", [])]

    def publish(self, run_results: RunResults, results: Sequence[TmsResult]) -> str:
        payload = build_run_payload(run_results, results, test_set_id=self.test_set_id)
        run = self._request("POST", "/api/v3/testruns", {k: v for k, v in payload.items() if k != "results"})
        run_id = run["id"]
        self._request("PUT", f"/api/v3/testruns/{run_id}/result", {"results": payload["results"]})
        return f"CB-{run_id}"
