# StreamCart QA — multi-platform test automation framework

A pytest framework for **StreamCart**, an e-commerce product that ships on Web, iOS, Android,
Fire TV, Roku and Apple TV. The tests are written once, in Gherkin. The platform they run on is a
command-line switch.

The **Web** platform is fully implemented and verified against
[SauceDemo](https://www.saucedemo.com/), the assessment's stand-in for StreamCart. The mobile and
TV platforms have documented stub adapters: they show how a new platform plugs in without
changing existing code.

| | |
|---|---|
| Product suite | 31 scenarios (22 definitions; outlines expand to 31) in [`features/`](features/): login, inventory, cart, checkout, the end-to-end journey, platform differences |
| Framework tests | 156 tests in [`tests/framework/`](tests/framework/): contracts, architecture rules, guardrails, the execution platform |
| Platforms | `web` (Selenium 4, working) · `ios` / `android` (Appium, stub) · `firetv` / `appletv` (Appium, stub) · `roku` (ECP over HTTP, stub) |
| Example reports | [`reports/examples/`](reports/examples/) — real runs, explained in [docs/reports.md](docs/reports.md) |
| Documents | [ADR.md](ADR.md) · [PIPELINE.md](PIPELINE.md) · [SUBMISSION.md](SUBMISSION.md) · [docs/](docs/) |

## Quick start

You need Python 3.10 or newer and a browser (Chrome, Edge or Firefox). Selenium Manager downloads
the matching driver on first use; there is nothing else to install.

```bash
# 1. Dependencies. uv installs the locked set in a few seconds (https://docs.astral.sh/uv/)
uv sync --extra dev

#    ...or plain pip, from the same pyproject.toml
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Credentials. They are never stored in the repository. Copy the template and fill in
#    the SauceDemo password (it is shown on the SauceDemo login page and in the brief).
cp .env.example .env

# 3. Run the product suite
uv run pytest -v          # inside an activated venv: pytest -v
```

A run starts by printing where it points and ends with a summary of what it produced:

```
streamcart: platform=web (web) | env=dev | target=chrome | base_url=https://www.saucedemo.com | run_id=20260823_...
streamcart: config .../config :: base.yaml -> platform/web.yaml -> target/chrome.yaml -> env/dev.yaml
streamcart: product run -> reports/runs/20260823_...
...
=========================== streamcart run summary ============================
run 20260823_... | web/chrome | dev | passed=30 skipped=1
ok local: reports/runs/20260823_.../run-results.json
ok allure-report: reports/runs/20260823_.../allure-report/index.html
========================= 30 passed, 1 skipped in 2m43s =======================
```

The one skipped scenario is *Swiping through the catalogue on a touch screen*. It is tagged
`@requires:swipe`; the web platform does not declare a swipe capability, so the framework skips
it and says why, instead of failing.

## Running

| I want to... | Command |
|---|---|
| Run everything on the default target (headless Chrome) | `pytest` |
| Watch the browser | `pytest --headed` |
| Use another browser | `pytest --target edge` · `--target firefox` · `--target chrome-headed` — the browser is part of the target; a report for `--target chrome` is always a Chrome report |
| Run in parallel | `pytest -n 4` (one browser session per scenario; the workers share one run id) |
| Run only the smoke suite | `pytest --suite smoke` (also `regression`, `e2e`, or `-m critical`) |
| Run one feature or one scenario | `pytest tests/steps/test_login.py` · `pytest -k "locked"` |
| Point at another environment | `pytest --env staging` (see `config/env/`; every environment points at SauceDemo here) |
| See what another platform would run | `pytest --platform roku --collect-only -q` — selection, configuration and capability skips work today; execution needs a device |
| Run against a Selenium Grid | `pytest --target chrome-grid` (`STREAMCART_WEB__REMOTE_URL` overrides the endpoint) |
| Run in Docker with the browser in a Grid container | `docker compose run --rm tests` (smoke, 2 workers) · `docker compose --profile firefox run --rm tests-firefox` |
| Run exactly the test cases of a TMS plan | `pytest --tms-plan SC-PLAN-7` (needs `STREAMCART_TMS__*` configured) |
| Retry more than environment failures | `pytest --retry-categories environment,product` (a pass on retry is always reported as *flaky*) |
| Run the framework's own tests | `pytest tests/framework` (add `--ignore=tests/framework/integration` to skip the browser-backed ones) |
| Run the static checks | `ruff check . && ruff format --check . && mypy && lint-imports` (or `pre-commit install` once) |

Every option also exists as an environment variable (`STREAMCART_PLATFORM`, `STREAMCART_ENV`,
`STREAMCART_TARGET`, `STREAMCART_WEB__HEADLESS`, ...), and you can keep personal overrides in
`config/local.yaml` (gitignored). Settings are applied in this order, later ones winning:

`base.yaml → platform/*.yaml → target/*.yaml → env/*.yaml → config/local.yaml → .env → environment variables → command line`

## Project layout

```
features/                 Gherkin. The product suite: one file per functional area, tagged (@smoke, @TC-..., @requires:...)
tests/steps/              Step definitions. One line each: attempts_to(Task), or asks(Question) + assert
tests/framework/          The framework's own tests: contracts, architecture rules, guardrails, plugin behaviour
streamcart/
  core/                   The contracts: Platform, Capability, Locator, waits, typed errors, configuration, driver protocol
    driver/adapters/      The only place Selenium / Appium / ECP are imported (web_selenium works; the others are stubs)
  ui/                     Pages and reusable Components. Locators and simple actions only: no assertions, no flows
  screenplay/             Actor, Abilities, Tasks, Questions. The business layer that every step talks to
  testdata/               Personas and the product catalogue from data/*.yaml; passwords come from the environment
streamcart_pytest/        The execution platform, as a pytest plugin: selection, failure classification, retry policy,
                          evidence capture, the run results, channels (TMS, team hooks), reports, the `streamcart` CLI
config/                   base.yaml · platform/ (6) · target/ (12) · env/ (3)
data/                     users.yaml (personas, no passwords) · products.yaml (reference catalogue and tax rate)
reports/examples/         Report sets from real runs (everything else under reports/ is ignored by git)
docs/                     Guides (reports, writing scenarios, adding a platform); docs/assignment/ is the brief, unchanged
.github/                  Reusable workflows (_run-tests, _lint, _framework-tests) and the workflows that call them
docker/ · compose.yaml    A browser-less runner image (built from uv.lock, non-root) plus Selenium Grid
```

The dependencies between these packages are enforced by tools, not by convention:
`streamcart_pytest → screenplay → ui | testdata → core`, and Selenium/Appium may only be imported
inside `core/driver/adapters/` (`lint-imports` and ruff's `banned-api` check both).

## How a scenario runs

```gherkin
@smoke @critical @TC-LOGIN-001
Scenario: A customer with valid credentials reaches the products
  When the customer signs in as "standard"
  Then the customer sees the products screen
```

```python
# tests/steps/session_steps.py — a step is one call into the Screenplay layer
@when(parsers.parse('the customer signs in as "{persona}"'))
def signs_in_as(customer: Actor, personas: PersonaCatalogue, persona: str) -> None:
    customer.attempts_to(Login.as_(personas.resolve(persona)))


# streamcart/screenplay/tasks/session.py — a Task describes what the user does, and waits for the outcome
class Login(Task):
    def perform_as(self, actor: Actor) -> None:
        page = LoginPage(actor.driver)
        page.username.type(self.username)
        page.password.type(self.password)
        page.login_button.press()
        actor.driver.wait.until(
            lambda: InventoryPage(actor.driver).is_displayed() or page.error.is_displayed(),
            message="login outcome (products or an error message)",
        )


# streamcart/ui/pages/login.py — a Page is a list of locators plus simple actions, nothing more
class LoginPage(Page):
    PATH = "/"
    USERNAME = Locator.test_id("username field", "username")  # resolved per platform
    LOGIN_BUTTON = Locator.test_id("login button", "login-button")
    MARKER = LOGIN_BUTTON
```

`actor.driver` is a `PlatformDriver`: a protocol whose methods are named after what the user
does (`open`, `find`, `select`, `enter_text`, `press`). On the web, `select` is a click. On a
television it means "move the focus with the d-pad until this element has it, then press OK".
The Task does not know which one it gets.

## Reports and evidence

Each run writes a folder `reports/runs/<run-id>/` (the path is printed at the start and the end
of the run; run ids are timestamps unless you pass `--run-id`). Real examples, including a run with one scenario per outcome, are kept in
[`reports/examples/`](reports/examples/) and explained file by file in [docs/reports.md](docs/reports.md).

| File | Who reads it | What it shows |
|---|---|---|
| `allure-report/index.html` | product owners, QA leads | feature → scenario → step view, failure categories, the environment panel, retries |
| `report.html` | engineers | every test with **Category** and **Attempts** columns, screenshots inline on failure |
| `summary.md` | PRs, chat | the run at a glance: counts, failures by category, flaky tests, where it was published |
| `junit.xml` | CI systems, dashboards | standard results plus `category`, `attempts` and `artifact:*` properties |
| `cucumber.json` | BDD tooling, TMS importers | Gherkin-structured results |
| `run-results.json` | integrations | the output contract: one record per test (outcome, category, attempts, evidence, TMS ids) |
| `artifacts/<test>/` | triage | screenshot, page source and console log captured at the moment of failure |

Every failure is classified from the typed exception that caused it. By default only
**environment** failures are retried (once); `--retry-categories` widens that, and a pass on retry
is reported as **flaky** everywhere, never as a plain pass. The framework's own tests report
separately under `reports/framework/`.

## Test management and other integrations

Everything below reads `run-results.json`; nothing here changes how tests are written.

| Integration | How to switch it on | What happens |
|---|---|---|
| Test-management system (Xray or codeBeamer) | `STREAMCART_TMS__PROVIDER=xray`, `STREAMCART_TMS__BASE_URL`, `STREAMCART_TMS__PROJECT_KEY`, `STREAMCART_TMS__TOKEN` (a secret), `STREAMCART_TMS__UPLOAD=true` | At the end of a run, one **execution** is created per (team, platform, target, env, run id) with one result per scenario tagged `@TC-...`. Reruns are attempts of one result; shards are merged first (`streamcart merge-results`, then `streamcart publish`). A TMS outage is a warning in the summary, never a failed build. `STREAMCART_TMS__PROVIDER=memory` is an in-process fake for demos. |
| Run exactly a plan | `pytest --tms-plan SC-PLAN-7` or `pytest --tms-ids TC-LOGIN-001,TC-CHK-003` | Only the scenarios linked to those test cases are collected. |
| Long-term evidence | `STREAMCART_ARTIFACTS__STORE=s3` + `STREAMCART_ARTIFACTS__S3_BUCKET` (or `azure` + container) | Screenshots, page sources and logs go to the store instead of the local folder, under `<team>/<env>/<platform>/<run-id>/`. **Stub**: the S3 and Azure stores make the real client calls (boto3 / Azure SDK, installed separately) but have not been run against a real bucket in this assessment; the local store is what every run here used. |
| A team's own destination (chat, dashboard, data lake) | in a `conftest.py`: `@pytest.hookimpl def pytest_streamcart_result_channels(settings, run_dir): return [MyChannel()]` — a channel is any object with a `name` and a `publish(run_results)` method returning a `ChannelReceipt` | Proven by a framework test. The channel receives the run results like every built-in one; a failing channel is reported in the summary and never fails the run. |

## Troubleshooting

| You see | It means | Do this |
|---|---|---|
| `No password configured for persona 'standard'...` | the SauceDemo password is not in the environment | `cp .env.example .env` and set `STREAMCART_USERS__DEFAULT__PASSWORD` (CI: a secret) |
| `Target 'chrome' runs chrome, but web.browser is 'edge'` | the browser was overridden underneath a browser-named target | use the matching target: `--target edge` |
| `No env configuration named 'qa'` | no `config/env/qa.yaml` | pick `dev`, `staging` or `prod`, or add the file |
| `Unknown platform 'tizen'. Registered: ...` | no adapter declares that platform | see [docs/adding-a-platform.md](docs/adding-a-platform.md) |
| `SKIPPED ... platform 'web' lacks capability: swipe` | expected: the scenario needs something this platform cannot do | nothing; it runs on platforms that declare the capability |
| `ok allure-report: Allure CLI not installed; run: allure serve ...` | results were written, the HTML was not rendered | install the Allure CLI (`npm i -g allure-commandline`, `scoop install allure`, `brew install allure`) or run the printed command; `report.html` carries the same data |
| `environment: browser dropped N input event(s); DOM fallback used` | the browser discarded clicks/keystrokes and the adapter recovered | an environment signal about that machine, not a product failure (ADR, section 7) |
| the first run is slow to start | Selenium Manager is downloading the matching driver | wait once; it is cached afterwards |

## Adding a platform

New files only; the registry finds them, nothing existing is edited:

1. `streamcart/core/driver/adapters/<name>.py` — declare the `Platform`, extend `BaseDriver`, add `@register_platform`.
2. `config/platform/<name>.yaml` and `config/target/<default-target>.yaml`.
3. Optionally a platform-specific selector on a locator (`roku=By.TEXT("Checkout")`); the family
   keys (`mobile=`, `tv=`) usually cover it already.

[`tests/framework/test_architecture.py::test_adding_a_platform_requires_new_files_only`](tests/framework/test_architecture.py)
does exactly this with a made-up platform and checks that configuration, driver creation,
capabilities and locators all resolve. The walkthrough is [docs/adding-a-platform.md](docs/adding-a-platform.md);
the first-day guide for a new SDET is [docs/writing-scenarios.md](docs/writing-scenarios.md).

## Quality gates

`ruff` (with `time.sleep` and Selenium/Appium imports banned outside their one allowed place),
`ruff format`, `mypy --strict`, `lint-imports` (three layer rules), `uv lock --check`, and the
guardrail tests in `tests/framework/test_guardrails.py`, which prove the bans actually bite and
that no credential is committed. `pre-commit install` runs the same set on every commit; CI runs
it on every pull request and every push.
