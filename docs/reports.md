# Reports: what a run produces and how to read it

Every run writes one folder. Everything in it is derived from the same facts, so the numbers
agree across files — they just serve different readers.

```
reports/
  runs/<run-id>/            a product run (pytest on features/)
  framework/<run-id>/       a framework self-test run (pytest tests/framework) — kept apart on purpose
  examples/                 real runs kept in git as examples (see the end of this page)
```

The run id comes from `--run-id`, from `STREAMCART_RUN_ID`, or is generated
(`YYYYMMDD_HHMMSS_<8 hex>`). All xdist workers, and all CI shards of one run, share it.

## The files in a run folder

| File | Made by | Best for |
|---|---|---|
| `console.txt`* | pytest's terminal output | what you saw on screen: the header, every test, the run summary |
| `summary.md` | the framework | a one-page digest to paste into a pull request or a chat message |
| `report.html` | pytest-html + the framework | engineers triaging: every test with its category, attempts and screenshot |
| `allure-report/index.html` | the Allure CLI, from `allure-results/` | product owners and QA leads: features, scenarios, steps, categories, retries |
| `allure-results/` | allure-pytest-bdd + the framework | the raw input for Allure (JSON per test, attachments, `environment.properties`, `categories.json`) |
| `junit.xml` | pytest + the framework | CI systems and dashboards; carries `category`, `attempts` and `artifact:*` properties |
| `cucumber.json` | pytest-bdd | BDD tooling and test-management importers (Xray, Zephyr) |
| `run-results.json` | the framework | integrations: the machine-readable record of the run, one entry per test |
| `artifacts/<test>/` | the framework | evidence: `screenshot.png`, `page_source.html`, `console.log`, taken when a test fails |

\* `console.txt` is not written by the framework; the examples include it because the commands
were run as `pytest ... > console.txt`.

### The terminal output

A run starts with three header lines and ends with a summary block:

```
streamcart: platform=web (web) | env=dev | target=chrome | base_url=https://www.saucedemo.com | run_id=product-regression
streamcart: config .../config :: base.yaml -> platform/web.yaml -> target/chrome.yaml -> env/dev.yaml -> local.yaml
streamcart: product run -> reports\runs\product-regression
```

- **platform / env / target** — what was selected. `(web)` after the platform is its family.
- **config** — the configuration files that were loaded, in order. Later files override earlier
  ones. `local.yaml` is a developer's personal override file and is never committed.
