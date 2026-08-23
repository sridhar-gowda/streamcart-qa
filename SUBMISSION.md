# Submission — StreamCart QA framework

**Candidate:** Sridhar Basavanapura
**Video walkthrough:** https://drive.google.com/file/d/102cFhBQMqgQ62UWuOYipe6SYwWhmzGs9/view?usp=sharing
**Repository:** https://github.com/sridhar-gowda/streamcart-qa.git

## Where to look

| Deliverable | Location |
|---|---|
| Working tests (`pytest -v`) — Gherkin with pytest-bdd (Bonus) | `features/` + `tests/steps/` — 31 scenarios. Verified from a clean clone on headless Chrome: 30 passed, 1 skipped because the web platform cannot swipe. |
| Example reports from real runs | [reports/examples/](reports/examples/) — the full regression, a parallel smoke run, a walkthrough with one scenario per outcome, a sharded run with the merged run-results file, a Docker/Grid run, and the framework's own tests. Explained in [docs/reports.md](docs/reports.md). |
| Architecture Decision Record | [ADR.md](ADR.md) |
| Screenplay layer (Bonus) | [streamcart/screenplay/](streamcart/screenplay/) — Actor, Abilities, Tasks, Questions |
| Composable page components (Bonus) | [streamcart/ui/components/](streamcart/ui/components/) — header, cart badge, menu, product card, sort control, error banner, order summary |
| Custom pytest plugin (Bonus) | [streamcart_pytest/](streamcart_pytest/) — selection, failure classification, retries, evidence, run results, channels, reports |
| Parallel execution (Bonus) | `pytest -n 4` (pytest-xdist) and CI shards (pytest-split) — see [PIPELINE.md](PIPELINE.md) |
| Linting and quality gates (Bonus) | ruff incl. banned imports, mypy --strict, import-linter (`pyproject.toml`), [.pre-commit-config.yaml](.pre-commit-config.yaml), [.github/workflows/_lint.yml](.github/workflows/_lint.yml) |
| CI/CD pipeline and strategy | [.github/workflows/](.github/workflows/) · [PIPELINE.md](PIPELINE.md) |
| Docker (Bonus) | [docker/Dockerfile](docker/Dockerfile) · [compose.yaml](compose.yaml) |
| How to run, layout, reports | [README.md](README.md) |
| Guides | [docs/writing-scenarios.md](docs/writing-scenarios.md) · [docs/adding-a-platform.md](docs/adding-a-platform.md) · [docs/reports.md](docs/reports.md) |
| The brief, unchanged | [docs/assignment/](docs/assignment/) |

## Time spent

Work sessions: Saturday 10:00-14:00 and 18:00-22:00, Sunday 10:00-12:00 and 20:00-23:00 CET — about 13 hours.

| Task | Time |
|---|---|
| 1 — Framework architecture and project structure | 4 h |
| 2 — Multi-platform abstraction (protocol, web adapter, three stubs, focus navigation) | 2 h |
| 3 — Test cases (UI model, Screenplay layer, 31 scenarios) | 1 h |
| 4 — CI/CD and the rest (workflows, Docker, Grid, plugin, reports, TMS) | 1 h |
| 5 — ADR and documentation | 2 h |
| 6 — End-to-end review and testing (clean clones, Docker, example reports) | 2 h |
| 7 — Video and upload | 1 h |

## Assumptions

- SauceDemo stands in for StreamCart on **every** environment. `dev`, `staging` and `prod` all
  point at it, so the environment layering is exercised but the environments do not really differ.
- The SauceDemo password is public, but it is still treated as a secret: it is read only from the
  environment (`.env` locally, GitHub Secrets in CI), and a framework test fails if it ever shows
  up in a tracked file.
- Only the Web platform executes. The Appium adapters (iOS/Android, Fire TV/Apple TV) and the
  Roku adapter are documented stubs with real signatures, capabilities and selector mappings.
  They have not run against a device.
- Bonus items were included only where they fit the design: BDD (pytest-bdd is the only way
  product tests are written), Screenplay, Docker with Selenium Grid, parallel execution, a custom
  pytest plugin (the execution platform), lint/type/import gates with pre-commit, and composable
  page components.

## Trade-offs

- **Selenium instead of Playwright.** Five of the six platforms are driven by WebDriver-style
  tools (Appium, Roku's ECP), and Selenium Grid is the shared infrastructure. One protocol across
  six platforms mattered more than web-only speed.
- **Screenplay on top of small Pages** instead of classic page objects with flow methods. One
  composition rule for the whole team, pages small enough to review per screen, and no second
  page-shaped API growing next to the first.
- **Flakiness reported per run.** A pass on retry is reported as *flaky* in
  every report format. Trends across runs are left to the CI analytics or test-management tool
  that receives every run results.
- **Delivery-verified input in the web adapter.** When a managed browser silently drops a click
  or a keystroke, the adapter falls back to a DOM event and counts it as an environment signal.
  It is extra machinery; it is isolated in one adapter and a team on clean infrastructure can
  remove it.
- **uv lockfile, pip still supported.** `uv.lock` is resolved for every supported OS and Python
  version; `pip install -e ".[dev]"` works from the same `pyproject.toml` for reviewers without uv.

## What I would improve with more time

1. Run `appium_mobile` against an Android emulator in CI (the device-lab matrix and the
   capability plumbing exist) and `roku_ecp` against a sideloaded channel.
2. Add an Allure TestOps or ReportPortal channel for cross-run trends, through the existing
   `pytest_streamcart_result_channels` hook.
3. Visual and accessibility checks as Tasks and Questions on the same Screenplay layer.
4. A step-through debugging mode beyond `--headed` (pause on failure with the page source open).
5. A separate configuration repository once more than one product repository uses the platform.
6. Testing of Allure - reports in depth with flaky category and screenshots. 
7. Test CI - executions
