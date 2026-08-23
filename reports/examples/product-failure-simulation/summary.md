# StreamCart run summary

- **Run**: `product-failure-simulation` on `SBASAVANAP3-NB`
- **Platform / target / env**: web / chrome (chrome) / dev
- **Base URL**: https://www.saucedemo.com
- **Configuration**: base.yaml -> platform/web.yaml -> target/chrome.yaml -> env/dev.yaml
- **Build**: n/a
- **Started / finished**: 2026-08-23T19:33:56+00:00 → 2026-08-23T19:34:40+00:00

| Outcome | Count |
|---|---|
| passed | 2 |
| failed | 2 |
| skipped | 1 |
| xfailed | 2 |
| xpassed | 0 |
| error | 0 |

## Failures by category

| Category | Test | Message |
|---|---|---|
| product | `failure_simulation/test_failure_simulation.py::test_a_product_defect__the_badge_count_is_wrong_simulated_by_expecting_2` | AssertionError: assert 1 == 2 |
| product | `failure_simulation/test_failure_simulation.py::test_a_quarantined_scenario__fails_without_blocking_the_build` | AssertionError: assert 1 == 4 |
| ui-contract | `failure_simulation/test_failure_simulation.py::test_a_ui_contract_failure__the_product_the_test_expects_does_not_exist` | streamcart.core.errors.ElementNotFoundError: Element 'product card 'Sauce Labs Teleporter'' not found on web within 10.0s using xpath="//*[@data-test='inventory |
| known-issue | `failure_simulation/test_failure_simulation.py::test_a_known_issue_tracked_in_ticket_sc42__fails_without_blocking_the_build` | AssertionError: assert 1 == 3 |

## Flaky (passed only on retry)

- `failure_simulation/test_failure_simulation.py::test_an_environment_failure_that_passes_on_retry__reported_as_flaky` (attempt 2)

## Published to

- ✅ **local**: reports\runs\product-failure-simulation\run-results.json
- ✅ **allure-report**: reports\runs\product-failure-simulation\allure-report\index.html

## Artifacts

`reports\runs\product-failure-simulation`