- **product run → ...** — where the reports go (`framework run` for the framework's own tests).

```
=========================== streamcart run summary ============================
run product-failure-simulation | web/chrome | dev | passed=2 failed=2 skipped=1 xfailed=2
failures by category: product=2, ui-contract=1, known-issue=1
  [product] failure_simulation/test_failure_simulation.py::test_a_product_defect...: AssertionError: assert 1 == 2
  [ui-contract] failure_simulation/test_failure_simulation.py::test_a_ui_contract_failure...: ElementNotFoundError: ...
  [known-issue] failure_simulation/test_failure_simulation.py::test_a_known_issue...: AssertionError: assert 1 == 3
flaky (passed only on retry): 1
  failure_simulation/test_failure_simulation.py::test_an_environment_failure_that_passes_on_retry... (attempt 2)
quarantined (non-blocking): 1
ok local: reports\runs\product-failure-simulation\run-results.json
ok allure-report: reports\runs\product-failure-simulation\allure-report\index.html
reports: reports\runs\product-failure-simulation
```

- **run line** — `platform/target [browser]`, environment, and the outcome counts. The browser
  appears in brackets only for targets that are not named after a browser (see *target vs browser*
  below).
- **failures by category** — every failure, sorted by what kind of problem it is (see
  *Failure categories* below), then one line per failing test with the first line of its error.
- **flaky** — tests that failed, were retried, and passed. The retry does not hide them.
- **quarantined** — tests tagged `@quarantine` that failed. They are reported but do not fail the build.
- **environment:** (when present) — `browser dropped N input event(s); DOM fallback used`: the web
  adapter noticed clicks or keystrokes that the browser silently discarded and recovered from
  them. Worth knowing about the machine, not about the product.
- **ok / FAILED lines** — one per *result channel*: where the run was published (the local results file, the
  Allure report, a test-management system when configured). A result channel that fails never fails the run.

### `summary.md`

The same information as the terminal summary, formatted for humans and for pasting:
run facts (run id, host, platform / target (browser) / env, base URL, configuration files, build,
start and end), the outcome table, **Failures by category** (category, test, message), **Flaky**,
an **Environment** note when input events were dropped, **Published to** (the result channels), and the
**Artifacts** folder.

### `report.html` (pytest-html)

Opens directly in a browser. At the top, the **Environment** table (Python, platform, installed
packages and plugins) and the **Summary** line with checkboxes to filter by outcome. Then the
**Results** table with two columns added by the framework:

- **Category** — the failure category (empty for a plain pass, `flaky` for a pass on retry);
- **Attempts** — how many times the test ran (`2` means it was retried once).

Click a failed row to expand it: the assertion or exception, the captured log, and the
**screenshot** taken at the moment of failure, inline. A retried test appears twice: once as
`Rerun` (the failed attempt) and once with its final result.

### `allure-report/index.html` (Allure)

A single self-contained file; open it directly. What to look at:

- **Overview** — the pass/fail donut, the **Environment** panel (below), **Categories** (the
  framework's failure categories as Allure categories), **Features by stories** (one feature file
  = one feature).
- **Suites** — feature → scenario. Open a scenario to see its Gherkin **steps** with durations,
  its **tags** (`@smoke`, `@TC-...`), and **attachments** (the captured log).
- **Categories** — the same taxonomy as the terminal: *Product defect*, *UI contract*,
  *Environment*, *Test defect*, *Known issue / quarantined*, *Flaky (passed only on retry)*.
- **Retries** tab on a scenario — every attempt is kept; the final one carries Allure's *flaky*
  marker when the pass came after a retry.
- **Timeline** — which tests ran when, and in parallel on which worker.

The **Environment** panel lists: `run_id`, `platform`, `target`, `browser`, `config_layers`,
`environment`, `base_url`, `build` (when set), `host`, `input_anomalies`.

#### Target vs browser

These are two different things, and the panel shows both on purpose:

- **target** is *where* the run executes — the name of a file in `config/target/`: `chrome`
  (local headless Chrome), `chrome-headed`, `edge`, `firefox`, `chrome-grid` (a Selenium Grid),
  `browserstack`, `pixel7-lab`, `roku-lab`, ...
- **browser** is the browser that was actually used, after every override was applied.

For a target named after a browser (`chrome`, `chrome-headed`, `chrome-grid`, `edge`, `firefox`,
`firefox-grid`) the two always agree: the framework refuses to start if `web.browser` was
overridden underneath such a target (`--target chrome` with `web.browser=edge` is an error that
points you to `--target edge`). A report for the `chrome` target is therefore always a Chrome
report. For targets that are not named after a browser (`browserstack`, a lab device) the panel
still tells you which browser ran, and the terminal run line shows it in brackets:
`web/browserstack [chrome]`. `config_layers` lists the files that shaped the run, in order, so an
unexpected value can be traced to the file that set it.

### `junit.xml`

One `<testcase>` per test with `<properties>` added by the framework:

```xml
<testcase classname="tests.steps.test_login" name="test_wrong_credentials_are_refused" time="4.9">
  <properties>
    <property name="category" value="product"/>
    <property name="attempts" value="1"/>
    <property name="artifact:screenshot" value="tests_steps_test_login.py_test_.../screenshot.png"/>
    <property name="artifact:page_source" value=".../page_source.html"/>
    <property name="artifact:console_log" value=".../console.log"/>
  </properties>
  <failure message="AssertionError: ...">...</failure>
</testcase>
```

Known issues and quarantined tests appear as `<skipped type="pytest.xfail" message="known issue SC-42"/>`;
capability skips as `<skipped message="platform 'web' lacks capability: swipe"/>`.

### `cucumber.json`

The standard Cucumber JSON shape: a list of features (`uri`, `name`, `tags`, `description`),
each with `elements` (scenarios: `name`, `tags`, `steps`), each step with `keyword`, `name` and a
`result` (`status`, `duration` in nanoseconds, `error_message` on failure). Test-management tools
import this format directly.

### `run-results.json`

The machine-readable record that every result channel consumes. Top level:

| Field | Meaning |
|---|---|
| `run_id`, `team`, `platform`, `target`, `env`, `base_url`, `build`, `browser` | what ran, where, against what |
| `config_layers` | the configuration files, in order |
| `started_at`, `finished_at`, `host`, `python` | when and on which machine |
| `input_anomalies` | dropped input events recovered by the web adapter (an environment signal) |
| `tms_execution` | the key of the execution created in the test-management system, when published |
| `receipts` | one line per result channel: where the run went |
| `results[]` | one record per test |

Each result record: `nodeid`, `name`, `outcome` (`passed` / `failed` / `skipped` / `xfailed` /
`xpassed` / `error`), `category`, `attempts`, `duration`, `message`, `exception_type`, `tms_ids`
(from `@TC-...` tags), `suites`, `platforms`, `feature`, `known_issue`, `quarantined`,
`skip_reason`, `artifacts` (name → relative path), `worker`.

Shards of one CI run each write a run-results file; `streamcart merge-results` combines them into one
(see the `product-sharded` example), so the test-management system receives one execution per run.

### `artifacts/<test>/`

Created for every failing test (and for the failed attempt of a test that later passed on retry):
`screenshot.png`, `page_source.html` (the DOM at the moment of failure) and `console.log` (the
browser console). The folder name is the test's node id made file-system safe. The same paths
are referenced from `junit.xml`, `run-results.json` and `report.html`.

## Failure categories

The framework looks at the exception that ended a test and assigns one category. The category
drives the retry policy, the reports and who should look.

| Category | What happened | Retried? | Blocks the build? |
|---|---|---|---|
| `product` | An assertion in a step failed: the application did the wrong thing. | no | yes |
| `ui-contract` | An element was missing, not interactable, or never settled: a stale locator or a UI change. | no | yes |
| `environment` | The browser session, the network or the app was unavailable. | once (the default; `--retry-categories` can widen this to other categories) | yes, if it fails again |
| `test-defect` | Wrong configuration or misuse of the framework (missing password, wrong ability). | no | yes |
| `flaky` | It failed, was retried, and passed. | — | no, but it is reported everywhere |
| `known-issue` | Tagged `@known_issue:TICKET`; the failure is expected and tracked. | no | no |
| (quarantined) | Tagged `@quarantine`; keeps its real category, cannot fail the build. | no | no |

## The examples in `reports/examples/`

Each folder is a complete, untouched run (only the folder was moved from `reports/runs/`).

| Folder | Command | What to look at |
|---|---|---|
| `product-regression/` | `pytest -v` on headless Chrome (the default) | the whole suite: 30 passed, 1 capability skip; `console.txt` is the `pytest -v` output; the Allure report's Suites and Environment |
| `product-smoke-parallel-edge/` | `pytest --suite smoke -n 4 --target edge` | 7 scenarios on 4 workers; `target=edge`, `browser=edge`; the Allure Timeline shows the parallel lanes |
| `product-failure-simulation/` | `pytest failure_simulation` — a throw-away feature with one scenario per outcome | the categories in action: a product defect, a missing element, a pass on retry (flaky), a known issue, a quarantined scenario, a capability skip; screenshots in `artifacts/` and in `report.html` |
| `product-sharded/` | `pytest --splits 2 --group 1` and `--group 2` on Edge, then `streamcart merge-results` | `shard-1/` and `shard-2/` are independent runs with the same run id; `run-results.json` at the top is the merged result (31 records); `merge.txt` is the CLI output |
| `framework-tests/` | `pytest tests/framework` | a *framework* run: it lands under `reports/framework/`, has no Allure or cucumber output and never touches product result channels |
| `docker-grid-smoke/` | `docker compose run --rm tests --platform web --target chrome-grid --suite smoke -n 2 -ra --run-id docker-grid-smoke`, then `allure generate` on the host (the image carries no Allure CLI) | `target=chrome-grid`: the suite in the container, the browser in a Selenium Grid container. |
